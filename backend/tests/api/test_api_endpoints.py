"""API integration tests covering authentication, devices, and hotspot plans."""
import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.config import settings

class ApiEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_cm = TestClient(app)
        cls.client = cls.client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_cm.__exit__(None, None, None)

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "ok")

    def test_auth_login_and_me_lifecycle(self):
        # 1. Login with correct default credentials
        login_payload = {
            "username": settings.DEFAULT_ADMIN_USER,
            "password": settings.DEFAULT_ADMIN_PASSWORD
        }
        resp = self.client.post("/api/v1/auth/login", json=login_payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"))
        self.assertIn("token", data)
        self.assertIn("csrf_token", data)

        token = data["token"]
        csrf_token = data["csrf_token"]
        cookies = {"oshin_session": token}
        headers = {"X-CSRF-Token": csrf_token}

        # 2. Check /api/v1/auth/me
        me_resp = self.client.get("/api/v1/auth/me", cookies=cookies)
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["user"]["username"], settings.DEFAULT_ADMIN_USER)

        # 3. Check /api/v1/dashboard/summary
        dash_resp = self.client.get("/api/v1/dashboard/summary", cookies=cookies)
        self.assertEqual(dash_resp.status_code, 200)
        dash_data = dash_resp.json()
        self.assertIn("devices", dash_data)
        self.assertIn("bandwidth", dash_data)

        # 4. Check /api/v1/devices
        dev_resp = self.client.get("/api/v1/devices", cookies=cookies)
        self.assertEqual(dev_resp.status_code, 200)
        self.assertIsInstance(dev_resp.json(), list)

        # 5. Check /api/v1/guests/plans
        plans_resp = self.client.get("/api/v1/guests/plans", cookies=cookies)
        self.assertEqual(plans_resp.status_code, 200)
        plans = plans_resp.json()
        self.assertEqual(len(plans), 5)
        starter = next((p for p in plans if p["plan_id"] == "starter"), None)
        self.assertIsNotNone(starter)
        self.assertEqual(starter["duration_minutes"], 30)

        # 6. Test public captive status endpoint
        cap_resp = self.client.get("/api/v1/guests/status")
        self.assertEqual(cap_resp.status_code, 200)

        # 7. Logout
        logout_resp = self.client.post("/api/v1/auth/logout", cookies=cookies, headers=headers)
        self.assertEqual(logout_resp.status_code, 200)

        # 8. Subsequent call should fail with 401
        after_resp = self.client.get("/api/v1/auth/me", cookies=cookies)
        self.assertEqual(after_resp.status_code, 401)

if __name__ == "__main__":
    unittest.main()
