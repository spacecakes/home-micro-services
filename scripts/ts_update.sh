#!/bin/bash

# Script for Synology NAS which updates Tailscale and notifies by email
# This is because Synology's package center is far behind Tailscale's own release.
# Also fixes issue with outbound connections breaking after update.

PATH=/usr/local/bin:/usr/bin:/bin:/usr/syno/bin:/var/packages/Tailscale/target/bin
export PATH

days_to_wait=1

# By default the mail is sent to eventmail1 in /usr/syno/etc/synosmtp.conf
# You can pass an argument as follows to pick another destination:
# ./ts_update.sh eventmail2
# ./ts_update.sh somebody@somewhere.com
# ./ts_update.sh nobody
mailtovar=${1:-eventmail1}

fix_issue_12203=1 # Set to 0 to skip fixing https://github.com/tailscale/tailscale/issues/12203
run_type="--yes"

# Uncomment line below for an update dry-run
#run_type="--dry-run"

((minutes_to_wait = days_to_wait * 24 * 60 - 1))
scriptdir=$(dirname "$0")
new_version_file=${scriptdir}/.tailscale_new_version

fix_daemon_capabilities() {
    [ "$fix_issue_12203" = "0" ] && return
    prepost=$1
    if [ "$prepost" = "pre" ];then
        pre_capabilities=$(getcap /var/packages/Tailscale/target/bin/tailscaled)
        echo "Pre-update capabilities: ${pre_capabilities:-none}"
    elif [ "$prepost" = "post" ];then
        if [ "$pre_capabilities" = "" ];then
            echo "No pre-update capabilities to check"
            return
        fi
        post_capabilities=$(getcap /var/packages/Tailscale/target/bin/tailscaled)
        if [ "$pre_capabilities" = "$post_capabilities" ];then
            echo "Capabilities intact after update"
            return
        fi
        echo "Capabilities lost after update! Restoring..."
        echo "  Before: $pre_capabilities"
        echo "  After:  ${post_capabilities:-none}"
        /var/packages/Tailscale/target/bin/tailscale configure-host; synosystemctl restart pkgctl-Tailscale.service
        echo "Capabilities restored via configure-host"
    fi
}

send_mail() {
    local prev="$1" new="$2"
    local cfgfile="/usr/syno/etc/synosmtp.conf"
    local thehost sender_name sender_mail mail_to sprefix dsmv dryrunmsg maninstmsg
    thehost=$(hostname)
    sender_name=$(grep 'smtp_from_name' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    sender_mail=$(grep 'smtp_from_mail' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    sender_mail=${sender_mail:-$(grep 'eventmail1' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')}
    mail_to=$(grep "$mailtovar" "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    [[ "$mailtovar" == *"@"* ]] && mail_to=${mail_to:-$mailtovar}
    sprefix=$(grep 'eventsubjectprefix' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    dsmv=$(grep 'majorversion' /etc.defaults/VERSION | cut -d\" -f2)
    [ "$run_type" == "--dry-run" ] && dryrunmsg="*** WARNING *** : This is only a dry run"$'\n\n'
    [ "$dryrunmsg" != "" ] && maninstmsg=$'\n'"Download a DSM${dsmv} version from here if you want to manually install:"$'\n\n'"https://pkgs.tailscale.com/stable/#spks"$'\n'

    if [ -z "$mail_to" ]; then
        logger -t ts_update "no mail recipient in $cfgfile (key=$mailtovar); update notification skipped ($prev -> $new)"
        return 1
    fi

    echo "Sending notification to $mail_to"
    local mail_output
    mail_output=$(ssmtp "$mail_to" 2>&1 << __EOF
From: "$sender_name" <$sender_mail>
date:$(date -R)
To: <$mail_to>
Subject: $sprefix The Tailscale package on $thehost was automatically updated
Content-Type: text/plain; charset=UTF-8; format=flowed
Content-Transfer-Encoding: 7bit

${dryrunmsg}After a waiting period of $days_to_wait days, the Tailscale package on $thehost was updated.

Previous version: $prev
New version: $new
$maninstmsg
 From $sender_name
__EOF
)
    local rc=$?
    if [ "$rc" -ne 0 ]; then
        logger -t ts_update "ssmtp failed (rc=$rc): $mail_output"
        return 1
    fi
}

send_mail_and_upgrade() {
    # Check the new version file or generate it if missing/outdated
    performed_update=false
    if [ -s "$new_version_file" ];then
        v_from_file=$(cat "$new_version_file")
        if [ "$v_from_file" != "$2" ];then
            echo "Upstream version changed from $v_from_file to $2 while waiting, resetting timer"
            echo "$2" > "$new_version_file"
        fi
    else
        echo "New upstream version $2 detected (installed: $1), starting ${days_to_wait}-day wait"
        echo "$2" > "$new_version_file"
    fi

    # Install Tailscale upgrade if waiting period has elapsed
    if [ "$(find "$new_version_file" -mmin +${minutes_to_wait})" ];then
        echo "Wait period elapsed, updating Tailscale $1 -> $2"
        fix_daemon_capabilities "pre"
        tailscale update $run_type
        retval=$?
        if [ "$retval" = "0" ];then
            echo "Update succeeded"
            rm -f "$new_version_file"
            performed_update=true
        else
            echo "Update failed (exit code $retval)"
            logger -t ts_update "tailscale update failed on $(hostname) (rc=$retval, $1 -> $2)"
        fi
    else
        echo "Still waiting (need ${days_to_wait} days before updating $1 -> $2)"
    fi
    [ "$performed_update" != "true" ] && return
    fix_daemon_capabilities "post"
    send_mail "$1" "$2"
}

main() {
    if [ "$EUID" -ne 0 ]; then
        echo "Please run as root"
        exit 1
    fi

    local ts_version current_v upstream_v
    ts_version=$(tailscale version --upstream --json)
    current_v=$(echo "$ts_version" | grep 'short":' | cut -d\" -f4)
    upstream_v=$(echo "$ts_version" | grep 'upstream":' | cut -d\" -f4)
    #upstream_v=${current_v}b # hack to fake a pending update

    if [ "$current_v" != "$upstream_v" ]; then
        send_mail_and_upgrade "$current_v" "$upstream_v"
    else
        echo "Tailscale $current_v is up to date"
    fi
    exit 0
}

# Only run main when executed directly, not when sourced (for testing send_mail)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
