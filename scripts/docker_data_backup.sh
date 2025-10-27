#!/bin/bash
set -euo pipefail

# -------------------------
# Configuration
# -------------------------
SRC="/srv/docker/data/"
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
sudo rsync -avh --no-perms --no-owner --no-group -l --delete "${RSYNC_EXCLUDE[@]}" "$SRC" "$DEST" >> "$LOG" 2>&1
echo "==== Backup completed at $(date) ====" >> "$LOG"
echo "" >> "$LOG"
