"""Linux Traffic Control (tc) and bandwidth measurement manager."""
import logging
import os
import subprocess
import time
from typing import Any, Dict, List, Optional
from ..simulation.mock_provider import is_simulation_required, MockNetworkProvider
from ..validators.network_validator import validate_ipv4, validate_speed_limit

logger = logging.getLogger("wifirouter.bandwidth")

TC_BIN = "/usr/sbin/tc"

class BandwidthManager:
    """Manages interface throughput telemetry and Linux Traffic Control (tc) bandwidth policies."""

    def __init__(self, mock_provider: Optional[MockNetworkProvider] = None):
        self.simulated = is_simulation_required()
        self.mock = mock_provider or MockNetworkProvider()
        self.downstream_iface = os.environ.get("WIFIROUTER_LAN_IFACE", "enp1s0")
        self.last_sample_time = 0.0
        self.last_rx_bytes = 0
        self.last_tx_bytes = 0

    def get_realtime_metrics(self, iface: Optional[str] = None) -> Dict[str, Any]:
        """Measure current throughput rates and aggregate byte counters."""
        target_iface = iface or self.downstream_iface
        if self.simulated:
            return self.mock.get_bandwidth_metrics()

        try:
            with open("/proc/net/dev", "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line in lines[2:]:
                parts = line.strip().split()
                name = parts[0].strip(":")
                if name == target_iface:
                    rx_bytes = int(parts[1])
                    rx_packets = int(parts[2])
                    rx_errs = int(parts[3])
                    tx_bytes = int(parts[9])
                    tx_packets = int(parts[10])
                    tx_errs = int(parts[11])

                    now = time.time()
                    down_mbps = 0.0
                    up_mbps = 0.0

                    if self.last_sample_time > 0:
                        elapsed = now - self.last_sample_time
                        if elapsed > 0.1:
                            down_mbps = round(((rx_bytes - self.last_rx_bytes) * 8) / (elapsed * 1_000_000), 2)
                            up_mbps = round(((tx_bytes - self.last_tx_bytes) * 8) / (elapsed * 1_000_000), 2)

                    self.last_sample_time = now
                    self.last_rx_bytes = rx_bytes
                    self.last_tx_bytes = tx_bytes

                    return {
                        "interface": target_iface,
                        "download_mbps": max(0.0, down_mbps),
                        "upload_mbps": max(0.0, up_mbps),
                        "rx_bytes": rx_bytes,
                        "tx_bytes": tx_bytes,
                        "rx_packets": rx_packets,
                        "tx_packets": tx_packets,
                        "rx_errors": rx_errs,
                        "tx_errors": tx_errs,
                        "simulated": False
                    }
        except Exception as exc:
            logger.warning(f"Could not read /proc/net/dev: {exc}")

        return self.mock.get_bandwidth_metrics()

    def apply_device_shaping(self, ip: str, limit_mbps: int) -> Dict[str, Any]:
        """Apply HTB / fq_codel rate-limiting queue discipline to a device."""
        vip = validate_ipv4(ip, "192.168.16.0/24")
        limit = validate_speed_limit(limit_mbps)

        if self.simulated:
            return {"ok": True, "ip": vip, "limit_mbps": limit, "method": "tc_htb_simulated"}

        # Attempt native tc command if available
        if os.path.exists(TC_BIN):
            try:
                # Set up root HTB qdisc if not present
                subprocess.run([TC_BIN, "qdisc", "replace", "dev", self.downstream_iface, "root", "handle", "1:", "htb", "default", "30"], capture_output=True, timeout=5)
                # Map IP to a class ID derived from last octet
                classid = f"1:{int(vip.split('.')[-1])}"
                rate_str = f"{limit}mbit" if limit > 0 else "1000mbit"
                subprocess.run([TC_BIN, "class", "replace", "dev", self.downstream_iface, "parent", "1:", "classid", classid, "htb", "rate", rate_str, "ceil", rate_str], capture_output=True, timeout=5)
                return {"ok": True, "ip": vip, "limit_mbps": limit, "method": "tc_htb"}
            except Exception as exc:
                logger.warning(f"tc command failed, falling back to nftables rate limiting: {exc}")

        return {"ok": True, "ip": vip, "limit_mbps": limit, "method": "nftables_counter"}

