"""Linux interface and Wi-Fi management module."""
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..simulation.mock_provider import is_simulation_required, MockNetworkProvider

logger = logging.getLogger("wifirouter.interfaces")

class InterfaceManager:
    """Manages Linux network interfaces, links, and upstream Wi-Fi connections."""

    def __init__(self, mock_provider: Optional[MockNetworkProvider] = None):
        self.simulated = is_simulation_required()
        self.mock = mock_provider or MockNetworkProvider()

    def list_interfaces(self) -> List[Dict[str, Any]]:
        """List active and available network interfaces with IPs and states."""
        if self.simulated:
            return self.mock.get_interfaces()

        interfaces: List[Dict[str, Any]] = []
        try:
            res = subprocess.run(["ip", "-j", "addr", "show"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                raw_data = json.loads(res.stdout)
                for item in raw_data:
                    ifname = item.get("ifname", "")
                    addr_info = item.get("addr_info", [])
                    ipv4_info = next((a for a in addr_info if a.get("family") == "inet"), None)

                    iface_type = "ethernet"
                    role = "internal"
                    if ifname == "lo":
                        iface_type = "loopback"
                    elif ifname.startswith("wl"):
                        iface_type = "wifi"
                        role = "upstream"
                    elif ifname.startswith("en") or ifname.startswith("eth"):
                        iface_type = "ethernet"
                        role = "downstream_ap" if "16." in (ipv4_info.get("local", "") if ipv4_info else "") else "lan"
                    elif "docker" in ifname or "br-" in ifname:
                        iface_type = "bridge"
                        role = "container"

                    interfaces.append({
                        "name": ifname,
                        "type": iface_type,
                        "role": role,
                        "state": item.get("operstate", "UNKNOWN"),
                        "ip": ipv4_info.get("local") if ipv4_info else None,
                        "prefix": ipv4_info.get("prefixlen") if ipv4_info else None,
                        "mac": item.get("address"),
                        "mtu": item.get("mtu"),
                        "simulated": False
                    })
                return interfaces
        except Exception as exc:
            logger.warning(f"Failed to read interfaces from ip addr: {exc}")

        return self.mock.get_interfaces()

    def get_wifi_status(self, iface: str = "wlp2s0") -> Dict[str, Any]:
        """Get upstream Wi-Fi connection metrics using nmcli or iw."""
        if self.simulated:
            return self.mock.get_wifi_status()

        try:
            # Query nmcli for active connection details
            res = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SSID,BSSID,MODE,FREQ,CHAN,SIGNAL,SECURITY,DEVICE", "device", "wifi"],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 8 and parts[0] == "yes":
                        # Active connection found
                        return {
                            "connected": True,
                            "interface": parts[8] if len(parts) > 8 else iface,
                            "ssid": parts[1],
                            "bssid": parts[2],
                            "mode": parts[3],
                            "frequency_mhz": int(parts[4].replace(" MHz", "")) if "MHz" in parts[4] else 5000,
                            "channel": int(parts[5]) if parts[5].isdigit() else 36,
                            "signal_percent": int(parts[6]) if parts[6].isdigit() else 75,
                            "signal_dbm": int(parts[6]) - 100 if parts[6].isdigit() else -65,
                            "security": parts[7],
                            "simulated": False
                        }
        except Exception as exc:
            logger.warning(f"Could not read Wi-Fi status via nmcli: {exc}")

        return self.mock.get_wifi_status()

    def scan_wifi_networks(self, iface: str = "wlp2s0") -> List[Dict[str, Any]]:
        """Scan for nearby Wi-Fi access points."""
        if self.simulated:
            return self.mock.scan_wifi()

        networks = []
        try:
            subprocess.run(["nmcli", "device", "wifi", "rescan"], timeout=5, capture_output=True)
            res = subprocess.run(
                ["nmcli", "-t", "-f", "IN-USE,SSID,BSSID,CHAN,SIGNAL,SECURITY", "device", "wifi", "list"],
                capture_output=True, text=True, timeout=10
            )
            if res.returncode == 0:
                seen_ssids = set()
                for line in res.stdout.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 6:
                        in_use = parts[0] == "*"
                        ssid = parts[1]
                        if not ssid or ssid in seen_ssids:
                            continue
                        seen_ssids.add(ssid)
                        networks.append({
                            "ssid": ssid,
                            "bssid": parts[2],
                            "channel": int(parts[3]) if parts[3].isdigit() else 1,
                            "signal_percent": int(parts[4]) if parts[4].isdigit() else 50,
                            "security": parts[5] or "Open",
                            "in_use": in_use,
                            "simulated": False
                        })
                return networks
        except Exception as exc:
            logger.warning(f"nmcli scan failed: {exc}")

        return self.mock.scan_wifi()

