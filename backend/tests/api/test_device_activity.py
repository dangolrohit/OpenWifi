import unittest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app.api.v1.endpoints.logs import router
from backend.app.api.dependencies.auth import get_current_user
from backend.app.integrations.agent_client import agent_client, AgentUnavailableError

class DeviceActivityApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix='/api/v1')
        app.dependency_overrides[get_current_user] = lambda: object()
        self.client = TestClient(app)

    def test_page_forwarded_for_selected_device(self):
        data = {'queries': [], 'page': 2, 'page_size': 20, 'total': 25, 'has_more': False}
        with patch.object(agent_client, 'get_device_activity', new_callable=AsyncMock, return_value=data) as call:
            response = self.client.get('/api/v1/logs/dns/device-activity?client=192.168.16.101&page=2')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), data)
            call.assert_awaited_once_with('192.168.16.101', 2)

    def test_invalid_parameters(self):
        for query in ['client=invalid', 'client=192.168.16.101&page=0', 'client=192.168.16.101&page=100001', 'page=1']:
            self.assertEqual(self.client.get('/api/v1/logs/dns/device-activity?' + query).status_code, 422)

    def test_failure_visible(self):
        with patch.object(agent_client, 'get_device_activity', side_effect=AgentUnavailableError('Agent unreachable')):
            response = self.client.get('/api/v1/logs/dns/device-activity?client=192.168.16.101')
        self.assertEqual(response.status_code, 503)
        self.assertIn('unreachable', response.json()['detail'])

    def test_login_required(self):
        self.client.app.dependency_overrides.clear()
        self.assertEqual(self.client.get('/api/v1/logs/dns/device-activity?client=192.168.16.101').status_code, 401)


class DeviceActivityClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_parameters_and_no_fabricated_failure(self):
        import os
        import httpx
        original = httpx.AsyncClient
        def handler(request):
            self.assertEqual(request.url.path, '/dns/device-activity')
            self.assertEqual(request.url.params['client'], '192.168.16.101')
            self.assertEqual(request.url.params['page'], '2')
            self.assertEqual(request.headers['X-Agent-Secret'], agent_client.secret)
            return httpx.Response(503, json={'error': 'DNS log unreadable'})
        with patch.dict(os.environ, {'WIFIROUTER_SIMULATE': '0'}), \
             patch('backend.app.integrations.agent_client.httpx.AsyncClient',
                   side_effect=lambda **kw: original(transport=httpx.MockTransport(handler), **kw)), \
             patch.object(agent_client, '_get_fallback_controller') as fallback:
            with self.assertRaisesRegex(AgentUnavailableError, 'DNS log unreadable'):
                await agent_client.get_device_activity('192.168.16.101', 2)
            fallback.assert_not_called()
