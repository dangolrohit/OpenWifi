"""Unit tests for network-agent controller, validators, and endpoints."""
import json
import sys
import unittest
from pathlib import Path

# Add network-agent root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.controller import AgentController
from agent.validators.network_validator import (
    validate_ipv4, validate_mac, validate_speed_limit, validate_time_hhmm,
    check_host_protection, NetworkValidationError
)
from agent.security.ipc_auth import verify_token

class NetworkValidatorTests(unittest.TestCase):
    def test_ipv4_validation(self):
        self.assertEqual(validate_ipv4("192.168.16.103"), "192.168.16.103")
        with self.assertRaises(NetworkValidationError):
            validate_ipv4("invalid-ip")
        with self.assertRaises(NetworkValidationError):
            validate_ipv4("127.0.0.1")
        with self.assertRaises(NetworkValidationError):
            validate_ipv4("192.168.1.103", subnet="192.168.16.0/24")

    def test_mac_validation(self):
        self.assertEqual(validate_mac("a4:83:e7:21:09:41"), "a4:83:e7:21:09:41")
        with self.assertRaises(NetworkValidationError):
            validate_mac("invalid-mac")

    def test_speed_limit_validation(self):
        self.assertEqual(validate_speed_limit(10), 10)
        self.assertEqual(validate_speed_limit(0), 0)
        with self.assertRaises(NetworkValidationError):
            validate_speed_limit(-5)
        with self.assertRaises(NetworkValidationError):
            validate_speed_limit(20000)

    def test_time_validation(self):
        self.assertEqual(validate_time_hhmm("22:30"), "22:30")
        with self.assertRaises(NetworkValidationError):
            validate_time_hhmm("25:00")
        with self.assertRaises(NetworkValidationError):
            validate_time_hhmm("invalid")

    def test_host_protection(self):
        with self.assertRaises(NetworkValidationError):
            check_host_protection("192.168.16.2", {"192.168.16.2"})
        with self.assertRaises(NetworkValidationError):
            check_host_protection("127.0.0.1", set())

class AgentControllerTests(unittest.TestCase):
    def setUp(self):
        self.ctrl = AgentController()

    def test_summary_data(self):
        summary = self.ctrl.get_dashboard_summary()
        self.assertIn("bandwidth", summary)
        self.assertIn("wifi", summary)
        self.assertIn("health", summary)
        self.assertGreaterEqual(summary["connected_device_count"], 1)

    def test_firewall_and_captive_flow(self):
        auth_res = self.ctrl.captive.authorize_client("192.168.16.105", "starter", 30, 2)
        self.assertTrue(auth_res["ok"])
        active = self.ctrl.captive.get_active_sessions()
        self.assertIn("192.168.16.105", active)

        revoke_res = self.ctrl.captive.revoke_client("192.168.16.105")
        self.assertTrue(revoke_res["ok"])
        active_after = self.ctrl.captive.get_active_sessions()
        self.assertNotIn("192.168.16.105", active_after)

    def test_token_verification(self):
        secret = "test-secret-12345"
        self.assertTrue(verify_token(secret, secret))
        self.assertFalse(verify_token("wrong", secret))
        self.assertFalse(verify_token(None, secret))

if __name__ == "__main__":
    unittest.main()
