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
ssh gabriel@home-server.local
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

## 4. Mount NAS Shares

Create mount points and add NFS entries to `/etc/fstab` (see `fstab.example` for the entries):

```bash
sudo mkdir -p /mnt/nas/{backup-homeserver,media,music,photos,video,downloads,home_video}
sudo mount -a
df -h | grep nas
```

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

## 6. Docker Service — Wait for Mounts

Override the Docker service so it waits for NAS mounts before starting containers:

```bash
sudo systemctl edit docker.service
```

```ini
[Unit]
After=network-online.target
Wants=network-online.target

RequiresMountsFor=/mnt/nas/backup-homeserver \
                  /mnt/nas/media \
                  /mnt/nas/music \
                  /mnt/nas/photos \
                  /mnt/nas/video \
                  /mnt/nas/downloads \
                  /mnt/nas/home_video
```

## 7. Backup

Symlink the backup script to run hourly:

```bash
sudo ln -sf /srv/docker/scripts/docker_data_backup.sh /etc/cron.hourly/docker_data_backup
```

This rsyncs `/srv/docker/` to the NAS every hour. Check the log:

```bash
cat /var/log/docker_backup.log
```

## 8. Free Port 53 (for AdGuard)

Follow: https://adguard-dns.io/kb/adguard-home/faq/#bindinuse

## 9. Automatic Updates (optional)

```bash
sudo apt install unattended-upgrades
```
