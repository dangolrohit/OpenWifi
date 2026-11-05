"""Real HTTP probe/portal tests with an isolated backend status server."""
import importlib.util
import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('portal_server', Path(__file__).resolve().parents[1] / 'server.py')
portal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portal)

class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.last_headers = self.headers
        body = json.dumps({'authorized': self.server.authorized}).encode()
        self.send_response(self.server.status)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

class PortalDetectionTests(unittest.TestCase):
    def setUp(self):
        self.backend = ThreadingHTTPServer(('127.0.0.1', 0), StatusHandler)
        self.backend.authorized = False
        self.backend.status = 200
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), portal.CaptiveRequestHandler)
        self.patches = [patch.object(portal, 'BACKEND_URL', f'http://127.0.0.1:{self.backend.server_port}'),
                        patch.object(portal, 'PROXY_SECRET', 'test-secret')]
        for p in self.patches:
            p.start()
        self.threads = []
        for server in (self.backend, self.server):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)

    def tearDown(self):
        for server in (self.server, self.backend):
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join(timeout=2)
        for p in self.patches:
            p.stop()

    def request(self, path, method='GET', host='127.0.0.1'):
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            connection.request(method, path, headers={'Host': host})
            response = connection.getresponse()
            return response.status, response.read().decode(), dict(response.getheaders())
        finally:
            connection.close()

    def test_unauthorized_probes_redirect_to_sign_in(self):
        for path in ['/generate_204', '/gen_204', '/connecttest.txt', '/ncsi.txt', '/hotspot-detect.html', '/library/test/success.html', '/success.txt']:
            with self.subTest(path=path):
                status, body, headers = self.request(path)
                self.assertEqual(status, 302)
                self.assertEqual(headers['Location'], f'http://{portal.GATEWAY_IP}:{portal.PORT}/guest')
        self.assertEqual(self.backend.last_headers['X-Captive-IP'], '127.0.0.1')
        self.assertTrue(self.backend.last_headers['X-Captive-Signature'])

    def test_authorized_probe_payloads(self):
        self.backend.authorized = True
        for path, expected in [('/connecttest.txt', 'Microsoft Connect Test'), ('/ncsi.txt', 'Microsoft NCSI'), ('/success.txt', 'success\n')]:
            status, body, headers = self.request(path)
            self.assertEqual((status, body), (200, expected))
        self.assertEqual(self.request('/generate_204')[:2], (204, ''))
        self.assertIn('<TITLE>Success</TITLE>', self.request('/hotspot-detect.html')[1])

    def test_head_and_query_string(self):
        status, body, headers = self.request('/generate_204?check=1', method='HEAD')
        self.assertEqual((status, body), (302, ''))
        self.assertIn('Location', headers)

    def test_backend_failure_still_redirects(self):
        self.backend.status = 503
        self.assertEqual(self.request('/connecttest.txt')[0], 302)

    def test_intercepted_root_uses_gateway_origin(self):
        status, body, headers = self.request('/', host='example.com')
        self.assertEqual(status, 302)
        self.assertIn('/guest', headers['Location'])

    def test_portal_offers_both_options_without_authorizing(self):
        status, body, headers = self.request('/guest')
        self.assertEqual(status, 200)
        self.assertIn('Continue as Guest', body)
        self.assertIn('Continue with Access Code', body)
        self.assertIn('1 Mbps Limit', body)
        self.assertFalse(self.backend.authorized)

    def test_arbitrary_http_request_redirects(self):
        self.assertEqual(self.request('/some/page?x=1', host='example.com')[0], 302)

    def test_health(self):
        status, body, headers = self.request('/health')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['status'], 'ok')
