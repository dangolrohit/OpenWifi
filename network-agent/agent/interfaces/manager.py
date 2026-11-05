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

def _parse_nmcli_line(line: str) -> List[str]:
    """Parse colon-delimited line from nmcli -t, unescaping colons inside fields."""
    return [p.replace(r"\:", ":") for p in re.split(r"(?<!\\):", line)]

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

    def get_wifi_status(self, iface: Optional[str] = None) -> Dict[str, Any]:
        """Get upstream Wi-Fi connection metrics using nmcli or iw."""
        if self.simulated:
            return self.mock.get_wifi_status()

        target_iface = iface or os.environ.get("WIFIROUTER_WAN_IFACE", "wlp2s0")

        # Discover Wi-Fi IP if assigned
        local_ip = "192.168.1.100"
        try:
            res_ip = subprocess.run(["ip", "-j", "addr", "show", target_iface], capture_output=True, text=True, timeout=3)
            if res_ip.returncode == 0:
                data = json.loads(res_ip.stdout)
                if data and "addr_info" in data[0]:
                    v4 = next((a["local"] for a in data[0]["addr_info"] if a.get("family") == "inet"), None)
                    if v4:
                        local_ip = v4
        except Exception:
            pass

        try:
            # Query nmcli for active connection details
            res = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SSID,BSSID,MODE,FREQ,CHAN,SIGNAL,SECURITY,DEVICE", "device", "wifi"],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    parts = _parse_nmcli_line(line)
                    if len(parts) >= 8 and parts[0] == "yes":
                        # Active connection found
                        actual_iface = parts[8] if len(parts) > 8 and parts[8] else target_iface
                        freq = 5000
                        if "MHz" in parts[4]:
                            freq_digits = re.sub(r"[^\d]", "", parts[4])
                            if freq_digits:
                                freq = int(freq_digits)
                        chan = int(parts[5]) if parts[5].isdigit() else 36
                        sig = int(parts[6]) if parts[6].isdigit() else 75

                        return {
                            "connected": True,
                            "interface": actual_iface,
                            "ssid": parts[1] or "Connected Network",
                            "bssid": parts[2],
                            "mode": parts[3] or "Infra",
                            "frequency_mhz": freq,
                            "channel": chan,
                            "signal_percent": sig,
                            "signal_dbm": sig - 100,
                            "security": parts[7] or "WPA2-PSK",
                            "ip": local_ip,
                            "simulated": False
                        }
        except Exception as exc:
            logger.warning(f"Could not read Wi-Fi status via nmcli: {exc}")

        return self.mock.get_wifi_status()

    def scan_wifi_networks(self, iface: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scan for nearby Wi-Fi access points."""
        if self.simulated:
            return self.mock.scan_wifi()

        networks = []
        try:
            # Trigger rescan (ignore failure if rate-limited)
            subprocess.run(["nmcli", "device", "wifi", "rescan"], timeout=4, capture_output=True)
            res = subprocess.run(
                ["nmcli", "-t", "-f", "IN-USE,SSID,BSSID,CHAN,SIGNAL,SECURITY", "device", "wifi"],
                capture_output=True, text=True, timeout=8
            )
            if res.returncode == 0:
                seen_ssids = set()
                for line in res.stdout.splitlines():
                    parts = _parse_nmcli_line(line)
                    if len(parts) >= 6:
                        in_use = (parts[0] == "*")
                        ssid = parts[1].strip()
                        # Ignore hidden networks or duplicate SSIDs
                        if not ssid or ssid in seen_ssids or ssid == "--":
                            continue
                        seen_ssids.add(ssid)
                        chan = int(parts[3]) if parts[3].isdigit() else 1
                        sig = int(parts[4]) if parts[4].isdigit() else 50
                        sec = parts[5].strip() if parts[5].strip() else "Open"
                        networks.append({
                            "ssid": ssid,
                            "bssid": parts[2],
                            "channel": chan,
                            "signal_percent": sig,
                            "security": sec,
                            "in_use": in_use,
                            "simulated": False
                        })
                if networks:
                    return networks
        except Exception as exc:
            logger.warning(f"nmcli scan failed: {exc}")

        # Fallback to simulated/cached list if interface is temporarily busy
        return self.mock.scan_wifi()

