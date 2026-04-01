import os
import re
import socket
import struct
import subprocess
import threading
import datetime
from urllib.parse import quote
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="dist", static_url_path="")

# ---------------------------------------------------------------------------
# Configuration (all overridable via environment variables)
# ---------------------------------------------------------------------------

LOG_FILE = "/var/log/backup.log"
LOG_MAX_LINES = 5000

# UPS monitoring (apcupsd NIS, always port 3551)
UPS_HOSTS = [h.strip() for h in os.environ["UPS_HOSTS"].split(",")]

# Backup root (NFS mount)
BACKUP_DST = os.environ.get("BACKUP_DST", "/destination")

# PVE host config backup (rsync over SSH)
PVE_HOST = os.environ["PVE_HOST"]
PVE_SSH_KEY = os.environ["PVE_SSH_KEY"]
PVE_DIR = os.environ.get("PVE_DIR", "pve-host")
PVE_SRCS = [s.strip() for s in os.environ["PVE_SRCS"].split(",")]

# UPS NMC config backup (FTP) — NMC_HOSTS format: "name:ip,name:ip"
NMC_USER = os.environ.get("NMC_USER", "apc")
NMC_PASS = os.environ.get("NMC_PASS", "")
NMC_DIR = os.environ.get("NMC_DIR", "apc-ups")
NMC_HOSTS = []
for entry in os.environ.get("NMC_HOSTS", "").split(","):
    entry = entry.strip()
    if not entry:
        continue
    if ":" in entry:
        name, ip = entry.split(":", 1)
        NMC_HOSTS.append((name.strip(), ip.strip()))
    else:
        NMC_HOSTS.append((entry, entry))

RSYNC_BASE = ["rsync", "-avh", "-l", "--delete"]

_lock = threading.Lock()
running = False
action = ""
last_backup_cache = None
last_error = None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _dst(subdir):
    return os.path.join(BACKUP_DST, subdir)


def _read_log(tail=200):
    try:
        with open(LOG_FILE) as f:
            lines = f.readlines()
            return "".join(lines[-tail:])
    except FileNotFoundError:
        return ""


def _init_last_backup_cache():
    global last_backup_cache
    try:
        with open(LOG_FILE) as f:
            content = f.read()
    except FileNotFoundError:
        return
    matches = re.findall(r"==== Config backup completed at (.+?) ====", content)
    if matches:
        last_backup_cache = matches[-1]


def _truncate_log():
    try:
        with open(LOG_FILE, "r+") as f:
            lines = f.readlines()
            if len(lines) > LOG_MAX_LINES:
                f.seek(0)
                f.writelines(lines[-LOG_MAX_LINES:])
                f.truncate()
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# apcupsd NIS client (pure Python, no apcupsd package needed)
# ---------------------------------------------------------------------------

