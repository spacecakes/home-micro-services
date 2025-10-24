# Home Micro Services

My Docker and reverse proxy setup for micro-services at home, shared publicly so I can discuss it with friends and get told what I'm doing wrong.

## Helpful commands to remember

### Disk usage

Volumes:

```bash
df -h
```

Top level:

```bash
sudo du -xh --max-depth=1 / 2>/dev/null | sort -rh
```

Look inside this folder and sort:

```bash
sudo du -h -d 1 | sort -h
```

Look inside a particular folder:

```bash
sudo du -sh /mnt/* 2>/dev/null | sort -rh
```

### SSH

Generate a key:

```bash
ssh-keygen -t ed25519 -C "someone@example.com"
```

See public key:

```bash
cat ~/.ssh/id_ed25519.pub
```

Put it in: `~/.ssh/authorized_keys` on host.

See agent keys:

```bash
ssh-add -l
```

### Truncate logs

```bash
sudo find /srv/docker -type f -name "*.log" -exec truncate -s 0 {} \;
```

### Copy files

```bash
sudo rsync -avh --progress --chown=1000:1000 --exclude="#snapshot" /mnt/docker/ /srv/docker/
```

With logging to file:

```bash
sudo rsync -avh --progress --chown=1000:1000 --exclude="#snapshot" /mnt/docker/ /srv/docker/ 2>&1 | tee ~/docker_copy.log
```

Diff dry run after copying:

```bash
rsync -avn --exclude="#snapshot" /mnt/docker/ /srv/docker/
```

### Create Samba share

```bash
sudo apt install samba -y
sudo smbpasswd -a $USER
sudo nano /etc/samba/smb.conf
```

```bash
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

### Create NFS mount

```bash
sudo apt install nfs-common -y
sudo mkdir -p /mnt/nas
sudo mount -t nfs 10.0.1.2:/volume1/docker /mnt/nas
```

Then add a line to `/etc/fstab`:

```bash
10.0.1.2:/volume1/docker  /mnt/nas/docker  nfs  defaults,_netdev  0  0
10.0.1.2:/volume1/media  /mnt/nas/media  nfs  defaults,_netdev  0  0
10.0.1.2:/volume1/music  /mnt/nas/music  nfs  defaults,_netdev  0  0
10.0.1.2:/volume1/video  /mnt/nas/video  nfs  defaults,_netdev  0  0
10.0.1.2:/volume1/photos  /mnt/nas/photos  nfs  defaults,_netdev  0  0
10.0.1.2:/volume1/home_video  /mnt/nas/home_video  nfs  defaults,_netdev  0  0
10.0.1.2:/volume1/downloads  /mnt/nas/downloads  nfs  defaults,_netdev  0  0
```

`systemctl daemon-reload`

Mount all:

```bash
sudo mount -a
```

See local vs mounted:

```bash
mount | grep /mnt
```

Pass down to an LCX container `/etc/pve/lxc/<CTID>.conf`

```bash
mp0: /mnt/nas/docker,mp=/mnt/nas/docker
mp1: /mnt/nas/media,mp=/mnt/nas/media
mp2: /mnt/nas/music,mp=/mnt/nas/music
mp3: /mnt/nas/video,mp=/mnt/nas/video
mp4: /mnt/nas/photos,mp=/mnt/nas/photos
mp5: /mnt/nas/home_video,mp=/mnt/nas/home_video
mp6: /mnt/nas/downloads,mp=/mnt/nas/downloads
```
