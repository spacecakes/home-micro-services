# Home Micro Services

My Docker and reverse proxy setup for micro-services at home, shared publicly so I can discuss it with friends and get told what I'm doing wrong.

## Stacks

| Stack          | Description                                                               |
| -------------- | ------------------------------------------------------------------------- |
| `stack-infra`  | Traefik reverse proxy, Homepage dashboard, Portainer, AdGuard Home        |
| `stack-auth`   | Authelia SSO with Redis session backend                                   |
| `stack-arr`    | Sonarr, Radarr, Prowlarr, qBittorrent                                     |
| `stack-plex`   | Plex Media Server                                                         |
| `stack-home`   | Home automation                                                           |
| `stack-immich` | Immich photo management                                                   |
| `stack-nas`    | NAS services: Portainer agent, AdGuard, iCloudPD                          |
| `stack-ops`    | apcupsd, ops-toolbox, ops-worker (hourly rsync backup to NAS), Watchtower |

## Setup

See [SETUP.md](SETUP.md) for the full bare-metal setup guide.

## Custom Images

Some services use locally built Docker images. When both `image:` and `build:` are specified in the compose file, `docker compose up -d` uses the cached image. Only pass `--build` when the source code changes.

| Image                | Build context            | Stack       |
| -------------------- | ------------------------ | ----------- |
| `apcupsd:latest`     | `stack-ops/apcupsd/`     | `stack-ops` |
| `ops-toolbox:latest` | `stack-ops/ops-toolbox/` | `stack-ops` |

### apcupsd

Monitors an APC UPS (with NMC) over SNMP. Exposes a NIS server on port 3551 for status queries (`apcaccess -h localhost:3551`). On critical battery, triggers host shutdown via D-Bus (works on any systemd host including Proxmox).

### ops-toolbox

Rarely-used ops toolbox web UI. Queries the apcupsd NIS server directly via TCP and proxies backup/restore actions to `ops-worker`. Accessible at `ops.lundmark.tech` behind Authelia.

## Backup

The `stack-ops` backup container rsyncs `/srv/docker/` to the NAS hourly. The NAS then snapshots and backs it up off-site.
