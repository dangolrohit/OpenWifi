import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.dns.manager import DnsActivityManager

class DeviceActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'dnsmasq.log'
        self.paths = patch('agent.dns.manager.LOG_PATHS', [self.path])
        self.paths.start()
        self.addCleanup(self.paths.stop)
        self.manager = DnsActivityManager()
        self.manager.simulated = False

    def test_paginate_individual_requests_and_filter_before_limiting(self):
        lines = [f'Nov 6 10:00:00 dnsmasq[1]: query[A] site{i}.example from 192.168.16.101\n' for i in range(45)]
        lines += ['Nov 6 10:01:00 dnsmasq[1]: query[A] other.example from 192.168.16.102\n'] * 900
        self.path.write_text(''.join(lines), encoding='utf-8')
        first = self.manager.get_device_activity('192.168.16.101')
        second = self.manager.get_device_activity('192.168.16.101', 2)
        third = self.manager.get_device_activity('192.168.16.101', 3)
        self.assertEqual(first['total'], 45)
        self.assertEqual([len(p['queries']) for p in (first, second, third)], [20, 20, 5])
        self.assertEqual(first['queries'][0]['domain'], 'site44.example')
        self.assertEqual(second['queries'][0]['domain'], 'site24.example')
        self.assertEqual(third['queries'][-1]['domain'], 'site0.example')
        self.assertTrue(second['has_more'])
        self.assertFalse(third['has_more'])
        self.assertEqual(self.manager.get_device_activity('192.168.16.101', 4)['queries'], [])

    def test_repeated_requests_not_deduplicated(self):
        self.path.write_text('Nov 6 10:00:00 dnsmasq: query[A] repeat.example from 192.168.16.101\n' * 21)
        self.assertEqual(self.manager.get_device_activity('192.168.16.101')['total'], 21)

    def test_validation(self):
        for ip, page in [('invalid', 1), ('192.168.16.101', 0), ('192.168.16.101', 100001)]:
            with self.assertRaises(ValueError):
                self.manager.get_device_activity(ip, page)

    def test_simulation_label_and_device_filter(self):
        self.manager.simulated = True
        data = self.manager.get_device_activity('192.168.16.101')
        self.assertTrue(data['simulated'])
        self.assertTrue(all(q['client'] == '192.168.16.101' for q in data['queries']))


    @patch('agent.dns.manager.subprocess.run')
    def test_missing_logs_are_distinguished_from_no_device_activity(self, run):
        import subprocess
        run.return_value = subprocess.CompletedProcess([], 0, '', '')
        self.assertFalse(self.manager.get_device_activity('192.168.16.101')['log_available'])
        self.path.write_text('')
        data = self.manager.get_device_activity('192.168.16.101')
        self.assertTrue(data['log_available'])
        self.assertEqual(data['total'], 0)

    @patch('agent.dns.manager.subprocess.run')
    def test_journal_failure_is_reported_when_no_file_exists(self, run):
        import subprocess
        run.return_value = subprocess.CompletedProcess([], 1, '', 'Permission denied')
        with self.assertRaisesRegex(RuntimeError, 'DNS logs are unavailable'):
            self.manager.get_device_activity('192.168.16.101')
