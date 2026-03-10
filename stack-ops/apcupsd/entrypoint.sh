#!/bin/sh
# Replace DEVICE IP in config if UPS_DEVICE env var is set
if [ -n "$UPS_DEVICE" ]; then
  sed -i "s/^DEVICE .*/DEVICE $UPS_DEVICE/" /etc/apcupsd/apcupsd.conf
fi
exec /sbin/apcupsd -b
