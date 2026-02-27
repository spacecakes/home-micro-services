# Proxmox LXC Setup Guide

## 1. Create the LXC Container

In the Proxmox web UI:

1. Download the **Ubuntu 24.04** container template (local storage → CT Templates → Templates)
2. Create CT with these settings:
   - **Unprivileged container**: Yes
   - **Nesting**: Enable (required for Docker)
   - **Cores**: 10–12
   - **Memory**: 12288–14336 MB
   - **Swap**: 512 MB
   - **Disk**: Size to match your SSD/NVMe (e.g., 500 GB)
   - **Network**: DHCP or static IP on your LAN bridge (e.g., `vmbr0`)
3. Enable **TUN/TAP** (needed for Tailscale)

## 2. Proxmox Host Configuration

After creating the container, edit its config on the Proxmox host. Replace `<CTID>` with your container ID:

```bash
nano /etc/pve/lxc/<CTID>.conf
```

### GPU passthrough (Intel Quick Sync)

Add these lines for Plex and Immich hardware transcoding:

```
lxc.cgroup2.devices.allow: c 226:* rwm
lxc.mount.entry: /dev/dri dev/dri none bind,optional,create=dir
```

### Verify nesting and keyctl

These should already be set from the creation wizard, but confirm:

```
features: keyctl=1,nesting=1
```

Start the container and SSH in (or use the Proxmox console):

```bash
ssh root@<LXC_IP>
```

## 3. Basic Setup

```bash
apt update && apt upgrade -y
apt install -y htop curl git vim nfs-common
timedatectl set-timezone Europe/Stockholm
```

Create a non-root user:

```bash
adduser gabriel
usermod -aG sudo gabriel
su - gabriel
```

## 4. Install Docker

Follow the official guide: https://docs.docker.com/engine/install/ubuntu/

Then:

```bash
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
```

Log out and back in for the group change to take effect.

## 5. GPU Permissions

To allow Docker containers to use Intel Quick Sync, add your user to the `render` and `video` groups:

```bash
sudo usermod -aG render,video $USER
```

Verify the device is visible inside the LXC:

```bash
ls -la /dev/dri/
```

You should see `card0` and `renderD128`.

## 6. Clone the Repo

```bash
sudo mkdir -p /srv/docker
sudo chown $USER:$USER /srv/docker
cd /srv/docker
git clone https://github.com/spacecakes/home-micro-services .
```

## 7. Restore Data from Backup

Before starting any stacks, restore persistent data from the NAS. This avoids starting services with empty data directories:

```bash
cd /srv/docker
sudo ./scripts/restore.sh
```

The script mounts the NAS NFS share temporarily, rsyncs all data, and cleans up the mount when done.

## 8. Set Up Environment Files

Each stack that needs secrets has a `.env.example`. Copy and fill them in:

```bash
cd /srv/docker
cp stack-infra/.env.example stack-infra/.env
cp stack-plex/.env.example stack-plex/.env
cp stack-immich/.env.example stack-immich/.env
# ... etc for any stack with an .env.example
```

Edit each `.env` and fill in the required values (see CLAUDE.md for key variables per stack).

## 9. Start Stacks (Order Matters)

Create the shared Traefik network first:

```bash
docker network create traefik-proxy
```

Then start stacks in order:

```bash
# 1. Core infrastructure (Traefik, Homepage, etc.)
cd /srv/docker/stack-infra && docker compose up -d

# 2. Authentication (Authelia + Redis)
cd /srv/docker/stack-auth && docker compose up -d

# 3. Everything else (order doesn't matter)
cd /srv/docker/stack-ops && docker compose up -d
cd /srv/docker/stack-dns && docker compose up -d
cd /srv/docker/stack-arr && docker compose up -d
cd /srv/docker/stack-plex && docker compose up -d
cd /srv/docker/stack-home && docker compose up -d
cd /srv/docker/stack-immich && docker compose up -d
```

Build custom images on first setup:

```bash
cd /srv/docker/stack-ops && docker compose up -d --build apcupsd ops-dashboard
```

## 10. Free Port 53 (for AdGuard)

Ubuntu 24.04 LXC containers typically don't run `systemd-resolved`, so port 53 should already be free. Verify:

```bash
ss -tlnp | grep :53
```

If something is listening, follow: https://adguard-dns.io/kb/adguard-home/faq/#bindinuse

## 11. Tailscale (Optional)

TUN/TAP was enabled during LXC creation. Install Tailscale directly in the LXC:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

## Notes

- **`stack-nas`** is versioned here but runs on the Synology NAS (`10.0.1.2`), not in this LXC.
- **NFS mounts** are handled by Docker's NFS volume driver — no fstab entries needed. Just ensure `nfs-common` is installed (step 3).
- **Automatic updates** (optional): `sudo apt install unattended-upgrades`
