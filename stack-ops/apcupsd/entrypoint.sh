#!/bin/sh
# Replace DEVICE IP in config if UPS_DEVICE env var is set
if [ -n "$UPS_DEVICE" ]; then
  sed -i "s/^DEVICE .*/DEVICE $UPS_DEVICE/" /etc/apcupsd/apcupsd.conf
fi

# Wait for UPS to be reachable before starting
while ! ping -c1 -W2 "$UPS_DEVICE" >/dev/null 2>&1; do
  echo "Waiting for UPS at $UPS_DEVICE to become reachable..."
  sleep 30
done

echo "UPS at $UPS_DEVICE is reachable, starting apcupsd"
exec /sbin/apcupsd -b
