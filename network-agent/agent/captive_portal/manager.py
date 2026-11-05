"""Captive Portal and openNDS gateway session manager."""
import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..simulation.mock_provider import is_simulation_required, MockNetworkProvider
from ..validators.network_validator import validate_ipv4

logger = logging.getLogger("wifirouter.captive")

NDSCTL_BIN = "/usr/bin/ndsctl"
GUEST_STATE_FILE = Path(os.environ.get("WIFIROUTER_GUESTS_STATE", "/var/lib/wifirouter/guests.json"))

class CaptivePortalManager:
    """Manages guest hotspot sessions using openNDS (when installed) or native nftables."""

    def __init__(self, mock_provider: Optional[MockNetworkProvider] = None):
        self.simulated = is_simulation_required()
        self.mock = mock_provider or MockNetworkProvider()
        self.has_opennds = bool(shutil.which("ndsctl") or os.path.exists(NDSCTL_BIN))
        self.state_file = GUEST_STATE_FILE

    def load_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Load active guest sessions from disk."""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def save_sessions(self, sessions: Dict[str, Dict[str, Any]]) -> None:
        """Save guest sessions to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.state_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(sessions, indent=2), encoding="utf-8")
            tmp.replace(self.state_file)
        except Exception as exc:
            logger.warning(f"Could not save guest sessions: {exc}")

    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Return all active, unexpired guest sessions."""
        if self.simulated:
            return self.mock.authenticated_guests

        now = time.time()
        sessions = self.load_sessions()
        active = {ip: s for ip, s in sessions.items() if s.get("expires_at", 0) > now}
        return active

    def authorize_client(self, ip: str, plan_id: str, duration_minutes: int, speed_limit_mbps: int = 0) -> Dict[str, Any]:
        """Authorize a client IP for internet access."""
        vip = validate_ipv4(ip, "192.168.16.0/24")
        now = time.time()
        expires_at = now + (duration_minutes * 60)

        session_data = {
            "ip": vip,
            "plan_id": plan_id,
            "speed_limit": speed_limit_mbps,
            "authorized_at": now,
            "expires_at": expires_at
        }

        if self.simulated:
            self.mock.authenticated_guests[vip] = session_data
            return {"ok": True, "session": session_data, "engine": "simulated"}

        # If openNDS is installed, notify ndsctl
        if self.has_opennds:
            try:
                # ndsctl auth IP [minutes] [upload_rate] [download_rate] [upload_quota] [download_quota]
                rate_kb = speed_limit_mbps * 125 if speed_limit_mbps > 0 else 0
                subprocess.run([NDSCTL_BIN, "auth", vip, str(duration_minutes), str(rate_kb), str(rate_kb)], capture_output=True, timeout=5)
            except Exception as exc:
                logger.warning(f"ndsctl auth call failed: {exc}")

        sessions = self.load_sessions()
        sessions[vip] = session_data
        self.save_sessions(sessions)
        return {"ok": True, "session": session_data, "engine": "opennds" if self.has_opennds else "nftables"}

    def revoke_client(self, ip: str) -> Dict[str, Any]:
        """Revoke a guest session immediately."""
        vip = validate_ipv4(ip, "192.168.16.0/24")
        if self.simulated:
            self.mock.authenticated_guests.pop(vip, None)
            return {"ok": True, "ip": vip, "simulated": True}

        if self.has_opennds:
            try:
                subprocess.run([NDSCTL_BIN, "deauth", vip], capture_output=True, timeout=5)
            except Exception:
                pass

        sessions = self.load_sessions()
        sessions.pop(vip, None)
        self.save_sessions(sessions)
        return {"ok": True, "ip": vip}

    def check_expiries(self) -> List[str]:
        """Remove expired sessions and return list of newly expired client IPs."""
        if self.simulated:
            return []

        now = time.time()
        sessions = self.load_sessions()
        expired = [ip for ip, s in sessions.items() if s.get("expires_at", 0) <= now]
        if expired:
            for ip in expired:
                sessions.pop(ip, None)
            self.save_sessions(sessions)
        return expired

