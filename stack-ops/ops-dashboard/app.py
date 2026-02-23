from flask import Flask, request, jsonify
import socket
import struct
import requests as http_requests

app = Flask(__name__)

APCUPSD_HOST = "apcupsd"
APCUPSD_PORT = 3551
BACKUP_API = "http://docker-backup:8000"


# ---------------------------------------------------------------------------
# apcupsd NIS client (pure Python, no apcupsd package needed)
# ---------------------------------------------------------------------------

def query_apcupsd():
    """Query apcupsd NIS and return status dict."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect((APCUPSD_HOST, APCUPSD_PORT))

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
    """Read exactly n bytes from socket."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


# ---------------------------------------------------------------------------
# Backup API proxy
# ---------------------------------------------------------------------------

def proxy_backup_get(path):
    try:
        r = http_requests.get(f"{BACKUP_API}{path}", timeout=10)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 502


def proxy_backup_post(path, query_string=""):
    try:
        url = f"{BACKUP_API}{path}"
        if query_string:
            url += f"?{query_string}"
        r = http_requests.post(url, timeout=10)
        return r.text, r.status_code
    except Exception as e:
        return str(e), 502


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return TEMPLATE


@app.route("/api/ups")
def api_ups():
    return jsonify(query_apcupsd())


@app.route("/api/backup")
def api_backup():
    data, status = proxy_backup_get("/api/status")
    return jsonify(data), status


@app.route("/backup/run", methods=["POST"])
def backup_run():
    text, status = proxy_backup_post("/run", request.query_string.decode())
    return text, status


@app.route("/backup/restore", methods=["POST"])
def backup_restore():
    text, status = proxy_backup_post("/restore", request.query_string.decode())
    return text, status


@app.route("/backup/setup-fstab", methods=["POST"])
def backup_setup_fstab():
    text, status = proxy_backup_post("/setup-fstab", request.query_string.decode())
    return text, status


@app.route("/backup/setup-docker-wait", methods=["POST"])
def backup_setup_docker_wait():
    text, status = proxy_backup_post("/setup-docker-wait")
    return text, status


