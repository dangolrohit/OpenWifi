#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [ "$EUID" -ne 0 ]; then
  echo 'Run: sudo bash install.sh'
  exit 1
fi
for binary in python3 nft ip sudo visudo openssl systemctl useradd install; do
  command -v "$binary" >/dev/null || { echo "Missing required command: $binary"; exit 1; }
done
if [ -e /opt/oshin-dashboard ] || id oshin-dashboard >/dev/null 2>&1; then
  echo 'An installation or oshin-dashboard account already exists. Stop here; see README.md.'
  exit 1
fi
if ! ip -4 address show enp1s0 | grep -q 'inet 192.168.16.2/24'; then
  echo 'Expected enp1s0 at 192.168.16.2/24. Activate blink-setup first.'
  exit 1
fi
python3 - <<'PY'
import socket
with socket.socket() as s:
    s.bind(('192.168.16.2',8090))
PY
echo 'Installing OshinWiFi dashboard for enp1s0 / 192.168.16.0/24.'
echo 'This creates two services, a restricted helper, and a separate nftables table.'
echo 'Existing firewall rules and NetworkManager profiles are not rewritten.'
useradd --system --user-group --home-dir /nonexistent --shell /usr/sbin/nologin oshin-dashboard
install -d -m 755 /opt/oshin-dashboard
install -d -m 750 -o root -g oshin-dashboard /etc/oshin-dashboard
install -d -m 700 /var/lib/oshin-firewall
install -d -m 755 /etc/NetworkManager/dnsmasq-shared.d
cat > /etc/NetworkManager/dnsmasq-shared.d/01-activity-log.conf <<'CONF'
log-queries
log-facility=/var/log/dnsmasq.log
CONF
touch /var/log/dnsmasq.log /var/log/oshin-dns.log
chmod 666 /var/log/dnsmasq.log /var/log/oshin-dns.log
pkill -f 'dnsmasq.*dnsmasq-shared' 2>/dev/null || true
if systemctl is-active --quiet NetworkManager; then
  systemctl restart NetworkManager || true
fi
install -m 644 web.py portal.html login.html guest.html app.js style.css /opt/oshin-dashboard/
install -m 755 helper.py /usr/local/sbin/oshin-fw
python3 - <<'PY'
import getpass,hashlib,json,os,secrets
from pathlib import Path
while True:
    password=getpass.getpass('Choose dashboard admin password (at least 12 characters): ')
    if len(password)<12:
        print('Use at least 12 characters.');continue
    if password!=getpass.getpass('Repeat password: '):
        print('Passwords do not match.');continue
    break
salt=secrets.token_bytes(32)
path=Path('/etc/oshin-dashboard/auth.json')
path.write_text(json.dumps({'salt':salt.hex(),'hash':hashlib.pbkdf2_hmac('sha256',password.encode(),salt,200000).hex()}))
os.chmod(path,0o640)
PY
chown root:oshin-dashboard /etc/oshin-dashboard/auth.json
openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
  -keyout /etc/oshin-dashboard/key.pem -out /etc/oshin-dashboard/cert.pem \
  -subj '/CN=OshinWiFi local dashboard' -addext 'subjectAltName=IP:192.168.16.2' 2>/dev/null
chown root:oshin-dashboard /etc/oshin-dashboard/key.pem /etc/oshin-dashboard/cert.pem
chmod 640 /etc/oshin-dashboard/key.pem /etc/oshin-dashboard/cert.pem
sudoers_tmp=$(mktemp)
trap 'rm -f "$sudoers_tmp"' EXIT
cat > "$sudoers_tmp" <<'RULE'
oshin-dashboard ALL=(root) NOPASSWD: /usr/local/sbin/oshin-fw
RULE
visudo -cf "$sudoers_tmp"
install -m 440 "$sudoers_tmp" /etc/sudoers.d/oshin-dashboard
cat > /etc/systemd/system/oshin-firewall.service <<'UNIT'
[Unit]
Description=OshinWiFi independent access rules
After=network-pre.target
Before=oshin-dashboard.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/oshin-fw restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/oshin-dashboard.service <<'UNIT'
[Unit]
Description=OshinWiFi private LAN dashboard
Wants=network-online.target
Requires=oshin-firewall.service
After=network-online.target oshin-firewall.service
StartLimitIntervalSec=0

[Service]
User=oshin-dashboard
Group=oshin-dashboard
ExecStart=/usr/bin/python3 -I /opt/oshin-dashboard/web.py
Restart=on-failure
RestartSec=5
UMask=0077
ProtectSystem=strict
ReadWritePaths=/var/lib/oshin-firewall
ProtectHome=yes
PrivateTmp=yes
# The restricted sudo helper requires setuid; do not set NoNewPrivileges here.

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now oshin-firewall.service oshin-dashboard.service
sudo -u oshin-dashboard sudo -n /usr/local/sbin/oshin-fw status
echo
echo 'Installed. Open https://192.168.16.2:8090 on Ubuntu or OshinWiFi.'
echo 'Username: admin. Use the password you just chose.'
echo 'The local HTTPS certificate is self-signed, so a browser warning is expected.'
openssl x509 -in /etc/oshin-dashboard/cert.pem -noout -fingerprint -sha256
echo 'See README.md for testing, emergency unblock, and removal.'
