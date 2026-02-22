#!/bin/bash
set -euo pipefail

# -------------------------
# Configuration
# -------------------------
SRC="/srv/docker/"
DEST="/mnt/nas/backup-homeserver/docker"
LOG="/var/log/docker_backup.log"
EXCLUDE=(
    ".git/"
    "temp/"
    "downloads/"
    ".DS_Store"
    "._*"
    "@eaDir"
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
echo "==== Backup started at $(date) ====" | tee -a "$LOG"
sudo rsync -avh --no-perms --no-owner --no-group -l --delete "${RSYNC_EXCLUDE[@]}" "$SRC" "$DEST/" 2>&1 | tee -a "$LOG"
echo "==== Backup completed at $(date) ====" | tee -a "$LOG"
echo "" | tee -a "$LOG"
