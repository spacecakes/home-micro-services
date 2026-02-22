# Home Micro Services

My Docker and reverse proxy setup for micro-services at home, shared publicly so I can discuss it with friends and get told what I'm doing wrong.

## Stacks

| Stack               | Description                                          |
| ------------------- | ---------------------------------------------------- |
| `stack-infra`       | Traefik reverse proxy, Homepage dashboard, Portainer |
| `stack-arr`         | Sonarr, Radarr, Prowlarr, qBittorrent                |
| `stack-plex`        | Plex Media Server                                    |
| `stack-dns`         | AdGuard Home                                         |
| `stack-home`        | Home automation                                      |
| `stack-immich`      | Immich photo management                              |
| `stack-photobackup` | Photo backup                                         |
| `stack-nas`         | NAS-related services                                 |

## Setup

See [SETUP.md](SETUP.md) for the full bare-metal setup guide.

## Backup

An hourly cron job rsyncs `/srv/docker/` to the NAS, which then snapshots and backs it up off-site. See [scripts/docker_data_backup.sh](scripts/docker_data_backup.sh).
