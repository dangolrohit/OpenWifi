# WiFiRouter V2 Troubleshooting Guide

## 1. Inspecting Service Health

Check Docker Compose containers:
```bash
sudo docker compose ps
sudo docker compose logs -f backend
```

Check Host Network Agent daemon:
```bash
sudo systemctl status wifirouter-agent --no-pager
sudo journalctl -u wifirouter-agent -n 50 --no-pager
```

## 2. Firewall and Forwarding Verification

Inspect the dedicated nftables table:
```bash
sudo nft list table inet wifirouter
```

Verify IP forwarding is enabled in the Linux kernel:
```bash
sysctl net.ipv4.ip_forward
# Should output: net.ipv4.ip_forward = 1
```

## 3. Emergency Network Rollback

If you ever need to immediately reset all WiFiRouter firewall and traffic shaping rules:
```bash
sudo bash scripts/recovery/rollback.sh
```

## 4. Captive Portal Detection on Smartphones

If a smartphone does not automatically trigger the "Sign in to network" popup:
1. Ensure the phone's Wi-Fi settings do not have "Private DNS" enabled (Private DNS uses encrypted port 853, which bypasses standard gateway DNS).
2. Manually open a browser on the phone and visit `http://connectivitycheck.gstatic.com` or `http://192.168.16.2:8088/guest`.


## 5. Browser Wi-Fi scanning

The V2 React page at `/wifi` requests `/api/v1/wifi/scan`. The backend forwards
this to the privileged Ubuntu host agent. A browser on a secondary laptop sees
networks near the Ubuntu gateway, not near the secondary laptop. The legacy
`install.sh` / `web.py` portal has no scanner; use the V2 installation for scanning.
The development runner deliberately uses simulated networks.

After updating this repository on Ubuntu, update **both** installed components:

```bash
sudo cp -a network-agent/. /opt/wifirouter/network-agent/
sudo systemctl restart wifirouter-agent
sudo docker compose up -d --build
sudo systemctl status wifirouter-agent --no-pager
```

Check hardware and scan directly on Ubuntu (replace `wlp2s0` with the actual
Wi-Fi device from the first command):

```bash
nmcli device status
rfkill list
sudo nmcli --wait 20 -t -f IN-USE,SSID,BSSID,CHAN,SIGNAL,SECURITY device wifi list ifname wlp2s0 --rescan yes
sudo journalctl -u wifirouter-agent -n 50 --no-pager
sudo docker compose logs --tail=50 backend
```

New installations auto-discover wireless adapters through sysfs. To select a
specific adapter, create `/etc/wifirouter/agent.env` containing
`WIFIROUTER_WAN_IFACE=your_interface`. Existing installations may still hard-code
`wlp2s0`; use `sudo systemctl edit wifirouter-agent` and add:

```ini
[Service]
Environment="WIFIROUTER_WAN_IFACE=your_interface"
```

Then run `sudo systemctl daemon-reload` and `sudo systemctl restart wifirouter-agent`.
Changing `.env` alone does not configure the host systemd service.

Scans may take up to 35 seconds (NetworkManager plus the iwlist fallback); the
backend allows 45 seconds. Errors now appear in the page instead of fabricated
networks or a silent empty list. A successful empty scan displays "No nearby
networks found." If the agent is unreachable, check that the backend's
`WIFIROUTER_AGENT_URL` reaches the Ubuntu host and that its agent secret matches
the host service. Never point a container at its own loopback address for the
host agent.

The scan command and escaped-field parsing follow the
[NetworkManager nmcli reference](https://networkmanager.dev/docs/api/latest/nmcli).

## 6. Device activity popup

Connected Devices > Actions > View opens the selected device's DNS activity.
Each row is one recorded lookup (including repeated lookups), newest first, with
20 records per page and Previous/Next controls. Refresh returns to page one.
The popup uses an authenticated `/api/v1/logs/dns/device-activity?client=IP&page=1`
endpoint. Update both the host agent and backend when deploying this feature.

Records are matched by IP, not permanent hardware identity. IP reassignment can
therefore include another device's prior activity. These are domain lookups,
including background app traffic, not proof of a person visiting a web page.
HTTPS URL paths, cached requests, encrypted DNS, and VPN activity are not exposed
by these DNS logs. The view reads the first retained configured log containing
that device's queries, falling back to the NetworkManager journal; rotated or
removed logs are not included. New requests or log rotation can change page
boundaries while navigating. No new traffic interception is enabled.

If the list is empty, verify dnsmasq query logging is enabled on Ubuntu and that
the client uses the gateway's DNS. Agent failures appear as errors, not fabricated
activity. Explicit development simulation is labelled in the popup.
