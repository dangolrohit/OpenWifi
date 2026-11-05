# WiFiRouter V2 Architecture Documentation

## Physical Network Topology

```
                  ┌───────────────────────┐
                  │    Primary Router     │  (192.168.1.1)
                  │   Internet Uplink     │
                  └──────────┬────────────┘
                             │
                      Wi-Fi (wlp2s0: 192.168.1.100)
                             │
                  ┌──────────▼────────────┐
                  │     Ubuntu Laptop     │  (Gateway Server)
                  │  WiFiRouter Platform  │
                  └──────────┬────────────┘
                             │
                    Ethernet (enp1s0: 192.168.16.2/24)
                             │
                  ┌──────────▼────────────┐
                  │   Secondary Router    │  (Access Point Mode)
                  │  SSID: Guest / Family │
                  └──────────┬────────────┘
                             │
             ┌───────────────┴───────────────┐
             │                               │
    ┌────────▼────────┐             ┌────────▼────────┐
    │ Family Devices  │             │ Guest Devices   │
    │ (Whitelisted)   │             │ (Captive Held)  │
    └─────────────────┘             └─────────────────┘
```

## Security & Privilege Separation

1. **Host Network Agent (`network-agent`)**:
   - Runs on the host as a minimal-privilege systemd daemon (`wifirouter-agent.service`).
   - Listens exclusively on `127.0.0.1:8091`.
   - Requires `X-Agent-Secret` token authentication on every IPC call.
   - Restricts commands to validated operations (inspecting interfaces, managing dedicated `inet wifirouter` nftables table, applying `tc` shaping, inspecting DHCP leases).
   - Never accepts arbitrary shell commands.

2. **Web Application Backend (`backend`)**:
   - Runs in Docker or as an unprivileged user on port `8090`.
   - Built on FastAPI with async SQLAlchemy, Argon2id password hashing, and HttpOnly session cookies.
   - Never runs as root. Communicates with `network-agent` over local IPC.

3. **Captive Portal (`captive-portal`)**:
   - Runs on port `8088`. Intercepts HTTP port 80 traffic redirected by `nftables` prerouting.
   - Unauthenticated visitors cannot forward packets to the internet until they agree to the Starter 30-min plan or redeem a valid voucher code.
   - Completely unprivileged.

4. **Coexistence with Docker, Coolify, and Cloudflare Tunnel**:
   - Uses a dedicated `nftables` table `inet wifirouter` with priority `-10`.
   - Never executes `flush ruleset`.
   - Never overrides Docker bridge networks, Coolify reverse proxies, or Cloudflare Tunnel routes.
   - Protects SSH (port 22) and gateway management (port 8090) from being blocked.

