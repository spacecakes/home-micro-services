# Home Micro-Services VM Setup Guide

This guide describes how to configure a clean, modular Ubuntu Server VM for Docker workloads with a dedicated data volume and NFS media mounts.
It’s optimized for Proxmox, local disks, and Synology NAS shares.

---

## 1. VM Layout Overview

| Purpose                   | Mount Path                                     | Location                | Notes                      |
| ------------------------- | ---------------------------------------------- | ----------------------- | -------------------------- |
| System + Docker engine    | `/`                                            | Main VM disk (32–64 GB) | OS + config only           |
| Persistent container data | `/srv/docker`                                  | Secondary SSD/HDD       | Preserved between rebuilds |
| Media + downloads         | `/mnt/media`, `/mnt/music`, `/mnt/video`, etc. | NFS from NAS            | Shared with Synology       |

This separation keeps your VM flexible — you can rebuild or migrate it anytime without touching data.

---

## 2. Initial Ubuntu Setup

Install Ubuntu Server (preferably 22.04 or 24.04 LTS).

Create a user (e.g., `gabriellundmark`) — this user will own most Docker data.

Update the system:

```bash
sudo apt update && sudo apt upgrade -y
```

Install essential tools and QEMU guest agent (for Proxmox):

```bash
sudo apt install -y ca-certificates curl nfs-common cifs-utils qemu-guest-agent
```

Enable QEMU guest agent:

```bash
sudo systemctl enable qemu-guest-agent
sudo systemctl start qemu-guest-agent
```

Install Docker using the official repository:

```bash
# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package index and install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Enable Docker:

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

Add your user to the docker group to run Docker without sudo:

```bash
sudo usermod -aG docker $USER
# Log out and back in for this to take effect
```

---

## 3. Add and Mount the Docker Data Volume

In Proxmox, attach a second disk (e.g., 64 GB or more) to the VM.

Inside Ubuntu, find and format it:

```bash
sudo fdisk -l
sudo mkfs.ext4 /dev/sdb
```

Mount it:

```bash
sudo mkdir -p /srv/docker
sudo blkid /dev/sdb
```

Add it to `/etc/fstab`:

```bash
# Example line to add (replace <your-uuid> with actual UUID)
UUID=<your-uuid> /srv/docker ext4 defaults 0 2
```

Mount and set permissions:

```bash
sudo mount -a
sudo chown -R 1000:1000 /srv/docker
```

Now `/srv/docker` is ready for persistent container data.

---

## 4. Docker Directory Structure

Compose project in home directory:

```
~/home-micro-services/
├── docker-compose.yml
├── .env
└── config/
```

All container data volumes go inside `/srv/docker` on second disk.

```yaml
volumes:
  - /srv/docker/jellyfin/config:/config
```

Actual own data goes into NFS mounts under `/mnt/media` etc.

---

## 5. PUID/PGID and Permissions

Use `PUID=1000` and `PGID=1000` for containers running as your main user.

This ensures they can read/write `/srv/docker`.

For NFS mounts from Synology:

- Keep their original PUID/PGID if the NAS controls permissions.
- For local data (`/srv/docker`), always use your Ubuntu user’s UID/GID.

To check:

```bash
id
# uid=1000(gabriellundmark) gid=1000(gabriellundmark)
```

---

## 6. NFS Mounts (Synology Shares)

Example for `/etc/fstab`:

```bash
10.0.1.2:/volume1/media      /mnt/media      nfs  defaults,nofail  0 0
10.0.1.2:/volume1/music      /mnt/music      nfs  defaults,nofail  0 0
10.0.1.2:/volume1/video      /mnt/video      nfs  defaults,nofail  0 0
10.0.1.2:/volume1/downloads  /mnt/downloads  nfs  defaults,nofail  0 0
```

Then mount all:

```bash
sudo mkdir -p /mnt/{media,music,video,downloads}
sudo mount -a
```

---

## 7. Copy Data from Synology (Optional Migration)

If you previously ran containers on Synology, use rsync to migrate their data:

```bash
rsync -avh --progress /path/to/synology/data/ /srv/docker/
```

Do not use `-a` if you intentionally want to reset ownerships to your new local user:

```bash
rsync -rvh --progress --chown=1000:1000 /path/to/synology/data/ /srv/docker/
```

---

## 8. Snapshot & Backup Strategy

Before any major change:

```bash
# Create VM snapshot in Proxmox
qm snapshot 102 "before-copy" --description "Pre rsync state"
```

If you see warnings like:

```
Sum of all thin volume sizes exceeds thin pool
```

your Proxmox storage is nearly full.
You can safely ignore this temporarily, but avoid too many snapshots.

---

## 9. VM Recreation Plan (Smaller + Cleaner Setup)

### Step 1: Stop and Backup

```bash
docker compose down
sync
tar czf ~/compose-backup.tar.gz ~/home-micro-services
```

### Step 2: Detach Data Volume

In Proxmox → VM → Hardware → Hard Disk (scsi1) → Detach → Remove → “Keep Disk”.

### Step 3: Create New VM

Set smaller root disk (e.g., 32 GB).
Install Ubuntu again.
Reattach old `/srv/docker` disk (Add → Existing Disk).

### Step 4: Mount and Fix Permissions

```bash
sudo blkid
sudo mkdir -p /srv/docker
sudo nano /etc/fstab   # add UUID line
sudo mount -a
sudo chown -R 1000:1000 /srv/docker
```

### Step 5: Restore Docker Setup

```bash
# Install Docker using official repository (see section 2 for full commands)
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Restore compose files and start services
tar xzf ~/compose-backup.tar.gz -C ~/
cd ~/home-micro-services
docker compose up -d
```

---

## 10. Verification Checklist

Run these to confirm everything’s clean:

```bash
df -h
ls /srv/docker
docker ps
mount | grep nfs
```

---

## 11. Summary

| Component              | Where                   | Notes                      |
| ---------------------- | ----------------------- | -------------------------- |
| Ubuntu system files    | `/`                     | 32–64 GB root disk         |
| Container data         | `/srv/docker`           | Separate volume, preserved |
| Compose configs        | `~/home-micro-services` | Easy backup                |
| Media mounts           | `/mnt/*`                | NFS from NAS               |
| User ID for containers | `1000:1000`             | Matches your Ubuntu user   |
