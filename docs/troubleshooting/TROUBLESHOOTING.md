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

