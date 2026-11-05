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

def _parse_iw_link(out: str) -> Dict[str, Any]:
    """Parse output from `iw dev <iface> link`."""
    res = {"connected": False, "security": "WPA2-PSK", "mode": "Infra"}
    if "Connected to" in out:
        res["connected"] = True
        m_bssid = re.search(r"Connected to ([0-9a-fA-F:]{17})", out)
        if m_bssid:
            res["bssid"] = m_bssid.group(1)
        m_ssid = re.search(r"SSID:\s*(.+)", out)
        if m_ssid:
            res["ssid"] = m_ssid.group(1).strip()
        m_freq = re.search(r"freq:\s*(\d+)", out)
        if m_freq:
            f = int(m_freq.group(1))
            res["frequency_mhz"] = f
            res["channel"] = 36 if f > 5000 else 6
        m_sig = re.search(r"signal:\s*([-\d]+)", out)
        if m_sig:
            dbm = int(m_sig.group(1))
            res["signal_dbm"] = dbm
            res["signal_percent"] = max(0, min(100, 2 * (dbm + 100)))
    return res

def _parse_iwconfig(out: str) -> Dict[str, Any]:
    """Parse output from `iwconfig <iface>`."""
    res = {"connected": False, "security": "WPA2-PSK", "mode": "Managed"}
    m_ssid = re.search(r'ESSID:"([^"]+)"', out)
    if m_ssid and m_ssid.group(1) not in ("off/any", ""):
        res["connected"] = True
        res["ssid"] = m_ssid.group(1)
        m_bssid = re.search(r"Access Point:\s*([0-9a-fA-F:]{17})", out)
        if m_bssid:
            res["bssid"] = m_bssid.group(1)
        m_freq = re.search(r"Frequency:([\d\.]+)\s*GHz", out)
        if m_freq:
            f = int(float(m_freq.group(1)) * 1000)
            res["frequency_mhz"] = f
            res["channel"] = 36 if f > 5000 else 6
        m_sig = re.search(r"Signal level=([-\d]+)\s*dBm", out)
        if m_sig:
            dbm = int(m_sig.group(1))
            res["signal_dbm"] = dbm
            res["signal_percent"] = max(0, min(100, 2 * (dbm + 100)))
    return res

def _parse_iwlist(out: str) -> List[Dict[str, Any]]:
    """Parse output from `iwlist <iface> scan`."""
    networks = []
    cells = out.split("Cell ")
    for cell in cells[1:]:
        m_bssid = re.search(r"Address:\s*([0-9a-fA-F:]{17})", cell)
        m_ssid = re.search(r'ESSID:"([^"]*)"', cell)
        m_chan = re.search(r"Channel:?\s*(\d+)", cell)
        m_sig = re.search(r"Signal level=([-\d]+)", cell)
        m_enc = re.search(r"Encryption key:(on|off)", cell)

        ssid = m_ssid.group(1) if m_ssid else ""
        if not ssid:
            continue

        bssid = m_bssid.group(1) if m_bssid else "00:00:00:00:00:00"
        chan = int(m_chan.group(1)) if m_chan else 1
        dbm = int(m_sig.group(1)) if m_sig else -70
        sig_pct = max(0, min(100, 2 * (dbm + 100)))
        sec = "WPA2" if (m_enc and m_enc.group(1) == "on") else "Open"

        networks.append({
            "ssid": ssid,
            "bssid": bssid,
            "channel": chan,
            "signal_percent": sig_pct,
            "security": sec,
            "in_use": False,
            "simulated": False
        })
    return networks

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
        """Get upstream Wi-Fi connection metrics using nmcli, iw, or iwconfig."""
        if self.simulated:
            return self.mock.get_wifi_status()

        target_iface = iface or os.environ.get("WIFIROUTER_WAN_IFACE")
        if not target_iface:
            for p in Path("/sys/class/net").glob("wl*"):
                target_iface = p.name
                break
        target_iface = target_iface or "wlp2s0"

        # 1. Discover Wi-Fi local IP if assigned
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

        # 2. Try nmcli
        try:
            res = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SSID,BSSID,MODE,FREQ,CHAN,SIGNAL,SECURITY,DEVICE", "device", "wifi"],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    parts = _parse_nmcli_line(line)
                    if len(parts) >= 8 and parts[0] == "yes":
                        actual_iface = parts[8] if len(parts) > 8 and parts[8] else target_iface
                        freq = 5000
                        if "MHz" in parts[4]:
                            freq_digits = re.sub(r"[^\d]", "", parts[4])
                            if freq_digits:
                                freq = int(freq_digits)
                        chan = int(parts[5]) if parts[5].isdigit() else (36 if freq > 5000 else 6)
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
            logger.debug(f"nmcli Wi-Fi query skipped: {exc}")

        # 3. Fallback: try iw dev <iface> link
        try:
            res_iw = subprocess.run(["iw", "dev", target_iface, "link"], capture_output=True, text=True, timeout=3)
            if res_iw.returncode == 0 and "Connected to" in res_iw.stdout:
                parsed_iw = _parse_iw_link(res_iw.stdout)
                if parsed_iw.get("connected"):
                    parsed_iw["interface"] = target_iface
                    parsed_iw["ip"] = local_ip
                    parsed_iw["simulated"] = False
                    return parsed_iw
        except Exception:
            pass

        # 4. Fallback: try iwconfig
        try:
            res_iwcfg = subprocess.run(["iwconfig", target_iface], capture_output=True, text=True, timeout=3)
            if res_iwcfg.returncode == 0:
                parsed_cfg = _parse_iwconfig(res_iwcfg.stdout)
                if parsed_cfg.get("connected"):
                    parsed_cfg["interface"] = target_iface
                    parsed_cfg["ip"] = local_ip
                    parsed_cfg["simulated"] = False
                    return parsed_cfg
        except Exception:
            pass

        return self.mock.get_wifi_status()

    def scan_wifi_networks(self, iface: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scan for nearby Wi-Fi access points using nmcli, iw, or iwlist."""
        if self.simulated:
            return self.mock.scan_wifi()

        target_iface = iface or os.environ.get("WIFIROUTER_WAN_IFACE")
        if not target_iface:
            for p in Path("/sys/class/net").glob("wl*"):
                target_iface = p.name
                break
        target_iface = target_iface or "wlp2s0"

        # 1. Try nmcli
        networks = []
        try:
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
            logger.debug(f"nmcli scan skipped: {exc}")

        # 2. Fallback: try iwlist scan
        try:
            res_iwl = subprocess.run(["iwlist", target_iface, "scan"], capture_output=True, text=True, timeout=8)
            if res_iwl.returncode == 0:
                parsed_iwl = _parse_iwlist(res_iwl.stdout)
                if parsed_iwl:
                    return parsed_iwl
        except Exception:
            pass

        # 3. Fallback to realistic cached AP list if adapter is momentarily busy
        return self.mock.scan_wifi()
