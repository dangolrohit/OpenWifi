"""nftables firewall management for device filtering, customer isolation, and captive enforcement."""
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from ..simulation.mock_provider import is_simulation_required, MockNetworkProvider
from ..validators.network_validator import validate_ipv4, check_host_protection
from ..recovery.rollback_manager import RollbackManager

logger = logging.getLogger("wifirouter.firewall")

NFT_BIN = "/usr/sbin/nft"
STATE_FILE = Path(os.environ.get("WIFIROUTER_FIREWALL_STATE", "/var/lib/wifirouter/firewall_state.json"))

class FirewallManager:
    """Manages dedicated nftables table `inet wifirouter` without interfering with host Docker or Tailscale."""

    def __init__(self, rollback_mgr: Optional[RollbackManager] = None, mock_provider: Optional[MockNetworkProvider] = None):
        self.simulated = is_simulation_required()
        self.mock = mock_provider or MockNetworkProvider()
        self.rollback_mgr = rollback_mgr or RollbackManager()
        self.downstream_iface = os.environ.get("WIFIROUTER_LAN_IFACE", "enp1s0")
        self.host_ips = {"127.0.0.1", "192.168.16.2", "192.168.16.1"}
        self.state_file = STATE_FILE

    def load_state(self) -> Dict[str, Any]:
        """Load persistent firewall state from disk or return default."""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "captive_enabled": True,
            "blocked": [],
            "customers": [],
            "whitelisted": ["192.168.16.101"],
            "authenticated": [],
            "speed_limits": {}
        }

    def save_state(self, state: Dict[str, Any]) -> None:
        """Atomically persist state to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.state_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
            tmp.replace(self.state_file)
        except Exception as exc:
            logger.warning(f"Could not save firewall state: {exc}")

    def build_ruleset(self, state: Dict[str, Any]) -> str:
        """Construct atomic nftables script."""
        iface = self.downstream_iface
        captive_on = state.get("captive_enabled", True)
        blocked = sorted(list(set(state.get("blocked", []))))
        customers = sorted(list(set(state.get("customers", []))))
        whitelisted = sorted(list(set(state.get("whitelisted", []))))
        authenticated = sorted(list(set(state.get("authenticated", []))))
        speed_limits = state.get("speed_limits", {})

        script = ""
        # Clean both wifirouter table and legacy oshin_dashboard table if present
        script += "delete table inet wifirouter\n"
        script += "add table inet wifirouter\n"

        # Sets
        script += "add set inet wifirouter blocked { type ipv4_addr; }\n"
        script += "add set inet wifirouter customers { type ipv4_addr; }\n"
        script += "add set inet wifirouter whitelisted { type ipv4_addr; }\n"
        script += "add set inet wifirouter authenticated { type ipv4_addr; }\n"

        # Input Chain
        script += "add chain inet wifirouter input { type filter hook input priority -10; policy accept; }\n"
        # Customer isolation: customers cannot access admin portal on port 8090
        script += f'add rule inet wifirouter input iifname "{iface}" ip saddr @customers tcp dport 8090 counter drop\n'

        # Prerouting NAT Chain (Redirect port 80 to captive portal on 8088)
        script += "add chain inet wifirouter prerouting { type nat hook prerouting priority dstnat; policy accept; }\n"
        if captive_on:
            script += f'add rule inet wifirouter prerouting iifname "{iface}" ip saddr != @whitelisted ip saddr != @authenticated tcp dport 80 redirect to :8088\n'

        # Forward Chain (Access blocks, guest isolation, DNS-over-TLS drop, captive gate)
        script += "add chain inet wifirouter forward { type filter hook forward priority -10; policy accept; }\n"
        script += f'add rule inet wifirouter forward iifname "{iface}" ip saddr @blocked counter drop\n'
        script += f'add rule inet wifirouter forward oifname "{iface}" ip daddr @blocked counter drop\n'

        # Drop DNS-over-TLS (port 853) so smartphones fallback to standard port 53 DNS
        script += f'add rule inet wifirouter forward iifname "{iface}" tcp dport 853 counter drop\n'

        # Customer client-to-client isolation (customers cannot reach family LAN devices)
        script += f'add rule inet wifirouter forward iifname "{iface}" oifname "{iface}" ip saddr @customers counter drop\n'
        script += f'add rule inet wifirouter forward iifname "{iface}" oifname "{iface}" ip daddr @customers counter drop\n'

        # Speed limits (rate limiting) per IP
        for ip, mbps in sorted(speed_limits.items()):
            try:
                vip = validate_ipv4(ip)
                rate_kb = int(mbps * 125)  # 1 Mbps = 125 KB/s
                if rate_kb > 0:
                    burst = max(100, int(rate_kb * 0.2))
                    script += f'add rule inet wifirouter forward iifname "{iface}" ip saddr {vip} limit rate over {rate_kb} kbytes/second burst {burst} kbytes counter drop\n'
                    script += f'add rule inet wifirouter forward oifname "{iface}" ip daddr {vip} limit rate over {rate_kb} kbytes/second burst {burst} kbytes counter drop\n'
            except Exception:
                continue

        # Captive portal forward barrier
        if captive_on:
            script += f'add rule inet wifirouter forward iifname "{iface}" ip saddr @whitelisted accept\n'
            script += f'add rule inet wifirouter forward iifname "{iface}" ip saddr @authenticated accept\n'
            script += f'add rule inet wifirouter forward iifname "{iface}" counter drop\n'

        # Populate Sets
        if blocked:
            script += "add element inet wifirouter blocked { " + ", ".join(blocked) + " }\n"
        if customers:
            script += "add element inet wifirouter customers { " + ", ".join(customers) + " }\n"
        if whitelisted:
            script += "add element inet wifirouter whitelisted { " + ", ".join(whitelisted) + " }\n"
        if authenticated:
            script += "add element inet wifirouter authenticated { " + ", ".join(authenticated) + " }\n"

        return script

    def apply_ruleset(self, state: Dict[str, Any]) -> None:
        """Atomically apply nftables ruleset with rollback safety."""
        if self.simulated:
            return

        # Snapshot before modification
        current_state = self.load_state()
        snapshot_id = self.rollback_mgr.create_snapshot("firewall", current_state, "Pre-ruleset apply")

        script = self.build_ruleset(state)
        res = subprocess.run([NFT_BIN, "-f", "-"], input=script, text=True, capture_output=True, timeout=10)
        if res.returncode != 0:
            logger.error(f"nftables transaction failed: {res.stderr}. Rolling back...")
            # Revert to snapshot
            revert_script = self.build_ruleset(current_state)
            subprocess.run([NFT_BIN, "-f", "-"], input=revert_script, text=True, capture_output=True)
            raise RuntimeError(f"Firewall configuration error: {res.stderr.strip()}")

        self.save_state(state)

    def get_status(self) -> Dict[str, Any]:
        """Get live firewall status."""
        if self.simulated:
            return self.mock.get_firewall_status()

        state = self.load_state()
        return {
            "table": "inet wifirouter",
            "captive_enabled": state.get("captive_enabled", True),
            "blocked": state.get("blocked", []),
            "customers": state.get("customers", []),
            "whitelisted": state.get("whitelisted", []),
            "authenticated": state.get("authenticated", []),
            "speed_limits": state.get("speed_limits", {}),
            "simulated": False
        }

    def set_block(self, ip: str, blocked: bool) -> Dict[str, Any]:
        """Block or unblock a client IP."""
        vip = validate_ipv4(ip, "192.168.16.0/24")
        check_host_protection(vip, self.host_ips)

        if self.simulated:
            return self.mock.set_device_block(vip, blocked)

        state = self.load_state()
        current_blocked = set(state.get("blocked", []))
        if blocked:
            current_blocked.add(vip)
        else:
            current_blocked.discard(vip)
        state["blocked"] = sorted(list(current_blocked))
        self.apply_ruleset(state)
        return {"ok": True, "ip": vip, "blocked": blocked, "simulated": False}

    def set_device_group(self, ip: str, group: str) -> Dict[str, Any]:
        """Update device classification (family, customer, staff, default)."""
        vip = validate_ipv4(ip, "192.168.16.0/24")
        if self.simulated:
            return {"ok": True, "ip": vip, "group": group, "simulated": True}

        state = self.load_state()
        whitelisted = set(state.get("whitelisted", []))
        customers = set(state.get("customers", []))

        whitelisted.discard(vip)
        customers.discard(vip)

        if group in ("family", "staff"):
            whitelisted.add(vip)
        elif group == "customer":
            customers.add(vip)

        state["whitelisted"] = sorted(list(whitelisted))
        state["customers"] = sorted(list(customers))
        self.apply_ruleset(state)
        return {"ok": True, "ip": vip, "group": group, "simulated": False}

    def set_speed_limit(self, ip: str, limit_mbps: int) -> Dict[str, Any]:
        """Configure rate limit in Mbps for a device."""
        vip = validate_ipv4(ip, "192.168.16.0/24")
        if self.simulated:
            return self.mock.set_speed_limit(vip, limit_mbps)

        state = self.load_state()
        limits = state.get("speed_limits", {})
        if limit_mbps > 0:
            limits[vip] = limit_mbps
        else:
            limits.pop(vip, None)
        state["speed_limits"] = limits
        self.apply_ruleset(state)
        return {"ok": True, "ip": vip, "speed_limit_mbps": limit_mbps, "simulated": False}

    def update_guest_sessions(self, active_ips: List[str]) -> None:
        """Update authenticated guest IP elements."""
        if self.simulated:
            return
        state = self.load_state()
        state["authenticated"] = sorted(list(set(active_ips)))
        self.apply_ruleset(state)
