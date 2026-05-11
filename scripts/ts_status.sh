#!/bin/bash

# Script for Synology NAS which notifies of available Tailscale updates
# This is because Synology's package center is far behind Tailscale's website

PATH=/usr/local/bin:/usr/bin:/bin:/usr/syno/bin:/var/packages/Tailscale/target/bin
export PATH

# By default the mail is sent to eventmail1 in /usr/syno/etc/synosmtp.conf
# You can pass an argument as follows to pick another destination:
# ./ts_status.sh eventmail2
# ./ts_status.sh somebody@somewhere.com
mailtovar=${1:-eventmail1}

send_mail() {
    local current="$1" upstream="$2"
    local cfgfile="/usr/syno/etc/synosmtp.conf"
    local thehost sender_name sender_mail mail_to sprefix dsmv
    thehost=$(hostname)
    sender_name=$(grep 'smtp_from_name' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    sender_mail=$(grep 'smtp_from_mail' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    sender_mail=${sender_mail:-$(grep 'eventmail1' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')}
    mail_to=$(grep "$mailtovar" "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    [[ "$mailtovar" == *"@"* ]] && mail_to=${mail_to:-$mailtovar}
    sprefix=$(grep 'eventsubjectprefix' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    dsmv=$(grep 'majorversion' /etc.defaults/VERSION | cut -d\" -f2)

    if [ -z "$mail_to" ]; then
        logger -t ts_status "no mail recipient in $cfgfile (key=$mailtovar); update notification skipped ($current -> $upstream)"
        return 1
    fi

    echo "Sending update notification to $mail_to ($current -> $upstream)"
    local mail_output
    mail_output=$(ssmtp "$mail_to" 2>&1 << __EOF
From: "$sender_name" <$sender_mail>
date:$(date -R)
To: <$mail_to>
Subject: $sprefix The Tailscale package on $thehost needs to be updated
Content-Type: text/plain; charset=UTF-8; format=flowed
Content-Transfer-Encoding: 7bit

The Tailscale package on $thehost needs to be updated:

Installed version: $current
Upstream version: $upstream

Download a DSM${dsmv} version from here:

https://pkgs.tailscale.com/stable/#spks

 From $sender_name
__EOF
)
    local rc=$?
    if [ "$rc" -ne 0 ]; then
        logger -t ts_status "ssmtp failed (rc=$rc): $mail_output"
        return 1
    fi
}

main() {
    local ts_version current_v upstream_v
    ts_version=$(tailscale version --upstream --json)
    current_v=$(echo "$ts_version" | grep 'short":' | cut -d\" -f4)
    upstream_v=$(echo "$ts_version" | grep 'upstream":' | cut -d\" -f4)
    #upstream_v=${current_v}b # hack to fake a pending update

    if [ "$current_v" != "$upstream_v" ]; then
        send_mail "$current_v" "$upstream_v"
    else
        echo "Tailscale $current_v is up to date"
    fi
    exit 0
}

# Only run main when executed directly, not when sourced (for testing send_mail)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
