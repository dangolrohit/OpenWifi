# WiFiRouter — OshinWiFi Admin Portal

Configured for Ubuntu, Python 3, enp1s0=192.168.16.2/24, upstream wlp2s0,
BL-WR450H AP=192.168.16.1. No router firmware changes. No pip packages needed.

## Update your installed version

Clone the source once on the Ubuntu gateway:

```bash
cd ~
git clone https://github.com/dangolrohit/WiFiRouter.git
cd ~/WiFiRouter
sudo bash update.sh
```

For later updates:

```bash
cd ~/WiFiRouter
git pull --ff-only && sudo bash update.sh
```

Do not rerun install.sh on an existing installation. `git pull` updates the
checkout; `update.sh` installs the checked-out web application and restarts it.
Clone and pull as your normal user, not with sudo. The update script currently
updates portal files only; changes to firewall helpers or system services would
need a separate migration. Internet access does not depend on the portal running.

The updater preserves credentials, certificate, firewall helper, and block list.
It backs up the previous application, checks the login page over HTTPS, and
restores the previous code if that check fails.

Open **https://192.168.16.2:8090**. Unauthenticated visits redirect to a real
login page. Sign in as **admin** using your existing password. There is no Basic
Auth popup. Logout revokes the server-side session. Cookies are Secure, HttpOnly,
and SameSite=Strict. Sessions expire after 30 idle minutes or 8 total hours and
are cleared on service restart. State-changing requests use CSRF protection.
Five failed login attempts per minute per source address trigger rate limiting.

## New installation

Run `sudo bash install.sh` and choose a password. The portal uses HTTPS with a
local self-signed certificate. Verify the SHA-256 fingerprint printed by the
installer before accepting the browser certificate warning. Keep the portal
private; do not expose it to the public internet.

## Pages in version 2

- Dashboard: discovered addresses, blocked count, gateway information.
- Wifi Settings: configured network details and link to the router admin UI.
  Direct SSID/password editing requires a router integration not yet provided.
- Connected Device: discovered IP/MAC addresses, search, block/unblock.
- Device Filtering: current blocked addresses and unblock controls.
- Usages: real aggregate enp1s0 RX/TX counters and average rate between refreshes;
  includes local traffic, not per-user internet totals. No monthly history yet.
- User Logs: last 300 admin sign-in/out and filtering events in memory; resets
  at service restart. This is not website/request logging.
- Settings: browser-local automatic refresh preference and configuration details.
- Logout: invalidates the current session and returns to the login page.

## What it does

- Password-protected device list drawn from Ubuntu's IPv4 neighbour cache.
- IPv4 block/unblock for selected addresses. Changes persist across reboot.
- Blocks both incoming and outgoing forwarded IPv4 packets for the selected
  address on enp1s0. Applies to all routed destinations, including the upstream LAN.
- Blocks stop internet traffic, not Wi-Fi association or same-subnet local traffic.
- The admin's current client IP cannot block itself through the UI.
- No per-device bandwidth history, hostnames, speed limits or captive portal in this version.

Devices appear after they exchange traffic with the gateway. The list is not a
definitive list of Wi-Fi connections. STALE is a neighbour-cache state, not proof
a device is offline. Refresh manually. Blocks are by IP, not durable device
identity: changes of address bypass them, and reassigned addresses inherit a
block. Review/remove old blocks. IPv6 is not controlled by this version; keep the
current downstream profile's IPv6 disabled. No transparent proxy or inspection
of browsing contents is installed.

## How privilege and firewall changes work

The web server runs as the dedicated unprivileged oshin-dashboard account. It
can call only the root-owned /usr/local/sbin/oshin-fw helper via sudo. The helper
accepts status, restore, block, unblock and tightly validated client IPv4 addresses
in 192.168.16.3–254; it does not execute shell input. The helper changes only the
inet oshin_dashboard table. Existing iptables/NAT/Docker/Tailscale rules are
retained. Its forward hook has priority -10; packets not blocked continue through
the existing firewall. Rules are changed in an atomic nft transaction.

Configuration: /etc/oshin-dashboard (password hash, TLS certificate/key).
Root-only block list: /var/lib/oshin-firewall/blocked.json.
Application: /opt/oshin-dashboard/ (Python, HTML, JS, CSS).
Services: oshin-dashboard.service and oshin-firewall.service.
The installer refuses to overwrite an existing installation/account.

## Validate on your laptop

1. Confirm the dashboard loads and mobile internet still works.
2. Open the dashboard on Ubuntu, refresh, and find the phone's IP (previously
   192.168.16.103; verify it on the phone before selecting).
3. Turn mobile data off on the phone. Block its IP from Ubuntu and try a new
   website or refresh a page. Cached pages are not a valid test.
4. Unblock it; verify browsing works again.
5. Confirm existing Docker services and Tailscale access still work.
6. After a planned reboot, check the dashboard and Wi-Fi internet again.

Local automated tests validate address boundaries, generated rule scope, helper
input rejection, authentication, session expiry/rotation/logout, CSRF enforcement, and self-block prevention.
They do not verify real packet forwarding on your laptop. Those checks require
the steps above. Existing firewall managers that flush all tables could remove
this application's rules; the dashboard reports missing/out-of-sync rules.

## Troubleshooting and emergency unblock

If a block needs clearing from the Ubuntu terminal:

```bash
sudo /usr/local/sbin/oshin-fw unblock 192.168.16.103
```

If the service or rules need inspection:

```bash
sudo systemctl status oshin-dashboard oshin-firewall --no-pager
sudo journalctl -u oshin-dashboard -n 40 --no-pager
sudo nft list table inet oshin_dashboard
```

If another tool removed the dedicated firewall table:

```bash
sudo systemctl restart oshin-firewall
```

If access is blocked by an existing host firewall, do not disable it globally;
inspect it and add a scoped rule for enp1s0/192.168.16.0/24 TCP 8090 if needed.
The installer deliberately does not change host INPUT policies.

## Remove

These commands remove only this dashboard and its access blocks; NetworkManager
sharing remains configured. They also discard the dashboard password and TLS key.

```bash
sudo systemctl disable --now oshin-dashboard oshin-firewall
sudo nft delete table inet oshin_dashboard
sudo rm -f /etc/systemd/system/oshin-dashboard.service /etc/systemd/system/oshin-firewall.service
sudo rm -f /etc/sudoers.d/oshin-dashboard /usr/local/sbin/oshin-fw
sudo rm -rf /opt/oshin-dashboard /etc/oshin-dashboard /var/lib/oshin-firewall
sudo userdel oshin-dashboard
sudo systemctl daemon-reload
```

An already missing table can produce an error during removal; that does not
affect other firewall tables. If installation stops partway through, retain the
error output and complete removal before retrying.
