"""Regression coverage for real Wi-Fi scanning without requiring radio hardware."""
import importlib
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.interfaces.manager import InterfaceManager, _parse_nmcli_line, _wifi_interface


class WifiScanTests(unittest.TestCase):
    def setUp(self):
        self.manager = InterfaceManager()
        self.manager.simulated = False
        self.manager.mock = Mock()

    def test_daemon_imports(self):
        module = importlib.import_module('agent.main')
        self.assertTrue(callable(module.run_agent))

    def test_escaped_fields(self):
        self.assertEqual(_parse_nmcli_line(r'Cafe\:West:Path\\:next'),
                         ['Cafe:West', 'Path\\', 'next'])

    @patch('agent.interfaces.manager.subprocess.run')
    def test_scan_preserves_bands_and_hidden_networks(self, run):
        run.return_value = subprocess.CompletedProcess([], 0,
            '*:Cafe\\:West:AA\\:BB\\:CC\\:DD\\:EE\\:01:6:80:WPA2\n'
            ':Cafe\\:West:AA\\:BB\\:CC\\:DD\\:EE\\:02:36:65:WPA2\n'
            '::AA\\:BB\\:CC\\:DD\\:EE\\:03:1:20:--\n', '')
        rows = self.manager.scan_wifi_networks('wlx123')
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['ssid'], 'Cafe:West')
        self.assertEqual(rows[0]['bssid'], 'AA:BB:CC:DD:EE:01')
        self.assertTrue(rows[0]['in_use'])
        self.assertEqual(rows[2]['security'], 'Open')
        command = run.call_args.args[0]
        self.assertEqual(command[-4:], ['ifname', 'wlx123', '--rescan', 'yes'])
        self.assertEqual(run.call_args.kwargs['env']['LC_ALL'], 'C')
        self.manager.mock.scan_wifi.assert_not_called()

    @patch('agent.interfaces.manager.subprocess.run')
    def test_empty_scan_is_not_simulated(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, '', '')
        self.assertEqual(self.manager.scan_wifi_networks('wlan0'), [])
        self.assertEqual(run.call_count, 1)
        self.manager.mock.scan_wifi.assert_not_called()

    @patch('agent.interfaces.manager.subprocess.run')
    def test_failure_is_reported(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, '', 'Radio blocked')
        with self.assertRaisesRegex(RuntimeError, 'Radio blocked'):
            self.manager.scan_wifi_networks('wlan0')
        self.manager.mock.scan_wifi.assert_not_called()

    @patch('agent.interfaces.manager.subprocess.run')
    def test_timeout_uses_iwlist(self, run):
        run.side_effect = [subprocess.TimeoutExpired('nmcli', 25),
            subprocess.CompletedProcess([], 0, '''Cell 01 - Address: AA:BB:CC:DD:EE:01
                ESSID:"Fallback"
                Channel:6
                Signal level=-60 dBm
                Encryption key:on
            ''', '')]
        self.assertEqual(self.manager.scan_wifi_networks('wlan0')[0]['ssid'], 'Fallback')

    @patch.dict(os.environ, {}, clear=True)
    @patch('agent.interfaces.manager.Path')
    def test_discovery_does_not_require_wl_prefix(self, path):
        device = Mock()
        device.name = 'radio0'
        device.__truediv__ = Mock(return_value=Mock(exists=Mock(return_value=True)))
        path.return_value.iterdir.return_value = [device]
        self.assertEqual(_wifi_interface(), 'radio0')

    @patch.dict(os.environ, {}, clear=True)
    @patch('agent.interfaces.manager.Path')
    def test_no_adapter(self, path):
        path.return_value.iterdir.return_value = []
        with self.assertRaisesRegex(RuntimeError, 'No Wi-Fi adapter'):
            _wifi_interface()

    def test_explicit_simulation(self):
        self.manager.simulated = True
        self.manager.mock.scan_wifi.return_value = [{'simulated': True}]
        self.assertEqual(self.manager.scan_wifi_networks(), [{'simulated': True}])


if __name__ == '__main__':
    unittest.main()
