# Home Micro Services

My Docker and reverse proxy setup for micro-services at home, shared publicly so I can discuss it with friends and get told what I'm doing wrong.

For full architecture documentation, see [CLAUDE.md](CLAUDE.md).

## Architecture

### How routing works

All `*.lundmark.tech` traffic flows through Traefik (running in Docker on `10.0.1.4`). DNS resolves via three layers:

1. **UniFi** — DHCP hands out AdGuard (`10.0.1.10`) as DNS + has local A records for `lundmark.tech` / `*.lundmark.tech` → `10.0.1.4`
2. **AdGuard Home** (`10.0.1.10`) — DNS rewrites `lundmark.tech` / `*.lundmark.tech` → `10.0.1.4`
3. **Cloudflare** — A record `lundmark.tech` → `10.0.1.4`, CNAME `*.lundmark.tech` → `lundmark.tech`. Also handles TLS cert DNS challenge.
4. **Tailscale** — Split DNS forwards `lundmark.tech` queries to AdGuard (`10.0.1.10`)

Docker services are discovered via labels. Non-Docker services (LXCs, VMs, NAS) use static routes in `dynamic.yml`. Authelia provides SSO for services that don't handle their own auth.

### How backups work

```
config-backup (Docker container)
├── Daily:   SSH into Proxmox host, rsync host configs → NAS
└── Manual:  FTP-download UPS NMC configs → NAS

Proxmox Backup Server
└── Nightly: Snapshot all LXCs/VMs → NAS
```

Docker config is version-controlled in this repo AND container data rsynced to NAS. Proxmox host config copies over SSH to NAS (`/etc/pve`, `/etc/nut`, `/etc/fstab`).

### Where services run

| Location | Services |
|---|---|
| **Docker LXC** (`10.0.1.4`) | Traefik, Authelia, Homepage, arr stack (Sonarr/Radarr/etc), config-backup, Watchtower, Tautulli, Uptime Kuma, Portainer, Dockge, Glances, File Browser, HandBrake |
| **Plex LXC** (`10.0.1.19`) | Plex (native .deb, privileged, GPU passthrough, NFS via internal fstab) |
| **Immich LXC** (TBD) | Immich (native via community script, internal upload library) |
| **AdGuard LXC** (`10.0.1.10`) | AdGuard Home + Sync |
| **Homebridge LXC** (`10.0.1.13`) | Homebridge |
| **Scrypted LXC** (`10.0.1.12`) | Scrypted (cameras) |
| **Home Assistant VM** (`10.0.1.7`) | HAOS |
| **OpenClaw VM** (`10.0.1.9`) | AI assistant |
| **Synology NAS** (`10.0.1.2`) | Portainer agent, Dockge agent, Watchtower, AdGuard (backup), iCloudPD |

### External access (no VPN required)

Plex and HaOS web UIs are CNAME'd through Cloudflare proxy to the public IP. Router port-forwards to Plex (`10.0.1.19:32400`) and Home Assistant (`10.0.1.7:8123`). Everything else requires VPN (Tailscale or to gateway).

## Cheatsheet

### Docker stacks

```bash
# Stop all stacks
for d in stack-*/; do [ "$d" = "stack-nas/" ] && continue; (cd "$d" && docker compose down); done

# Start all stacks (infra and auth first)
for d in stack-infra stack-auth; do (cd "$d" && docker compose up -d); done
for d in stack-*/; do [ "$d" = "stack-nas/" ] && continue; (cd "$d" && docker compose up -d); done
```

### Disk Usage

```bash
df -h
sudo du -xh --max-depth=1 / 2>/dev/null | sort -rh
```

### Docker Logs

```bash
sudo find /srv/docker -type f -name "*.log" -exec truncate -s 0 {} \;
```

### NFS Volumes

```bash
docker volume ls | grep nfs-
docker volume inspect nfs-media
```
