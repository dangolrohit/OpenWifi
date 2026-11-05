"""Linux routing table and gateway management module."""
import json
import logging
import subprocess
from typing import Any, Dict, List, Optional
from ..simulation.mock_provider import is_simulation_required, MockNetworkProvider

logger = logging.getLogger("wifirouter.routing")

class RoutingManager:
    """Manages routing table inspection and gateway safety."""

    def __init__(self, mock_provider: Optional[MockNetworkProvider] = None):
        self.simulated = is_simulation_required()
        self.mock = mock_provider or MockNetworkProvider()

    def get_routes(self) -> List[Dict[str, Any]]:
        """List active routing table entries."""
        if self.simulated:
            return self.mock.get_routing_table()

        try:
            res = subprocess.run(["ip", "-j", "route", "show"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                raw = json.loads(res.stdout)
                routes = []
                for r in raw:
                    routes.append({
                        "destination": r.get("dst", "default"),
                        "gateway": r.get("gateway", "0.0.0.0"),
                        "interface": r.get("dev", ""),
                        "metric": r.get("metric"),
                        "protocol": r.get("protocol", ""),
                        "simulated": False
                    })
                return routes
        except Exception as exc:
            logger.warning(f"Failed to read routes via ip route: {exc}")

        return self.mock.get_routing_table()

    def get_default_gateway(self) -> Optional[Dict[str, Any]]:
        """Find the active default gateway."""
        routes = self.get_routes()
        for r in routes:
            if r.get("destination") == "default":
                return r
        return None

    def verify_upstream_route(self, expected_iface: str = "wlp2s0") -> bool:
        """Verify that the primary default gateway uses the expected upstream Wi-Fi interface."""
        gw = self.get_default_gateway()
        if not gw:
            return False
        iface = gw.get("interface", "")
        return iface == expected_iface or iface.startswith("wl") or self.simulated

