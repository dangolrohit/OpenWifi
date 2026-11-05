import base64
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

if not hasattr(os, 'geteuid'):
    os.geteuid = lambda: 0

def load(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

helper=load('helper')
web=load('web')

class FirewallTests(unittest.TestCase):
    def test_addresses_and_injection(self):
        for invalid in ['192.168.16.0','192.168.16.1','192.168.16.2','192.168.16.255','192.168.1.103','::1','192.168.16.103; flush ruleset','--help']:
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):helper.valid_ip(invalid)
        self.assertEqual(helper.valid_ip('192.168.16.103'),'192.168.16.103')

    def test_rule_scope(self):
        with patch.object(helper,'run') as run:
            run.return_value=subprocess.CompletedProcess([],0,'','')
            helper.apply_rules({'192.168.16.103'})
            script=run.call_args.kwargs['input']
            self.assertNotIn('flush ruleset',script)
            self.assertIn('delete table inet oshin_dashboard',script)
            self.assertIn('priority -10',script)
            self.assertIn('iifname "enp1s0" ip saddr @blocked',script)
            self.assertIn('oifname "enp1s0" ip daddr @blocked',script)
            self.assertNotIn('DOCKER',script)

    def test_failure_does_not_save(self):
        with tempfile.TemporaryDirectory() as td:
            state=Path(td)/'blocked.json';state.write_text('[]')
            with patch.object(helper,'STATE',state),patch.object(helper.os,'geteuid',return_value=0),patch.object(helper,'apply_rules',side_effect=RuntimeError('failure')):
                with self.assertRaises(RuntimeError):helper.main(['block','192.168.16.103'])
            self.assertEqual(json.loads(state.read_text()),[])

    def test_schedule_evaluation(self):
        from datetime import time as dtime
        sched_night = {'enabled': True, 'start': '22:00', 'end': '06:00'}
        self.assertTrue(helper.is_schedule_active(sched_night, dtime(23, 0)))
        self.assertTrue(helper.is_schedule_active(sched_night, dtime(2, 30)))
        self.assertFalse(helper.is_schedule_active(sched_night, dtime(12, 0)))

        sched_day = {'enabled': True, 'start': '08:00', 'end': '18:00'}
        self.assertTrue(helper.is_schedule_active(sched_day, dtime(12, 0)))
        self.assertFalse(helper.is_schedule_active(sched_day, dtime(20, 0)))

        sched_disabled = {'enabled': False, 'start': '22:00', 'end': '06:00'}
        self.assertFalse(helper.is_schedule_active(sched_disabled, dtime(23, 0)))

    def test_customer_isolation_and_qos_rules(self):
        with patch.object(helper, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, '', '')
            meta = {
                'devices': {
                    '192.168.16.105': {
                        'name': 'Customer Table 1',
                        'group': 'customer',
                        'speed_limit': 5,
                        'schedule': {'enabled': False}
                    }
                }
            }
            helper.apply_rules({'192.168.16.103'}, meta)
            script = run.call_args.kwargs['input']
            self.assertIn('ip saddr @customers tcp dport 8090 counter drop', script)
            self.assertIn('forward iifname "enp1s0" oifname "enp1s0" ip saddr @customers counter drop', script)
            self.assertIn('limit rate over 625 kbytes/second', script)
            self.assertIn('add element inet oshin_dashboard customers { 192.168.16.105 }', script)

    def test_captive_portal_nft_rules(self):
        with patch.object(helper, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, '', '')
            meta = {
                'captive_enabled': True,
                'devices': {
                    '192.168.16.104': {'name': 'Dad Phone', 'group': 'family'},
                    '192.168.16.105': {'name': 'Visitor', 'group': 'customer'}
                }
            }
            guests = {
                '192.168.16.110': {'expires_at': time.time() + 1800, 'speed_limit': 2}
            }
            helper.apply_rules({'192.168.16.103'}, meta, guests)
            script = run.call_args.kwargs['input']
            self.assertIn('add set inet oshin_dashboard whitelisted', script)
            self.assertIn('add set inet oshin_dashboard authenticated', script)
            self.assertIn('add element inet oshin_dashboard whitelisted { 192.168.16.104 }', script)
            self.assertIn('add element inet oshin_dashboard authenticated { 192.168.16.110 }', script)
            self.assertIn('tcp dport 80 redirect to :8088', script)
            self.assertIn('tcp dport 853 counter drop', script)
            self.assertIn('forward iifname "enp1s0" counter drop', script)

        # When captive portal is disabled:
        with patch.object(helper, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, '', '')
            meta['captive_enabled'] = False
            helper.apply_rules(set(), meta, {})
            script = run.call_args.kwargs['input']
            self.assertNotIn('redirect to :8088', script)
            self.assertNotIn('forward iifname "enp1s0" counter drop', script)

    def test_plans_and_voucher_helper_actions(self):
        with tempfile.TemporaryDirectory() as td:
            p_state = Path(td) / 'plans.json'
            v_state = Path(td) / 'vouchers.json'
            g_state = Path(td) / 'guests.json'
            m_state = Path(td) / 'metadata.json'
            s_state = Path(td) / 'blocked.json'
            lock_f = Path(td) / 'lock'
            lock_f.touch()

            with patch.object(helper, 'PLANS_STATE', p_state), \
                 patch.object(helper, 'VOUCHERS_STATE', v_state), \
                 patch.object(helper, 'GUEST_STATE', g_state), \
                 patch.object(helper, 'METADATA', m_state), \
                 patch.object(helper, 'STATE', s_state), \
                 patch.object(helper.os, 'geteuid', return_value=0), \
                 patch.object(helper, 'apply_rules'):
                import io

                # 1. set_plans
                plans_input = [{'id': 'custom', 'name': 'Custom Plan', 'type': 'click', 'duration_minutes': 45, 'speed_limit': 4, 'active': True, 'description': 'Custom'}]
                with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
                    helper.main(['set_plans', json.dumps(plans_input)])
                    res = json.loads(fake_out.getvalue())
                    self.assertTrue(res['ok'])
                    self.assertEqual(len(res['plans']), 1)

                # 2. create_voucher
                with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
                    helper.main(['create_voucher', 'standard', '123456'])
                    res = json.loads(fake_out.getvalue())
                    self.assertTrue(res['ok'])
                    self.assertEqual(res['voucher']['code'], '123456')

                # 3. delete_voucher
                with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
                    helper.main(['delete_voucher', '123456'])
                    res = json.loads(fake_out.getvalue())
                    self.assertTrue(res['ok'])

                # 4. authorize_guest
                with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
                    helper.main(['authorize_guest', '192.168.16.105', 'starter', '30', '2'])
                    res = json.loads(fake_out.getvalue())
                    self.assertTrue(res['ok'])
                    self.assertEqual(res['session']['ip'], '192.168.16.105')

                # 5. check_guest_expiries (not expired yet)
                with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
                    helper.main(['check_guest_expiries'])
                    res = json.loads(fake_out.getvalue())
                    self.assertTrue(res['ok'])
                    self.assertEqual(res['active_count'], 1)
                    self.assertEqual(res['expired_count'], 0)

                # 6. revoke_guest
                with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
                    helper.main(['revoke_guest', '192.168.16.105'])
                    res = json.loads(fake_out.getvalue())
                    self.assertTrue(res['ok'])

                # 7. toggle_captive
                with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
                    helper.main(['toggle_captive', 'false'])
                    res = json.loads(fake_out.getvalue())
                    self.assertTrue(res['ok'])
                    self.assertFalse(res['captive_enabled'])

    def test_dns_log_parsing(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / 'test-dns.log'
            log.write_text(
                "Nov  5 22:42:01 dnsmasq[1832]: query[A] www.google.com from 192.168.16.103\n"
                "Nov  5 22:42:02 dnsmasq[1832]: reply www.google.com is 142.250.190.36\n"
                "Nov  5 22:42:03 dnsmasq[1832]: query[AAAA] instagram.com from 192.168.16.105\n"
                "Nov  5 22:42:04 dnsmasq[1832]: query[HTTPS] youtube.com from 192.168.16.103\n"
            )
            all_q = helper.parse_dns_log(log)
            self.assertEqual(len(all_q), 3)
            self.assertEqual(all_q[0]['domain'], 'youtube.com')
            self.assertEqual(all_q[0]['type'], 'HTTPS')
            self.assertEqual(all_q[0]['client'], '192.168.16.103')

            filtered = helper.parse_dns_log(log, filter_ip='192.168.16.105')
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0]['domain'], 'instagram.com')

            limited = helper.parse_dns_log(log, limit=1)
            self.assertEqual(len(limited), 1)
            self.assertEqual(limited[0]['domain'], 'youtube.com')

    def test_activity_helper_actions(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / 'oshin-dns.log'
            log.write_text("Nov  5 22:42:01 dnsmasq[1832]: query[A] example.org from 192.168.16.103\n")
            with patch.object(helper, 'DNS_LOG', log), patch.object(helper.os, 'geteuid', return_value=0):
                import io
                with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
                    helper.main(['activity'])
                    res = json.loads(fake_out.getvalue())
                    self.assertEqual(len(res['queries']), 1)
                    self.assertEqual(res['queries'][0]['domain'], 'example.org')

                with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
                    helper.main(['clear_activity'])
                    res = json.loads(fake_out.getvalue())
                    self.assertTrue(res['ok'])
                self.assertEqual(log.read_text(), '')

    def test_bad_actions_never_run(self):
        with patch.object(helper.os,'geteuid',return_value=0),patch.object(helper,'run') as run:
            for args in [[],['shell'],['block'],['status','extra'],['block','192.168.16.103','extra'],['clear_activity','extra']]:
                with self.assertRaises(ValueError):helper.main(args)
            run.assert_not_called()

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        salt=b'1'*32
        web.CONFIG={'salt':salt.hex(),'hash':hashlib.pbkdf2_hmac('sha256',b'test-only-password',salt,200000).hex()}
        cls.server=web.ThreadingHTTPServer(('127.0.0.1',0),web.Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def setUp(self):
        web.SESSIONS.clear();web.FAILURES.clear()
    def request(self,method,path,body=None,token=None,csrf=None,host=web.AUTHORITY):
        headers={'Host':host,'Origin':web.ORIGIN}
        if token:headers['Cookie']='oshin_session='+token
        if csrf:headers['X-CSRF-Token']=csrf
        if body is not None:body=json.dumps(body);headers['Content-Type']='application/json'
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        conn.request(method,path,body,headers);r=conn.getresponse();data=r.read();status=r.status;hdr=dict(r.getheaders());conn.close();return status,data,hdr
    def test_login_page_no_popup(self):
        status,body,headers=self.request('GET','/login')
        self.assertEqual(status,200);self.assertIn(b'id="login-form"',body)
        self.assertNotIn('WWW-Authenticate',headers)
        self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('Secure',headers['Set-Cookie'])
    def test_all_private_pages_and_apis(self):
        for path in web.PAGES:
            self.assertEqual(self.request('GET',path)[0],303)
        for path in ['/api/devices','/api/usage','/api/logs','/api/activity','/api/plans']:
            self.assertEqual(self.request('GET',path)[0],401)
    def test_login_rotation_logout_revocation(self):
        token,s=web.new_session()
        status,body,h=self.request('POST','/api/login',{'username':'admin','password':'test-only-password'},token,s['csrf'])
        self.assertEqual(status,200)
        new=h['Set-Cookie'].split(';')[0].split('=')[1]
        self.assertNotEqual(new,token);self.assertNotIn(token,web.SESSIONS)
        self.assertEqual(self.request('GET','/dashboard',token=new)[0],200)
        self.assertEqual(self.request('POST','/api/logout',{},new,web.SESSIONS[new]['csrf'])[0],200)
        self.assertEqual(self.request('GET','/dashboard',token=new)[0],303)
    def test_bad_login_and_rate_limit(self):
        token,s=web.new_session()
        for i in range(5):self.assertEqual(self.request('POST','/api/login',{'username':'admin','password':'wrong'},token,s['csrf'])[0],401)
        self.assertEqual(self.request('POST','/api/login',{'username':'admin','password':'test-only-password'},token,s['csrf'])[0],429)
    def test_csrf(self):
        token,s=web.new_session(True)
        with patch.object(web,'helper') as call:
            self.assertEqual(self.request('POST','/api/action',{'action':'block','ip':'192.168.16.103'},token,'wrong')[0],403)
            call.assert_not_called()
    def test_self_block_and_invalid_action(self):
        token,s=web.new_session(True)
        with patch.object(web,'helper') as call:
            for data in [{'action':'block','ip':'127.0.0.1'},{'action':'restore','ip':'192.168.16.103'}]:
                self.assertEqual(self.request('POST','/api/action',data,token,s['csrf'])[0],400)
            call.assert_not_called()
    def test_block_unblock(self):
        token,s=web.new_session(True)
        with patch.object(web,'helper',return_value={'blocked':[]}) as call:
            for action in ['block','unblock']:
                self.assertEqual(self.request('POST','/api/action',{'action':action,'ip':'192.168.16.103'},token,s['csrf'])[0],200)
                call.assert_called_with(action,'192.168.16.103')
    def test_expiry(self):
        token,s=web.new_session(True);s['last']-=1801
        self.assertEqual(self.request('GET','/dashboard',token=token)[0],303)
        token,s=web.new_session(True);s['created']-=28801
        self.assertEqual(self.request('GET','/dashboard',token=token)[0],303)
    def test_host_validation(self):
        self.assertEqual(self.request('GET','/login',host='evil.example')[0],403)
    def test_anonymous_cannot_mutate(self):
        token,s=web.new_session()
        self.assertEqual(self.request('POST','/api/action',{'action':'block','ip':'192.168.16.103'},token,s['csrf'])[0],401)
        self.assertEqual(self.request('POST','/api/activity/clear',{},token,s['csrf'])[0],401)
    def test_activity_api(self):
        token,s=web.new_session(True)
        with patch.object(web,'helper',return_value={'queries':[],'log_exists':True}) as call, patch.object(web,'devices',return_value=[]):
            st,body,_=self.request('GET','/api/activity',token=token)
            self.assertEqual(st,200)
            call.assert_called_with('activity')
            st,body,_=self.request('GET','/api/activity?ip=192.168.16.103',token=token)
            self.assertEqual(st,200)
            call.assert_called_with('activity','192.168.16.103')
            st,body,_=self.request('GET','/api/activity?ip=bad_ip',token=token)
            self.assertEqual(st,400)
    def test_clear_activity_api(self):
        token,s=web.new_session(True)
        with patch.object(web,'helper',return_value={'ok':True}) as call:
            st,body,_=self.request('POST','/api/activity/clear',{},token,s['csrf'])
            self.assertEqual(st,200)
            call.assert_called_with('clear_activity')
    def test_device_update_api(self):
        token,s=web.new_session(True)
        with patch.object(web,'helper',return_value={'ok':True}) as call:
            data={
                'ip':'192.168.16.105',
                'name':'Living Room TV',
                'group':'family',
                'speed_limit':10,
                'schedule':{'enabled':True,'start':'22:00','end':'06:00'}
            }
            st,body,_=self.request('POST','/api/device/update',data,token,s['csrf'])
            self.assertEqual(st,200)
            self.assertEqual(call.call_args[0][0],'set_device')
            self.assertEqual(call.call_args[0][1],'192.168.16.105')
            # Test bad payload
            st,body,_=self.request('POST','/api/device/update',{'ip':'bad'},token,s['csrf'])
            self.assertEqual(st,400)

    def test_plans_admin_apis(self):
        token, s = web.new_session(True)
        # 1. GET /api/plans
        with patch.object(web, 'helper', return_value={'plans': [], 'vouchers': {}, 'guests': {}, 'metadata': {'captive_enabled': True}}) as call, \
             patch.object(web, 'devices', return_value=[]):
            st, body, _ = self.request('GET', '/api/plans', token=token)
            self.assertEqual(st, 200)
            res = json.loads(body.decode())
            self.assertTrue(res['captive_enabled'])
            call.assert_called_with('status')

        # 2. POST /api/plans/update
        with patch.object(web, 'helper', return_value={'ok': True}) as call:
            st, body, _ = self.request('POST', '/api/plans/update', {'plans': [{'id': 'starter'}]}, token, s['csrf'])
            self.assertEqual(st, 200)
            self.assertEqual(call.call_args[0][0], 'set_plans')

        # 3. POST /api/plans/toggle
        with patch.object(web, 'helper', return_value={'ok': True}) as call:
            st, body, _ = self.request('POST', '/api/plans/toggle', {'enabled': False}, token, s['csrf'])
            self.assertEqual(st, 200)
            call.assert_called_with('toggle_captive', '0')

        # 4. POST /api/vouchers/create
        with patch.object(web, 'helper', return_value={'ok': True, 'voucher': {'code': '112233'}}) as call:
            st, body, _ = self.request('POST', '/api/vouchers/create', {'plan_id': 'standard'}, token, s['csrf'])
            self.assertEqual(st, 200)
            call.assert_called_with('create_voucher', 'standard')

        # 5. POST /api/vouchers/delete
        with patch.object(web, 'helper', return_value={'ok': True}) as call:
            st, body, _ = self.request('POST', '/api/vouchers/delete', {'code': '112233'}, token, s['csrf'])
            self.assertEqual(st, 200)
            call.assert_called_with('delete_voucher', '112233')

        # 6. POST /api/guest/revoke
        with patch.object(web, 'helper', return_value={'ok': True}) as call:
            st, body, _ = self.request('POST', '/api/guest/revoke', {'ip': '192.168.16.105'}, token, s['csrf'])
            self.assertEqual(st, 200)
            call.assert_called_with('revoke_guest', '192.168.16.105')

        # 7. POST /api/guest/extend
        with patch.object(web, 'helper') as call:
            call.side_effect = [
                {'guests': {'192.168.16.105': {'plan_id': 'starter', 'speed_limit': 2}}},
                {'ok': True}
            ]
            st, body, _ = self.request('POST', '/api/guest/extend', {'ip': '192.168.16.105', 'minutes': 45}, token, s['csrf'])
            self.assertEqual(st, 200)
            call.assert_any_call('authorize_guest', '192.168.16.105', 'starter', '45', '2')

class CaptiveHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = web.ThreadingHTTPServer(('127.0.0.1', 0), web.CaptiveHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None):
        headers = {}
        if body is not None:
            body = json.dumps(body)
            headers['Content-Type'] = 'application/json'
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        conn.request(method, path, body, headers)
        r = conn.getresponse()
        data = r.read()
        status = r.status
        hdr = dict(r.getheaders())
        conn.close()
        return status, data, hdr

    def test_unauthenticated_probes_redirect_to_guest(self):
        with patch.object(web, 'helper', return_value={'guests': {}}):
            for probe in ['/generate_204', '/hotspot-detect.html', '/connecttest.txt', '/ncsi.txt']:
                st, body, h = self.request('GET', probe)
                self.assertEqual(st, 302)
                self.assertIn('/guest', h.get('Location', ''))

    def test_guest_landing_page(self):
        st, body, h = self.request('GET', '/guest')
        self.assertEqual(st, 200)
        self.assertIn(b'OshinWiFi Hotspot', body)
        self.assertIn(b'Starter Plan', body)

    def test_guest_status_api(self):
        with patch.object(web, 'helper', return_value={'guests': {}, 'plans': [{'id': 'starter', 'active': True}]}):
            st, body, h = self.request('GET', '/api/guest/status')
            self.assertEqual(st, 200)
            res = json.loads(body.decode())
            self.assertFalse(res['authorized'])
            self.assertEqual(len(res['plans']), 1)

    def test_guest_connect_starter_plan(self):
        st_data = {
            'plans': [{'id': 'starter', 'name': 'Starter Free', 'type': 'click', 'duration_minutes': 30, 'speed_limit': 2, 'active': True}],
            'vouchers': {},
            'guests': {}
        }
        with patch.object(web, 'helper') as mock_helper:
            def helper_side_effect(*args):
                if args[0] == 'status':
                    return st_data
                if args[0] == 'authorize_guest':
                    return {'ok': True, 'session': {'ip': args[1], 'plan_id': args[2], 'expires_at': time.time() + 1800}}
                return {'ok': True}
            mock_helper.side_effect = helper_side_effect

            st, body, h = self.request('POST', '/api/guest/connect', {'plan_id': 'starter'})
            self.assertEqual(st, 200)
            res = json.loads(body.decode())
            self.assertTrue(res['ok'])
            self.assertEqual(res['plan_name'], 'Starter Free')
            self.assertEqual(res['duration_minutes'], 30)

    def test_guest_connect_voucher(self):
        st_data = {
            'plans': [{'id': 'standard', 'name': 'Standard 2-Hour', 'type': 'voucher', 'duration_minutes': 120, 'speed_limit': 5, 'active': True}],
            'vouchers': {'987654': {'code': '987654', 'plan_id': 'standard', 'used': False}},
            'guests': {}
        }
        with patch.object(web, 'helper') as mock_helper:
            def helper_side_effect(*args):
                if args[0] == 'status':
                    return st_data
                if args[0] == 'delete_voucher':
                    return {'ok': True}
                if args[0] == 'authorize_guest':
                    return {'ok': True, 'session': {'ip': args[1], 'plan_id': args[2], 'expires_at': time.time() + 7200}}
                return {'ok': True}
            mock_helper.side_effect = helper_side_effect

            # Test invalid voucher
            st, body, h = self.request('POST', '/api/guest/connect', {'voucher': '000000'})
            self.assertEqual(st, 400)

            # Test valid voucher
            st, body, h = self.request('POST', '/api/guest/connect', {'voucher': '987654'})
            self.assertEqual(st, 200)
            res = json.loads(body.decode())
            self.assertTrue(res['ok'])
            self.assertEqual(res['plan_name'], 'Standard 2-Hour')

    def test_authenticated_probes_succeed(self):
        with patch.object(web, 'helper', return_value={'guests': {'127.0.0.1': {'expires_at': time.time() + 1800}}}):
            st, body, h = self.request('GET', '/generate_204')
            self.assertEqual(st, 204)

            st, body, h = self.request('GET', '/connecttest.txt')
            self.assertEqual(st, 200)
            self.assertEqual(body.strip(), b'Success')

if __name__=='__main__':unittest.main()
