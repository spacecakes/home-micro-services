# CLAUDE.md — Project Guide

Update this file whenever changes are made so it is always up to date. **Do not put sensitive information (IPs, emails, domains, URLs, secrets, LXC IDs) in this file — it is checked into git.** Use `dynamic.yml`, `.env` files, or Proxmox itself as the source of truth for those details.

## Repository Overview

Home server Docker infrastructure. ~30 containerized services across 6 compose stacks, reverse-proxied through Traefik with Authelia SSO. Some services have been migrated to dedicated Proxmox LXCs. PBS (LXC) backs up all VMs/LXCs; config-backup backs up PVE host config (daily) and UPS NMC configs (manual) to the NAS.

Domain: wildcard TLS via Cloudflare DNS challenge (see compose labels and dynamic.yml for the actual domain).

### DNS Resolution

The wildcard domain resolves to the Docker LXC (Traefik). AdGuard Home is the primary LAN DNS, with a secondary instance on a Raspberry Pi using keepalived for failover. Cloudflare has matching A/CNAME records as a fallback. Tailscale split DNS forwards domain queries to AdGuard. See `dynamic.yml` for IPs.

External access: select subdomains are CNAME'd to the public IP via Cloudflare proxy, with router port-forwards to the relevant LXCs/VMs.

## Stack Organization

| Stack           | Purpose                                                                                  |
| --------------- | ---------------------------------------------------------------------------------------- |
| `stack-infra`   | Core infra: reverse proxy, dashboard, monitoring                                         |
| `stack-auth`    | Authelia SSO + Redis session backend                                                     |
| `stack-ops`     | Config backup (PVE host + NMC), auto-updates                                             |
| `stack-arr`     | Media automation (*arr apps, downloaders, requests)                                      |
| `stack-agents`  | Remote-management agents (Portainer, Dockge, dockerproxy, watchtower, uptime-kuma) — **runs on the NAS** |

`stack-infra`, `stack-auth`, `stack-ops`, and `stack-arr` run on the Docker LXC on PVE. `stack-agents` is checked into this repo for versioning but deployed on the Synology NAS via Container Manager.

### Stack startup order matters

`stack-infra` first (Traefik), then `stack-auth` (Authelia), then `stack-ops`/`stack-arr`. Within `stack-arr`, `gluetun` must be healthy before qbittorrent/transmission start (handled by `depends_on`). AdGuard Home runs in a Proxmox LXC, not Docker.

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

Backend-only services use `traefik.enable=false`.

## Networking

- **`traefik-proxy`**: External Docker network shared across all stacks. Needed for Traefik routing and cross-stack container DNS.
- **DNS override**: gluetun handles DNS for qbittorrent/transmission via its own resolver. Other containers use the Docker LXC's resolver (AdGuard via the LAN).

## Custom Images

Some services use `image:` + `build:` in compose (grep for `build:` in compose files). `docker compose up -d` uses the cached image; pass `--build` only when source changes. Each image's `Dockerfile` and source live in the same directory as the service.

### NUT (Network UPS Tools) — runs on Proxmox host, not Docker

NUT server runs directly on the Proxmox host using the `snmp-ups` driver to monitor both APC UPS units via their NMCs. Config files in `/etc/nut/` on the host, backed up daily to NAS via config-backup. Graceful host shutdown is handled by NUT.

## Homepage Dashboard

When adding or renaming a service, update `stack-infra/homepage/services.yaml` (follow the existing format in that file) and `proxmox-notes.md`. Two Docker servers: `local-docker` (via dockerproxy) and `homecloud-docker` (NAS).

## Backup Architecture

### Tier 1: PBS (LXC)
Proxmox Backup Server in an LXC with NFS backend on Synology. Backs up all VMs/LXCs except the PBS instances themselves. Twice daily, with GC daily and verify weekly.

### Tier 2: PBS instances → NAS (vzdump)
Weekly vzdump of PBS instances to NAS. This is the disaster recovery bootstrap — if PVE dies, restore PBS LXC from NAS, then restore everything else from PBS. The backup data is already on the NAS (NFS), so even an old vzdump works.

### Tier 3: Config backup (config-backup)
Flask app in stack-ops. Daily rsync of PVE host configs to NAS. Manual FTP snapshots of UPS NMC configs.

### Tier 4: NAS-to-NAS replication
Synology 1 → Synology 2: Snapshot Replication for PBS data, Active Backup for Business for vzdump archives, Hyper Backup for general files.

### Tier 5: Cloud
Critical data on Synology C2. Not backup infra — too expensive at volume.

### Notifications
PVE and PBS send email alerts (configured in their respective UIs, not in this repo).

## Environment Variables

Each stack has its own `.env` (gitignored). Key variables:

See each stack's `.env` for the specific variables used.

## NAS Storage Access

NFS shares from the Synology NAS are mounted via Docker's native NFS volume driver, defined inline in each stack's `docker-compose.yml`. Naming convention: `nfs-{share}` (e.g. `nfs-media`, `nfs-music`, `nfs-photos-immich`). Requires `nfs-common` on the LXC.

Do NOT use `/etc/fstab` + host bind mounts on the Docker LXC. Bind mounts don't follow NFS remounts: if Docker starts before the NFS mount (the usual case with `bg,nofail`), containers pin to the empty stub dir and stay broken until manually restarted.

### Hardlinks and the single-mount layout

For *arr-style hardlink imports to work, the download-complete tree and the media library must share a single NFS mount on the LXC (same `st_dev`). `stack-arr` achieves this by mounting the `media` share once (`nfs-media`) and using a hidden `/volume1/media/.downloads/` subtree for SAB complete + qBit save paths. The dot-prefix keeps it out of Plex library scans.

Music is exempt — Lidarr writes to a separate `nfs-music` mount, so music imports are a same-server cross-mount copy. Acceptable cost for small files.

For `stack-agents` running on the NAS itself: bind-mount `/volume1/<share>` directly.

## Common Patterns

- **YAML anchors**: `x-common: &common` with `<<: *common` for shared restart policy
- **Restart policy**: `unless-stopped` (most), `always` (critical: AdGuard, Immich, Redis)
- **Data directories**: `/srv/docker/stack-*/data/` for persistent state
- **Watchtower opt-out**: `com.centurylinklabs.watchtower.enable=false` on services needing manual control
- **GPU passthrough**: Plex and Immich run in their own LXCs with GPU passthrough configured in Proxmox.
- **VPN sidecar**: qbittorrent runs in gluetun's network namespace (WireGuard, `custom` provider). Traefik labels and the qbit port live on gluetun. A `qbittorrent` network alias on gluetun keeps *arr DNS lookups working. WG creds in `stack-arr/.env`.

## Proxmox LXC/VM Services (outside Docker)

Some services run in dedicated Proxmox LXCs/VMs instead of Docker. IPs and hostnames are in `stack-infra/traefik/dynamic.yml`. Prefer privileged LXCs with internal `/etc/fstab` for NFS mounts (supports Proxmox snapshots). PBS backs up all LXCs/VMs (except the PBS instances themselves). PBS instances are backed up weekly to the NAS as vzdump files (bootstrap for disaster recovery). config-backup rsyncs PVE host config daily and can snapshot UPS NMC configs on demand.
