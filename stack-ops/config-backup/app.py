import os
import re
import socket
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

# Backup root (NFS mount)
BACKUP_DST = os.environ.get("BACKUP_DST", "/destination")

# PVE host config backup (rsync over SSH)
PVE_HOST = os.environ["PVE_HOST"]
PVE_SSH_KEY = os.environ["PVE_SSH_KEY"]
PVE_DIR = os.environ.get("PVE_DIR", "pve-host")
PVE_SRCS = [s.strip() for s in os.environ["PVE_SRCS"].split(",")]

# UPS NMC config snapshot (FTP, manual only) — NMC_HOSTS format: "name:ip,name:ip"
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
    matches = re.findall(r"==== .+ completed at (.+?) ====", content)
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
# Backup targets
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


def _backup_pve(log, dry_run=False):
    """Rsync PVE host config files over SSH."""
    log(f"\n[PVE host] {PVE_HOST} -> {PVE_DIR}/")
    pve_dst = _dst(PVE_DIR)
    rc = 0
    for src in PVE_SRCS:
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
        # Check reachability before attempting FTP — offline NMCs are skipped, not failures
        try:
            s = socket.create_connection((ip, 21), timeout=5)
            s.close()
        except OSError:
            log(f"    SKIPPED (offline)\n")
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

def _run_backup(label, backup_fn, dry_run=False):
    global running, action, last_backup_cache, last_error
    with _lock:
        if running:
            return
        running = True
    suffix = " dry-run" if dry_run else ""
    action = f"{label}{'-dry' if dry_run else ''}"
    with open(LOG_FILE, "a") as f:
        log = LogWriter(f)
        log(f"==== {label}{suffix} started at {_now()} ====")
        rc = backup_fn(log, dry_run=dry_run)
        ts = _now()
        if rc != 0:
            log(f"==== {label}{suffix} FAILED (exit {rc}) at {ts} ====")
            last_error = f"{label}{suffix} failed (exit {rc}) at {ts}"
        else:
            log(f"==== {label}{suffix} completed at {ts} ====")
            if not dry_run:
                last_backup_cache = ts
            last_error = None
        log("")
    _truncate_log()
    running = False
    action = ""


# ---------------------------------------------------------------------------
# API routes
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
            "schedule": "Daily 02:00",
        },
    ]
    if NMC_HOSTS and NMC_PASS:
        targets.append({
            "name": "UPS NMC",
            "icon": "ups",
            "detail": f"{len(NMC_HOSTS)} device{'s' if len(NMC_HOSTS) != 1 else ''}",
            "items": [f"{name} ({ip})" for name, ip in NMC_HOSTS],
            "dest": NMC_DIR,
            "schedule": "Manual",
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


@app.route("/backup/pve", methods=["POST"])
def backup_pve():
    dry = request.args.get("dry") == "1"
    threading.Thread(target=_run_backup, args=("PVE config backup", _backup_pve, dry), daemon=True).start()
    return "ok"


@app.route("/backup/nmc", methods=["POST"])
def backup_nmc():
    dry = request.args.get("dry") == "1"
    threading.Thread(target=_run_backup, args=("NMC config snapshot", _backup_nmc, dry), daemon=True).start()
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
