#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [ "$EUID" -ne 0 ]; then echo 'Run: sudo bash update.sh'; exit 1; fi
if [ ! -f /opt/oshin-dashboard/web.py ] || [ ! -f /etc/oshin-dashboard/auth.json ]; then echo 'Existing installation not found. Use install.sh for a new installation.'; exit 1; fi
python3 - <<'PY'
from pathlib import Path
compile(Path('web.py').read_text(),'web.py','exec')
compile(Path('helper.py').read_text(),'helper.py','exec')
for name in ['portal.html','login.html','app.js','style.css','helper.py']:
    if not Path(name).is_file():raise SystemExit('Missing file: '+name)
PY
backup_dir=$(mktemp -d /opt/oshin-dashboard-backup.XXXXXX)
cp -a /opt/oshin-dashboard/. "$backup_dir/"
if [ -f /usr/local/sbin/oshin-fw ]; then
  cp -a /usr/local/sbin/oshin-fw "$backup_dir/oshin-fw.bak"
fi
rollback(){
  echo "Update failed; restoring previous files from $backup_dir"
  cp -a "$backup_dir/." /opt/oshin-dashboard/
  if [ -f "$backup_dir/oshin-fw.bak" ]; then
    cp -a "$backup_dir/oshin-fw.bak" /usr/local/sbin/oshin-fw
  fi
  systemctl restart oshin-dashboard || true
}
trap rollback ERR
systemctl stop oshin-dashboard

# Enable dnsmasq query logging for Wi-Fi client activity
install -d -m 755 /etc/NetworkManager/dnsmasq-shared.d
cat > /etc/NetworkManager/dnsmasq-shared.d/01-activity-log.conf <<'CONF'
log-queries
log-facility=/var/log/dnsmasq.log
CONF
touch /var/log/dnsmasq.log /var/log/oshin-dns.log
chmod 666 /var/log/dnsmasq.log /var/log/oshin-dns.log

# Kill stale dnsmasq and restart NetworkManager so logging activates immediately
pkill -f 'dnsmasq.*dnsmasq-shared' 2>/dev/null || true
if systemctl is-active --quiet NetworkManager; then
  systemctl restart NetworkManager || true
fi

install -m 755 helper.py /usr/local/sbin/oshin-fw
install -o root -g root -m 644 web.py portal.html login.html app.js style.css /opt/oshin-dashboard/
systemctl start oshin-dashboard
python3 - <<'PY'
import ssl,time,urllib.request
context=ssl._create_unverified_context()
for attempt in range(10):
    try:
        with urllib.request.urlopen('https://192.168.16.2:8090/login',context=context,timeout=3) as r:
            if r.status==200 and b'id="login-form"' in r.read():break
    except Exception:
        time.sleep(1)
else:raise SystemExit('Login health check failed')
PY
trap - ERR
echo 'Portal updated. Open https://192.168.16.2:8090 and sign in with your existing admin password.'
echo "Previous application files saved in: $backup_dir"
echo 'The firewall helper, activity logger, block list, credentials, and TLS certificates were preserved.'
