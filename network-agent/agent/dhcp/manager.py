"""DHCP lease inspection and Linux ARP/neighbour device discovery."""
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..simulation.mock_provider import is_simulation_required, MockNetworkProvider

logger = logging.getLogger("wifirouter.dhcp")

LEASE_FILES = [
    Path("/var/lib/misc/dnsmasq.leases"),
    Path("/var/lib/NetworkManager/dnsmasq-enp1s0.leases"),
    Path("/var/lib/NetworkManager/dnsmasq-shared.leases")
]

class DhcpManager:
    """Discovers connected devices using DHCP lease files and Linux neighbour tables."""

    def __init__(self, mock_provider: Optional[MockNetworkProvider] = None):
        self.simulated = is_simulation_required()
        self.mock = mock_provider or MockNetworkProvider()

    def get_dhcp_leases(self) -> Dict[str, Dict[str, Any]]:
        """Parse active dnsmasq DHCP leases."""
        leases: Dict[str, Dict[str, Any]] = {}
        for lpath in LEASE_FILES:
            if lpath.exists():
                try:
                    with lpath.open("r", encoding="utf-8") as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) >= 4:
                                # expiry_ts, mac, ip, hostname, client_id
                                exp_ts = int(parts[0]) if parts[0].isdigit() else 0
                                mac = parts[1].lower()
                                ip = parts[2]
                                hostname = parts[3] if parts[3] != "*" else ""
                                leases[ip] = {
                                    "ip": ip,
                                    "mac": mac,
                                    "hostname": hostname,
                                    "expires_at": exp_ts
                                }
                except Exception as exc:
                    logger.warning(f"Error reading lease file {lpath}: {exc}")
        return leases

    def get_neighbours(self) -> Dict[str, Dict[str, Any]]:
        """Query kernel neighbour/ARP table via `ip -j neigh`."""
        neighbours: Dict[str, Dict[str, Any]] = {}
        try:
            res = subprocess.run(["ip", "-j", "neigh", "show"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                for item in data:
                    dst = item.get("dst")
                    lladdr = item.get("lladdr")
                    state = item.get("state", ["UNKNOWN"])
                    state_str = state[0] if isinstance(state, list) and state else str(state)
                    if dst and lladdr:
                        neighbours[dst] = {
                            "ip": dst,
                            "mac": lladdr.lower(),
                            "dev": item.get("dev"),
                            "state": state_str
                        }
        except Exception as exc:
            logger.warning(f"Failed to query neighbour table: {exc}")
        return neighbours

    def discover_devices(self) -> List[Dict[str, Any]]:
        """Combine DHCP leases and neighbour table into unified device records."""
        if self.simulated:
            return self.mock.get_devices()

        leases = self.get_dhcp_leases()
        neighbours = self.get_neighbours()
        all_ips = set(leases.keys()) | set(neighbours.keys())

        discovered: List[Dict[str, Any]] = []
        now = time.time()

        for ip in sorted(all_ips):
            # Only consider client IPs in 192.168.16.0/24 excluding router/gateway
            if not ip.startswith("192.168.16.") or ip in ("192.168.16.1", "192.168.16.2", "192.168.16.255"):
                continue

            lease = leases.get(ip, {})
            neigh = neighbours.get(ip, {})

            mac = lease.get("mac") or neigh.get("mac") or "unknown"
            hostname = lease.get("hostname") or ""
            state = neigh.get("state", "STALE")

            discovered.append({
                "ip": ip,
                "mac": mac,
                "hostname": hostname,
                "status": state,
                "first_seen": now - 3600,
                "last_seen": now if state in ("REACHABLE", "DELAY") else now - 300,
                "simulated": False
            })

        return discovered if discovered else self.mock.get_devices()
