from flask import Flask, request, jsonify
import subprocess
import threading
import datetime
import glob
import re
import os
from html import escape

app = Flask(__name__)
LOG_FILE = "/var/log/backup.log"
LOG_MAX_LINES = 5000
SELF_CONTAINER = "backup"
EXCLUDES = [".git/", "temp/", "downloads/", ".DS_Store", "._*", "@eaDir"]
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


def _time_ago(iso_str):
    if not iso_str:
        return None
    dt = datetime.datetime.fromisoformat(iso_str)
    diff = (datetime.datetime.now().astimezone() - dt).total_seconds()
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{int(diff // 60)}m ago"
    if diff < 86400:
        return f"{int(diff // 3600)}h ago"
    return f"{int(diff // 86400)}d ago"


TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<title>Docker Backup & Restore</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, system-ui, sans-serif; background: #0d1117; color: #c9d1d9; padding: 2rem; }
  h1 { font-size: 1.4rem; display: inline; margin-right: 0.6rem; }
  .status { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.75rem; vertical-align: middle; }
  .idle { background: #238636; }
  .active { background: #d29922; }
  .danger { background: #da3633; }
  .meta { font-size: 0.8rem; color: #8b949e; margin-top: 0.4rem; }
  button { color: #fff; border: none; padding: 0.5rem 1.2rem; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
  .btn-backup { background: #238636; }
  .btn-backup:hover { background: #2ea043; }
  .btn-restore { background: #da3633; }
  .btn-restore:hover { background: #f85149; }
  .btn-secondary { background: transparent; border: 1px solid #30363d; color: #8b949e; font-size: 0.8rem; padding: 0.4rem 0.8rem; }
  .btn-secondary:hover { border-color: #8b949e; color: #c9d1d9; }
  button:disabled { background: #484f58 !important; border-color: #484f58 !important; cursor: not-allowed; color: #8b949e !important; }
  .checkbox-label { font-size: 0.8rem; color: #8b949e; cursor: pointer; display: flex; align-items: center; gap: 0.3rem; }
  .checkbox-label input { accent-color: #8b949e; }
  pre { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 1rem; margin-top: 1rem;
        overflow-x: auto; font-size: 0.8rem; line-height: 1.5; max-height: 70vh; overflow-y: auto; white-space: pre-wrap; }
  .actions { margin-top: 1rem; display: flex; align-items: center; flex-wrap: wrap; gap: 0.5rem; }
  .sep { color: #30363d; }
  .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 10; }
  .modal { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.5rem; max-width: 500px; margin: 15vh auto; }
  .modal h2 { font-size: 1.1rem; margin-bottom: 0.8rem; color: #f85149; }
  .modal p { font-size: 0.85rem; margin-bottom: 1rem; line-height: 1.5; }
  .modal .warn { background: #da36331a; border: 1px solid #da3633; border-radius: 4px; padding: 0.8rem; margin-bottom: 1rem; font-size: 0.8rem; }
  .modal input { background: #0d1117; border: 1px solid #30363d; color: #c9d1d9; padding: 0.4rem 0.6rem; border-radius: 4px;
                 width: 100%; font-size: 0.85rem; margin-bottom: 1rem; }
  .modal-buttons { display: flex; gap: 0.5rem; justify-content: flex-end; }
</style>
</head>
<body>
  <div>
    <h1>Docker Backup & Restore <span class="status $STATUS_CLASS" id="status">$STATUS_TEXT</span></h1>
    <p class="meta" id="last-backup">$LAST_BACKUP</p>
  </div>
  <pre id="log">$LOG</pre>
  <div class="actions">
    <button class="btn-backup" onclick="runAction('/run')" id="btn-backup" $DISABLED>Run backup</button>
    <button class="btn-restore" onclick="showRestore()" id="btn-restore" $DISABLED>Restore</button>
    <label class="checkbox-label"><input type="checkbox" id="dry-run"> Dry run</label>
    <span class="sep">|</span>
    <button class="btn-secondary" onclick="setupFstab()" id="btn-fstab" $DISABLED>Setup NFS mounts</button>
    <button class="btn-secondary" onclick="clearLog()" id="btn-clear">Clear log</button>
  </div>

  <div class="modal-overlay" id="restore-modal">
    <div class="modal">
      <h2>Restore from NAS backup</h2>
      <div class="warn">
        This will stop all running Docker containers (except this one), rsync from the NAS backup back to /srv/docker, then restart all stacks via docker compose.
      </div>
      <p>Type <strong>RESTORE</strong> to confirm:</p>
      <input type="text" id="confirm-input" placeholder="Type RESTORE" autocomplete="off">
      <div class="modal-buttons">
        <button class="btn-backup" onclick="hideRestore()">Cancel</button>
        <button class="btn-restore" onclick="doRestore()">Restore</button>
      </div>
    </div>
  </div>

  <script>
    var logEl = document.getElementById('log');
    var statusEl = document.getElementById('status');
    var lastBackupEl = document.getElementById('last-backup');
    var dryEl = document.getElementById('dry-run');
    var btns = ['btn-backup', 'btn-restore', 'btn-fstab'];
    var isRunning = $IS_RUNNING;

    logEl.scrollTop = logEl.scrollHeight;

    function setDisabled(disabled) {
      btns.forEach(function(id) { document.getElementById(id).disabled = disabled; });
      dryEl.disabled = disabled;
    }

    function runAction(url) {
      if (dryEl.checked) url += (url.indexOf('?') === -1 ? '?' : '&') + 'dry=1';
      setDisabled(true);
      isRunning = true;
      fetch(url, {method: 'POST'});
    }

    function showRestore() {
      if (dryEl.checked) { runAction('/restore'); return; }
      document.getElementById('restore-modal').style.display = 'block';
      document.getElementById('confirm-input').value = '';
      document.getElementById('confirm-input').focus();
    }

    function hideRestore() {
      document.getElementById('restore-modal').style.display = 'none';
    }

    function doRestore() {
      if (document.getElementById('confirm-input').value.trim() !== 'RESTORE') {
        alert('Please type RESTORE to confirm.');
        return;
      }
      hideRestore();
      runAction('/restore');
    }

    function setupFstab() {
      setDisabled(true);
      isRunning = true;
      fetch('/setup-fstab', {method: 'POST'});
    }

    function clearLog() {
      fetch('/clear-log', {method: 'POST'}).then(function() { poll(); });
    }

    function timeAgo(iso) {
      if (!iso) return '';
      var s = (Date.now() - new Date(iso).getTime()) / 1000;
      if (s < 60) return 'just now';
      if (s < 3600) return Math.floor(s / 60) + 'm ago';
      if (s < 86400) return Math.floor(s / 3600) + 'h ago';
      return Math.floor(s / 86400) + 'd ago';
    }

    function poll() {
      return fetch('/api/status').then(function(r) { return r.json(); }).then(function(d) {
        isRunning = d.running;
        var cls = 'idle', txt = 'Idle';
        if (d.running) {
          var r = d.action.indexOf('restore') !== -1;
          var dry = d.action.indexOf('dry') !== -1;
          if (d.action === 'fstab') { cls = 'active'; txt = 'Setting up fstab...'; }
          else if (r) { cls = 'danger'; txt = dry ? 'Restore dry-run...' : 'Restoring...'; }
          else { cls = 'active'; txt = dry ? 'Backup dry-run...' : 'Backing up...'; }
        }
        statusEl.textContent = txt;
        statusEl.className = 'status ' + cls;
        setDisabled(d.running);
        var atBottom = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight < 50;
        logEl.textContent = d.log || 'No backup runs yet.';
        if (atBottom) logEl.scrollTop = logEl.scrollHeight;
        lastBackupEl.textContent = d.last_backup ? 'Last backup: ' + timeAgo(d.last_backup) : '';
      }).catch(function() {});
    }

    (function schedule() {
      setTimeout(function() { poll().then(schedule); }, isRunning ? 2000 : 15000);
    })();
  </script>
</body>
</html>"""


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


FSTAB_EXAMPLE = "/source/fstab.example"
HOST_FSTAB = "/host/fstab"
FSTAB_MARKER_START = "# BEGIN nfs-mounts (managed by backup-ops)"
FSTAB_MARKER_END = "# END nfs-mounts (managed by backup-ops)"


def setup_fstab():
    global running, action
    running = True
    action = "fstab"

    with open(LOG_FILE, "a") as f:
        def log(msg):
            f.write(msg + "\n")
            f.flush()

        log(f"==== Setup fstab started at {_now()} ====")

        if not os.path.exists(FSTAB_EXAMPLE):
            log("ERROR: fstab.example not found")
            log(f"==== Setup fstab failed at {_now()} ====")
            log("")
            running = False
            action = ""
            return

        with open(FSTAB_EXAMPLE) as ef:
            new_entries = ef.read().strip()

        with open(HOST_FSTAB) as hf:
            current = hf.read()

        managed_block = f"{FSTAB_MARKER_START}\n{new_entries}\n{FSTAB_MARKER_END}"

        if FSTAB_MARKER_START in current:
            pattern = re.escape(FSTAB_MARKER_START) + r".*?" + re.escape(FSTAB_MARKER_END)
            new_fstab = re.sub(pattern, managed_block, current, flags=re.DOTALL)
            log("Updated existing NFS mount block in /etc/fstab")
        else:
            new_fstab = current.rstrip("\n") + "\n\n" + managed_block + "\n"
            log("Added NFS mount block to /etc/fstab")

        with open(HOST_FSTAB, "w") as hf:
            hf.write(new_fstab)

        # Extract mount points and create directories on host via docker
        mount_points = []
        for line in new_entries.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                if len(parts) >= 2:
                    mount_points.append(parts[1])
                    log(f"  {parts[1]} <- {parts[0]}")

        if mount_points:
            log("Creating mount directories on host...")
            subprocess.run(
                ["docker", "run", "--rm", "-v", "/mnt:/mnt", "alpine",
                 "mkdir", "-p"] + mount_points,
                stdout=f, stderr=f
            )

        log("Mounting all fstab entries on host...")
        subprocess.run(
            ["docker", "run", "--rm", "--privileged", "--pid=host",
             "alpine", "nsenter", "-t", "1", "-m", "-u", "-i", "-n", "--",
             "mount", "-a"],
            stdout=f, stderr=f
        )
        log(f"==== Setup fstab completed at {_now()} ====")
        log("")

    running = False
    action = ""


@app.route("/")
def index():
    log = _read_log()

    if running and action == "fstab":
        status_class, status_text = "active", "Setting up fstab..."
    elif running and action.startswith("restore"):
        status_class = "danger"
        status_text = "Restore dry-run..." if "dry" in action else "Restoring..."
    elif running:
        status_class = "active"
        status_text = "Backup dry-run..." if "dry" in action else "Backing up..."
    else:
        status_class, status_text = "idle", "Idle"

    ago = _time_ago(last_backup_cache)
    html = TEMPLATE
    html = html.replace("$STATUS_CLASS", status_class)
    html = html.replace("$STATUS_TEXT", status_text)
    html = html.replace("$DISABLED", "disabled" if running else "")
    html = html.replace("$LOG", escape(log) if log else "No backup runs yet.")
    html = html.replace("$LAST_BACKUP", f"Last backup: {ago}" if ago else "")
    html = html.replace("$IS_RUNNING", "true" if running else "false")
    return html


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


@app.route("/setup-fstab", methods=["POST"])
def setup_fstab_route():
    if not running:
        threading.Thread(target=setup_fstab, daemon=True).start()
    return "ok"


@app.route("/clear-log", methods=["POST"])
def clear_log():
    global last_backup_cache
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w"):
            pass
    last_backup_cache = None
    return "ok"


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
