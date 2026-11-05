# Open Wi-Fi and captive guest access

## Guest flow

1. Join the secondary router's open SSID (no Wi-Fi password).
2. Open the captive login screen. If the operating system does not open it,
   browse to `http://192.168.16.2:8088/guest` or an ordinary HTTP website.
3. Choose **Access as a Guest** for 30 minutes at 1 Mbps, or enter a six-digit
   access code generated in **Guests**.
4. Codes are single-use and apply their active plan's duration and speed at
   redemption. Disabled plans and reused codes are rejected.
5. At expiry, internet forwarding stops. A new code is required to continue.

Clicking free access again does not reset the timer. The free allowance is once
per IP in retained guest-session history, not once per person or per day. DHCP
address changes can bypass this restriction or cause another device to inherit
an exhausted allowance. Stable DHCP leases help, but this is not a strong device
identity system. Existing free sessions retain their original cap until expiry;
new free sessions use 30 minutes / 1 Mbps. Family/staff whitelist entries bypass
the captive gate intentionally.

## Required physical setup

- Configure the secondary router as an **access point/bridge**, with an open SSID.
  Connect it to Ubuntu's downstream Ethernet interface, not directly to the
  primary internet router. Do not use secondary-router NAT: Ubuntu must see each
  client's individual address.
- Ubuntu must provide DHCP/routing/NAT (for example its existing NetworkManager
  shared Ethernet connection). Client gateway and DNS should be `192.168.16.2`,
  with client addresses in `192.168.16.0/24`. The secondary AP must not advertise
  a different internet gateway. This update does not reconfigure physical routers
  or NetworkManager profiles automatically.
- The agent's `WIFIROUTER_LAN_IFACE` must be the downstream interface (default
  `enp1s0`). AP client isolation, if desired, must also be enabled on the AP;
  same-SSID traffic may never reach Ubuntu.
- Captive enforcement must be enabled in `/var/lib/wifirouter/firewall_state.json`.
  Inspect existing whitelist entries. Older installations seeded `192.168.16.101`;
  if this is a guest, use Connected Devices > Edit to put it in the Default Guest
  group instead of Family/Staff. New installations do not seed this exemption.
- IPv6 forwarding on the downstream interface is blocked by the captive gate;
  this implementation authorizes IPv4 clients only.

## Updating Ubuntu

Run from the Ubuntu project checkout. Both application containers and the host
agent must be updated together:

```bash
git pull --ff-only origin feature/v2-platform
sudo cp -a network-agent/. /opt/wifirouter/network-agent/
sudo docker compose up -d --build
sudo systemctl restart wifirouter-agent
sudo systemctl status wifirouter-agent --no-pager
```

The captive container now uses Linux host networking to receive HTTP redirects
and preserve the original guest IP. It forwards only public guest endpoints to
the backend at `http://127.0.0.1:8090`. A signed client-IP header verifies portal
identity using the secret passed to both services by Compose. Do not configure
wildcard trust of arbitrary forwarded client IP headers. This production Compose
configuration targets Ubuntu, not Windows Docker networking.

Keep `WIFIROUTER_AGENT_URL=http://host.docker.internal:8091` in `.env` for the
backend container. A stopped/unreachable agent fails authorization instead of
pretending internet access succeeded.

## Verify with a guest device

- Before confirming or entering a code: internet browsing should be blocked;
  the captive page should load.
- Click **Access as a Guest**: verify the active session in Guests is the actual
  client's IP, lasts 30 minutes, and shows 1 Mbps. Re-clicking does not extend it.
- Test upload and download limits. These are nftables packet-rate caps per
  direction, not a guaranteed throughput or smooth traffic shaping; short bursts
  are possible.
- Generate a code in Guests, redeem it on another test client, and check its plan
  speed/duration. Reusing the same code on a third client must fail.
- Revoke a session in Guests: existing downloads and new internet connections
  should stop. For expiry testing, create a short test voucher plan through the
  plan API and verify the kernel removes its authorization.

Useful diagnostics (these do not print shared secrets):

```bash
sudo nft list table inet wifirouter
sudo journalctl -u wifirouter-agent -n 50 --no-pager
sudo docker compose logs --tail=50 backend captive-portal
nmcli device status
sysctl net.ipv4.ip_forward
```

The agent restores the gate at startup. Authorization, speed and expiry are
applied together; nftables set-element timeouts stop access even if the periodic
cleanup task is delayed. See the [nftables reference](https://www.netfilter.org/projects/nftables/manpage.html)
and [element timeout documentation](https://wiki.nftables.org/wiki-nftables/index.php/Element_timeouts).

Local tests cover free limits, repeated clicks, expired free access, code
validation/redemption, disabled plans, failure rollback, signed guest identity,
and firewall script generation. Actual Ubuntu forwarding, captive detection,
PostgreSQL concurrent redemptions and measured radio throughput still need the
on-device checks above.
