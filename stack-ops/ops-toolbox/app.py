import os
import re
import glob
import socket
import struct
import subprocess
import threading
import datetime
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="dist", static_url_path="")

LOG_FILE = "/var/log/backup.log"
LOG_MAX_LINES = 5000
SELF_CONTAINERS = {"ops-toolbox"}
EXCLUDES = [".git/", "temp/", "downloads/", ".DS_Store", "._*", "@eaDir", "logs/", "Logs/"]
RSYNC_BASE = ["rsync", "-avh", "-l", "--delete"]
STACK_PRIORITY = {"stack-infra": 0, "stack-auth": 1}

UPS_INSTANCES = {
    "rack":    {"host": "apcupsd",  "port": 3551},
    "desktop": {"host": "apcupsd2", "port": 3551},
}

running = False
action = ""
last_backup_cache = None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _exclude_args():
    args = []
    for e in EXCLUDES:
        args.extend(["--exclude", e])
    return args


def _read_log(tail=200):
    if not os.path.exists(LOG_FILE):
        return ""
    with open(LOG_FILE) as f:
        lines = f.readlines()
        return "".join(lines[-tail:])


def _init_last_backup_cache():
    global last_backup_cache
    if not os.path.exists(LOG_FILE):
        return
    with open(LOG_FILE) as f:
        content = f.read()
    matches = re.findall(r"==== Backup completed at (.+?) ====", content)
    if matches:
        last_backup_cache = matches[-1]


def _truncate_log():
    if not os.path.exists(LOG_FILE):
        return
    with open(LOG_FILE, "r+") as f:
        lines = f.readlines()
        if len(lines) > LOG_MAX_LINES:
            f.seek(0)
            f.writelines(lines[-LOG_MAX_LINES:])
            f.truncate()


def _rsync(src, dst, f, dry_run=False):
    cmd = RSYNC_BASE + _exclude_args()
    if dry_run:
        cmd.append("--dry-run")
    cmd += [src, dst]
    subprocess.run(cmd, stdout=f, stderr=f)


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
    global running, action, last_backup_cache
    running = True
    label = "Backup dry-run" if dry_run else "Backup"
    action = "backup-dry" if dry_run else "backup"
    with open(LOG_FILE, "a") as f:
        def log(msg):
            f.write(msg + "\n")
            f.flush()
        log(f"==== {label} started at {_now()} ====")
        _rsync("/source/", "/destination/", f, dry_run=dry_run)
        ts = _now()
        log(f"==== {label} completed at {ts} ====")
        log("")
        if not dry_run:
            last_backup_cache = ts
    _truncate_log()
    running = False
    action = ""


def _compose_up_stacks(f, log):
    subprocess.run(
        ["docker", "network", "create", "traefik-proxy"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    compose_files = glob.glob("/source/stack-*/docker-compose.yml")
    compose_files.sort(key=lambda p: (
        STACK_PRIORITY.get(os.path.basename(os.path.dirname(p)), 99),
        os.path.basename(os.path.dirname(p))
    ))
    for compose_file in compose_files:
        stack = os.path.basename(os.path.dirname(compose_file))
        if stack == "stack-ops":
            continue
        log(f"Starting {stack}...")
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "up", "-d"],
            stdout=f, stderr=f
        )


def run_restore(dry_run=False):
    global running, action
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
        _rsync("/destination/", "/source/", f, dry_run=dry_run)
        log(f"==== {label} completed at {_now()} ====")
        log("")
    _truncate_log()
    running = False
    action = ""


def run_stop_all():
    global running, action
    running = True
    action = "stop-all"
    with open(LOG_FILE, "a") as f:
        def log(msg):
            f.write(msg + "\n")
            f.flush()
        log(f"==== Stop all started at {_now()} ====")
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
        log(f"==== Stop all completed at {_now()} ====")
        log("")
    _truncate_log()
    running = False
    action = ""


def run_start_all():
    global running, action
    running = True
    action = "start-all"
    with open(LOG_FILE, "a") as f:
        def log(msg):
            f.write(msg + "\n")
            f.flush()
        log(f"==== Start all started at {_now()} ====")
        _compose_up_stacks(f, log)
        log(f"==== Start all completed at {_now()} ====")
        log("")
    _truncate_log()
    running = False
    action = ""


# ---------------------------------------------------------------------------
# API routes — UPS
# ---------------------------------------------------------------------------

@app.route("/api/ups")
def api_ups():
    return jsonify(query_apcupsd(**UPS_INSTANCES["rack"]))


@app.route("/api/ups2")
def api_ups2():
    return jsonify(query_apcupsd(**UPS_INSTANCES["desktop"]))


# ---------------------------------------------------------------------------
# API routes — Backup & containers
# ---------------------------------------------------------------------------

@app.route("/api/backup")
def api_backup():
    return jsonify(
        running=running,
        action=action,
        log=_read_log(),
        last_backup=last_backup_cache
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


@app.route("/backup/clear-log", methods=["POST"])
def backup_clear_log():
    global last_backup_cache
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w"):
            pass
    last_backup_cache = None
    return "ok"


@app.route("/containers/stop-all", methods=["POST"])
def containers_stop_all():
    if not running:
        threading.Thread(target=run_stop_all, daemon=True).start()
    return "ok"


@app.route("/containers/start-all", methods=["POST"])
def containers_start_all():
    if not running:
        threading.Thread(target=run_start_all, daemon=True).start()
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
