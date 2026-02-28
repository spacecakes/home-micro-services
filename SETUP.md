# Ubuntu Server Setup Guide

## 1. Install Ubuntu Server

Flash Ubuntu Server 24.04 LTS to a USB drive.

During installation:

- Enable OpenSSH server
- Set hostname (e.g., `home-server`)
- Choose your main SSD/NVMe as the install target
- Skip Snap packages

After installation, reboot and SSH in:

```bash
ssh server
```

## 2. Basic Setup

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install htop curl git vim nfs-common
sudo timedatectl set-timezone Europe/Stockholm
```

## 3. Install Docker

Follow the official guide: https://docs.docker.com/engine/install/ubuntu/

Then:

```bash
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
```

Log out and back in for the group change to take effect.

## 4. NAS Shares

NFS shares are mounted automatically via Docker NFS volumes defined in each stack's `docker-compose.yml`. No host-level fstab configuration needed — `docker compose up -d` handles everything.

Ensure `nfs-common` is installed (included in step 2) so the kernel NFS client is available.

## 5. Clone and Start Stacks

```bash
sudo mkdir -p /srv/docker
cd /srv/docker
git clone https://github.com/spacecakes/home-micro-services .
```

Each stack lives in its own directory with a `docker-compose.yml`. Copy `.env.example` to `.env` where needed and fill in the values, then start:

```bash
cd stack-infra && docker compose up -d
cd stack-arr && docker compose up -d
# ... etc
```

**Note:** `stack-nas` is checked into this repo for versioning but runs on the Synology NAS (`10.0.1.2`), not the home server. Deploy it on the NAS separately.

## 6. Backup

Handled by the `stack-ops` backup container (Flask API + hourly cron). No host-side cron needed — the container manages its own schedule.

## 7. UPS Monitoring (apcupsd)

If the host has a native `apcupsd` installation, disable it before starting the containerized version:

```bash
sudo systemctl stop apcupsd
sudo systemctl disable apcupsd
sudo apt purge apcupsd
```

The `apcupsd` container in `stack-infra` replaces it. It monitors the UPS over SNMP and can shut down the host via D-Bus when battery is critical. Build the image on first setup:

```bash
cd /srv/docker/stack-infra
docker compose up -d --build apcupsd ops-toolbox
```

## 8. Free Port 53 (for AdGuard)

Follow: https://adguard-dns.io/kb/adguard-home/faq/#bindinuse

## 9. Automatic Updates (optional)

```bash
sudo apt install unattended-upgrades
```
