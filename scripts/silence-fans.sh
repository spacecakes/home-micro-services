#!/bin/bash
# Quieter fan curve for a Synology RS1221+, applied to Quiet mode only.
#
# Rewrites the DUAL_MODE_LOW block ("Quiet mode" in DSM) of scemd.xml with the
# values below. Cool mode (DUAL_MODE_HIGH) is never touched, so switching to
# Cool mode in DSM still gives Synology's stock curve.
#
# Sets absolute values on every run, so running it again changes nothing.
# Run as root via Task Scheduler, triggered at boot-up: DSM updates restore the
# stock file.
#
#   sudo ./silence-fans.sh             apply and restart scemd if anything changed
#   DRY_RUN=1 ./silence-fans.sh        show the diff only (no root needed)
#
# Keep the top step of each sensor at 255, so the fans can still reach full
# speed before DSM's alert/shutdown temperatures (cpu 90/95, disk 58/61,
# m2 68/71). The old version capped pwm_duty_high at 80, which held the fans at
# ~1900 RPM no matter how hot it got.

set -euo pipefail
PATH=/usr/local/bin:/usr/bin:/bin:/usr/syno/bin:/usr/syno/sbin
export PATH

# PWM duty is 0-255. On the RS1221+, 80 is ~1900 RPM and 150 is ~3350 RPM.
# DUTY_LOW is the floor the controller allows, so it must be <= the lowest step.
DUTY_LOW=80
DUTY_HIGH=255

# "temp:speed" steps, lowest first. The number of steps per sensor must match
# the stock file: cpu 4, disk 4, m2 4, nic 3.
# Stock Quiet mode: duty 120-255
#   cpu  0:120 60:150 70:220 85:255
#   disk 0:120 45:150 50:220 54:255
#   m2   0:120 55:150 60:220 64:255
#   nic  0:120 75:150 90:255
CPU="0:80 65:110 75:170 85:255"
DISK="0:80 45:120 50:200 54:255"
M2="0:80 55:120 60:200 64:255"
NIC="0:80 75:150 90:255"

SCEMD=/usr/syno/etc.defaults/scemd.xml
BACKUP=$SCEMD.bak

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT

if ! awk -v duty_low="$DUTY_LOW" -v duty_high="$DUTY_HIGH" \
    -v cpu="$CPU" -v disk="$DISK" -v m2="$M2" -v nic="$NIC" '
function load(name, spec,    parts, n, i, s, prev) {
    n = split(spec, parts, " ")
    cnt[name] = n
    prev = -1
    for (i = 1; i <= n; i++) {
        if (split(parts[i], s, ":") != 2 || s[1] !~ /^[0-9]+$/ || s[2] !~ /^[0-9]+$/ ||
            s[1] + 0 <= prev || s[2] + 0 > 255 || s[2] + 0 < duty_low + 0) {
            print "invalid step for " name ": " parts[i] > "/dev/stderr"; bad = 1
        }
        prev = s[1] + 0
        temp[name, i] = s[1]; speed[name, i] = s[2]
    }
    if (name != "nic_temperature" && speed[name, n] != 255) {
        print "top step for " name " must be 255" > "/dev/stderr"; bad = 1
    }
}
BEGIN {
    load("cpu_temperature", cpu); load("disk_temperature", disk)
    load("m2_temperature", m2); load("nic_temperature", nic)
    if (duty_high != 255) { print "DUTY_HIGH must be 255" > "/dev/stderr"; bad = 1 }
    if (bad) exit 2
}
/<adt_fan_config / {
    inblk = ($0 ~ /type="DUAL_MODE_LOW"/)
    if (inblk) { found = 1; split("", seen) }
}
inblk && /<pwm_config / {
    sub(/pwm_duty_high="[0-9]+"/, "pwm_duty_high=\"" duty_high "\"")
    sub(/pwm_duty_low="[0-9]+"/, "pwm_duty_low=\"" duty_low "\"")
}
inblk && /<manual_config / && match($0, /name="[a-z0-9_]+"/) {
    name = substr($0, RSTART + 6, RLENGTH - 7)
    if (name in cnt) {
        i = ++seen[name]
        if (i > cnt[name]) { mismatch = 1 }
        else {
            sub(/temp="[0-9]+"/, "temp=\"" temp[name, i] "\"")
            sub(/fan_speed="[0-9]+"/, "fan_speed=\"" speed[name, i] "\"")
        }
    }
}
inblk && /<\/adt_fan_config>/ {
    for (k in cnt) if (seen[k] != cnt[k]) {
        print k ": file has " seen[k] + 0 " steps, script has " cnt[k] > "/dev/stderr"; mismatch = 1
    }
    inblk = 0
}
{ print }
END {
    if (bad) exit 2
    if (!found) { print "DUAL_MODE_LOW block not found" > "/dev/stderr"; exit 3 }
    if (mismatch) exit 4
}' "$SCEMD" > "$tmp"; then
    echo "Not applied: $SCEMD left unchanged." >&2
    exit 1
fi

if [ "${DRY_RUN:-0}" = 1 ]; then
    diff "$SCEMD" "$tmp" || true
    exit 0
fi

if cmp -s "$SCEMD" "$tmp"; then
    echo "Fan curve already applied."
    exit 0
fi

[ -f "$BACKUP" ] || cp -p "$SCEMD" "$BACKUP"
cat "$tmp" > "$SCEMD"
synosystemctl restart scemd
echo "Fan curve applied, scemd restarted."
