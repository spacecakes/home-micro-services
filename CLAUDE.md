# CLAUDE.md — Project Guide

Update this file whenever changes are made so it is always up to date.

## Repository Overview

Home server Docker infrastructure. ~30 containerized services across 6 compose stacks, reverse-proxied through Traefik with Authelia SSO. Some services have been migrated to dedicated Proxmox LXCs. Proxmox snapshots handle container/LXC backup; ops-toolbox backs up PVE host config daily to the NAS.

Domain: `lundmark.tech` (wildcard TLS via Cloudflare DNS challenge).

### DNS Resolution

`*.lundmark.tech` resolves to `10.0.1.4` (Docker LXC where Traefik runs) via three layers:

- **UniFi**: DHCP hands out AdGuard (`10.0.1.10`) as DNS + has local A records for `lundmark.tech` / `*.lundmark.tech` → `10.0.1.4`.
- **AdGuard Home** (`10.0.1.10`): DNS rewrites for `lundmark.tech` and `*.lundmark.tech` → `10.0.1.4`. Primary DNS for LAN clients.
- **Cloudflare**: A record `lundmark.tech` → `10.0.1.4`, CNAME `*.lundmark.tech` → `lundmark.tech`. Fallback for clients not using AdGuard.
- **Tailscale**: Split DNS configured to forward `lundmark.tech` queries to AdGuard (`10.0.1.10`) so VPN clients resolve correctly.

External access (no VPN): `watch.lundmark.tech` and `home.lundmark.tech` are CNAME'd to `public.lundmark.tech` (public IP) with Cloudflare proxy enabled. Router port-forwards to Plex LXC (`10.0.1.19:32400`) and Home Assistant VM (`10.0.1.7:8123`).

## Stack Organization

| Stack          | Purpose                                                                                                                                 |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `stack-infra`  | Core infra: Traefik, Homepage dashboard, Portainer, Dockge, Uptime Kuma, dockerproxy, Glances, File Browser, Tautulli                    |
| `stack-auth`   | Authelia SSO + Redis session backend                                                                                                    |
| `stack-ops`    | apcupsd + apcupsd2 (dual UPS monitoring, monitor-only), ops-toolbox (UPS monitoring + PVE host backup), Watchtower                    |
| `stack-arr`    | Sonarr, Radarr, Lidarr, Bazarr, Prowlarr, NZBHydra2, SABnzbd, qBittorrent, Seerr, Aurral                                                |
| `stack-nas`    | Portainer Edge Agent, Dockge Agent, Watchtower, AdGuard Home, iCloudPD — **runs on the Synology NAS (`10.0.1.2`), not the home server** |

`stack-nas` is checked into this repo for versioning but deployed on the NAS. All other stacks run on the home server.

### Stack startup order matters

`stack-infra` first (Traefik), then `stack-auth` (Authelia), then the rest. AdGuard Home now runs in a Proxmox LXC (`10.0.1.10`), not Docker.

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

Non-Docker services (Synology apps, UniFi, UPS NMCs, LXCs, VMs) are routed via `stack-infra/traefik/dynamic.yml`, not Docker labels. When adding routes for things outside Docker, edit dynamic.yml. Key static routes:

- `dsm/drive/backup/downloads/files/vm.lundmark.tech` → Synology NAS `10.0.1.2:5001` (path-prefixed)
- `network.lundmark.tech` → UniFi `10.0.1.1`
- `ups1/ups2.lundmark.tech` → APC NMC web interfaces
- `photos.lundmark.tech` → Immich LXC `10.0.1.18:2283`
- `icloudpd/icloudpd-shared.lundmark.tech` → NAS `10.0.1.2:8080/8081`
- `dns1.lundmark.tech` → AdGuard Home LXC `10.0.1.10`
- `dns-sync.lundmark.tech` → AdGuard Home Sync LXC `10.0.1.10:8080`
- `dns2.lundmark.tech` → NAS AdGuard `10.0.1.2:3000`
- `watch.lundmark.tech` → Plex LXC `10.0.1.19:32400`
- `homebridge.lundmark.tech` → Homebridge LXC `10.0.1.13:8581`
- `cameras.lundmark.tech` → Scrypted LXC `10.0.1.12:10443`
- `home.lundmark.tech` → Home Assistant OS VM `10.0.1.7:8123`
- `bot.lundmark.tech` → OpenClaw AI assistant VM `10.0.1.9:18789`
- `hypervisor.lundmark.tech` → Proxmox `10.0.1.3:8006`

### Authelia middleware

`authelia@file` is defined in `dynamic.yml` as a forward-auth middleware pointing to `http://authelia:9091`. Add it to any route that should require SSO. Services without it (e.g. DSM) handle their own auth.

### Services that disable Traefik

Backend-only services use `traefik.enable=false`. Services that only need intra-stack communication use the default network (e.g. `apcupsd`).

## Networking

- **`traefik-proxy`**: External Docker network shared across all stacks. Needed for Traefik routing and cross-stack container DNS.
- **DNS override**: Some stacks (`stack-arr`) set explicit Cloudflare/Google DNS to bypass AdGuard filtering.

## Custom Images

