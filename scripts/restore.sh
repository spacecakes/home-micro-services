#!/bin/bash
set -euo pipefail

DOCKER_DIR="/srv/docker"
NAS_ADDR="10.0.1.2"
NAS_PATH="/volume1/backup-homeserver/docker"
EXCLUDES=(--exclude .git/)

echo "=== Restore from NAS backup ==="
echo "Source:      ${NAS_ADDR}:${NAS_PATH}/"
echo "Destination: ${DOCKER_DIR}/"
echo ""

# Check nfs-common
if ! command -v mount.nfs &>/dev/null; then
    echo "Error: nfs-common is not installed. Run: sudo apt install nfs-common"
    exit 1
fi

# Test NAS reachability
if ! ping -c1 -W2 "$NAS_ADDR" &>/dev/null; then
    echo "Error: NAS ($NAS_ADDR) is not reachable"
    exit 1
fi

# Mount NFS temporarily
MOUNT_DIR=$(mktemp -d)
trap 'sudo umount "$MOUNT_DIR" 2>/dev/null; rmdir "$MOUNT_DIR"' EXIT

echo "Mounting NFS share..."
sudo mount -t nfs -o soft,timeo=50,vers=4.1,noatime "${NAS_ADDR}:${NAS_PATH}" "$MOUNT_DIR"

echo "Starting rsync..."
rsync -avh --no-perms --no-owner --no-group -l --delete \
    "${EXCLUDES[@]}" \
    "$MOUNT_DIR/" "$DOCKER_DIR/"

echo ""
echo "=== Restore complete ==="
