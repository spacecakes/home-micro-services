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

On the remote host:

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "your-public-key-content" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

## Docker Stacks

```bash
# Stop all stacks
for d in stack-*/; do [ "$d" = "stack-nas/" ] && continue; (cd "$d" && docker compose down); done

# Start all stacks but nas (infra and auth first)
for d in stack-infra stack-auth; do (cd "$d" && docker compose up -d); done
for d in stack-*/; do [ "$d" = "stack-nas/" ] && continue; (cd "$d" && docker compose up -d); done
```

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

NFS shares are mounted via Docker NFS volumes (defined in each stack's `docker-compose.yml`). No host fstab needed.

```bash
docker volume ls | grep nfs-           # list NFS volumes
docker volume inspect nfs-media        # inspect a volume
```

The host still needs `nfs-common` for the kernel NFS client.

## Proxmox LXC

Docker NFS volumes mount directly inside the LXC — no host-side NAS passthrough needed. The LXC just needs to be **privileged** (for NFS kernel access) and have `nfs-common` installed.

Keep `/srv/docker` inside the LXC rootfs (no bind mount) so Proxmox Backup Server includes it in snapshots. The hourly rsync to the NAS provides a second backup.
