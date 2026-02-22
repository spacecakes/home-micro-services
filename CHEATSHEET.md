# Cheatsheet

## Disk Usage

```bash
df -h                                            # mounted volumes
sudo du -xh --max-depth=1 / 2>/dev/null | sort -rh  # top-level breakdown
sudo du -h -d 1 | sort -h                       # current directory breakdown
sudo du -sh /mnt/* 2>/dev/null | sort -rh        # NAS mount sizes
```

## SSH

```bash
ssh-keygen -t ed25519 -C "someone@example.com"   # generate key
cat ~/.ssh/id_ed25519.pub                        # view public key
ssh-add -l                                       # list agent keys
```

Add the public key to `~/.ssh/authorized_keys` on the remote host.

## Docker Logs

```bash
sudo find /srv/docker -type f -name "*.log" -exec truncate -s 0 {} \;
```

## Rsync

Copy from NAS to local:

```bash
sudo rsync -avh --progress --chown=1000:1000 --exclude="#snapshot" /mnt/docker/ /srv/docker/
```

With logging:

```bash
sudo rsync -avh --progress --chown=1000:1000 --exclude="#snapshot" /mnt/docker/ /srv/docker/ 2>&1 | tee ~/docker_copy.log
```

Dry-run diff:

```bash
rsync -avn --exclude="#snapshot" /mnt/docker/ /srv/docker/
```

## Samba

```bash
sudo apt install samba -y
sudo smbpasswd -a $USER
```

Add shares to `/etc/samba/smb.conf`:

```ini
[home]
   path = /home/gabriel
   read only = no
   browsable = yes
   guest ok = no

[docker]
   path = /srv/docker
   read only = no
   browsable = yes
   guest ok = no
```

```bash
sudo systemctl restart smbd
```

## NFS

```bash
sudo apt install nfs-common -y
sudo mkdir -p /mnt/nas
sudo mount -a
mount | grep /mnt
```

See `fstab.example` for the mount entries.

## Proxmox LXC Passthrough

Pass NAS mounts to an LXC container in `/etc/pve/lxc/<CTID>.conf`:

```
mp0: /mnt/nas/docker,mp=/mnt/nas/docker
mp1: /mnt/nas/media,mp=/mnt/nas/media
mp2: /mnt/nas/music,mp=/mnt/nas/music
mp3: /mnt/nas/video,mp=/mnt/nas/video
mp4: /mnt/nas/photos,mp=/mnt/nas/photos
mp5: /mnt/nas/home_video,mp=/mnt/nas/home_video
mp6: /mnt/nas/downloads,mp=/mnt/nas/downloads
```
