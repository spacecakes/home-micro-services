FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends apcupsd dbus && \
    rm -rf /var/lib/apt/lists/*

COPY apcupsd.conf /etc/apcupsd/apcupsd.conf
COPY doshutdown /etc/apcupsd/doshutdown
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /etc/apcupsd/doshutdown /entrypoint.sh

EXPOSE 3551

ENTRYPOINT ["/entrypoint.sh"]
