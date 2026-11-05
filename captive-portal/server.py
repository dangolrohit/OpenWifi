"""Lightweight, standalone captive portal daemon for hotspot probe detection and login redirection."""
import hashlib
import hmac
import time
import json
import logging
import os
import urllib.request
from urllib.parse import urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [wifirouter-captive] %(message)s")
logger = logging.getLogger("wifirouter.captive")

HOST = os.environ.get("WIFIROUTER_CAPTIVE_HOST", "0.0.0.0")
PORT = int(os.environ.get("WIFIROUTER_CAPTIVE_PORT", "8088"))
GATEWAY_IP = os.environ.get("WIFIROUTER_GATEWAY_IP", "192.168.16.2")
BACKEND_URL = os.environ.get("WIFIROUTER_BACKEND_URL", "http://127.0.0.1:8090")
PROXY_SECRET = os.environ.get("WIFIROUTER_CAPTIVE_SECRET", "")
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "index.html"

def client_headers(client_ip):
    timestamp = str(int(time.time()))
    signature = hmac.new(PROXY_SECRET.encode(), f"{client_ip}|{timestamp}".encode(), hashlib.sha256).hexdigest()
    return {"X-Captive-IP": client_ip, "X-Captive-Time": timestamp, "X-Captive-Signature": signature}


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
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        client_ip = self.client_address[0]
        clean_path = urlsplit(self.path).path
        probes = {
            "/generate_204": (204, "", "text/plain"),
            "/gen_204": (204, "", "text/plain"),
            "/connecttest.txt": (200, "Microsoft Connect Test", "text/plain"),
            "/ncsi.txt": (200, "Microsoft NCSI", "text/plain"),
            "/hotspot-detect.html": (200, "<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>", "text/html"),
            "/library/test/success.html": (200, "<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>", "text/html"),
            "/success.txt": (200, "success\n", "text/plain"),
        }

        # Captive probe handling
        if clean_path in probes:
            try:
                # Check status via backend API
                req = urllib.request.Request(f"{BACKEND_URL}/api/v1/guests/status", headers=client_headers(client_ip))
                with urllib.request.urlopen(req, timeout=1) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode())
                        if data.get("authorized"):
                            code, body, kind = probes[clean_path]
                            self.respond(code, body, kind)
                            return
            except Exception as exc:
                if isinstance(exc, urllib.error.HTTPError):
                    exc.close()
                logger.warning("Probe status unavailable; showing sign-in: %s", type(exc).__name__)

            logger.info("Captive probe from %s: %s -> /guest", client_ip, clean_path)
            # Unauthorized: redirect to captive portal landing page
            self.respond(302, "", "text/plain", location=f"http://{GATEWAY_IP}:{PORT}/guest")
            return

        if clean_path == "/health":
            self.respond(200, json.dumps({"status": "ok", "service": "captive-portal"}), "application/json")
            return

        if clean_path in ("/", "/guest"):
            # Normalize intercepted root-page probes to the gateway origin so
            # portal assets/API requests do not depend on the original hostname.
            try:
                hostname = urlsplit("//" + self.headers.get("Host", "")).hostname
            except ValueError:
                hostname = None
            if hostname not in (GATEWAY_IP, "127.0.0.1", "localhost"):
                self.respond(302, "", "text/plain", location=f"http://{GATEWAY_IP}:{PORT}/guest")
                return
            if TEMPLATE_PATH.exists():
                self.respond(200, TEMPLATE_PATH.read_text(encoding="utf-8"), "text/html")
            else:
                self.respond(200, "<h1>WiFiRouter Hotspot</h1><p>Welcome! Tap to connect.</p>", "text/html")
            return

        # Reverse proxy to backend API for guest status
        if clean_path in ("/api/v1/guests/status", "/api/v1/guests/plans"):
            try:
                url = f"{BACKEND_URL}{self.path}"
                req = urllib.request.Request(url, headers=client_headers(client_ip))
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
        clean_path = urlsplit(self.path).path

        # Reverse proxy to backend API for guest connection
        if clean_path == "/api/v1/guests/connect":
            try:
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 4096:
                    self.respond(400, json.dumps({"error": "Invalid request size"}), "application/json")
                    return
                payload = self.rfile.read(size)

                url = f"{BACKEND_URL}{self.path}"
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        **client_headers(client_ip)
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=25) as resp:
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

