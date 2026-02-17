#!/bin/bash
set -euo pipefail

# -------------------------
# Configuration
# -------------------------
SRC_DIRS=(
    "/srv/docker/stack-infra/data/"
    "/srv/docker/stack-media/data/"
    "/srv/docker/stack-dns/data/"
    "/srv/docker/stack-home/data/"
    "/srv/docker/stack-immich/data/"
)
DEST="/mnt/nas/backup-homeserver/docker_data"
LOG="/var/log/docker_data_backup.log"
EXCLUDE=(
    "/temp/*"
    "/downloads/*"
)

# -------------------------
# Build rsync exclude options
# -------------------------
RSYNC_EXCLUDE=()
for e in "${EXCLUDE[@]}"; do
    RSYNC_EXCLUDE+=(--exclude="$e")
done

# -------------------------
# Perform the backup
# -------------------------
echo "==== Backup started at $(date) ====" >> "$LOG"
for SRC in "${SRC_DIRS[@]}"; do
    if [ -d "$SRC" ]; then
        STACK_NAME=$(basename "$(dirname "$SRC")")
        echo "-- Backing up $STACK_NAME --" >> "$LOG"
        sudo rsync -avh --no-perms --no-owner --no-group -l --delete "${RSYNC_EXCLUDE[@]}" "$SRC" "$DEST/$STACK_NAME/" >> "$LOG" 2>&1
    fi
done
echo "==== Backup completed at $(date) ====" >> "$LOG"
echo "" >> "$LOG"
