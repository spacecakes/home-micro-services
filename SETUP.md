# Ubuntu Server Bare-Metal Setup Guide

## 1. Installation

Flash Ubuntu Server 24.04 LTS (or 22.04 for stability) to a USB drive.

During installation:

- Enable OpenSSH server
- Set hostname (e.g., `home-server`)
- Choose your main SSD/NVMe as the install target
- Skip Snap packages (you'll use Docker instead)

After installation, reboot and SSH in from another machine:

```bash
ssh gabriel@home-server.local
```

## 2. Basic Setup

Update the system and install essential packages:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install htop curl git vim nfs-common
```

Optionally, set your timezone:

```bash
sudo timedatectl set-timezone Europe/Stockholm
```

## 3. Mount NAS Shares

Edit `/etc/fstab`:

```bash
sudo nano /etc/fstab
```

Add the following NFS mount entries:

```fstab
10.0.1.2:/volume1/media      /mnt/nas/media      nfs defaults,_netdev 0 0
10.0.1.2:/volume1/music      /mnt/nas/music      nfs defaults,_netdev 0 0
10.0.1.2:/volume1/photos     /mnt/nas/photos     nfs defaults,_netdev 0 0
10.0.1.2:/volume1/video      /mnt/nas/video      nfs defaults,_netdev 0 0
10.0.1.2:/volume1/docker     /mnt/nas/docker     nfs defaults,_netdev 0 0
10.0.1.2:/volume1/downloads  /mnt/nas/downloads  nfs defaults,_netdev 0 0
10.0.1.2:/volume1/home_video /mnt/nas/home_video nfs defaults,_netdev 0 0
```

Create mount points and mount all shares:

```bash
sudo mkdir -p /mnt/nas/{media,music,photos,video,home_video,docker,downloads}
sudo mount -a
```

Verify the mounts:

```bash
df -h | grep nas
```

## 4. Install Docker and Docker Compose

Install Docker's prerequisites and add the official repository:
https://docs.docker.com/engine/install/ubuntu/

Enable and start Docker:

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

Add your user to the Docker group (requires re-login to take effect):

```bash
sudo usermod -aG docker $USER
```

**Note:** Log out and back in for the group change to take effect.

## 5. Organize Docker data

Create directories for Docker containers:

```bash
sudo mkdir -p /srv/docker/{plex,sonarr,radarr,downloads} # add more as needed
```

Each container gets its own folder under `/srv/docker/<name>`.

**Example structure:**

- `/srv/docker/plex/config`
- `/srv/docker/plex/transcode`

## 6. Configure env vars and run compose

Edit `.env` to add required variables for the compose file. Start containers:

```bash
docker compose up -d
```

Verify it's running:

```bash
docker ps
```

## 7. Misc settings

Follow this guide to free port 53 on Ubuntu: https://adguard-dns.io/kb/adguard-home/faq/#bindinuse

### Automatic System Updates (optional)

Enable unattended upgrades for security patches:

```bash
sudo apt install unattended-upgrades
```

## 8. Backup Strategy

Add `docker-data-backup.sh` as hourly cron job:

```bash
sudo crontab -e
```

```cron
sudo cp /srv/docker/compose/scripts/docker_data_backup.sh /etc/cron.hourly/docker_data_backup
```

Test run it:

```bash
sudo run-parts /etc/cron.hourly
```