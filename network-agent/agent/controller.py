"""Unified controller orchestrating all network subsystem managers."""
import logging
import time
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

    def sync_guest_expiries(self) -> List[str]:
        """Periodic maintenance task: prune expired guests and refresh firewall set."""
        expired = self.captive.check_expiries()
        if expired:
            active_sessions = self.captive.get_active_sessions()
            self.firewall.update_guest_sessions(list(active_sessions.keys()))
        return expired
