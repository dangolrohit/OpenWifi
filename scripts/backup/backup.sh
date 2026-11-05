#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/var/backups/wifirouter"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ARCHIVE="$BACKUP_DIR/wifirouter_backup_$TIMESTAMP.tar.gz"

echo "Creating WiFiRouter backup at $ARCHIVE..."
mkdir -p "$BACKUP_DIR"

tar -czf "$ARCHIVE" \
  --exclude="*.log" \
  /var/lib/wifirouter \
  /etc/NetworkManager/dnsmasq-shared.d 2>/dev/null || true

echo "Backup created successfully: $ARCHIVE"
