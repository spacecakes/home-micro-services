# Scripts

## Tailscale on Synology (`ts.sh`)

`ts.sh` keeps the Tailscale package on a Synology NAS running, updated and
with a valid HTTPS certificate. One subcommand per Task Scheduler task:

| Subcommand | What it does |
| --- | --- |
| `watchdog` | Restarts the package when tailscaled is down or stuck. Runs `configure-host` and restarts when tailscaled runs without a TUN device. |
| `update` | Installs the upstream Tailscale release one day after it appears. Mails when it has updated. |
| `cert` | Renews the Tailscale HTTPS certificate and installs it in DSM. Mails when all attempts fail. |

Why the watchdog exists: the DSM package unit has no restart policy, so a
crashed tailscaled stays down. DSM also starts the package at boot before
`/dev/net/tun` exists, and udev resets that device to root-only when the tun
module loads. Both leave tailscaled in userspace mode: inbound connections
work, but the NAS cannot reach the tailnet itself (Hyper Backup, Drive).

`cert` is safe to run monthly. Tailscale returns the cached certificate until
two thirds of its 90-day lifetime have passed, so a real renewal happens once
per quarter.

### Prerequisites

1. Install the **Git** package from Package Center.
2. Clone this repository to `/volume1/docker` as root:

   ```sh
   sudo git clone https://github.com/spacecakes/home-micro-services.git /volume1/docker
   ```

   Use the same path on every NAS so the task definitions are identical.
   After a change to `ts.sh`, run `git pull` in that directory on each NAS.
3. Set up email in **Control Panel > Notification > Email**. `ts.sh` sends
   mail to the recipients configured there. Without it, mail is skipped and a
   line is written to Log Center instead.

### Tasks

Create these in **Control Panel > Task Scheduler**. All run as user `root`.

| Task name | Create > | Schedule | User-defined script |
| --- | --- | --- | --- |
| Tailscale watchdog (boot) | Triggered Task > User-defined script | Event: **Boot-up** | `/volume1/docker/scripts/ts.sh watchdog` |
| Tailscale watchdog | Scheduled Task > User-defined script | Daily, repeat **every 5 minutes** | `/volume1/docker/scripts/ts.sh watchdog` |
| Tailscale update | Scheduled Task > User-defined script | Daily at 00:00 | `/volume1/docker/scripts/ts.sh update` |
| Tailscale cert | Scheduled Task > User-defined script | Monthly | `/volume1/docker/scripts/ts.sh cert` |

Steps for each task:

1. **General**: enter the task name, set **User** to `root`, keep **Enabled**
   checked.
2. **Schedule**: set the trigger from the table. For the 5-minute watchdog,
   choose *Run on the following days: Daily* and *Frequency: Every 5 minutes*.
3. **Task Settings**: paste the command into **User-defined script**. Leave
   **Send run details by email** off; `ts.sh` mails on its own.

Keep **Task Scheduler > Settings > Save output results** on. On DSM 7.3 it
stores the output of triggered tasks only, so the boot-up watchdog leaves one
folder per boot under the output share and the 5-minute task leaves none.

The boot-up task replaces any older "configure host" boot task. Delete that
one.

### Checking

- **Log Center > Logs > System**, filter on `ts`, lists every restart,
  skipped mail and failed renewal.
- **Task Scheduler > View Result** on the boot-up task shows what the watchdog
  did at the last boot.
- `tailscale status --json | grep -E '"(BackendState|TUN)"'` as root must show
  `Running` and `true`.

### Manual run

```sh
sudo /volume1/docker/scripts/ts.sh watchdog
```

Set `update_args="--dry-run"` at the top of `ts.sh` to test `update` without
installing anything.
