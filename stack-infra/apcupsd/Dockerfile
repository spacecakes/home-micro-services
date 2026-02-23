FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends apcupsd dbus busybox && \
    rm -rf /var/lib/apt/lists/*

COPY doshutdown /etc/apcupsd/doshutdown
RUN chmod +x /etc/apcupsd/doshutdown

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN mkdir -p /var/www/cgi-bin
COPY status.cgi /var/www/cgi-bin/status.cgi
RUN chmod +x /var/www/cgi-bin/status.cgi

EXPOSE 3551 3552

ENTRYPOINT ["/entrypoint.sh"]
