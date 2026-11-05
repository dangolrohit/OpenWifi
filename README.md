# WiFiRouter V2 — Complete Network Management System

A production-quality, secure, self-hosted network-management platform designed for Ubuntu gateways and guest Wi-Fi environments.

```
Primary Router (192.168.1.1)
      ↓ Wi-Fi (wlp2s0: 192.168.1.100)
Ubuntu Gateway Laptop (WiFiRouter V2)
      ↓ Ethernet (enp1s0: 192.168.16.2/24)
Secondary Router (Access Point Mode)
      ↓ Open Guest Wi-Fi
Client Devices (Smartphones, Laptops, IoT)
```

---

## 🚀 Key Features

- **Modern Web Stack**:
  - **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Lucide icons, TanStack Query, React Router, Recharts.
  - **Backend**: FastAPI, Pydantic, SQLAlchemy 2.0 async, PostgreSQL (with SQLite dev fallback), Argon2id auth, WebSockets.
  - **Linux Network Agent**: Minimal-privilege host systemd service managing `nftables`, Linux Traffic Control (`tc`), NetworkManager D-Bus API, DHCP leases, and dnsmasq.
- **Dedicated Firewall Table (`inet wifirouter`)**:
  - Atomic transactions with automatic snapshot rollback.
  - Never flushes unrelated rules; seamlessly coexists with Docker, Coolify, Tailscale, and Cloudflare Tunnel.
- **Open Wi-Fi Captive Portal**:
  - Intercepts OS probe requests on port 80 and redirects to captive portal on port 8088.
  - **Starter Plan**: 1-click "Continue as Guest" button granting 30 minutes of internet access at 1 Mbps speed limit.
  - **Tiered Hotspot Plans**: 4 customizable voucher/account plans (Standard 2-Hour, Half-Day Pass, Full-Day Pass, VIP Premium).
  - Real-time countdown timer, 1-click session extension (+30m), and immediate revocation.
- **Customer Isolation & Admin Lockdown**:
  - Customer devices are dropped from accessing admin port 8090 and isolated client-to-client from local family devices.
  - Family & Staff devices are whitelisted in `nftables` and bypass the captive portal completely.
- **Bandwidth QoS & Curfews**:
  - Per-device bandwidth throttling (Mbps).
  - Bedtime access curfews (e.g. 22:00 to 06:00).
- **DNS Activity Tracking**:
  - Real-time logging of website domains requested by connected devices via gateway dnsmasq.

---

## 📂 Navigation Sections (11 Pages)

1. **Dashboard**: High-level telemetry, live download/upload speeds, active device counters, 24h bandwidth charts, and host health.
2. **Wi-Fi Settings**: Upstream Wi-Fi metrics (SSID, BSSID, signal dBm, channel), nearby network scanner.
3. **Connected Devices**: Discovered device inventory, search, nickname editor, network group assignment, QoS limits, and curfew schedules.
4. **Device Filtering**: Dedicated firewall sets, blocklist management, customer isolation status, and quick IP block form.
5. **Usage Analytics**: Historical bandwidth curves (24h, 7d, 30d), peak throughput metrics, and CSV export.
6. **Guest Management**: Tiered hotspot plan customizer, 6-digit voucher PIN generator, and active guest sessions with live countdowns.
7. **User Logs**: Audit trail of administrator logins, policy changes, and gateway DNS domain lookup history.
8. **Network Settings**: Physical and virtual interface states, IP routing table, and default upstream gateway verification.
9. **System Monitoring**: CPU, RAM, root disk storage gauges, host uptime, and systemd service supervisor (Docker, Cloudflare Tunnel, etc.).
10. **Settings**: Admin profile, Argon2id password change, configuration snapshots, and JSON backup export.
11. **Sign Out**: Revokes server-side session token and clears HttpOnly cookies.

---

## 🛠️ Quick Start & Production Deployment

### Production Installation on Ubuntu Laptop

```bash
cd ~
git clone https://github.com/dangolrohit/WiFiRouter.git
cd ~/WiFiRouter
git checkout feature/v2-platform
sudo bash scripts/installation/install_v2.sh
```

Open your browser at **http://192.168.16.2:8090**.
- Default Username: `admin`
- Default Password: `admin12345678` (change immediately in **Settings**!)

### Development Mode (Windows / macOS / Linux)

Run the all-in-one development orchestrator (starts simulated agent, FastAPI backend, and Vite frontend):

```bash
python scripts/development/run_dev.py
```

- **Frontend UI**: http://localhost:5173
- **Backend API**: http://127.0.0.1:8090/api/docs
- **Network Agent**: http://127.0.0.1:8091/health

---

## 🧪 Automated Testing

### Backend & API Tests
```bash
python -m unittest discover -s backend/tests -p "test_*.py"
```

### Network Agent Tests
```bash
python -m unittest discover -s network-agent/tests -p "test_*.py"
```

### Frontend TypeScript & Vite Build
```bash
npm run build --prefix frontend
```

---

## 🛡️ Reliability & Emergency Rollback

If you ever need to reset all WiFiRouter firewall and traffic shaping rules to baseline:

```bash
sudo bash scripts/recovery/rollback.sh
```

For open Wi-Fi, free guest access, and voucher deployment, see [Hotspot setup](docs/deployment/HOTSPOT.md).
