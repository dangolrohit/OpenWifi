"""Unified controller orchestrating all network subsystem managers."""
import logging
import time
import threading
from typing import Any, Dict, List, Optional
from .interfaces.manager import InterfaceManager
from .routing.manager import RoutingManager
from .firewall.manager import FirewallManager
from .bandwidth.manager import BandwidthManager
from .dhcp.manager import DhcpManager
from .dns.manager import DnsActivityManager
from .captive_portal.manager import CaptivePortalManager
from .monitoring.manager import SystemMonitor
from .recovery.rollback_manager import RollbackManager
from .simulation.mock_provider import MockNetworkProvider

logger = logging.getLogger("wifirouter.agent.controller")

class AgentController:
    """Central coordinator for host network operations, policy enforcement, and telemetry."""

    def __init__(self):
        self.guest_lock = threading.RLock()
        self.mock = MockNetworkProvider()
        self.rollback_mgr = RollbackManager()
        self.interfaces = InterfaceManager(self.mock)
        self.routing = RoutingManager(self.mock)
        self.firewall = FirewallManager(self.rollback_mgr, self.mock)
        self.bandwidth = BandwidthManager(self.mock)
        self.dhcp = DhcpManager(self.mock)
        self.dns = DnsActivityManager()
        self.captive = CaptivePortalManager(self.mock)
        self.monitoring = SystemMonitor(self.mock)

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Collect aggregated telemetry for dashboard consumption."""
        bw = self.bandwidth.get_realtime_metrics()
        wifi = self.interfaces.get_wifi_status()
        health = self.monitoring.get_full_health()
        devices = self.dhcp.discover_devices()
        fw_status = self.firewall.get_status()
        guests = self.captive.get_active_sessions()

        return {
            "bandwidth": bw,
            "wifi": wifi,
            "health": health,
            "connected_device_count": len(devices),
            "blocked_device_count": len(fw_status.get("blocked", [])),
            "active_guest_count": len(guests),
            "timestamp": time.time()
        }

    def restore_guest_firewall(self):
        with self.guest_lock:
            self.captive.check_expiries()
            self.firewall.update_guest_sessions(self.captive.get_active_sessions())

    def authorize_guest(self, ip, plan_id, duration, speed):
        with self.guest_lock:
            previous = self.captive.get_active_sessions().copy()
            try:
                result = self.captive.authorize_client(ip, plan_id, duration, speed)
                self.firewall.update_guest_sessions(self.captive.get_active_sessions())
                return result
            except Exception:
                if not self.captive.simulated:
                    self.captive.save_sessions(previous)
                raise

    def revoke_guest(self, ip):
        with self.guest_lock:
            previous = self.captive.get_active_sessions().copy()
            try:
                result = self.captive.revoke_client(ip)
                self.firewall.update_guest_sessions(self.captive.get_active_sessions())
                return result
            except Exception:
                if not self.captive.simulated:
                    self.captive.save_sessions(previous)
                raise

    def sync_guest_expiries(self) -> List[str]:
        """Prune persisted sessions; kernel set timeouts enforce expiry independently."""
        with self.guest_lock:
            expired = self.captive.check_expiries()
            if expired:
                self.firewall.update_guest_sessions(self.captive.get_active_sessions())
            return expired
