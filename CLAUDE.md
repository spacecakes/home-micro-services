# CLAUDE.md — Project Guide

Update this file whenever changes are made so it is always up to date. **Do not put sensitive information (IPs, emails, domains, URLs, secrets, LXC IDs) in this file — it is checked into git.** Use `dynamic.yml`, `.env` files, or Proxmox itself as the source of truth for those details.

## Repository Overview

Home server Docker infrastructure. ~30 containerized services across 6 compose stacks, reverse-proxied through Traefik with Authelia SSO. Some services have been migrated to dedicated Proxmox LXCs. PBS (LXC) backs up all VMs/LXCs; ops-toolbox backs up PVE host config and UPS NMC configs to the NAS.

Domain: wildcard TLS via Cloudflare DNS challenge (see compose labels and dynamic.yml for the actual domain).

### DNS Resolution

The wildcard domain resolves to the Docker LXC (Traefik). AdGuard Home is the primary LAN DNS, with a secondary instance on a Raspberry Pi using keepalived for failover. Cloudflare has matching A/CNAME records as a fallback. Tailscale split DNS forwards domain queries to AdGuard. See `dynamic.yml` for IPs.

External access: select subdomains are CNAME'd to the public IP via Cloudflare proxy, with router port-forwards to the relevant LXCs/VMs.

## Stack Organization

| Stack          | Purpose                                              |
| -------------- | ---------------------------------------------------- |
| `stack-infra`  | Core infra: reverse proxy, dashboard, monitoring     |
| `stack-auth`   | Authelia SSO + Redis session backend                 |
| `stack-ops`    | UPS monitoring, PVE host backup, auto-updates        |
| `stack-arr`    | Media automation (*arr apps, downloaders, requests)   |
| `stack-nas`    | NAS-side agents — **runs on the Synology NAS, not the home server** |

See each stack's `docker-compose.yml` for the full list of services. `stack-nas` is checked into this repo for versioning but deployed on the NAS.

### Stack startup order matters

`stack-infra` first (Traefik), then `stack-auth` (Authelia), then the rest. AdGuard Home now runs in a Proxmox LXC, not Docker.

## Routing & Traefik

### Docker label pattern (most services)

```yaml
labels:
  - 'traefik.http.routers.{name}.rule=Host(`{name}.<domain>`)'
  - 'traefik.http.routers.{name}.middlewares=authelia@file'
  - 'traefik.http.services.{name}.loadbalancer.server.port={port}'
```

Multi-network services need explicit `traefik.docker.network=traefik-proxy`.

### Static routes in dynamic.yml

Non-Docker services (Synology apps, UniFi, UPS NMCs, LXCs, VMs) are routed via `stack-infra/traefik/dynamic.yml`, not Docker labels. When adding routes for things outside Docker, edit dynamic.yml. See that file for the full list of routers and services.

### Authelia middleware

`authelia@file` is defined in `dynamic.yml` as a forward-auth middleware. Add it to any route that should require SSO. Services without it (e.g. DSM) handle their own auth.

### Services that disable Traefik

Backend-only services use `traefik.enable=false`. Services that only need intra-stack communication use the default network (e.g. `apcupsd`).

## Networking

- **`traefik-proxy`**: External Docker network shared across all stacks. Needed for Traefik routing and cross-stack container DNS.
- **DNS override**: Some stacks (`stack-arr`) set explicit Cloudflare/Google DNS to bypass AdGuard filtering.

## Custom Images

Some services use `image:` + `build:` in compose (grep for `build:` in compose files). `docker compose up -d` uses the cached image; pass `--build` only when source changes. Each image's `Dockerfile` and source live in the same directory as the service.

### NUT (Network UPS Tools) — runs on Proxmox host, not Docker

NUT server runs directly on the Proxmox host using the `snmp-ups` driver to monitor both APC UPS units via their NMCs. Config files in `/etc/nut/` on the host, backed up daily to NAS via ops-toolbox. The apcupsd Docker containers are monitor-only — they serve UPS status to ops-toolbox via the NIS protocol. Graceful host shutdown is handled by NUT, not apcupsd.

## Homepage Dashboard

When adding or renaming a service, update `stack-infra/homepage/services.yaml` (follow the existing format in that file) and `proxmox-notes.md`. Two Docker servers: `local-docker` (via dockerproxy) and `homecloud-docker` (NAS).

## Backup Architecture

### Tier 1: PBS (LXC)
Proxmox Backup Server in an LXC with NFS backend on Synology. Backs up all VMs/LXCs except the PBS instances themselves. Twice daily, with GC daily and verify weekly.

### Tier 2: PBS instances → NAS (vzdump)
Weekly vzdump of PBS instances to NAS. This is the disaster recovery bootstrap — if PVE dies, restore PBS LXC from NAS, then restore everything else from PBS. The backup data is already on the NAS (NFS), so even an old vzdump works.

### Tier 3: Config backup (ops-toolbox)
Flask app in stack-ops rsyncs PVE host configs and FTP-downloads UPS NMC configs to NAS.

### Tier 4: NAS-to-NAS replication
Synology 1 → Synology 2: Snapshot Replication for PBS data, Active Backup for Business for vzdump archives, Hyper Backup for general files.

### Tier 5: Cloud
Critical data on Synology C2. Not backup infra — too expensive at volume.

### Notifications
PVE and PBS send email alerts (configured in their respective UIs, not in this repo).

## Environment Variables

Each stack has its own `.env` (gitignored). Key variables:

See each stack's `.env` for the specific variables used.

## NAS Mounts

NFS shares from the Synology NAS are mounted via Docker's native NFS volume driver, defined inline in each stack's `docker-compose.yml`. No host-level fstab or systemd configuration needed — `docker compose up -d` handles mounting automatically.

Volume naming convention: `nfs-{share}` (e.g. `nfs-media`, `nfs-music`, `nfs-downloads`). Sub-paths get their own volumes (e.g. `nfs-downloads-seeding`, `nfs-photos-immich`).

## Common Patterns

- **YAML anchors**: `x-common: &common` with `<<: *common` for shared restart policy
- **Restart policy**: `unless-stopped` (most), `always` (critical: AdGuard, Immich, Redis)
- **Data directories**: `/srv/docker/stack-*/data/` for persistent state
- **Watchtower opt-out**: `com.centurylinklabs.watchtower.enable=false` on services needing manual control
- **GPU passthrough**: Plex and Immich run in their own LXCs with GPU passthrough configured in Proxmox.

## Proxmox LXC/VM Services (outside Docker)

Some services run in dedicated Proxmox LXCs/VMs instead of Docker. IPs and hostnames are in `stack-infra/traefik/dynamic.yml`. Prefer privileged LXCs with internal `/etc/fstab` for NFS mounts (supports Proxmox snapshots). PBS backs up all LXCs/VMs (except the PBS instances themselves). PBS instances are backed up weekly to the NAS as vzdump files (bootstrap for disaster recovery). ops-toolbox rsyncs PVE host config and UPS NMC configs to NAS.
