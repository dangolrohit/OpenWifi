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

## Pages in version 2.3

- Dashboard: overview of total discovered devices, family devices, isolated customer
  devices, active hotspot guests, and active access rules.
- Plans & Hotspot: complete hotspot management. Toggle Captive Portal on/off, customize
  5 access plans (Starter 30-min agreement, Standard, Half-Day, Full-Day, VIP) with custom
  durations and QoS speed limits, generate and delete 6-digit access voucher PINs, and monitor
  live guest sessions with real-time countdown timers, extend (+30m), and revoke controls.
- Wifi Settings: configured network details and link to the router admin UI.
  Direct SSID/password editing requires a router integration not yet provided.
- Connected Device: full device management. Assign device nicknames (e.g., "Dad's Phone",
  "Table 4 Customer"), assign network groups (Family, Customer, Staff), configure QoS
  speed limits (e.g. 5 Mbps), set bedtime/curfew access schedules, and block/unblock.
  *Note: Devices marked as Family or Staff automatically bypass the captive portal.*
- Device Filtering: current blocked addresses and unblock controls.
- Usages: real aggregate enp1s0 RX/TX counters and average rate between refreshes.
- Activity Logs: real-time DNS query monitoring recording website and domain requests
  (e.g., youtube.com, instagram.com) made by connected devices. Filterable by client
  device IP, searchable by domain name, and clearable by the administrator.
- User Logs: last 300 admin sign-in/out, filtering, and hotspot connection events in memory; resets
  at service restart. This is admin portal audit logging.
- Settings: browser-local automatic refresh preference and configuration details.
- Logout: invalidates the current session and returns to the login page.

## What it does

- **Open Wi-Fi Captive Portal**: Clients connect to an open Wi-Fi network with zero password hassle.
  Internet forwarding is strictly barred until the user accepts the Starter Plan terms or enters a voucher PIN.
- **5 Customizable Access Plans**:
  1. **Starter Plan (Free)**: 1-click "Yes, I Agree & Connect" button granting 30 minutes of light internet access (2 Mbps speed limit). Expires automatically after 30 minutes.
  2. **Standard 2-Hour**: 120 minutes voucher code access (5 Mbps limit).
  3. **Half-Day Pass**: 6 hours high-speed voucher code access (10 Mbps limit).
  4. **Full-Day Pass**: 24 hours unlimited access voucher code access (15 Mbps limit).
  5. **VIP Premium**: 3-day unrestricted high-bandwidth VIP access (25 Mbps limit).
  *All 5 plans are fully customizable by the admin (custom duration, speed limit, active status, description).*
- **Voucher PIN Generation**: Admin can generate random 6-digit vouchers (or custom codes) with 1 click in the dashboard and hand them to customers.
- **Whitelisting for Family & Staff**: Mark any device as `Family` or `Staff` in Connected Devices, and they bypass the captive portal completely with permanent internet access.
- **Device identification**: assign custom nicknames and categorize devices into Family vs. Customer vs. Staff.
- **Customer Isolation & Portal Lockdown**: devices marked as Customer are blocked from opening
  the admin portal (port 8090) and isolated from accessing family devices on the local subnet.
- **Bandwidth QoS / Speed Limits**: throttle customer or heavy-usage devices (e.g. 2 Mbps, 5 Mbps,
  10 Mbps) to ensure family devices always have full gateway speed.
- **Access Schedules (Curfews & Bedtime)**: automatically disable internet access for selected
  devices during bedtime (e.g. 22:00 to 06:00) or outside business hours.
- **Website and domain activity tracking** via gateway DNS query logging.
- **IPv4 block/unblock** for selected addresses. Changes persist across reboot.
- The admin's current client IP cannot block itself through the UI.

### How the Captive Portal & Hotspot Work

1. **Probe Interception**: When a smartphone or laptop connects to the open Wi-Fi, it sends HTTP probes to domains such as `connectivitycheck.gstatic.com/generate_204`, `captive.apple.com/hotspot-detect.html`, or `msftconnecttest.com/connecttest.txt`.
2. **NAT Redirection**: Unauthenticated devices have their port 80 traffic intercepted by `nftables` in prerouting:
   `iifname "enp1s0" ip saddr != @whitelisted ip saddr != @authenticated tcp dport 80 redirect to :8088`
3. **Portal Prompt**: The unprivileged captive daemon on port 8088 intercepts probe requests and returns HTTP 302 pointing to `http://192.168.16.2:8088/guest`, which automatically opens the system "Sign in to Wi-Fi network" prompt on Android, iOS, Windows, and macOS.
4. **Starter & Voucher Authorization**: The user taps "Yes, I Agree & Connect" (or enters a voucher PIN). The backend validates the plan/voucher, registers the client IP in `guests.json` with an expiration timestamp and QoS limit, and adds the IP to the `@authenticated` nftables set.
5. **Forwarding Barrier**: The `nftables` forward chain strictly drops all traffic from non-whitelisted, unauthenticated devices (`forward iifname "enp1s0" counter drop`). Once authenticated, packets flow seamlessly through the gateway to the internet.
6. **Automatic Expiration**: A background thread running every 30 seconds checks for expired guest sessions, cleans up expired entries, and updates the nftables firewall set dynamically. When the session expires, the client immediately loses internet access and is redirected back to the captive portal on their next web request.

Devices appear after they exchange traffic with the gateway. The list is not a
definitive list of Wi-Fi connections. STALE is a neighbour-cache state, not proof
a device is offline. Refresh manually. Blocks are by IP, not durable device
identity: changes of address bypass them, and reassigned addresses inherit a
block. Review/remove old blocks. IPv6 is not controlled by this version; keep the
current downstream profile's IPv6 disabled.

### How Customer Isolation, QoS, and Schedules Work

1. **Portal Lockdown**: Devices marked as `Customer` have an `nftables` input rule
   dropping all packets destined for TCP port 8090 (`drop tcp dport 8090`). Customers
   cannot load the login screen or admin portal.
2. **Client-to-Client Isolation**: Customer devices are blocked from forwarding packets
   to other clients on the local network (`iifname enp1s0 oifname enp1s0 drop`), keeping
   family laptops, phones, and shared printers private.
3. **Bandwidth Throttling (QoS)**: Configured speed limits (e.g., 5 Mbps = 625 KB/s)
   use native `nftables` rate-limiting counters (`limit rate over <X> kbytes/second drop`),
   preventing customers from monopolizing total internet bandwidth.
4. **Access Schedules**: Devices with an enabled schedule are automatically evaluated against
   local system time. During curfew windows, internet access is dropped and marked in the UI.

### How DNS activity logging works

Modern web browsing uses HTTPS/TLS encryption. Routers cannot inspect encrypted
web page contents, search queries, passwords, or messages without installing a
custom root TLS certificate on each client device. However, devices send DNS queries
to resolve domain names (e.g. `youtube.com`, `instagram.com`).

The gateway captures these domain lookups via NetworkManager's shared dnsmasq service
configured at `/etc/NetworkManager/dnsmasq-shared.d/01-activity-log.conf` logging to
`/var/log/oshin-dns.log`. The restricted helper (`/usr/local/sbin/oshin-fw activity`)
parses recent queries and provides them to the authenticated dashboard. Devices with
explicit "Private DNS" (DNS-over-TLS on port 853 or DNS-over-HTTPS) bypass standard
gateway DNS.

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
