"""Lightweight, standalone captive portal daemon for hotspot probe detection and login redirection."""
import json
import logging
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [wifirouter-captive] %(message)s")
logger = logging.getLogger("wifirouter.captive")

HOST = os.environ.get("WIFIROUTER_CAPTIVE_HOST", "0.0.0.0")
PORT = int(os.environ.get("WIFIROUTER_CAPTIVE_PORT", "8088"))
GATEWAY_IP = os.environ.get("WIFIROUTER_GATEWAY_IP", "192.168.16.2")
BACKEND_URL = os.environ.get("WIFIROUTER_BACKEND_URL", "http://127.0.0.1:8090")
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "index.html"

class CaptiveRequestHandler(BaseHTTPRequestHandler):
    server_version = "WiFiRouter-Captive/2.0"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def respond(self, code: int, data: str = "", content_type: str = "text/html", location: str = None):
        body = data.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        if location:
            self.send_header("Location", location)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        client_ip = self.client_address[0]
        clean_path = self.path.split("?")[0]
        probes = ("/generate_204", "/gen_204", "/hotspot-detect.html", "/connecttest.txt", "/ncsi.txt", "/success.txt")

        # Captive probe handling
        if clean_path in probes:
            try:
                # Check status via backend API
                req = urllib.request.Request(f"{BACKEND_URL}/api/v1/guests/status", headers={"X-Forwarded-For": client_ip})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode())
                        if data.get("authorized"):
                            if "204" in clean_path:
                                self.send_response(204)
                                self.end_headers()
                                return
                            self.respond(200, "Success", "text/plain")
                            return
            except Exception:
                pass

            # Unauthorized: redirect to captive portal landing page
            self.respond(302, "", "text/plain", location=f"http://{GATEWAY_IP}:{PORT}/guest")
            return

        if clean_path in ("/", "/guest"):
            if TEMPLATE_PATH.exists():
                self.respond(200, TEMPLATE_PATH.read_text(encoding="utf-8"), "text/html")
            else:
                self.respond(200, "<h1>WiFiRouter Hotspot</h1><p>Welcome! Tap to connect.</p>", "text/html")
            return

        # Reverse proxy to backend API for guest status
        if clean_path.startswith("/api/v1/guests/"):
            try:
                url = f"{BACKEND_URL}{self.path}"
                req = urllib.request.Request(url, headers={"X-Forwarded-For": client_ip})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    self.respond(resp.status, resp.read().decode(), "application/json")
                return
            except urllib.error.HTTPError as e:
                self.respond(e.code, e.read().decode(), "application/json")
                return
            except Exception as exc:
                self.respond(502, json.dumps({"error": str(exc)}), "application/json")
                return

        # Fallback redirect to captive landing page
        self.respond(302, "", "text/plain", location=f"http://{GATEWAY_IP}:{PORT}/guest")

    def do_POST(self):
        client_ip = self.client_address[0]
        clean_path = self.path.split("?")[0]

        # Reverse proxy to backend API for guest connection
        if clean_path.startswith("/api/v1/guests/"):
            try:
                size = int(self.headers.get("Content-Length", 0))
                payload = self.rfile.read(size) if size > 0 else b"{}"

                url = f"{BACKEND_URL}{self.path}"
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Forwarded-For": client_ip
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    self.respond(resp.status, resp.read().decode(), "application/json")
                return
            except urllib.error.HTTPError as e:
                self.respond(e.code, e.read().decode(), "application/json")
                return
            except Exception as exc:
                self.respond(502, json.dumps({"error": str(exc)}), "application/json")
                return

        self.respond(404, json.dumps({"error": "Not found"}), "application/json")

def run_captive():
    server = ThreadingHTTPServer((HOST, PORT), CaptiveRequestHandler)
    logger.info(f"WiFiRouter Captive Portal listening at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping captive portal...")
        server.server_close()

if __name__ == "__main__":
    run_captive()

