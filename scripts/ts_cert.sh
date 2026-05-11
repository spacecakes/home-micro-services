#!/bin/bash

# Script for Synology NAS which renews the Tailscale HTTPS certificate
# Schedule monthly — certs are valid for 90 days

PATH=/usr/local/bin:/usr/bin:/bin:/usr/syno/bin:/var/packages/Tailscale/target/bin
export PATH

max_retries=3
retry_delay=60

# By default the mail is sent to eventmail1 in /usr/syno/etc/synosmtp.conf
# You can pass an argument as follows to pick another destination:
# ./ts_cert.sh eventmail2
# ./ts_cert.sh somebody@somewhere.com
mailtovar=${1:-eventmail1}

send_mail() {
    local body="$1"
    local cfgfile="/usr/syno/etc/synosmtp.conf"
    local thehost sender_name sender_mail mail_to sprefix
    thehost=$(hostname)
    sender_name=$(grep 'smtp_from_name' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    sender_mail=$(grep 'smtp_from_mail' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    sender_mail=${sender_mail:-$(grep 'eventmail1' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')}
    mail_to=$(grep "$mailtovar" "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    [[ "$mailtovar" == *"@"* ]] && mail_to=${mail_to:-$mailtovar}
    sprefix=$(grep 'eventsubjectprefix' "$cfgfile" | sed -n 's/.*"\([^"]*\)".*/\1/p')

    if [ -z "$mail_to" ]; then
        logger -t ts_cert "no mail recipient in $cfgfile (key=$mailtovar); notification skipped"
        return 1
    fi

    echo "Sending failure notification to $mail_to"
    local mail_output
    mail_output=$(ssmtp "$mail_to" 2>&1 << __EOF
From: "$sender_name" <$sender_mail>
date:$(date -R)
To: <$mail_to>
Subject: $sprefix Tailscale certificate renewal failed on $thehost
Content-Type: text/plain; charset=UTF-8; format=flowed
Content-Transfer-Encoding: 7bit

Tailscale certificate renewal failed on $thehost after $max_retries attempts.

Last error:
$body

Please renew manually by running:
  tailscale configure synology-cert

 From $sender_name
__EOF
)
    local rc=$?
    if [ "$rc" -ne 0 ]; then
        logger -t ts_cert "ssmtp failed (rc=$rc): $mail_output"
        return 1
    fi
}

main() {
    if [ "$EUID" -ne 0 ]; then
        echo "Please run as root"
        exit 1
    fi

    local last_error=""
    local output retval
    for ((i = 1; i <= max_retries; i++)); do
        echo "Certificate renewal attempt $i/$max_retries"
        output=$(tailscale configure synology-cert 2>&1)
        retval=$?
        if [ "$retval" = "0" ]; then
            echo "Certificate renewed successfully"
            [ -n "$output" ] && echo "$output"
            exit 0
        fi
        last_error="$output"
        echo "Attempt $i failed (exit code $retval)"
        [ -n "$output" ] && echo "$output"
        if [ "$i" -lt "$max_retries" ]; then
            echo "Retrying in ${retry_delay}s..."
            sleep "$retry_delay"
        fi
    done

    echo "All $max_retries attempts failed"
    logger -t ts_cert "renewal failed on $(hostname) after $max_retries attempts: $last_error"
    send_mail "$last_error"
    exit 1
}

# Only run main when executed directly, not when sourced (for testing send_mail)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