def query_apcupsd(host, port=3551):
    """Query apcupsd NIS and return status dict."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect((host, port))
        cmd = b"status"
        sock.send(struct.pack("!H", len(cmd)) + cmd)

        result = {}
        while True:
            length_bytes = _recv_exact(sock, 2)
            if not length_bytes:
                break
            length = struct.unpack("!H", length_bytes)[0]
            if length == 0:
                break
            data = _recv_exact(sock, length)
            if not data:
                break
            line = data.decode("utf-8", errors="replace").strip()
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        return {"ok": True, "data": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        sock.close()


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


# ---------------------------------------------------------------------------
# Backup targets
# ---------------------------------------------------------------------------

def _backup_pve(log, dry_run=False):
    """Rsync PVE host config files over SSH."""
    log(f"\n[PVE host] {PVE_HOST} -> {PVE_DIR}/")
    pve_dst = _dst(PVE_DIR)
    rc = 0
    for src in PVE_SRCS:
        # rsync trailing-slash semantics: dirs need trailing / to sync contents,
        # single files need their parent dir as destination
        if src.endswith("/"):
            dst = os.path.join(pve_dst, src.strip("/")) + "/"
        else:
            dst = os.path.join(pve_dst, os.path.dirname(src).strip("/")) + "/"
        os.makedirs(dst, exist_ok=True)
        log(f"--- {src} -> {dst}")
        ret = _rsync(f"{PVE_HOST}:{src}", dst, log, dry_run=dry_run)
        if ret != 0:
            log(f"    FAILED (exit {ret})\n")
            rc = ret
        else:
            log(f"    OK\n")
    return rc


def _backup_nmc(log, dry_run=False):
    """Download config.ini from each UPS NMC via FTP."""
    if not NMC_HOSTS or not NMC_PASS:
        log("\n[UPS NMC] skipped (NMC_HOSTS or NMC_PASS not set)")
        return 0
    log(f"\n[UPS NMC] {len(NMC_HOSTS)} devices -> {NMC_DIR}/")
    rc = 0
    nmc_dst = _dst(NMC_DIR)
    os.makedirs(nmc_dst, exist_ok=True)
    encoded_pass = quote(NMC_PASS, safe="")
    for name, ip in NMC_HOSTS:
        dst = os.path.join(nmc_dst, f"{name}.ini")
        log(f"--- NMC {ip} ({name}) -> {dst}" + (" (dry-run)" if dry_run else ""))
        if dry_run:
            continue
        url = f"ftp://{NMC_USER}:{encoded_pass}@{ip}/config.ini"
        result = subprocess.run(
            ["curl", "-s", "--connect-timeout", "10", "--use-ascii", "-o", dst, url],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            log(f"    FAILED (exit {result.returncode}): {result.stderr.strip()}\n")
            rc = result.returncode
        else:
            log(f"    OK ({os.path.getsize(dst)} bytes)\n")
    return rc


# ---------------------------------------------------------------------------
# Background runner
# ---------------------------------------------------------------------------

class LogWriter:
    """File-backed logger that implements the file protocol for subprocess."""
    def __init__(self, f):
        self.f = f

    def __call__(self, msg):
        self.f.write(msg + "\n")
        self.f.flush()

    def write(self, data):
        self.f.write(data)
        return len(data)

    def flush(self):
        self.f.flush()

    def fileno(self):
        return self.f.fileno()


def _rsync(src, dst, log, dry_run=False):
    cmd = RSYNC_BASE[:]
    cmd += ["-e", f"ssh -i {PVE_SSH_KEY} -o StrictHostKeyChecking=no -o BatchMode=yes"]
    if dry_run:
        cmd.append("--dry-run")
    cmd += [src, dst]
    result = subprocess.run(cmd, stdout=log, stderr=log)
    return result.returncode


def run_config_backup(dry_run=False):
    global running, action, last_backup_cache, last_error
    with _lock:
        if running:
            return
        running = True
    label = "Config backup dry-run" if dry_run else "Config backup"
    action = "config-backup-dry" if dry_run else "config-backup"
    with open(LOG_FILE, "a") as f:
        log = LogWriter(f)
        log(f"==== {label} started at {_now()} ====")
        rc = 0

        ret = _backup_pve(log, dry_run=dry_run)
        if ret != 0:
            rc = ret

        ret = _backup_nmc(log, dry_run=dry_run)
        if ret != 0:
            rc = ret

        ts = _now()
        if rc != 0:
            log(f"==== {label} FAILED (exit {rc}) at {ts} ====")
            last_error = f"{label} failed (exit {rc}) at {ts}"
        else:
            log(f"==== {label} completed at {ts} ====")
            if not dry_run:
                last_backup_cache = ts
            last_error = None
        log("")
    _truncate_log()
    running = False
    action = ""


# ---------------------------------------------------------------------------
# API routes — UPS
# ---------------------------------------------------------------------------

@app.route("/api/ups")
def api_ups():
    return jsonify(query_apcupsd(UPS_HOSTS[0]))


@app.route("/api/ups2")
def api_ups2():
    return jsonify(query_apcupsd(UPS_HOSTS[1]) if len(UPS_HOSTS) > 1 else {"ok": False, "error": "No second UPS configured"})


# ---------------------------------------------------------------------------
# API routes — Config Backup
# ---------------------------------------------------------------------------

@app.route("/api/targets")
def api_targets():
    targets = [
        {
            "name": "PVE host",
            "icon": "pve",
            "detail": PVE_HOST.split("@")[-1],
            "items": PVE_SRCS,
            "dest": PVE_DIR,
        },
    ]
    if NMC_HOSTS and NMC_PASS:
        targets.append({
            "name": "UPS NMC",
            "icon": "ups",
            "detail": f"{len(NMC_HOSTS)} device{'s' if len(NMC_HOSTS) != 1 else ''}",
            "items": [f"{name} ({ip})" for name, ip in NMC_HOSTS],
            "dest": NMC_DIR,
        })
    return jsonify(targets=targets)


@app.route("/api/status")
def api_status():
    return jsonify(
        running=running,
        action=action,
        log=_read_log(),
        last_backup=last_backup_cache,
        last_error=last_error
    )


@app.route("/backup/run", methods=["POST"])
def backup_run():
    dry = request.args.get("dry") == "1"
    threading.Thread(target=run_config_backup, args=(dry,), daemon=True).start()
    return "ok"


@app.route("/backup/clear-log", methods=["POST"])
def backup_clear_log():
    global last_backup_cache, last_error
    try:
        with open(LOG_FILE, "w"):
            pass
    except FileNotFoundError:
        pass
    last_backup_cache = None
    last_error = None
    return "ok"


# ---------------------------------------------------------------------------
# SPA catch-all (serves Vue build from dist/)
# ---------------------------------------------------------------------------

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    _init_last_backup_cache()
    app.run(host="0.0.0.0", port=8000)
