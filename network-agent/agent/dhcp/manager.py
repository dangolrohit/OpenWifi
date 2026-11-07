"""DHCP lease inspection, ICMP/ARP active probe, and Linux neighbour device discovery."""
import concurrent.futures
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
    Path("/var/lib/NetworkManager/dnsmasq-shared.leases"),
    Path("/run/dnsmasq/dnsmasq.leases"),
    Path("/var/lib/dhcp/dhcpd.leases"),
    Path("/tmp/dnsmasq.leases"),
]

class DhcpManager:
    """Discovers connected devices using DHCP lease files, live ARP probing, and Linux neighbour tables."""

    def __init__(self, mock_provider: Optional[MockNetworkProvider] = None):
        self.simulated = is_simulation_required()
        self.mock = mock_provider or MockNetworkProvider()

    def get_dhcp_leases(self) -> Dict[str, Dict[str, Any]]:
        """Parse active dnsmasq and system DHCP lease files."""
        leases: Dict[str, Dict[str, Any]] = {}
        candidate_paths = list(LEASE_FILES)

        # Dynamically discover any NetworkManager dnsmasq lease files
        nm_dir = Path("/var/lib/NetworkManager")
        if nm_dir.is_dir():
            try:
                candidate_paths.extend(nm_dir.glob("dnsmasq*.leases"))
            except Exception:
                pass

        seen_paths = set()
        for lpath in candidate_paths:
            if lpath in seen_paths or not lpath.exists():
                continue
            seen_paths.add(lpath)
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
        """Query kernel neighbour/ARP table via `ip -j neigh` and /proc/net/arp."""
        neighbours: Dict[str, Dict[str, Any]] = {}
        try:
            res = subprocess.run(["ip", "-j", "neigh", "show"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
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

        # Augment with /proc/net/arp if available on Linux
        arp_path = Path("/proc/net/arp")
        if arp_path.exists():
            try:
                with arp_path.open("r", encoding="utf-8") as f:
                    lines = f.readlines()[1:]  # skip header
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 6:
                            ip = parts[0]
                            flags = parts[2]
                            mac = parts[3].lower()
                            dev = parts[5]
                            if flags == "0x2" and mac != "00:00:00:00:00:00":
                                if ip not in neighbours or neighbours[ip]["state"] in ("FAILED", "UNKNOWN"):
                                    neighbours[ip] = {
                                        "ip": ip,
                                        "mac": mac,
                                        "dev": dev,
                                        "state": "REACHABLE"
                                    }
            except Exception as exc:
                logger.debug(f"Reading /proc/net/arp: {exc}")

        return neighbours

    def probe_candidates(self, ips: List[str]):
        """Concurrently probe candidate IPs with 1 fast ICMP ping to refresh kernel ARP states."""
        if not ips:
            return

        def _ping_one(ip: str):
            try:
                subprocess.run(
                    ["ping", "-c", "1", "-W", "1", ip],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1.2
                )
            except Exception:
                pass

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, len(ips))) as executor:
                list(executor.map(_ping_one, ips, timeout=1.5))
        except Exception as exc:
            logger.debug(f"ARP probe batch error: {exc}")

    def discover_devices(self) -> List[Dict[str, Any]]:
        """Combine DHCP leases and neighbour table into unified device records with live online status."""
        if self.simulated:
            return self.mock.get_devices()

        leases = self.get_dhcp_leases()
        initial_neighbours = self.get_neighbours()
        all_candidate_ips = {
            ip for ip in (set(leases.keys()) | set(initial_neighbours.keys()))
            if ip.startswith("192.168.16.") and ip not in ("192.168.16.1", "192.168.16.2", "192.168.16.255")
        }

        # Concurrently probe candidates to refresh kernel ARP states
        if all_candidate_ips:
            self.probe_candidates(list(all_candidate_ips))

        # Read fresh neighbour table after active probes
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
            state = neigh.get("state", "DISCONNECTED")

            is_online = state in ("REACHABLE", "DELAY", "PERMANENT")

            discovered.append({
                "ip": ip,
                "mac": mac,
                "hostname": hostname,
                "status": state if is_online else "DISCONNECTED",
                "is_online": is_online,
                "first_seen": now - 3600,
                "last_seen": now if is_online else now - 300,
                "simulated": False
            })

        return discovered

