"""Async client for communicating with the privileged network-agent service."""
import logging
from typing import Any, Dict, List, Optional
import httpx
from ..core.config import settings

logger = logging.getLogger("wifirouter.agent_client")

class NetworkAgentClient:
    """Async HTTP client to network-agent daemon with in-process simulation fallback."""

    def __init__(self):
        self.base_url = settings.AGENT_BASE_URL.rstrip("/")
        self.secret = settings.AGENT_SECRET
        self._in_process_controller = None

    def _get_fallback_controller(self):
        """Lazy-load the in-process AgentController for development and unit testing."""
        if self._in_process_controller is None:
            try:
                import sys
                from pathlib import Path
                # Ensure network-agent directory is in sys.path
                root_agent_dir = Path(__file__).resolve().parent.parent.parent.parent / "network-agent"
                if str(root_agent_dir) not in sys.path:
                    sys.path.insert(0, str(root_agent_dir))
                from agent.controller import AgentController
                self._in_process_controller = AgentController()
            except Exception as exc:
                logger.warning(f"Could not initialize in-process AgentController fallback: {exc}")
        return self._in_process_controller

    async def _request(self, method: str, endpoint: str, payload: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        headers = {
            "X-Agent-Secret": self.secret,
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                if method.upper() == "GET":
                    resp = await client.get(url, headers=headers, params=params)
                else:
                    resp = await client.post(url, headers=headers, json=payload or {})

                if resp.status_code == 200:
                    return resp.json()
                else:
                    logger.warning(f"Agent daemon HTTP {resp.status_code} ({url}): {resp.text}")
        except Exception as exc:
            logger.warning(f"HTTP request to agent daemon ({url}) failed: {exc}. Using fallback...")

        # Fallback to in-process controller if available
        ctrl = self._get_fallback_controller()
        clean = endpoint.rstrip("/")
        if not ctrl:
            logger.warning(f"Network agent unreachable and in-process controller unavailable for {clean}")
            if clean == "/wifi/status":
                return {"connected": False, "interface": "wlp2s0", "ssid": None, "signal_percent": 0, "security": "Unknown"}
            elif clean == "/wifi/scan":
                return {"networks": []}
            elif clean == "/interfaces":
                return {"interfaces": []}
            elif clean == "/devices":
                return {"devices": []}
            elif clean == "/bandwidth":
                return {"interface": "enp1s0", "download_mbps": 0.0, "upload_mbps": 0.0, "rx_bytes": 0, "tx_bytes": 0}
            elif clean == "/summary":
                return {
                    "active_devices": 0, "blocked_devices": 0, "active_guests": 0,
                    "download_mbps": 0.0, "upload_mbps": 0.0, "cpu_percent": 0.0,
                    "ram_percent": 0.0, "uptime_seconds": 0
                }
            return {}
        if method.upper() == "GET":
            if clean == "/summary":
                return ctrl.get_dashboard_summary()
            elif clean == "/interfaces":
                return {"interfaces": ctrl.interfaces.list_interfaces()}
            elif clean == "/wifi/status":
                return ctrl.interfaces.get_wifi_status()
            elif clean == "/wifi/scan":
                return {"networks": ctrl.interfaces.scan_wifi_networks()}
            elif clean == "/routes":
                return {"routes": ctrl.routing.get_routes(), "default_gateway": ctrl.routing.get_default_gateway()}
            elif clean == "/devices":
                return {"devices": ctrl.dhcp.discover_devices()}
            elif clean == "/bandwidth":
                return ctrl.bandwidth.get_realtime_metrics()
            elif clean == "/firewall":
                return ctrl.firewall.get_status()
            elif clean == "/dns/activity":
                client_ip = params.get("client") if params else None
                return {"queries": ctrl.dns.get_recent_queries(client_ip)}
            elif clean == "/captive/sessions":
                return {"sessions": ctrl.captive.get_active_sessions()}
            elif clean == "/system/health":
                return ctrl.monitoring.get_full_health()
        elif method.upper() == "POST":
            p = payload or {}
            if clean == "/firewall/block":
                return ctrl.firewall.set_block(p.get("ip", ""), bool(p.get("blocked", True)))
            elif clean == "/firewall/group":
                return ctrl.firewall.set_device_group(p.get("ip", ""), p.get("group", "default"))
            elif clean == "/bandwidth/shape":
                limit = int(p.get("speed_limit_mbps", 0))
                ctrl.firewall.set_speed_limit(p.get("ip", ""), limit)
                return ctrl.bandwidth.apply_device_shaping(p.get("ip", ""), limit)
            elif clean == "/dns/clear":
                return ctrl.dns.clear_logs()
            elif clean == "/captive/authorize":
                return ctrl.captive.authorize_client(
                    p.get("ip", ""),
                    p.get("plan_id", "starter"),
                    int(p.get("duration_minutes", 30)),
                    int(p.get("speed_limit_mbps", 0))
                )
            elif clean == "/captive/revoke":
                return ctrl.captive.revoke_client(p.get("ip", ""))

        return {"ok": True}

    async def get_summary(self) -> Dict[str, Any]:
        return await self._request("GET", "/summary")

    async def get_interfaces(self) -> List[Dict[str, Any]]:
        res = await self._request("GET", "/interfaces")
        return res.get("interfaces", [])

    async def get_wifi_status(self) -> Dict[str, Any]:
        return await self._request("GET", "/wifi/status")

    async def scan_wifi(self) -> List[Dict[str, Any]]:
        res = await self._request("GET", "/wifi/scan")
        return res.get("networks", [])

    async def get_routes(self) -> Dict[str, Any]:
        return await self._request("GET", "/routes")

    async def discover_devices(self) -> List[Dict[str, Any]]:
        res = await self._request("GET", "/devices")
        return res.get("devices", [])

    async def get_bandwidth(self, iface: Optional[str] = None) -> Dict[str, Any]:
        params = {"iface": iface} if iface else None
        return await self._request("GET", "/bandwidth", params=params)

    async def get_firewall_status(self) -> Dict[str, Any]:
        return await self._request("GET", "/firewall")

    async def set_block(self, ip: str, blocked: bool) -> Dict[str, Any]:
        return await self._request("POST", "/firewall/block", {"ip": ip, "blocked": blocked})

    async def set_group(self, ip: str, group: str) -> Dict[str, Any]:
        return await self._request("POST", "/firewall/group", {"ip": ip, "group": group})

    async def set_speed_limit(self, ip: str, speed_limit_mbps: int) -> Dict[str, Any]:
        return await self._request("POST", "/bandwidth/shape", {"ip": ip, "speed_limit_mbps": speed_limit_mbps})

    async def get_dns_activity(self, client_ip: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        params = {"client": client_ip, "limit": limit} if client_ip else {"limit": limit}
        res = await self._request("GET", "/dns/activity", params=params)
        return res.get("queries", [])

    async def clear_dns_activity(self) -> Dict[str, Any]:
        return await self._request("POST", "/dns/clear")

    async def get_captive_sessions(self) -> Dict[str, Any]:
        res = await self._request("GET", "/captive/sessions")
        return res.get("sessions", {})

    async def authorize_guest(self, ip: str, plan_id: str, duration_minutes: int, speed_limit_mbps: int = 0) -> Dict[str, Any]:
        return await self._request("POST", "/captive/authorize", {
            "ip": ip,
            "plan_id": plan_id,
            "duration_minutes": duration_minutes,
            "speed_limit_mbps": speed_limit_mbps
        })

    async def revoke_guest(self, ip: str) -> Dict[str, Any]:
        return await self._request("POST", "/captive/revoke", {"ip": ip})

    async def get_system_health(self) -> Dict[str, Any]:
        return await self._request("GET", "/system/health")

agent_client = NetworkAgentClient()

