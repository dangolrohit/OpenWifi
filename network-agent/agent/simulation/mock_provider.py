"""Simulated Linux networking provider for development on Windows/macOS and automated testing."""
import os
import random
import time
from typing import Any, Dict, List, Optional

def is_simulation_required() -> bool:
    """Determine whether the agent should operate in simulated networking mode."""
    if os.environ.get("WIFIROUTER_SIMULATE", "").lower() in ("1", "true", "yes"):
        return True
    # Non-Linux environments (like Windows) always simulate
    if os.name != "posix":
        return True
    # If not running as root on Linux, simulation is required
    try:
        return os.geteuid() != 0
    except AttributeError:
        return True

class MockNetworkProvider:
    """Provides realistic simulated Linux network metrics, interfaces, and devices."""

    def __init__(self):
        self.start_time = time.time()
        self.blocked_ips = set()
        self.whitelisted_ips = {"192.168.16.101"}
        self.customer_ips = {"192.168.16.105", "192.168.16.106"}
        self.authenticated_guests = {
            "192.168.16.105": {
                "ip": "192.168.16.105",
                "plan_id": "starter",
                "speed_limit": 2,
                "authorized_at": time.time() - 300,
                "expires_at": time.time() + 1500
            }
        }
        self.speed_limits = {
            "192.168.16.105": 2,
            "192.168.16.106": 5
        }
        self.devices = [
            {
                "ip": "192.168.16.101",
                "mac": "a4:83:e7:21:09:41",
                "hostname": "Family-iPhone-14",
                "vendor": "Apple, Inc.",
                "group": "family",
                "status": "REACHABLE",
                "is_online": True,
                "first_seen": time.time() - 86400,
                "last_seen": time.time() - 12,
                "rx_bytes": 1284501230,
                "tx_bytes": 182390120,
                "speed_limit": 0,
                "schedule": {"enabled": False}
            },
            {
                "ip": "192.168.16.102",
                "mac": "68:db:f5:12:33:9a",
                "hostname": "Samsung-Smart-TV",
                "vendor": "Samsung Electronics",
                "group": "family",
                "status": "REACHABLE",
                "is_online": True,
                "first_seen": time.time() - 172800,
                "last_seen": time.time() - 5,
                "rx_bytes": 4829104810,
                "tx_bytes": 310492810,
                "speed_limit": 0,
                "schedule": {"enabled": True, "start": "23:00", "end": "06:00"}
            },
            {
                "ip": "192.168.16.103",
                "mac": "b0:7d:64:99:a1:c2",
                "hostname": "Work-ThinkPad",
                "vendor": "Lenovo",
                "group": "staff",
                "status": "REACHABLE",
                "is_online": True,
                "first_seen": time.time() - 43200,
                "last_seen": time.time() - 30,
                "rx_bytes": 892301920,
                "tx_bytes": 492019201,
                "speed_limit": 0,
                "schedule": {"enabled": False}
            },
            {
                "ip": "192.168.16.105",
                "mac": "3c:22:fb:44:81:aa",
                "hostname": "Guest-Galaxy-S23",
                "vendor": "Samsung",
                "group": "customer",
                "status": "REACHABLE",
                "is_online": True,
                "first_seen": time.time() - 1800,
                "last_seen": time.time() - 2,
                "rx_bytes": 89401200,
                "tx_bytes": 12401920,
                "speed_limit": 2,
                "schedule": {"enabled": False}
            },
            {
                "ip": "192.168.16.106",
                "mac": "5e:88:01:aa:22:cc",
                "hostname": "Visitor-Pixel-8",
                "vendor": "Google",
                "group": "customer",
                "status": "STALE",
                "is_online": False,
                "first_seen": time.time() - 3600,
                "last_seen": time.time() - 240,
                "rx_bytes": 32104010,
                "tx_bytes": 4910200,
                "speed_limit": 5,
                "schedule": {"enabled": False}
            }
        ]

    def get_interfaces(self) -> List[Dict[str, Any]]:
        """Simulate physical network interfaces."""
        return [
            {
                "name": "wlp2s0",
                "type": "wifi",
                "role": "upstream",
                "state": "UP",
                "ip": "192.168.1.100",
                "prefix": 24,
                "mac": "00:15:5d:01:22:33",
                "gateway": "192.168.1.1",
                "speed_mbps": 866,
                "mtu": 1500,
                "simulated": True
            },
            {
                "name": "enp1s0",
                "type": "ethernet",
                "role": "downstream_ap",
                "state": "UP",
                "ip": "192.168.16.2",
                "prefix": 24,
                "mac": "00:15:5d:01:44:55",
                "gateway": None,
                "speed_mbps": 1000,
                "mtu": 1500,
                "simulated": True
            },
            {
                "name": "lo",
                "type": "loopback",
                "role": "internal",
                "state": "UP",
                "ip": "127.0.0.1",
                "prefix": 8,
                "mac": "00:00:00:00:00:00",
                "gateway": None,
                "speed_mbps": None,
                "mtu": 65536,
                "simulated": True
            },
            {
                "name": "docker0",
                "type": "bridge",
                "role": "container",
                "state": "UP",
                "ip": "172.17.0.1",
                "prefix": 16,
                "mac": "02:42:1a:8b:9c:01",
                "gateway": None,
                "speed_mbps": None,
                "mtu": 1500,
                "simulated": True
            }
        ]

    def get_routing_table(self) -> List[Dict[str, Any]]:
        """Simulate IP routing table."""
        return [
            {
                "destination": "default",
                "gateway": "192.168.1.1",
                "interface": "wlp2s0",
                "metric": 600,
                "protocol": "dhcp",
                "simulated": True
            },
            {
                "destination": "192.168.1.0/24",
                "gateway": "0.0.0.0",
                "interface": "wlp2s0",
                "metric": 600,
                "protocol": "kernel",
                "simulated": True
            },
            {
                "destination": "192.168.16.0/24",
                "gateway": "0.0.0.0",
                "interface": "enp1s0",
                "metric": 100,
                "protocol": "kernel",
                "simulated": True
            },
            {
                "destination": "172.17.0.0/16",
                "gateway": "0.0.0.0",
                "interface": "docker0",
                "metric": 0,
                "protocol": "kernel",
                "simulated": True
            }
        ]

    def get_wifi_status(self) -> Dict[str, Any]:
        """Simulate upstream Wi-Fi connection info."""
        return {
            "connected": True,
            "interface": "wlp2s0",
            "ssid": "HomeWiFi_5G",
            "bssid": "30:23:03:77:88:99",
            "mode": "Infra",
            "frequency_mhz": 5180,
            "channel": 36,
            "signal_percent": 88,
            "signal_dbm": -56,
            "bitrate_mbps": 866.7,
            "security": "WPA2-PSK",
            "ip": "192.168.1.100",
            "gateway": "192.168.1.1",
            "dns": ["1.1.1.1", "8.8.8.8"],
            "simulated": True
        }

    def scan_wifi(self) -> List[Dict[str, Any]]:
        """Simulate scanned Wi-Fi access points."""
        return [
            {
                "ssid": "HomeWiFi_5G",
                "bssid": "30:23:03:77:88:99",
                "signal_percent": 90,
                "channel": 36,
                "security": "WPA2",
                "in_use": True,
                "simulated": True
            },
            {
                "ssid": "HomeWiFi_2.4G",
                "bssid": "30:23:03:77:88:98",
                "signal_percent": 98,
                "channel": 6,
                "security": "WPA2",
                "in_use": False,
                "simulated": True
            },
            {
                "ssid": "Neighbor_Net",
                "bssid": "74:ac:b9:11:22:33",
                "signal_percent": 42,
                "channel": 11,
                "security": "WPA2/WPA3",
                "in_use": False,
                "simulated": True
            },
            {
                "ssid": "FiberOptic_Guest",
                "bssid": "8c:15:c7:44:55:66",
                "signal_percent": 35,
                "channel": 1,
                "security": "WPA2",
                "in_use": False,
                "simulated": True
            }
        ]

    def get_bandwidth_metrics(self) -> Dict[str, Any]:
        """Simulate live throughput counters with realistic fluctuations."""
        now = time.time()
        uptime_sec = now - self.start_time
        # Generate jittered live throughput rates
        base_down = 18.5 + 4.2 * (uptime_sec % 30) / 10 + random.uniform(-1.5, 1.5)
        base_up = 4.2 + 1.1 * (uptime_sec % 20) / 10 + random.uniform(-0.4, 0.4)

        return {
            "interface": "enp1s0",
            "download_mbps": max(0.2, round(base_down, 2)),
            "upload_mbps": max(0.1, round(base_up, 2)),
            "rx_bytes": int(2849102490 + uptime_sec * 2200000),
            "tx_bytes": int(491029140 + uptime_sec * 450000),
            "rx_packets": int(2104920 + uptime_sec * 1800),
            "tx_packets": int(1492019 + uptime_sec * 950),
            "rx_errors": 0,
            "tx_errors": 0,
            "simulated": True
        }

    def get_system_health(self) -> Dict[str, Any]:
        """Simulate host system resource usage."""
        now = time.time()
        return {
            "cpu_percent": round(14.5 + random.uniform(-3, 5), 1),
            "memory": {
                "total_mb": 15890,
                "used_mb": 4820,
                "available_mb": 11070,
                "percent": 30.3
            },
            "disk": {
                "total_gb": 468.2,
                "used_gb": 128.4,
                "free_gb": 339.8,
                "percent": 27.4
            },
            "uptime_seconds": int(now - self.start_time + 86400 * 3),
            "services": {
                "NetworkManager": {"status": "active", "enabled": True},
                "docker": {"status": "active", "enabled": True},
                "cloudflared": {"status": "active", "enabled": True},
                "wifirouter_agent": {"status": "active", "enabled": True},
                "wifirouter_backend": {"status": "active", "enabled": True},
                "postgresql": {"status": "active", "enabled": True}
            },
            "simulated": True
        }

    def get_devices(self) -> List[Dict[str, Any]]:
        """Return discovered connected devices with live simulation updates."""
        return self.devices

    def get_firewall_status(self) -> Dict[str, Any]:
        """Return simulated firewall state."""
        return {
            "table": "inet wifirouter",
            "captive_enabled": True,
            "blocked": sorted(list(self.blocked_ips)),
            "whitelisted": sorted(list(self.whitelisted_ips)),
            "customers": sorted(list(self.customer_ips)),
            "authenticated": sorted(list(self.authenticated_guests.keys())),
            "speed_limits": self.speed_limits,
            "simulated": True
        }

    def set_device_block(self, ip: str, blocked: bool) -> Dict[str, Any]:
        """Simulate blocking or unblocking an IP address."""
        if blocked:
            self.blocked_ips.add(ip)
        else:
            self.blocked_ips.discard(ip)
        return {"ok": True, "ip": ip, "blocked": blocked, "simulated": True}

    def set_speed_limit(self, ip: str, limit_mbps: int) -> Dict[str, Any]:
        """Simulate setting a QoS speed limit."""
        if limit_mbps > 0:
            self.speed_limits[ip] = limit_mbps
        else:
            self.speed_limits.pop(ip, None)
        return {"ok": True, "ip": ip, "speed_limit_mbps": limit_mbps, "simulated": True}

