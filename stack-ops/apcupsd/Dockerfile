FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends apcupsd dbus && \
    rm -rf /var/lib/apt/lists/*

COPY doshutdown /etc/apcupsd/doshutdown
RUN chmod +x /etc/apcupsd/doshutdown

EXPOSE 3551

CMD ["/sbin/apcupsd", "-b"]
