FROM debian:bookworm-slim

RUN apt-get update &&     apt-get install -y --no-install-recommends apcupsd iputils-ping &&     rm -rf /var/lib/apt/lists/*

COPY apcupsd.conf /etc/apcupsd/apcupsd.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3551

ENTRYPOINT ["/entrypoint.sh"]
