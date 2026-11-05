import sys
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.firewall.manager import FirewallManager
from agent.controller import AgentController

class CaptiveFirewallTests(unittest.TestCase):
    @patch('agent.firewall.manager.time.time', return_value=1000)
    def test_expiry_rates_and_bidirectional_gate(self, clock):
        manager = FirewallManager()
        state = {'authenticated': ['192.168.16.110', '192.168.16.111'],
                 'guest_expiries': {'192.168.16.110': 2800, '192.168.16.111': 999},
                 'guest_speed_limits': {'192.168.16.110': 1}, 'whitelisted': []}
        rules = manager.build_ruleset(state)
        self.assertIn('192.168.16.110 timeout 1800s', rules)
        self.assertNotIn('192.168.16.111 timeout', rules)
        self.assertIn('flags timeout', rules)
        self.assertEqual(rules.count('125000 bytes/second'), 2)
        self.assertIn('oifname "enp1s0" counter drop', rules)
        self.assertIn('iifname "enp1s0" counter drop', rules)
        self.assertTrue(rules.startswith('add table inet wifirouter\ndelete table inet wifirouter\n'))

    def test_auth_failure_restores_persistent_sessions(self):
        controller = AgentController()
        controller.captive = Mock(simulated=False)
        controller.captive.get_active_sessions.return_value = {}
        controller.firewall = Mock()
        controller.firewall.update_guest_sessions.side_effect = RuntimeError('nft failed')
        with self.assertRaisesRegex(RuntimeError, 'nft failed'):
            controller.authorize_guest('192.168.16.110', 'starter', 30, 1)
        controller.captive.save_sessions.assert_called_once_with({})

    def test_startup_restores_guest_firewall(self):
        controller = AgentController()
        controller.captive = Mock()
        controller.captive.get_active_sessions.return_value = {}
        controller.firewall = Mock()
        controller.restore_guest_firewall()
        controller.captive.check_expiries.assert_called_once()
        controller.firewall.update_guest_sessions.assert_called_once_with({})


    def test_prelogin_dns_and_http_are_redirected_without_allowing_forwarding(self):
        manager = FirewallManager()
        rules = manager.build_ruleset({"captive_enabled": True})
        for protocol in ("udp", "tcp"):
            self.assertIn(f'ip saddr != @whitelisted ip saddr != @authenticated {protocol} dport 53 counter redirect to :53', rules)
        self.assertIn('tcp dport 80 counter redirect to :8088', rules)
        self.assertIn('iifname "enp1s0" counter drop', rules)
        disabled = manager.build_ruleset({"captive_enabled": False})
        self.assertNotIn('redirect to :53', disabled)
        self.assertNotIn('redirect to :8088', disabled)
