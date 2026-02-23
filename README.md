# Home Micro Services

My Docker and reverse proxy setup for micro-services at home, shared publicly so I can discuss it with friends and get told what I'm doing wrong.

## Stacks

| Stack               | Description                                          |
| ------------------- | ---------------------------------------------------- |
| `stack-infra`       | Traefik reverse proxy, Homepage dashboard, Portainer |
| `stack-auth`        | Authelia SSO with Redis session backend              |
| `stack-arr`         | Sonarr, Radarr, Prowlarr, qBittorrent                |
| `stack-plex`        | Plex Media Server                                    |
| `stack-dns`         | AdGuard Home                                         |
| `stack-home`        | Home automation                                      |
| `stack-immich`      | Immich photo management                              |
| `stack-photobackup` | Photo backup                                         |
| `stack-nas`         | NAS-related services                                 |
| `stack-ops`         | Watchtower auto-updates, hourly rsync backup to NAS  |

## Setup

See [SETUP.md](SETUP.md) for the full bare-metal setup guide.

## Backup

The `stack-ops` backup container rsyncs `/srv/docker/` to the NAS hourly. The NAS then snapshots and backs it up off-site.
