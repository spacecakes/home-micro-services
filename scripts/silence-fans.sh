#!/bin/bash
# Synology RS1221+ fan silence script
# Only modifies DUAL_MODE_LOW (quiet mode), leaves cool mode untouched
# Run via Task Scheduler as root (triggered on boot)

SCEMD="/usr/syno/etc.defaults/scemd.xml"
BACKUP="/usr/syno/etc.defaults/scemd.xml.bak"

# Backup only if no backup exists yet
if [ ! -f "$BACKUP" ]; then
    cp "$SCEMD" "$BACKUP"
fi

# Replace only the first occurrence (DUAL_MODE_LOW block)
sed -i '0,/pwm_duty_high="255" pwm_duty_low="120"/s/pwm_duty_high="255" pwm_duty_low="120"/pwm_duty_high="80" pwm_duty_low="60"/' "$SCEMD"

synosystemctl restart scemd
