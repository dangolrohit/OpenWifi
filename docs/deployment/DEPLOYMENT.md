# WiFiRouter V2 Deployment Guide

## Production Setup on Ubuntu Laptop

### Step 1: Clone Repository
```bash
cd ~
git clone https://github.com/dangolrohit/WiFiRouter.git
cd ~/WiFiRouter
```

### Step 2: Switch to Feature Branch
```bash
git checkout feature/v2-platform
```

### Step 3: Run Production Installer
```bash
sudo bash scripts/installation/install_v2.sh
```

The installer will:
1. Verify system tools (`python3`, `nft`, `tc`, `ip`, `systemctl`, `curl`).
2. Install Docker and Docker Compose if missing.
3. Configure dnsmasq query logging in `/etc/NetworkManager/dnsmasq-shared.d/`.
4. Install and start `wifirouter-agent.service` systemd daemon.
5. Launch the Docker Compose stack (PostgreSQL, FastAPI Backend, Captive Portal).
6. Verify API health checks.

### Step 4: Open Administration Portal
Navigate to:
```
http://192.168.16.2:8090
```
- Default Username: `admin`
- Default Password: `admin12345678` (change immediately in **Settings**!)

## Upgrading Future Versions
```bash
cd ~/WiFiRouter
git pull --ff-only
sudo docker compose up -d --build
sudo systemctl restart wifirouter-agent
```

