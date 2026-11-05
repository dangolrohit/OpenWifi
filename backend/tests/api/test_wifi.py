"""Exercise browser-facing routes through the agent HTTP client."""
import os
import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app.api.v1.endpoints.wifi import router
from backend.app.api.dependencies.auth import get_current_user
from backend.app.integrations.agent_client import agent_client


class WifiApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix='/api/v1')
        app.dependency_overrides[get_current_user] = lambda: object()
        self.client = TestClient(app)
        self.env = patch.dict(os.environ, {'WIFIROUTER_SIMULATE': '0'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.original_client = httpx.AsyncClient

    def request_with_agent(self, handler):
        transport = httpx.MockTransport(handler)
        def make_client(**kwargs):
            self.assertEqual(kwargs['timeout'], 45.0)
            return self.original_client(transport=transport, **kwargs)
        with patch('backend.app.integrations.agent_client.httpx.AsyncClient', side_effect=make_client), \
             patch.object(agent_client, '_get_fallback_controller') as fallback:
            response = self.client.get('/api/v1/wifi/scan')
            fallback.assert_not_called()
        return response

    def test_real_results_pass_through(self):
        networks = [{'ssid': 'Real AP', 'simulated': False}]
        def handler(request):
            self.assertEqual(request.url.path, '/wifi/scan')
            self.assertEqual(request.headers['X-Agent-Secret'], agent_client.secret)
            return httpx.Response(200, json={'networks': networks})
        response = self.request_with_agent(handler)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'networks': networks})

    def test_agent_failure_reaches_browser(self):
        response = self.request_with_agent(lambda r: httpx.Response(500, json={'error': 'Radio blocked'}))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['detail'], 'Radio blocked')

    def test_timeout_does_not_generate_fake_results(self):
        def handler(request):
            raise httpx.ReadTimeout('scan timed out', request=request)
        response = self.request_with_agent(handler)
        self.assertEqual(response.status_code, 503)
        self.assertIn('agent', response.json()['detail'])

    def test_authentication_error_does_not_fall_back(self):
        response = self.request_with_agent(lambda r: httpx.Response(401, json={'error': 'Invalid agent secret'}))
        self.assertEqual(response.status_code, 503)
        self.assertIn('secret', response.json()['detail'])

    def test_scan_requires_login(self):
        self.client.app.dependency_overrides.clear()
        self.assertEqual(self.client.get('/api/v1/wifi/scan').status_code, 401)


class WifiHttpIntegrationTests(unittest.TestCase):
    def test_api_to_host_agent_to_scanner(self):
        import sys
        import threading
        import subprocess
        from pathlib import Path
        from http.server import ThreadingHTTPServer
        from types import SimpleNamespace
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'network-agent'))
        from agent.main import AgentRequestHandler
        from agent.interfaces.manager import InterfaceManager

        interfaces = InterfaceManager()
        interfaces.simulated = False
        server = ThreadingHTTPServer(('127.0.0.1', 0), AgentRequestHandler)
        server.controller = SimpleNamespace(interfaces=interfaces)
        server.shared_secret = agent_client.secret
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        app = FastAPI()
        app.include_router(router, prefix='/api/v1')
        app.dependency_overrides[get_current_user] = lambda: object()
        try:
            with patch.dict(os.environ, {'WIFIROUTER_SIMULATE': '0', 'WIFIROUTER_WAN_IFACE': 'wlan0'}), \
                 patch.object(agent_client, 'base_url', f'http://127.0.0.1:{server.server_port}'), \
                 patch('agent.interfaces.manager.subprocess.run') as run, \
                 TestClient(app) as client:
                run.return_value = subprocess.CompletedProcess([], 0,
                    r'*:Live AP:AA\:BB\:CC\:DD\:EE\:FF:6:80:WPA2', '')
                response = client.get('/api/v1/wifi/scan')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['networks'][0]['ssid'], 'Live AP')
                self.assertFalse(response.json()['networks'][0]['simulated'])
                run.return_value = subprocess.CompletedProcess([], 1, '', 'Radio blocked')
                response = client.get('/api/v1/wifi/scan')
                self.assertEqual(response.status_code, 503)
                self.assertIn('Radio blocked', response.json()['detail'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
