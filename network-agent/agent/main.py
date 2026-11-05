"""Lightweight, secure HTTP agent daemon listening on 127.0.0.1:8091 for privileged host networking tasks."""
import json
import logging
import os
import sys
import threading
import time
from typing import Any
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from .controller import AgentController
from .security.ipc_auth import get_or_create_shared_secret, verify_token

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [wifirouter-agent] %(message)s"
)
logger = logging.getLogger("wifirouter.agent")

AGENT_HOST = os.environ.get("WIFIROUTER_AGENT_HOST", "127.0.0.1")
AGENT_PORT = int(os.environ.get("WIFIROUTER_AGENT_PORT", "8091"))

class AgentRequestHandler(BaseHTTPRequestHandler):
    server_version = "WiFiRouter-Agent/2.0"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format, *args):
        # Concise logging
        logger.debug(f"{self.client_address[0]} - {format % args}")

    def respond_json(self, status_code: int, data: Any):
        """Send a JSON HTTP response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def is_authorized(self) -> bool:
        """Validate token from X-Agent-Secret or Authorization header."""
        secret = self.server.shared_secret
        token = self.headers.get("X-Agent-Secret")
        if not token:
            auth_hdr = self.headers.get("Authorization", "")
            if auth_hdr.startswith("Bearer "):
                token = auth_hdr.split(" ", 1)[1]
        return verify_token(token, secret)

    def do_GET(self):
        url = urlparse(self.path)
        clean_path = url.path.rstrip("/")
        qs = parse_qs(url.query)

        # Health endpoint does not require auth
        if clean_path in ("", "/health"):
            self.respond_json(200, {"status": "ok", "service": "wifirouter-agent", "time": time.time()})
            return

        if not self.is_authorized():
            self.respond_json(401, {"error": "Unauthorized: invalid or missing agent secret"})
            return

        ctrl: AgentController = self.server.controller

        try:
            if clean_path == "/summary":
                self.respond_json(200, ctrl.get_dashboard_summary())
            elif clean_path == "/interfaces":
                self.respond_json(200, {"interfaces": ctrl.interfaces.list_interfaces()})
            elif clean_path == "/wifi/status":
                self.respond_json(200, ctrl.interfaces.get_wifi_status())
            elif clean_path == "/wifi/scan":
                self.respond_json(200, {"networks": ctrl.interfaces.scan_wifi_networks()})
            elif clean_path == "/routes":
                self.respond_json(200, {"routes": ctrl.routing.get_routes(), "default_gateway": ctrl.routing.get_default_gateway()})
            elif clean_path == "/devices":
                self.respond_json(200, {"devices": ctrl.dhcp.discover_devices()})
            elif clean_path == "/bandwidth":
                iface = qs.get("iface", [None])[0]
                self.respond_json(200, ctrl.bandwidth.get_realtime_metrics(iface))
            elif clean_path == "/firewall":
                self.respond_json(200, ctrl.firewall.get_status())
            elif clean_path == "/dns/device-activity":
                self.respond_json(200, ctrl.dns.get_device_activity(
                    qs.get("client", [""])[0], int(qs.get("page", ["1"])[0])))
            elif clean_path == "/dns/activity":
                client = qs.get("client", [None])[0]
                limit = int(qs.get("limit", [200])[0])
                self.respond_json(200, {"queries": ctrl.dns.get_recent_queries(client, limit)})
            elif clean_path == "/captive/sessions":
                self.respond_json(200, {"sessions": ctrl.captive.get_active_sessions()})
            elif clean_path == "/system/health":
                self.respond_json(200, ctrl.monitoring.get_full_health())
            elif clean_path == "/snapshots":
                self.respond_json(200, {"snapshots": ctrl.rollback_mgr.list_snapshots()})
            else:
                self.respond_json(404, {"error": f"Endpoint not found: {clean_path}"})
        except Exception as exc:
            logger.error(f"Error handling GET {clean_path}: {exc}", exc_info=True)
            self.respond_json(500, {"error": str(exc)})

    def do_POST(self):
        if not self.is_authorized():
            self.respond_json(401, {"error": "Unauthorized: invalid or missing agent secret"})
            return

        url = urlparse(self.path)
        clean_path = url.path.rstrip("/")

        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
        except Exception:
            self.respond_json(400, {"error": "Invalid JSON body"})
            return

        ctrl: AgentController = self.server.controller

        try:
            if clean_path == "/firewall/block":
                ip = payload.get("ip")
                blocked = bool(payload.get("blocked", True))
                res = ctrl.firewall.set_block(ip, blocked)
                self.respond_json(200, res)
            elif clean_path == "/firewall/group":
                ip = payload.get("ip")
                group = payload.get("group", "default")
                res = ctrl.firewall.set_device_group(ip, group)
                self.respond_json(200, res)
            elif clean_path == "/bandwidth/shape":
                ip = payload.get("ip")
                limit_mbps = int(payload.get("speed_limit_mbps", 0))
                res = ctrl.firewall.set_speed_limit(ip, limit_mbps)
                ctrl.bandwidth.apply_device_shaping(ip, limit_mbps)
                self.respond_json(200, res)
            elif clean_path == "/dns/clear":
                res = ctrl.dns.clear_logs()
                self.respond_json(200, res)
            elif clean_path == "/captive/authorize":
                ip = payload.get("ip")
                plan_id = payload.get("plan_id", "starter")
                duration = int(payload.get("duration_minutes", 30))
                speed = int(payload.get("speed_limit_mbps", 0))
                res = ctrl.authorize_guest(ip, plan_id, duration, speed)
                self.respond_json(200, res)
            elif clean_path == "/captive/revoke":
                ip = payload.get("ip")
                res = ctrl.revoke_guest(ip)
                self.respond_json(200, res)
            else:
                self.respond_json(404, {"error": f"Endpoint not found: {clean_path}"})
        except Exception as exc:
            logger.error(f"Error handling POST {clean_path}: {exc}", exc_info=True)
            self.respond_json(400, {"error": str(exc)})

def background_maintenance(controller: AgentController):
    """Background task running every 20 seconds for guest session expiry and health sync."""
    while True:
        try:
            time.sleep(20)
            controller.sync_guest_expiries()
        except Exception as exc:
            logger.warning(f"Error in background maintenance loop: {exc}")

def run_agent():
    """Start the network agent daemon."""
    controller = AgentController()
    controller.restore_guest_firewall()
    shared_secret = get_or_create_shared_secret()

    server = ThreadingHTTPServer((AGENT_HOST, AGENT_PORT), AgentRequestHandler)
    server.controller = controller
    server.shared_secret = shared_secret

    # Start background maintenance thread
    m_thread = threading.Thread(target=background_maintenance, args=(controller,), daemon=True)
    m_thread.start()

    logger.info(f"WiFiRouter Network Agent listening at http://{AGENT_HOST}:{AGENT_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping network agent...")
        server.server_close()

if __name__ == "__main__":
    run_agent()

