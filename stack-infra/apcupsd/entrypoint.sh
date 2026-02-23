#!/bin/sh

# Start web UI in background (busybox httpd with CGI)
busybox httpd -p 3552 -h /var/www

# Start apcupsd in foreground (main process)
exec /sbin/apcupsd -b
