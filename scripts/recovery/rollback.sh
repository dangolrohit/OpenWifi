#!/usr/bin/env bash
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root: sudo bash scripts/recovery/rollback.sh"
  exit 1
fi

echo "============================================================"
echo "  WiFiRouter Emergency Network Rollback"
echo "============================================================"

# Revert nftables ruleset safely without touching other tables
if command -v nft >/dev/null 2>&1; then
  echo "Flushing only WiFiRouter dedicated tables..."
  nft delete table inet wifirouter 2>/dev/null || true
  nft delete table inet oshin_dashboard 2>/dev/null || true
fi

# Reset traffic shaping queue disciplines on LAN interface
if command -v tc >/dev/null 2>&1; then
  echo "Resetting tc qdisc on enp1s0..."
  tc qdisc del dev enp1s0 root 2>/dev/null || true
fi

echo "Restarting NetworkManager to restore baseline connectivity..."
systemctl restart NetworkManager || true

echo "Rollback completed. Network baseline restored."

