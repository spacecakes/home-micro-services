# Docker LXC — lundmark.tech

Traefik + Authelia SSO | hourly NAS backup

[Dashboard](https://homepage.lundmark.tech) | [Portainer](https://portainer.lundmark.tech) | [Dockge](https://dockge.lundmark.tech) | [Repo](https://github.com/spacecakes/home-micro-services)

---

| Stack | Services |
|-------|----------|
| **stack-infra** | Traefik, Homepage, Portainer, Dockge, Uptime Kuma, AdGuard |
| **stack-auth** | Authelia SSO + Redis |
| **stack-ops** | apcupsd, ops-toolbox, ops-worker, Watchtower, HandBrake |
| **stack-arr** | Sonarr, Radarr, Lidarr, Bazarr, Prowlarr, SABnzbd, qBittorrent, Seerr |
| **stack-plex** | Plex + Tautulli |
| **stack-home** | Homebridge, Scrypted |
| **stack-immich** | Immich + ML + PostgreSQL + Valkey |
| **stack-nas** | *runs on Synology NAS (10.0.1.2)* |

---

Data: `/srv/docker` | Backup: Synology NAS via NFS | Domain: `*.lundmark.tech`
