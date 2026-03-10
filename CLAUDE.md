# CLAUDE.md — Project Guide

Update this file whenever changes are made so it is always up to date.

## Repository Overview

Home server Docker infrastructure. ~45 containerized services across 8 compose stacks, reverse-proxied through Traefik with Authelia SSO, backed up hourly to a Synology NAS.

Domain: `lundmark.tech` (wildcard TLS via Cloudflare DNS challenge).

## Stack Organization

| Stack          | Purpose                                                                                                                                 |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `stack-infra`  | Core infra: Traefik, Homepage dashboard, Portainer, Dockge, Uptime Kuma, dockerproxy, Glances, File Browser                             |
| `stack-dns`    | Legacy AdGuard Home + sync containers (now running in Proxmox LXC `10.0.1.10`; kept for rollback, normally stopped)                     |
| `stack-auth`   | Authelia SSO + Redis session backend                                                                                                    |
| `stack-ops`    | apcupsd + apcupsd2 (dual UPS monitoring), ops-toolbox (UPS + ops web UI), ops-worker (hourly rsync + API), Watchtower, iperf3, OpenSpeedTest, HandBrake |
| `stack-arr`    | Sonarr, Radarr, Lidarr, Bazarr, Prowlarr, NZBHydra2, SABnzbd, qBittorrent, Seerr, Aurral                                                |
| `stack-plex`   | Plex (host network) + Tautulli                                                                                                          |
| `stack-home`   | Homebridge, Scrypted (both host network)                                                                                                |
| `stack-immich` | Immich server + ML + PostgreSQL (custom vectorchord) + Valkey                                                                           |
| `stack-nas`    | Portainer Edge Agent, Dockge Agent, Watchtower, AdGuard Home, iCloudPD — **runs on the Synology NAS (`10.0.1.2`), not the home server** |

`stack-nas` is checked into this repo for versioning but deployed on the NAS. All other stacks run on the home server.

### Stack startup order matters

`stack-infra` first (Traefik), then `stack-auth` (Authelia), then the rest. AdGuard Home now runs in a Proxmox LXC (`10.0.1.10`), not Docker. The backup service respects this via `STACK_PRIORITY` in `stack-ops/ops-worker/web.py`.

## Routing & Traefik

### Docker label pattern (most services)

```yaml
labels:
  - 'traefik.http.routers.{name}.rule=Host(`{name}.lundmark.tech`)'
  - 'traefik.http.routers.{name}.middlewares=authelia@file'
  - 'traefik.http.services.{name}.loadbalancer.server.port={port}'
```

Multi-network services need explicit `traefik.docker.network=traefik-proxy`.

### Static routes in dynamic.yml

Non-Docker services (Synology apps, UniFi, UPS NMCs, iCloudPD on NAS) are routed via `stack-infra/traefik/dynamic.yml`, not Docker labels. When adding routes for things outside Docker, edit dynamic.yml. Key static routes:

- `dsm/drive/backup/downloads/files/vm.lundmark.tech` → Synology NAS `10.0.1.2:5001` (path-prefixed)
- `network.lundmark.tech` → UniFi `10.0.1.1`
- `ups1/ups2.lundmark.tech` → APC NMC web interfaces
- `icloudpd/icloudpd-shared.lundmark.tech` → NAS `10.0.1.2:8080/8081`
- `dns1.lundmark.tech` → AdGuard Home LXC `10.0.1.10`
- `dns-sync.lundmark.tech` → AdGuard Home Sync LXC `10.0.1.10:8080`
- `dns2.lundmark.tech` → NAS AdGuard `10.0.1.2:3000`
- `home.lundmark.tech` → Home Assistant OS VM `10.0.1.7:8123`
- `bot.lundmark.tech` → OpenClaw AI assistant VM `10.0.1.9:18789`
- `hypervisor.lundmark.tech` → Proxmox `10.0.1.3:8006`

### Authelia middleware

`authelia@file` is defined in `dynamic.yml` as a forward-auth middleware pointing to `http://authelia:9091`. Add it to any route that should require SSO. Services without it (e.g. DSM) handle their own auth.

### Services that disable Traefik

