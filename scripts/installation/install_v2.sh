#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo "  WiFiRouter V2 — Production Gateway Installation"
echo "============================================================"

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root: sudo bash scripts/installation/install_v2.sh"
  exit 1
fi

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT_DIR"

# 1. Dependency checks
echo "[1/6] Checking system tools..."
for bin in python3 nft ip systemctl curl; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "Missing required system binary: $bin"
    exit 1
  fi
done

# Check Docker and Docker Compose
if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
fi

# 2. Check Interface configuration
echo "[2/6] Verifying network interfaces..."
if ! ip -4 address show enp1s0 | grep -q 'inet 192.168.16.2/24'; then
  echo "Warning: enp1s0 is not configured at 192.168.16.2/24. Please verify NetworkManager profile."
fi

# 3. Setup directories & permissions
echo "[3/6] Setting up state directories..."
install -d -m 750 /var/lib/wifirouter
install -d -m 750 /var/lib/wifirouter/snapshots
install -d -m 755 /etc/NetworkManager/dnsmasq-shared.d

# Enable dnsmasq query logging
cat > /etc/NetworkManager/dnsmasq-shared.d/01-activity-log.conf <<'CONF'
log-queries
log-facility=/var/log/dnsmasq.log
CONF
touch /var/log/dnsmasq.log /var/log/oshin-dns.log
chmod 666 /var/log/dnsmasq.log /var/log/oshin-dns.log

# 4. Migrate & Transition Legacy Configuration
if [ -f /var/lib/oshin-firewall/blocked.json ]; then
  echo "Migrating legacy firewall state..."
  cp -a /var/lib/oshin-firewall/. /var/lib/wifirouter/ 2>/dev/null || true
fi

# Stop and disable legacy V1 portal service to free port 8090
if systemctl list-unit-files | grep -q 'oshin-dashboard.service'; then
  echo "Stopping and disabling legacy oshin-dashboard service..."
  systemctl stop oshin-dashboard 2>/dev/null || true
  systemctl disable oshin-dashboard 2>/dev/null || true
fi

# Free port 8090 if still held by any lingering process
if command -v fuser >/dev/null 2>&1; then
  fuser -k 8090/tcp 2>/dev/null || true
fi

# Generate or load persistent agent secret key
install -d -m 750 /etc/wifirouter
if [ ! -f /etc/wifirouter/agent.key ]; then
  python3 -c "import secrets; print(secrets.token_hex(16))" > /etc/wifirouter/agent.key
  chmod 600 /etc/wifirouter/agent.key
fi
AGENT_SECRET_KEY=$(tr -d '\r\n' < /etc/wifirouter/agent.key)

# 5. Install Network Agent as host systemd service
echo "[4/6] Installing WiFiRouter Network Agent systemd unit..."
install -d -m 755 /opt/wifirouter
cp -rf "$ROOT_DIR/network-agent" /opt/wifirouter/
cat > /etc/systemd/system/wifirouter-agent.service <<SERVICE
[Unit]
Description=WiFiRouter Linux Network Management Agent
After=network.target NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/wifirouter/network-agent
ExecStart=/usr/bin/python3 -m agent.main
Restart=on-failure
RestartSec=5
KillMode=mixed
TimeoutStopSec=10
Environment="PYTHONUNBUFFERED=1"
Environment="WIFIROUTER_AGENT_HOST=0.0.0.0"
Environment="WIFIROUTER_AGENT_PORT=8091"
Environment="WIFIROUTER_AGENT_SECRET=${AGENT_SECRET_KEY}"
Environment="WIFIROUTER_LAN_IFACE=enp1s0"
Environment="WIFIROUTER_WAN_IFACE=wlp2s0"

[Install]
WantedBy=multi-user.target
SERVICE
systemctl daemon-reload
systemctl enable --now wifirouter-agent.service
systemctl restart wifirouter-agent.service

# 6. Launch Docker Compose Stack
echo "[5/6] Starting application services with Docker Compose..."
if [ ! -f .env ]; then
  cp .env.example .env
fi
# Sync secret and database hostname in .env
sed -i 's/@localhost:5432/@postgres:5432/g' .env 2>/dev/null || true
sed -i "s|^WIFIROUTER_AGENT_SECRET=.*|WIFIROUTER_AGENT_SECRET=${AGENT_SECRET_KEY}|g" .env 2>/dev/null || true

docker compose pull || true
docker compose up -d --build

# 7. Verification
echo "[6/6] Verifying service health..."
sleep 5
for attempt in {1..15}; do
  if curl -sf http://127.0.0.1:8090/health >/dev/null 2>&1 || curl -sf http://192.168.16.2:8090/health >/dev/null 2>&1; then
    echo "WiFiRouter V2 Backend is healthy!"
    break
  fi
  sleep 2
done

echo "============================================================"
echo "  Installation Successful!"
echo "  Administration Portal: http://192.168.16.2:8090"
echo "  Default Username:      admin"
echo "  Default Password:      admin12345678"
echo "============================================================"
