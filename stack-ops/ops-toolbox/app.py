import os
import re
import shutil
import socket
import struct
import subprocess
import threading
import datetime
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="dist", static_url_path="")

# ---------------------------------------------------------------------------
# Configuration (all overridable via environment variables)
# ---------------------------------------------------------------------------

LOG_FILE = "/var/log/backup.log"
LOG_MAX_LINES = 5000
SELF_CONTAINERS = {"ops-toolbox"}

# UPS
UPS1_HOST = os.environ["UPS1_HOST"]
UPS1_PORT = int(os.environ["UPS1_PORT"])
UPS2_HOST = os.environ["UPS2_HOST"]
UPS2_PORT = int(os.environ["UPS2_PORT"])

# Docker backup
BACKUP_SRC = os.environ["BACKUP_SRC"]
BACKUP_DST = os.environ["BACKUP_DST"]
BACKUP_EXCLUDES = os.environ["BACKUP_EXCLUDES"].split(",")

# PVE backup (rsync over SSH)
PVE_HOST = os.environ["PVE_HOST"]
PVE_SSH_KEY = os.environ["PVE_SSH_KEY"]
PVE_SRC = os.environ["PVE_SRC"]
PVE_DST = os.environ["PVE_DST"]

RSYNC_BASE = ["rsync", "-avh", "-l", "--delete"]

running = False
action = ""
last_backup_cache = None
last_pve_backup_cache = None
last_error = None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _exclude_args():
    args = []
    for e in BACKUP_EXCLUDES:
        e = e.strip()
        if e:
            args.extend(["--exclude", e])
    return args


def _read_log(tail=200):
    if not os.path.exists(LOG_FILE):
        return ""
    with open(LOG_FILE) as f:
        lines = f.readlines()
        return "".join(lines[-tail:])


def _init_last_backup_cache():
    global last_backup_cache, last_pve_backup_cache
    if not os.path.exists(LOG_FILE):
        return
    with open(LOG_FILE) as f:
        content = f.read()
    matches = re.findall(r"==== Backup completed at (.+?) ====", content)
    if matches:
        last_backup_cache = matches[-1]
    pve_matches = re.findall(r"==== PVE backup completed at (.+?) ====", content)
    if pve_matches:
        last_pve_backup_cache = pve_matches[-1]


def _truncate_log():
    if not os.path.exists(LOG_FILE):
        return
    with open(LOG_FILE, "r+") as f:
        lines = f.readlines()
        if len(lines) > LOG_MAX_LINES:
            f.seek(0)
            f.writelines(lines[-LOG_MAX_LINES:])
            f.truncate()


def _rsync(src, dst, f, dry_run=False, exclude=True, ssh=False):
    cmd = RSYNC_BASE[:]
    if exclude:
        cmd += _exclude_args()
    if ssh:
        cmd += ["-e", f"ssh -i {PVE_SSH_KEY} -o StrictHostKeyChecking=no -o BatchMode=yes"]
    if dry_run:
        cmd.append("--dry-run")
    cmd += [src, dst]
    result = subprocess.run(cmd, stdout=f, stderr=f)
    return result.returncode


# ---------------------------------------------------------------------------
# apcupsd NIS client (pure Python, no apcupsd package needed)
# ---------------------------------------------------------------------------

def query_apcupsd(host="apcupsd", port=3551):
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
# Background operations
# ---------------------------------------------------------------------------

def run_backup(dry_run=False):
    global running, action, last_backup_cache, last_error
    running = True
    label = "Backup dry-run" if dry_run else "Backup"
    action = "backup-dry" if dry_run else "backup"
    with open(LOG_FILE, "a") as f:
        def log(msg):
            f.write(msg + "\n")
            f.flush()
        log(f"==== {label} started at {_now()} ====")
        rc = _rsync(BACKUP_SRC, BACKUP_DST, f, dry_run=dry_run)
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



