import base64
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

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

    def test_bad_actions_never_run(self):
        with patch.object(helper.os,'geteuid',return_value=0),patch.object(helper,'run') as run:
            for args in [[],['shell'],['block'],['status','extra'],['block','192.168.16.103','extra']]:
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
        for path in ['/api/devices','/api/usage','/api/logs']:
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

if __name__=='__main__':unittest.main()
