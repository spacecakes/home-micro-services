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

| Stack          | Purpose                                              |
| -------------- | ---------------------------------------------------- |
| `stack-infra`  | Core infra: reverse proxy, dashboard, monitoring     |
| `stack-auth`   | Authelia SSO + Redis session backend                 |
| `stack-ops`    | UPS monitoring, PVE host backup, auto-updates        |
| `stack-arr`    | Media automation (*arr apps, downloaders, requests)   |
| `stack-nas`    | NAS-side agents — **runs on the Synology NAS (`10.0.1.2`), not the home server** |

See each stack's `docker-compose.yml` for the full list of services. `stack-nas` is checked into this repo for versioning but deployed on the NAS.

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

Non-Docker services (Synology apps, UniFi, UPS NMCs, LXCs, VMs) are routed via `stack-infra/traefik/dynamic.yml`, not Docker labels. When adding routes for things outside Docker, edit dynamic.yml. See that file for the full list of routers and services.

### Authelia middleware

`authelia@file` is defined in `dynamic.yml` as a forward-auth middleware pointing to `http://authelia:9091`. Add it to any route that should require SSO. Services without it (e.g. DSM) handle their own auth.

### Services that disable Traefik

Backend-only services use `traefik.enable=false`. Services that only need intra-stack communication use the default network (e.g. `apcupsd`).

## Networking

- **`traefik-proxy`**: External Docker network shared across all stacks. Needed for Traefik routing and cross-stack container DNS.
- **DNS override**: Some stacks (`stack-arr`) set explicit Cloudflare/Google DNS to bypass AdGuard filtering.

## Custom Images

Some services use `image:` + `build:` in compose (grep for `build:` in compose files). `docker compose up -d` uses the cached image; pass `--build` only when source changes. Each image's `Dockerfile` and source live in the same directory as the service.

### NUT (Network UPS Tools) — runs on Proxmox host, not Docker

NUT server runs directly on the Proxmox host (`10.0.1.3`) using the `snmp-ups` driver to monitor both APC UPS units via their NMCs (SNMPv3). Config files in `/etc/nut/` on the host, backed up daily to NAS via ops-toolbox. The apcupsd Docker containers are monitor-only — they serve UPS status to ops-toolbox via the NIS protocol. Graceful host shutdown is handled by NUT, not apcupsd.

## Homepage Dashboard

When adding or renaming a service, update `stack-infra/homepage/services.yaml` (follow the existing format in that file) and `proxmox-notes.md`. Two Docker servers: `local-docker` (via dockerproxy) and `homecloud-docker` (NAS).

## Environment Variables

Each stack has its own `.env` (gitignored). Key variables:

- `stack-infra`: `CLOUDFLARE_API_TOKEN`, `HOMEPAGE_UNIFI_PASSWORD`
- `stack-nas`: `PORTAINER_EDGE_ID`, `PORTAINER_EDGE_KEY`

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

Some services run in dedicated Proxmox LXCs/VMs instead of Docker. IPs and hostnames are in `stack-infra/traefik/dynamic.yml`. Prefer privileged LXCs with internal `/etc/fstab` for NFS mounts (supports Proxmox snapshots). Proxmox backs up all LXCs/VMs to the NAS; ops-toolbox also rsyncs PVE host config daily.
