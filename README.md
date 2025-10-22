# Home Micro Services

My Docker and reverse proxy setup for micro-services at home, shared publicly so I can discuss it with friends and get told what I'm doing wrong.

## Helpful commands to remember

### Generate a key

```bash
ssh-keygen -t ed25519 -C "someone@example.com"
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
[share]
   path = /home/YOURUSER
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
sudo mount -t nfs nas-ip:/volume1/docker /mnt/nas
```

Then add a line to `/etc/fstab`:

```bash
<some-ip>:/volume1/docker /mnt/nas nfs defaults 0 0
```
