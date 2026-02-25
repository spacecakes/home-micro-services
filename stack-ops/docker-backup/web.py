from flask import Flask, request, jsonify
import subprocess
import threading
import datetime
import glob
import re
import os

app = Flask(__name__)
LOG_FILE = "/var/log/backup.log"
LOG_MAX_LINES = 5000
SELF_CONTAINER = "docker-backup"
EXCLUDES = [".git/", "temp/", "downloads/", ".DS_Store", "._*", "@eaDir", "logs/"]
RSYNC_BASE = ["rsync", "-avh", "--no-perms", "--no-owner", "--no-group", "-l", "--delete"]
STACK_PRIORITY = {"stack-infra": 0, "stack-auth": 1}

running = False
action = ""
last_backup_cache = None


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
    """Start all stacks via docker compose, ordered by priority."""
    # Ensure the shared external network exists
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
            continue  # skip ourselves
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
            to_stop = [c for c in all_containers if c != SELF_CONTAINER]

            if to_stop:
                log(f"Stopping containers: {', '.join(to_stop)}")
                subprocess.run(["docker", "stop"] + to_stop, stdout=f, stderr=f)
            else:
                log("No other containers to stop")

        log("Restoring files from NAS backup..." + (" (dry-run)" if dry_run else ""))
        _rsync("/destination/", "/source/", f, dry_run=dry_run)

        if not dry_run:
            _compose_up_stacks(f, log)

        log(f"==== {label} completed at {_now()} ====")
        log("")

    _truncate_log()
    running = False
    action = ""



@app.route("/run", methods=["POST"])
def trigger():
    if not running:
        dry = request.args.get("dry") == "1"
        threading.Thread(target=run_backup, args=(dry,), daemon=True).start()
    return "ok"


@app.route("/restore", methods=["POST"])
def restore():
    if not running:
        dry = request.args.get("dry") == "1"
        threading.Thread(target=run_restore, args=(dry,), daemon=True).start()
    return "ok"


@app.route("/clear-log", methods=["POST"])
def clear_log():
    global last_backup_cache
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w"):
            pass
    last_backup_cache = None
    return "ok"


@app.route("/test-shutdown", methods=["POST"])
def test_shutdown_route():
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


@app.route("/api/status")
def api_status():
    return jsonify(
        running=running,
        action=action,
        log=_read_log(),
        last_backup=last_backup_cache
    )


if __name__ == "__main__":
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    _init_last_backup_cache()
    app.run(host="0.0.0.0", port=8000)