@app.route("/backup/clear-log", methods=["POST"])
def backup_clear_log():
    text, status = proxy_backup_post("/clear-log")
    return text, status


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<title>Ops Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, system-ui, sans-serif; background: #0d1117; color: #c9d1d9; padding: 2rem; }
  h1 { font-size: 1.4rem; margin-bottom: 1rem; }
  h2 { font-size: 1.1rem; display: inline; margin-right: 0.6rem; }

  .dashboard { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
  .panel { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.5rem; }
  .panel-wide { grid-column: 1 / -1; }

  .status { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.75rem; vertical-align: middle; }
  .idle { background: #238636; }
  .active { background: #d29922; }
  .danger { background: #da3633; }
  .offline { background: #484f58; }

  .meta { font-size: 0.8rem; color: #8b949e; margin-top: 0.4rem; }

  /* UPS metrics */
  .metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin: 1rem 0; }
  .metric { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 0.75rem; }
  .metric .label { font-size: 0.75rem; color: #8b949e; }
  .metric .value { font-size: 1.2rem; font-weight: 600; margin-top: 0.2rem; }

  details { margin-top: 0.75rem; }
  summary { font-size: 0.8rem; color: #8b949e; cursor: pointer; }
  details table { width: 100%; margin-top: 0.5rem; font-size: 0.8rem; }
  details td { padding: 0.25rem 0.5rem; border-bottom: 1px solid #21262d; }
  details td:first-child { color: #8b949e; width: 40%; }

  /* Backup panel */
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
  pre { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 1rem; margin-top: 1rem;
        overflow-x: auto; font-size: 0.8rem; line-height: 1.5; max-height: 55vh; overflow-y: auto; white-space: pre-wrap; }
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

  .spinner { display: inline-block; width: 0.8em; height: 0.8em; border: 2px solid rgba(255,255,255,0.3);
             border-top-color: #fff; border-radius: 50%; animation: spin 0.6s linear infinite;
             vertical-align: middle; margin-left: 0.4em; }
  .btn-secondary .spinner { border-color: rgba(139,148,158,0.3); border-top-color: #c9d1d9; }
  @keyframes spin { to { transform: rotate(360deg); } }

  @media (max-width: 800px) { .dashboard { grid-template-columns: 1fr; } }
</style>
</head>
<body>
  <h1>Ops Dashboard</h1>
  <div class="dashboard">

    <!-- UPS Panel -->
    <div class="panel">
      <div>
        <h2>UPS Status</h2>
        <span class="status offline" id="ups-status">Loading...</span>
      </div>
      <div class="metrics">
        <div class="metric"><div class="label">Load</div><div class="value" id="ups-load">—</div></div>
        <div class="metric"><div class="label">Battery</div><div class="value" id="ups-battery">—</div></div>
        <div class="metric"><div class="label">Runtime</div><div class="value" id="ups-runtime">—</div></div>
        <div class="metric"><div class="label">Line voltage</div><div class="value" id="ups-voltage">—</div></div>
      </div>
      <details>
        <summary>Show raw output</summary>
        <table id="ups-raw"></table>
      </details>
    </div>

    <!-- Backup & Restore Panel -->
    <div class="panel">
      <div>
        <h2>Backup & Restore</h2>
        <span class="status idle" id="backup-status">Idle</span>
        <p class="meta" id="last-backup"></p>
      </div>
      <div class="actions">
        <button class="btn-backup" onclick="runAction('/backup/run','btn-backup')" id="btn-backup">Run backup</button>
        <button class="btn-restore" onclick="showRestore()" id="btn-restore">Restore</button>
        <label class="checkbox-label"><input type="checkbox" id="dry-run"> Dry run</label>
      </div>

      <div class="modal-overlay" id="restore-modal">
        <div class="modal">
          <h2>Restore from NAS backup</h2>
          <div class="warn">
            This will stop all running Docker containers (except backup), rsync from the NAS backup back to /srv/docker, then restart all stacks via docker compose.
          </div>
          <p>Type <strong>RESTORE</strong> to confirm:</p>
          <input type="text" id="confirm-input" placeholder="Type RESTORE" autocomplete="off">
          <div class="modal-buttons">
            <button class="btn-backup" onclick="hideRestore()">Cancel</button>
            <button class="btn-restore" onclick="doRestore()">Restore</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Host Setup Panel -->
    <div class="panel panel-wide">
      <h2>Host Setup</h2>
      <p class="meta">One-time setup tasks for configuring the host (uses fstab.example as source)</p>
      <div class="actions">
        <button class="btn-secondary" onclick="setupFstab()" id="btn-fstab">Setup NFS mounts</button>
        <button class="btn-secondary" onclick="setupDockerWait()" id="btn-docker-wait">Setup Docker wait</button>
      </div>
    </div>

    <!-- Activity Log -->
    <div class="panel panel-wide">
      <h2>Activity Log</h2>
      <pre id="log">Loading...</pre>
      <div class="actions">
        <button class="btn-secondary" onclick="clearLog()" id="btn-clear">Clear log</button>
      </div>
    </div>

  </div>

<script>
// === UPS Panel ===
var upsStatusEl = document.getElementById('ups-status');
var upsLoadEl = document.getElementById('ups-load');
var upsBatteryEl = document.getElementById('ups-battery');
var upsRuntimeEl = document.getElementById('ups-runtime');
var upsVoltageEl = document.getElementById('ups-voltage');
var upsRawEl = document.getElementById('ups-raw');

function stripUnit(val) {
  if (!val) return '—';
  return val.replace(/ (Percent|Volts|Minutes|Seconds|Hz|Watts|VA)$/i, '').trim();
}

function pollUps() {
  fetch('/api/ups').then(function(r) { return r.json(); }).then(function(d) {
    if (!d.ok) {
      upsStatusEl.textContent = 'Offline';
      upsStatusEl.className = 'status offline';
      upsLoadEl.textContent = '—';
      upsBatteryEl.textContent = '—';
      upsRuntimeEl.textContent = '—';
      upsVoltageEl.textContent = '—';
      return;
    }
    var data = d.data;
    var st = data.STATUS || 'UNKNOWN';
    upsStatusEl.textContent = st;
    if (st.indexOf('ONLINE') !== -1) upsStatusEl.className = 'status idle';
    else if (st.indexOf('ONBATT') !== -1) upsStatusEl.className = 'status danger';
    else upsStatusEl.className = 'status active';

    upsLoadEl.textContent = stripUnit(data.LOADPCT) + '%';
    upsBatteryEl.textContent = stripUnit(data.BCHARGE) + '%';
    upsRuntimeEl.textContent = stripUnit(data.TIMELEFT) + ' min';
    upsVoltageEl.textContent = stripUnit(data.LINEV) + ' V';

    upsRawEl.innerHTML = '';
    for (var key in data) {
      var tr = document.createElement('tr');
      var td1 = document.createElement('td');
      var td2 = document.createElement('td');
      td1.textContent = key;
      td2.textContent = data[key];
      tr.appendChild(td1);
      tr.appendChild(td2);
      upsRawEl.appendChild(tr);
    }
  }).catch(function() {
    upsStatusEl.textContent = 'Offline';
    upsStatusEl.className = 'status offline';
  });
}
setInterval(pollUps, 30000);
pollUps();

// === Actions & Activity Log ===
var logEl = document.getElementById('log');
var backupStatusEl = document.getElementById('backup-status');
var lastBackupEl = document.getElementById('last-backup');
var dryEl = document.getElementById('dry-run');
var btns = ['btn-backup', 'btn-restore', 'btn-fstab', 'btn-docker-wait'];
var isRunning = false;
var activeBtn = null;
var activeBtnText = '';

function setDisabled(disabled) {
  btns.forEach(function(id) { document.getElementById(id).disabled = disabled; });
  dryEl.disabled = disabled;
}

function setLoading(btnId) {
  activeBtn = btnId;
  var el = document.getElementById(btnId);
  activeBtnText = el.textContent;
  var span = document.createElement('span');
  span.className = 'spinner';
  el.appendChild(span);
}

function clearLoading() {
  if (!activeBtn) return;
  var el = document.getElementById(activeBtn);
  el.textContent = activeBtnText;
  activeBtn = null;
  activeBtnText = '';
}

function runAction(url, btnId) {
  if (dryEl.checked) url += (url.indexOf('?') === -1 ? '?' : '&') + 'dry=1';
  setDisabled(true);
  setLoading(btnId);
  isRunning = true;
  fetch(url, {method: 'POST'});
}

function showRestore() {
  if (dryEl.checked) { runAction('/backup/restore', 'btn-restore'); return; }
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
  runAction('/backup/restore', 'btn-restore');
}

function setupFstab() {
  setDisabled(true);
  setLoading('btn-fstab');
  isRunning = true;
  fetch('/backup/setup-fstab', {method: 'POST'});
}

function setupDockerWait() {
  setDisabled(true);
  setLoading('btn-docker-wait');
  isRunning = true;
  fetch('/backup/setup-docker-wait', {method: 'POST'});
}

function clearLog() {
  fetch('/backup/clear-log', {method: 'POST'}).then(function() { poll(); });
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
  return fetch('/api/backup').then(function(r) { return r.json(); }).then(function(d) {
    isRunning = d.running;
    var bCls = 'idle', bTxt = 'Idle';
    if (d.running) {
      var isRestore = d.action.indexOf('restore') !== -1;
      var isDry = d.action.indexOf('dry') !== -1;
      if (isRestore) { bCls = 'danger'; bTxt = isDry ? 'Restore dry-run...' : 'Restoring...'; }
      else if (d.action.indexOf('backup') !== -1 || d.action === '') { bCls = 'active'; bTxt = isDry ? 'Backup dry-run...' : 'Backing up...'; }
    }
    backupStatusEl.textContent = bTxt;
    backupStatusEl.className = 'status ' + bCls;
    setDisabled(d.running);
    if (!d.running) clearLoading();
    var atBottom = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight < 50;
    logEl.textContent = d.log || 'No activity yet.';
    if (atBottom) logEl.scrollTop = logEl.scrollHeight;
    lastBackupEl.textContent = d.last_backup ? 'Last backup: ' + timeAgo(d.last_backup) : '';
  }).catch(function() {});
}

(function schedule() {
  setTimeout(function() { poll().then(schedule); }, isRunning ? 2000 : 15000);
})();
poll();
</script>
</body>
</html>"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
