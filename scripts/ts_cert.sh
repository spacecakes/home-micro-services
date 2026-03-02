#!/bin/bash

# Script for Synology NAS which renews the Tailscale HTTPS certificate
# Schedule monthly — certs are valid for 90 days

max_retries=3
retry_delay=60

# By default the mail is sent to eventmail1 in /usr/syno/etc/synosmtp.conf
# You can pass an argument as follows to pick another destination:
# ./ts_cert.sh eventmail2
# ./ts_cert.sh somebody@somewhere.com
# ./ts_cert.sh nobody
mailtovar=${1:-eventmail1}

send_mail() {
    cfgfile="/usr/syno/etc/synosmtp.conf"
    thehost=$(hostname)
    sender_name=$(grep 'smtp_from_name' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    sender_mail=$(grep 'smtp_from_mail' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    sender_mail=${sender_mail:-$(grep 'eventmail1' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')}
    mail_to=$(grep "$mailtovar" "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    [[ "$mailtovar" == *"@"* ]] && mail_to=${mail_to:-$mailtovar}
    sprefix=$(grep 'eventsubjectprefix' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    if [ "$mail_to" = "" ];then
        echo "No mail recipient configured, skipping notification"
        return
    fi
    echo "Sending failure notification to $mail_to"
    ssmtp "$mail_to" << __EOF
From: "$sender_name" <$sender_mail>
date:$(date -R)
To: <$mail_to>
Subject: $sprefix Tailscale certificate renewal failed on $thehost
Content-Type: text/plain; charset=UTF-8; format=flowed
Content-Transfer-Encoding: 7bit

Tailscale certificate renewal failed on $thehost after $max_retries attempts.

Last error:
$1

Please renew manually by running:
  tailscale configure synology-cert

 From $sender_name
__EOF
}

if [ "$EUID" -ne 0 ];then
    echo "Please run as root"
    exit
fi

last_error=""
for ((i = 1; i <= max_retries; i++)); do
    echo "Certificate renewal attempt $i/$max_retries"
    output=$(tailscale configure synology-cert 2>&1)
    retval=$?
    if [ "$retval" = "0" ];then
        echo "Certificate renewed successfully"
        [ -n "$output" ] && echo "$output"
        exit 0
    fi
    last_error="$output"
    echo "Attempt $i failed (exit code $retval)"
    [ -n "$output" ] && echo "$output"
    if [ "$i" -lt "$max_retries" ];then
        echo "Retrying in ${retry_delay}s..."
        sleep "$retry_delay"
    fi
done

echo "All $max_retries attempts failed"
send_mail "$last_error"
exit 1