def run_restore(dry_run=False):
    global running, action, last_error
    running = True
    action = "restore-dry" if dry_run else "restore"
    with open(LOG_FILE, "a") as f:
        def log(msg):
            f.write(msg + "\n")
            f.flush()
        label = "Restore dry-run" if dry_run else "Restore"
        log(f"==== {label} started at {_now()} ====")
        if not dry_run:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True, text=True
            )
            all_containers = [c.strip() for c in result.stdout.strip().split("\n") if c.strip()]
            to_stop = [c for c in all_containers if c not in SELF_CONTAINERS]
            if to_stop:
                log(f"Stopping containers: {', '.join(to_stop)}")
                subprocess.run(["docker", "stop"] + to_stop, stdout=f, stderr=f)
            else:
                log("No other containers to stop")
        log("Restoring files from NAS backup..." + (" (dry-run)" if dry_run else ""))
        rc = _rsync(BACKUP_DST, BACKUP_SRC, f, dry_run=dry_run)
        ts = _now()
        if rc != 0:
            log(f"==== {label} FAILED (exit {rc}) at {ts} ====")
            last_error = f"{label} failed (exit {rc}) at {ts}"
        else:
            log(f"==== {label} completed at {ts} ====")
            last_error = None
        log("")
    _truncate_log()
    running = False
    action = ""



def run_pve_backup(dry_run=False):
    global running, action, last_pve_backup_cache, last_error
    running = True
    label = "PVE backup dry-run" if dry_run else "PVE backup"
    action = "pve-backup-dry" if dry_run else "pve-backup"
    with open(LOG_FILE, "a") as f:
        def log(msg):
            f.write(msg + "\n")
            f.flush()
        log(f"==== {label} started at {_now()} ====")
        rc = _rsync(f"{PVE_HOST}:{PVE_SRC}", PVE_DST, f, dry_run=dry_run, exclude=False, ssh=True)
        ts = _now()
        if rc != 0:
            log(f"==== {label} FAILED (exit {rc}) at {ts} ====")
            last_error = f"{label} failed (exit {rc}) at {ts}"
        else:
            log(f"==== {label} completed at {ts} ====")
            if not dry_run:
                last_pve_backup_cache = ts
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
    return jsonify(query_apcupsd(UPS1_HOST, UPS1_PORT))


@app.route("/api/ups2")
def api_ups2():
    return jsonify(query_apcupsd(UPS2_HOST, UPS2_PORT))


# ---------------------------------------------------------------------------
# API routes — Backup & containers
# ---------------------------------------------------------------------------

@app.route("/api/backup")
def api_backup():
    return jsonify(
        running=running,
        action=action,
        log=_read_log(),
        last_backup=last_backup_cache,
        last_pve_backup=last_pve_backup_cache,
        last_error=last_error
    )


@app.route("/backup/run", methods=["POST"])
def backup_run():
    if not running:
        dry = request.args.get("dry") == "1"
        threading.Thread(target=run_backup, args=(dry,), daemon=True).start()
    return "ok"


@app.route("/backup/restore", methods=["POST"])
def backup_restore():
    if not running:
        dry = request.args.get("dry") == "1"
        threading.Thread(target=run_restore, args=(dry,), daemon=True).start()
    return "ok"


@app.route("/proxmox/run", methods=["POST"])
def proxmox_run():
    if not running:
        dry = request.args.get("dry") == "1"
        threading.Thread(target=run_pve_backup, args=(dry,), daemon=True).start()
    return "ok"


@app.route("/backup/clear-log", methods=["POST"])
def backup_clear_log():
    global last_backup_cache, last_pve_backup_cache, last_error
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w"):
            pass
    last_backup_cache = None
    last_pve_backup_cache = None
    last_error = None
    return "ok"



@app.route("/api/test-shutdown", methods=["POST"])
def test_shutdown():
    try:
        result = subprocess.run(
            ["docker", "exec", "apcupsd", "dbus-send", "--system", "--print-reply",
             "--dest=org.freedesktop.login1",
             "/org/freedesktop/login1",
             "org.freedesktop.login1.Manager.CanPowerOff"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout + result.stderr
        if result.returncode == 0 and 'string "yes"' in output:
            return jsonify(ok=True, message="D-Bus shutdown path is working")
        else:
            return jsonify(ok=False, message=output.strip() or "Unknown error")
    except Exception as e:
        return jsonify(ok=False, message=str(e))


# ---------------------------------------------------------------------------
# API routes — Storage
# ---------------------------------------------------------------------------

def _disk_usage(path):
    try:
        u = shutil.disk_usage(path)
        return {"total": u.total, "used": u.used, "free": u.free, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.route("/api/storage")
def api_storage():
    host = _disk_usage(BACKUP_SRC)
    nas = _disk_usage(BACKUP_DST)
    return jsonify(host=host, nas=nas)


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
