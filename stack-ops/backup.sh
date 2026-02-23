#!/bin/sh
set -eu

# -------------------------
# Configuration
# -------------------------
SRC="/source/"
DEST="/destination/"
EXCLUDE="
    .git/
    temp/
    downloads/
    .DS_Store
    ._*
    @eaDir
"

# -------------------------
# Build rsync exclude options
# -------------------------
RSYNC_EXCLUDE=""
for e in $EXCLUDE; do
    RSYNC_EXCLUDE="$RSYNC_EXCLUDE --exclude=$e"
done

# -------------------------
# Perform the backup
# -------------------------
echo "==== Backup started at $(date -Iseconds) ===="
# shellcheck disable=SC2086
rsync -avh --no-perms --no-owner --no-group -l --delete $RSYNC_EXCLUDE "$SRC" "$DEST"
echo "==== Backup completed at $(date -Iseconds) ===="