Backend-only services use `traefik.enable=false`. Services that only need intra-stack communication use the default network (e.g. `apcupsd`, `ops-worker`).

## Networking

- **`traefik-proxy`**: External Docker network shared across all stacks. Needed for Traefik routing and cross-stack container DNS.
- **Host network**: Used by Plex, Homebridge, Scrypted (need device/port access).
- **DNS override**: Some stacks (`stack-arr`) set explicit Cloudflare/Google DNS to bypass AdGuard filtering.

## Custom Images

Two services use `image:` + `build:` in compose. `docker compose up -d` uses the cached image; pass `--build` only when source changes.

| Image                | Source                   | Stack       |
| -------------------- | ------------------------ | ----------- |
| `apcupsd:latest`     | `stack-ops/apcupsd/`     | `stack-ops` |
| `ops-toolbox:latest` | `stack-ops/ops-toolbox/` | `stack-ops` |

### apcupsd

Debian-slim container running apcupsd in SNMP mode. The `UPS_DEVICE` env var sets the NMC IP (entrypoint.sh substitutes it into the baked-in config). Two instances:

- **apcupsd** (Rack UPS, `10.0.1.5`, port 3551): On critical battery, `doshutdown` triggers host shutdown via D-Bus. Requires `apparmor:unconfined` and host D-Bus socket.
- **apcupsd2** (Desktop UPS, `10.0.1.6`, port 3552): Monitor-only — no D-Bus, no shutdown capability.

### ops-toolbox

Flask app serving as an ops web UI (rarely-used toolbox, not a glance-at dashboard). Pure Python NIS client talks to apcupsd, and all backup/setup actions proxy to `ops-worker:8000`. Stateless — can be rebuilt anytime without affecting running jobs.

## Backup System

`stack-ops/ops-worker/web.py` is bind-mounted (`:ro`) into an Alpine container. Restart the container to pick up changes (no rebuild needed). It provides:

- Hourly rsync via cron: `/srv/docker/` → NAS backup (via Docker NFS volume)
- Flask API for manual backup/restore

## Homepage Dashboard

When adding or renaming a service, update `stack-infra/homepage/services.yaml` and `proxmox-notes.md` (the Proxmox LXC notes template — Markdown format, copy-paste into Proxmox notes field). Format:

```yaml
- Service Name:
    icon: name.png # or /icons/custom.svg
    href: https://x.lundmark.tech/
    description: Short description
    container: container_name # optional, for Docker status
    server: local-docker # or homecloud-docker for NAS
```

Two Docker servers: `local-docker` (via dockerproxy on localhost:2375) and `homecloud-docker` (NAS at 10.0.1.2:2375).

## Environment Variables

Each stack has its own `.env` (gitignored). Key variables:

- `stack-infra`: `CLOUDFLARE_API_TOKEN`, `HOMEPAGE_UNIFI_PASSWORD`
- `stack-plex`: `PLEX_CLAIM`
- `stack-nas`: `PORTAINER_EDGE_ID`, `PORTAINER_EDGE_KEY`, `APPLE_ID`, `ICLOUD_SHARED_LIBRARY`
- `stack-immich`: `DB_PASSWORD`

## NAS Mounts

NFS shares from `10.0.1.2` are mounted via Docker's native NFS volume driver, defined inline in each stack's `docker-compose.yml`. No host-level fstab or systemd configuration needed — `docker compose up -d` handles mounting automatically.

Volume naming convention: `nfs-{share}` (e.g. `nfs-media`, `nfs-music`, `nfs-downloads`). Sub-paths get their own volumes (e.g. `nfs-downloads-seeding`, `nfs-photos-immich`).

## Common Patterns

- **YAML anchors**: `x-common: &common` with `<<: *common` for shared restart policy
- **Restart policy**: `unless-stopped` (most), `always` (critical: AdGuard, Immich, Redis)
- **Data directories**: `/srv/docker/stack-*/data/` for persistent state
- **Watchtower opt-out**: `com.centurylinklabs.watchtower.enable=false` on services needing manual control
- **GPU passthrough**: `/dev/dri` for Intel Quick Sync (Plex, Immich)