Two services use `image:` + `build:` in compose. `docker compose up -d` uses the cached image; pass `--build` only when source changes.

| Image                | Source                   | Stack       |
| -------------------- | ------------------------ | ----------- |
| `apcupsd:latest`     | `stack-ops/apcupsd/`     | `stack-ops` |
| `ops-toolbox:latest` | `stack-ops/ops-toolbox/` | `stack-ops` |

### apcupsd

Debian-slim container running apcupsd in SNMP mode. The `UPS_DEVICE` env var sets the NMC IP (entrypoint.sh substitutes it into the baked-in config). Both instances are monitor-only — they serve UPS status to ops-toolbox via the NIS protocol. Graceful host shutdown is handled by NUT on the Proxmox host (see below).

- **apcupsd** (Rack UPS, `10.0.1.5`, port 3551)
- **apcupsd2** (Desktop UPS, `10.0.1.6`, port 3552)

### NUT (Network UPS Tools) — runs on Proxmox host, not Docker

NUT server runs directly on the Proxmox host (`10.0.1.3`) using the `snmp-ups` driver to monitor both APC UPS units via their NMCs (SNMPv3). Config files in `/etc/nut/` on the host, backed up daily to NAS via ops-toolbox.

- **`rack-ups`** (Smart-UPS X 1500, NMC at `10.0.1.5`) — triggers Proxmox shutdown on battery via `upssched` (30s grace period)
- **`desktop-ups`** (Smart-UPS 750, NMC at `10.0.1.6`) — monitored, no shutdown action

Clients: Proxmox `upsmon` (local, master), Home Assistant NUT integration (`10.0.1.3:3493`, slave). The apcupsd Docker containers remain for ops-toolbox UPS status display only.

### ops-toolbox

Alpine multi-stage build: Node builds the Vue 3 + Vite + Tailwind SPA, Alpine runtime runs Flask + rsync + openssh-client. Serves as the ops web UI with:

- Pure Python NIS client for dual UPS monitoring (apcupsd + apcupsd2)
- Daily rsync via cron (2am): Proxmox host config (`/etc/pve/`, `/etc/nut/`, `/etc/fstab`, `/etc/network/interfaces`, `/etc/modprobe.d/`, `/etc/modules`, `/etc/sysctl.conf`, `/etc/apt/sources.list.d/`) → NAS backup (`/destination/` via NFS volume `nfs-backup-pve-host`)
- Flask API for manual PVE backup trigger
- Vue 3 SPA baked into image (`dist/`); `app.py` bind-mounted for backend changes without rebuild
- All config via environment variables (UPS hosts, PVE host, SSH key path, backup destination)
- SSH key for PVE backup stored in `data/ssh/` (gitignored, bind-mounted read-only)

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
- `stack-nas`: `PORTAINER_EDGE_ID`, `PORTAINER_EDGE_KEY`, `APPLE_ID`, `ICLOUD_SHARED_LIBRARY`

## NAS Mounts

NFS shares from `10.0.1.2` are mounted via Docker's native NFS volume driver, defined inline in each stack's `docker-compose.yml`. No host-level fstab or systemd configuration needed — `docker compose up -d` handles mounting automatically.

Volume naming convention: `nfs-{share}` (e.g. `nfs-media`, `nfs-music`, `nfs-downloads`). Sub-paths get their own volumes (e.g. `nfs-downloads-seeding`, `nfs-photos-immich`).

## Common Patterns

- **YAML anchors**: `x-common: &common` with `<<: *common` for shared restart policy
- **Restart policy**: `unless-stopped` (most), `always` (critical: AdGuard, Immich, Redis)
- **Data directories**: `/srv/docker/stack-*/data/` for persistent state
- **Watchtower opt-out**: `com.centurylinklabs.watchtower.enable=false` on services needing manual control
- **GPU passthrough**: Plex and Immich run in their own LXCs with GPU passthrough configured in Proxmox.

## Proxmox LXC/VM Services (outside Docker)

Services migrated out of Docker to dedicated Proxmox LXCs/VMs. NFS mounts inside privileged LXCs use `/etc/fstab`; unprivileged LXCs use host bind mounts. Prefer privileged with internal fstab for services needing NAS access (supports Proxmox snapshots).

| Service        | Type           | IP           | Notes                                                     |
| -------------- | -------------- | ------------ | --------------------------------------------------------- |
| AdGuard Home   | LXC            | `10.0.1.10`  | Primary DNS, also handles `*.lundmark.tech` DNS rewrite   |
| Homebridge     | LXC            | `10.0.1.13`  |                                                           |
| Scrypted       | LXC            | `10.0.1.12`  | Camera management                                         |
| Plex           | LXC (native)   | `10.0.1.19`  | Privileged, GPU passthrough, NFS via internal fstab       |
| Immich         | LXC (native)   | `10.0.1.18`  | Community script install, internal upload library          |
| Home Assistant | VM (HAOS)      | `10.0.1.7`   |                                                           |
| OpenClaw       | VM             | `10.0.1.9`   | AI assistant                                              |
| Tailscale      | LXC            |              | VPN access                                                |

Proxmox backs up all LXCs/VMs to the NAS. The ops-toolbox daily rsync also backs up `/etc/fstab` from the Proxmox host.
