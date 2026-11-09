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
| **Docker LXC** (`10.0.1.4`) | Traefik, Authelia, Homepage, arr stack (Sonarr/Radarr/etc), config-backup, Watchtower, Tautulli, Portainer, Dockge, Glances, File Browser, HandBrake |
| **Plex LXC** (`10.0.1.19`) | Plex (native .deb, privileged, GPU passthrough, NFS via internal fstab) |
| **Immich LXC** (`10.0.1.18`) | Immich (native via community script, internal upload library) |
| **AdGuard LXC** (`10.0.1.10`) | AdGuard Home + Sync |
| **Raspberry Pi** (`10.0.1.22`) | AdGuard Home secondary (keepalived failover) |
| **PBS LXC** (`10.0.1.20`) | Proxmox Backup Server |
| **Change Detection LXC** (`10.0.1.28`) | changedetection.io |
| **FreshRSS LXC** (`10.0.1.29`) | FreshRSS |
| **Guacamole LXC** (`10.0.1.27`) | Guacamole (remote desktop gateway) |
| **Homebridge LXC** (`10.0.1.13`) | Homebridge |
| **Scrypted LXC** (`10.0.1.12`) | Scrypted (cameras) |
| **Home Assistant VM** (`10.0.1.7`) | HAOS |
| **OpenClaw VM** (`10.0.1.9`) | AI assistant |
| **Synology NAS** (`10.0.1.2`) | Uptime Kuma, Portainer agent, Dockge agent, Watchtower, iCloudPD |

### External access (no VPN required)

Plex and HaOS web UIs are CNAME'd through Cloudflare proxy to the public IP. Router port-forwards to Plex (`10.0.1.19:32400`) and Home Assistant (`10.0.1.7:8123`). Everything else requires VPN (Tailscale or to gateway).

### Monitoring

Uptime Kuma runs on the NAS (so it still alerts when the Proxmox host is down) and alerts via Pushover. Each LXC/VM gets a ping monitor; each web service gets an HTTP monitor.

HTTP monitors for services behind Authelia must use **basic auth as the `kuma` user, HEAD, max redirects 0, and a real health path** (e.g. `/ping` on the *arr apps). Authelia allows `kuma` with one factor, and only from the NAS (`10.0.1.2`). Basic auth through forward-auth is stateless. Without it, the monitor gets redirected to the Authelia login page and reports Authelia's health instead of the app's. Every cookieless check also creates a new Redis session, and this once piled up 170k of them. A `bypass` rule doesn't avoid that: Authelia still creates the session. A daily cron on the Docker LXC prunes kuma's logins from Authelia's `authentication_logs` table. Don't expose backend ports for monitoring, because that bypasses Authelia for everyone.

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
