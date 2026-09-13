#!/bin/bash

# Tailscale maintenance for Synology NAS. One command per Task Scheduler task,
# all run as root:
#   ts.sh watchdog   on boot-up and every 5 minutes: keep tailscaled running with a TUN device
#   ts.sh update     daily: install the upstream Tailscale release after a one-day wait
#   ts.sh cert       monthly: renew the Tailscale HTTPS certificate
# Mail goes to the recipients configured in DSM (Control Panel > Notification > Email).

PATH=/usr/local/bin:/usr/bin:/bin:/usr/syno/bin:/var/packages/Tailscale/target/bin
export PATH

days_to_wait=1                  # update: delay between an upstream release and installing it
update_args="--yes"             # update: set to "--dry-run" to test without installing
package_wait=180                # watchdog: seconds to wait for DSM to start the package (boot-up)
backend_wait=60                 # watchdog: seconds to wait for a Starting backend to reach Running
restart_cooldown=600            # watchdog: seconds between two restarts
cert_retries=3
cert_retry_delay=60

new_version_file=/root/.tailscale_new_version
restart_stamp=/tmp/ts_watchdog.last_restart

main() {
    if [ "$EUID" -ne 0 ]; then
        echo "Please run as root"
        exit 1
    fi
    case "$1" in
    watchdog | update | cert) "$1" ;;
    *)
        echo "Usage: $0 watchdog|update|cert"
        exit 1
        ;;
    esac
}

# Restarts the package when tailscaled is down or stuck, and reruns
# configure-host when it runs without a TUN device. Without a TUN device
# inbound connections still work, but the NAS cannot open outbound
# connections to the tailnet (Hyper Backup, Drive, ...).
# The DSM package unit has no restart policy, so a crashed tailscaled stays
# down. DSM udev also resets /dev/net/tun to root-only when the tun module
# loads, so a restart without configure-host falls back to userspace mode.
watchdog() {
    if ! wait_for "$package_wait" package_active; then
        repair "package not active after ${package_wait}s"
        return
    fi

    if ! wait_for "$backend_wait" backend_running; then
        local state
        state=$(backend_state)
        case "$state" in
        NeedsLogin | NeedsMachineAuth | Stopped)
            echo "Tailscale backend is $state; a restart cannot fix this, log in with 'tailscale up'"
            logger -t ts "watchdog: backend $state, needs manual login"
            exit 1
            ;;
        *)
            repair "backend state '${state:-none}' after ${backend_wait}s"
            return
            ;;
        esac
    fi

    if ! tun_enabled; then
        repair "running without TUN device"
        return
    fi

    echo "Tailscale is running with a TUN device"
}

