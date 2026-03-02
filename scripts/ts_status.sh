#!/bin/bash

# Script for Synology NAS which notifies of available Tailscale updates
# This is because Synology's package center is far behind Tailscale's website

# By default the mail is sent to eventmail1 in /usr/syno/etc/synosmtp.conf
# You can pass an argument as follows to pick another destination:
# ./ts_status.sh eventmail2
# ./ts_status.sh somebody@somewhere.com
mailtovar=${1:-eventmail1}

send_mail() {
    #printf "\nSending email notification\n"
    cfgfile="/usr/syno/etc/synosmtp.conf"
    thehost=$(hostname)
    sender_name=$(grep 'smtp_from_name' $cfgfile | sed -n 's/.*"\([^"]*\)".*/\1/p')
    sender_mail=$(grep 'smtp_from_mail' $cfgfile | sed -n 's/.*"\([^"]*\)".*/\1/p')
    sender_mail=${sender_mail:-$(grep 'eventmail1' $cfgfile | sed -n 's/.*"\([^"]*\)".*/\1/p')}
    mail_to=$(grep "$mailtovar" $cfgfile | sed -n 's/.*"\([^"]*\)".*/\1/p')
    [[ "$mailtovar" == *"@"* ]] && mail_to=${mail_to:-$mailtovar}
    sprefix=$(grep 'eventsubjectprefix' $cfgfile | sed -n 's/.*"\([^"]*\)".*/\1/p')
    dsmv=$(grep 'majorversion' /etc.defaults/VERSION | cut -d\" -f2)
    if [ "$mail_to" = "" ];then
        echo "No mail recipient configured, skipping notification"
        return
    fi
    echo "Sending update notification to $mail_to ($1 -> $2)"
    ssmtp "$mail_to" << __EOF
From: "$sender_name" <$sender_mail>
date:$(date -R)
To: <$mail_to>
Subject: $sprefix The Tailscale package on $thehost needs to be updated
Content-Type: text/plain; charset=UTF-8; format=flowed
Content-Transfer-Encoding: 7bit

The Tailscale package on $thehost needs to be updated:

Installed version: $1
Upstream version: $2

Download a DSM${dsmv} version from here:

https://pkgs.tailscale.com/stable/#spks

 From $sender_name
__EOF
}

ts_version=$(tailscale version --upstream --json)
current_v=$(echo "$ts_version" | grep 'short":' | cut -d\" -f4)
upstream_v=$(echo "$ts_version" | grep 'upstream":' | cut -d\" -f4)
#upstream_v=${current_v}b # hack to fake a pending update

if [ "$current_v" != "$upstream_v" ];then
    send_mail "$current_v" "$upstream_v"
else
    echo "Tailscale $current_v is up to date"
fi
exit 0