# Synology's package center is far behind Tailscale's own releases. An update
# restarts the package without a TUN device; the watchdog repairs that on its
# next run.
update() {
    local ts_version current upstream
    ts_version=$(tailscale version --upstream --json)
    current=$(echo "$ts_version" | grep 'short":' | cut -d\" -f4)
    upstream=$(echo "$ts_version" | grep 'upstream":' | cut -d\" -f4)

    if [ "$current" = "$upstream" ]; then
        echo "Tailscale $current is up to date"
        return
    fi

    if [ -s "$new_version_file" ]; then
        local waiting_for
        waiting_for=$(cat "$new_version_file")
        if [ "$waiting_for" != "$upstream" ]; then
            echo "Upstream version changed from $waiting_for to $upstream while waiting, resetting timer"
            echo "$upstream" > "$new_version_file"
        fi
    else
        echo "New upstream version $upstream detected (installed: $current), starting ${days_to_wait}-day wait"
        echo "$upstream" > "$new_version_file"
    fi

    if [ -z "$(find "$new_version_file" -mmin +$((days_to_wait * 24 * 60 - 1)))" ]; then
        echo "Still waiting (need ${days_to_wait} days before updating $current -> $upstream)"
        return
    fi

    echo "Wait period elapsed, updating Tailscale $current -> $upstream"
    if ! tailscale update $update_args; then
        echo "Update failed"
        logger -t ts "update: tailscale update failed ($current -> $upstream)"
        exit 1
    fi
    echo "Update succeeded"
    rm -f "$new_version_file"

    local subject="The Tailscale package on $(hostname) was automatically updated"
    [ "$update_args" = "--dry-run" ] && subject="[dry run] $subject"
    send_mail "$subject" \
"After a waiting period of $days_to_wait days, the Tailscale package on $(hostname) was updated.

Previous version: $current
New version: $upstream"
}

# Certificates are valid for 90 days.
cert() {
    local output i
    for ((i = 1; i <= cert_retries; i++)); do
        echo "Certificate renewal attempt $i/$cert_retries"
        if output=$(tailscale configure synology-cert 2>&1); then
            echo "Certificate renewed successfully"
            [ -n "$output" ] && echo "$output"
            return
        fi
        echo "Attempt $i failed"
        [ -n "$output" ] && echo "$output"
        if [ "$i" -lt "$cert_retries" ]; then
            echo "Retrying in ${cert_retry_delay}s..."
            sleep "$cert_retry_delay"
        fi
    done

    echo "All $cert_retries attempts failed"
    logger -t ts "cert: renewal failed after $cert_retries attempts: $output"
    send_mail "Tailscale certificate renewal failed on $(hostname)" \
"Tailscale certificate renewal failed on $(hostname) after $cert_retries attempts.

Last error:
$output

Please renew manually by running:
  tailscale configure synology-cert"
    exit 1
}

# --- watchdog helpers ---

package_active() {
    [ "$(synosystemctl get-active-status pkgctl-Tailscale.service 2>/dev/null)" = "active" ]
}

backend_state() {
    tailscale status --json 2>/dev/null | grep '"BackendState"' | cut -d\" -f4
}

backend_running() {
    [ "$(backend_state)" = "Running" ]
}

tun_enabled() {
    tailscale status --json 2>/dev/null | grep -q '"TUN": true'
}

wait_for() {
    local seconds=$1 check=$2
    local waited=0
    until $check; do
        [ "$waited" -ge "$seconds" ] && return 1
        sleep 5
        ((waited += 5))
    done
}

repair() {
    local reason=$1
    if [ -f "$restart_stamp" ] && [ -z "$(find "$restart_stamp" -mmin +$((restart_cooldown / 60)))" ]; then
        echo "Tailscale unhealthy ($reason) but restarted less than ${restart_cooldown}s ago, leaving it alone"
        logger -t ts "watchdog: unhealthy ($reason), restart skipped: cooldown"
        return 1
    fi
    echo "Tailscale unhealthy ($reason), running configure-host and restarting the package"
    logger -t ts "watchdog: unhealthy ($reason), running configure-host and restarting"
    tailscale configure-host
    synosystemctl restart pkgctl-Tailscale.service
    touch "$restart_stamp"
}

# --- mail ---

# Sends through DSM's mail setup: ssmtp reads the server from the DSM config,
# the recipients come from the eventmails key of synosmtp.conf.
send_mail() {
    local subject="$1" body="$2"
    local recipients sender_name sender_mail prefix
    recipients=$(smtp_value eventmails | tr ';,' '  ')
    sender_name=$(smtp_value smtp_from_name)
    sender_mail=$(smtp_value smtp_from_mail)
    prefix=$(smtp_value eventsubjectprefix)

    if [ -z "$recipients" ]; then
        logger -t ts "no notification recipients configured in DSM; mail skipped: $subject"
        return 1
    fi

    echo "Sending mail to $recipients: $subject"
    local output rc
    output=$(ssmtp $recipients 2>&1 << __EOF
From: "$sender_name" <$sender_mail>
date:$(date -R)
To: <${recipients// />, <}>
Subject: $prefix $subject
Content-Type: text/plain; charset=UTF-8; format=flowed
Content-Transfer-Encoding: 7bit

$body
__EOF
)
    rc=$?
    if [ "$rc" -ne 0 ]; then
        logger -t ts "ssmtp failed (rc=$rc): $output"
        return 1
    fi
}

smtp_value() {
    sed -n "s/^$1=\"\([^\"]*\)\".*/\1/p" /usr/syno/etc/synosmtp.conf
}

main "$@"
