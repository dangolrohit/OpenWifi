#!/usr/bin/python3
"""Private LAN portal with HTTPS admin dashboard and HTTP Captive Hotspot Portal."""
import hashlib, hmac, ipaddress, json, secrets, ssl, subprocess, threading, time
from pathlib import Path
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections import deque

HOST = '192.168.16.2'
PORT = 8090
CAPTIVE_PORT = 8088
AUTHORITY = f'{HOST}:{PORT}'
ORIGIN = f'https://{AUTHORITY}'
ROOT = Path(__file__).resolve().parent
CONFIG = {}
SESSIONS = {}
FAILURES = {}
LOCK = threading.RLock()
EVENTS = deque(maxlen=300)
PAGES = {'/', '/dashboard', '/wifi', '/devices', '/filtering', '/usages', '/activity', '/plans', '/logs', '/settings'}

def audit(action, client, target=''):
    with LOCK:
        EVENTS.appendleft({'time': time.time(), 'action': action, 'client': client, 'target': target})

def new_session(auth=False):
    now = time.monotonic()
    with LOCK:
        for key in list(SESSIONS):
            s = SESSIONS[key]
            if now - s['last'] > (1800 if s['auth'] else 600) or now - s['created'] > 28800:
                del SESSIONS[key]
        if len(SESSIONS) >= 1000:
            raise ValueError('Too many sessions; try again later')
        token = secrets.token_urlsafe(32)
        SESSIONS[token] = {'auth': auth, 'csrf': secrets.token_urlsafe(32), 'created': now, 'last': now}
        return token, SESSIONS[token]

def helper(*args):
    result = subprocess.run(['/usr/bin/sudo', '-n', '/usr/local/sbin/oshin-fw', *args], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Firewall helper failed')
    return json.loads(result.stdout)

def devices():
    status = helper('status')
    blocked = set(status.get('blocked', []))
    scheduled = set(status.get('scheduled_active', []))
    meta = status.get('metadata', {}).get('devices', {})
    guests = status.get('guests', {})
    result = subprocess.run(['/usr/sbin/ip', '-j', '-4', 'neigh', 'show', 'dev', 'enp1s0'], capture_output=True, text=True, timeout=5, check=True)
    rows = {}
    for item in json.loads(result.stdout):
        addr = ipaddress.IPv4Address(item['dst'])
        if addr not in ipaddress.IPv4Network('192.168.16.0/24') or int(addr) % 256 in (0, 1, 2, 255):
            continue
        ip = str(addr)
        dev_meta = meta.get(ip, {})
        guest_info = guests.get(ip)
        rows[ip] = {
            'ip': ip,
            'mac': item.get('lladdr', ''),
            'state': ', '.join(item.get('state', [])),
            'blocked': ip in blocked,
            'scheduled': ip in scheduled,
            'guest_session': guest_info if guest_info and guest_info.get('expires_at', 0) > time.time() else None,
            'name': dev_meta.get('name', ''),
            'group': dev_meta.get('group', 'default'),
            'speed_limit': dev_meta.get('speed_limit', 0),
            'schedule': dev_meta.get('schedule', {'enabled': False, 'start': '22:00', 'end': '06:00'})
        }
    for ip in blocked | set(meta.keys()) | set(guests.keys()):
        if ip not in rows:
            dev_meta = meta.get(ip, {})
            guest_info = guests.get(ip)
            rows[ip] = {
                'ip': ip,
                'mac': '',
                'state': 'Not in neighbour cache',
                'blocked': ip in blocked,
                'scheduled': ip in scheduled,
                'guest_session': guest_info if guest_info and guest_info.get('expires_at', 0) > time.time() else None,
                'name': dev_meta.get('name', ''),
                'group': dev_meta.get('group', 'default'),
                'speed_limit': dev_meta.get('speed_limit', 0),
                'schedule': dev_meta.get('schedule', {'enabled': False, 'start': '22:00', 'end': '06:00'})
            }
    return sorted(rows.values(), key=lambda x: ipaddress.IPv4Address(x['ip']))

def usage():
    base = Path('/sys/class/net/enp1s0/statistics')
    return {'upload': int((base / 'rx_bytes').read_text()), 'download': int((base / 'tx_bytes').read_text()), 'at': time.time()}

class Handler(BaseHTTPRequestHandler):
    server_version = 'OshinPortal'
    sys_version = ''
    def setup(self):
        super().setup(); self.connection.settimeout(10)
    def respond(self, code, data='', kind='application/json', cookie=None, location=None):
        body = (json.dumps(data) if kind == 'application/json' else data).encode()
        self.send_response(code)
        for k, v in {
            'Content-Type': kind + '; charset=utf-8',
            'Content-Length': str(len(body)),
            'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'Referrer-Policy': 'no-referrer',
            'Content-Security-Policy': "default-src 'none'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        }.items():
            self.send_header(k, v)
        if cookie is not None:
            self.send_header('Set-Cookie', f'oshin_session={cookie}; Path=/; Secure; HttpOnly; SameSite=Strict' + ('' if cookie else '; Max-Age=0'))
        if location:
            self.send_header('Location', location)
        self.end_headers(); self.wfile.write(body)

    def valid_host(self):
        if self.headers.get('Host') != AUTHORITY:
            self.respond(403, {'error': 'Use ' + ORIGIN}); return False
        return True

    def session(self):
        try:
            cookies = SimpleCookie(); cookies.load(self.headers.get('Cookie', ''))
            token = cookies['oshin_session'].value
        except Exception:
            return None, None
        with LOCK:
            s = SESSIONS.get(token); now = time.monotonic()
            if not s: return None, None
            if now - s['last'] > (1800 if s['auth'] else 600) or now - s['created'] > 28800:
                del SESSIONS[token]; return None, None
            s['last'] = now
            return token, s.copy()

    def auth(self):
        token, s = self.session()
        if s and s['auth']: return token, s
        if self.path.startswith('/api/'): self.respond(401, {'error': 'Please sign in again'})
        else: self.respond(303, '', 'text/plain', location='/login')
        return None, None

    def do_GET(self):
        if not self.valid_host(): return
        assets = {'/style.css': ('style.css', 'text/css'), '/app.js': ('app.js', 'text/javascript')}
        if self.path in assets:
            name, kind = assets[self.path]; self.respond(200, (ROOT / name).read_text(), kind); return
        if self.path == '/login':
            token, s = self.session()
            if s and s['auth']: self.respond(303, '', 'text/plain', location='/dashboard'); return
            try:
                if not s: token, s = new_session()
                self.respond(200, (ROOT / 'login.html').read_text().replace('__CSRF__', s['csrf']), 'text/html', cookie=token)
            except ValueError as e: self.respond(429, {'error': str(e)})
            return
        token, s = self.auth()
        if not s: return
        clean_path = self.path.split('?')[0]
        if clean_path in PAGES:
            self.respond(200, (ROOT / 'portal.html').read_text().replace('__CSRF__', s['csrf']), 'text/html')
        elif clean_path == '/api/devices':
            try: self.respond(200, {'devices': devices(), 'client': self.client_address[0]})
            except Exception as e: self.respond(503, {'error': str(e)})
        elif clean_path == '/api/usage':
            try: self.respond(200, usage())
            except Exception: self.respond(503, {'error': 'Interface counters unavailable'})
        elif clean_path == '/api/logs':
            with LOCK: rows = list(EVENTS)
            self.respond(200, {'events': rows})
        elif clean_path == '/api/activity':
            target = None
            if '?' in self.path:
                from urllib.parse import parse_qs, urlparse
                qs = parse_qs(urlparse(self.path).query)
                ip_param = qs.get('ip', [None])[0]
                if ip_param and ip_param != 'all':
                    try: target = str(ipaddress.IPv4Address(ip_param))
                    except ValueError: self.respond(400, {'error': 'Invalid IP address'}); return
            try:
                res = helper('activity', target) if target else helper('activity')
                res['client'] = self.client_address[0]
                res['devices'] = devices()
                self.respond(200, res)
            except Exception as e: self.respond(503, {'error': str(e)})
        elif clean_path == '/api/plans':
            try:
                st = helper('status')
                self.respond(200, {
                    'plans': st.get('plans', []),
                    'vouchers': st.get('vouchers', {}),
                    'guests': st.get('guests', {}),
                    'captive_enabled': st.get('metadata', {}).get('captive_enabled', True),
                    'devices': devices()
                })
            except Exception as e: self.respond(503, {'error': str(e)})
        else: self.respond(404, {'error': 'Not found'})

    def do_POST(self):
        if not self.valid_host(): return
        token, s = self.session()
        if not s: self.respond(401, {'error': 'Reload the login page'}); return
        if self.headers.get('Origin') != ORIGIN or not hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), s['csrf']):
            self.respond(403, {'error': 'Reload this page and try again'}); return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 4096 or self.headers.get('Content-Type') != 'application/json': raise ValueError()
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict): raise ValueError()
        except Exception: self.respond(400, {'error': 'Invalid request'}); return
        if self.path == '/api/login':
            client = self.client_address[0]; now = time.monotonic()
            with LOCK:
                for ip in list(FAILURES):
                    if now - FAILURES[ip][0] > 60: del FAILURES[ip]
                first, count = FAILURES.get(client, (now, 0))
                if count >= 5: self.respond(429, {'error': 'Too many attempts. Wait one minute.'}); return
                FAILURES[client] = (first, count + 1)
            password = data.get('password'); user = data.get('username')
            valid = False
            if isinstance(password, str) and isinstance(user, str) and len(password) <= 1024:
                value = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(CONFIG['salt']), 200000).hex()
                valid = hmac.compare_digest(user, 'admin') and hmac.compare_digest(value, CONFIG['hash'])
            if not valid: self.respond(401, {'error': 'Incorrect username or password'}); return
            with LOCK:
                FAILURES.pop(client, None); SESSIONS.pop(token, None)
                token, s = new_session(True)
            audit('Signed in', client)
            self.respond(200, {'ok': True}, cookie=token); return
        if not s['auth']: self.respond(401, {'error': 'Please sign in'}); return
        if self.path == '/api/logout':
            with LOCK: SESSIONS.pop(token, None)
            audit('Signed out', self.client_address[0]); self.respond(200, {'ok': True}, cookie=''); return
        if self.path == '/api/activity/clear':
            try:
                res = helper('clear_activity')
                audit('Cleared DNS activity logs', self.client_address[0])
                self.respond(200, res)
            except Exception as e: self.respond(503, {'error': str(e)})
            return
        if self.path == '/api/device/update':
            try:
                ip = str(ipaddress.IPv4Address(data.get('ip', '')))
                payload = {
                    'name': str(data.get('name', ''))[:64],
                    'group': data.get('group', 'default'),
                    'speed_limit': int(data.get('speed_limit', 0)),
                    'schedule': data.get('schedule', {})
                }
                res = helper('set_device', ip, json.dumps(payload))
                audit('Updated device settings', self.client_address[0], f"{ip} ({payload['name'] or payload['group']})")
                self.respond(200, res)
            except (ValueError, TypeError) as e: self.respond(400, {'error': str(e) or 'Invalid device settings'})
            except Exception as e: self.respond(503, {'error': str(e)})
            return
        if self.path == '/api/plans/update':
            try:
                plans = data.get('plans', [])
                res = helper('set_plans', json.dumps(plans))
                audit('Updated hotspot plans', self.client_address[0])
                self.respond(200, res)
            except Exception as e: self.respond(400, {'error': str(e)})
            return
        if self.path == '/api/plans/toggle':
            try:
                enabled = '1' if data.get('enabled') else '0'
                res = helper('toggle_captive', enabled)
                audit('Toggled captive portal', self.client_address[0], 'Enabled' if enabled == '1' else 'Disabled')
                self.respond(200, res)
            except Exception as e: self.respond(400, {'error': str(e)})
            return
        if self.path == '/api/vouchers/create':
            try:
                plan_id = str(data.get('plan_id', 'standard'))
                code = data.get('code')
                args = ('create_voucher', plan_id, str(code)) if code else ('create_voucher', plan_id)
                res = helper(*args)
                audit('Created access voucher', self.client_address[0], res.get('voucher', {}).get('code', ''))
                self.respond(200, res)
            except Exception as e: self.respond(400, {'error': str(e)})
            return
        if self.path == '/api/vouchers/delete':
            try:
                code = str(data.get('code', ''))
                res = helper('delete_voucher', code)
                audit('Deleted access voucher', self.client_address[0], code)
                self.respond(200, res)
            except Exception as e: self.respond(400, {'error': str(e)})
            return
        if self.path == '/api/guest/revoke':
            try:
                ip = str(ipaddress.IPv4Address(data.get('ip', '')))
                res = helper('revoke_guest', ip)
                audit('Revoked guest session', self.client_address[0], ip)
                self.respond(200, res)
            except Exception as e: self.respond(400, {'error': str(e)})
            return
        if self.path == '/api/guest/extend':
            try:
                ip = str(ipaddress.IPv4Address(data.get('ip', '')))
                extra = int(data.get('minutes', 30))
                st = helper('status')
                session = st.get('guests', {}).get(ip, {})
                plan_id = session.get('plan_id', 'starter')
                speed = session.get('speed_limit', 0)
                res = helper('authorize_guest', ip, plan_id, str(extra), str(speed))
                audit('Extended guest session', self.client_address[0], f"{ip} (+{extra}m)")
                self.respond(200, res)
            except Exception as e: self.respond(400, {'error': str(e)})
            return
        if self.path == '/api/action':
            try:
                if data.get('action') not in ('block', 'unblock'): raise ValueError()
                ip = str(ipaddress.IPv4Address(data.get('ip', '')))
                if ip == self.client_address[0] and data['action'] == 'block': raise ValueError()
                result = helper(data['action'], ip)
                audit('Blocked address' if data['action'] == 'block' else 'Unblocked address', self.client_address[0], ip)
                self.respond(200, result)
            except (ValueError, TypeError): self.respond(400, {'error': 'Invalid address or action. You cannot block your current admin device.'})
            except Exception as e: self.respond(503, {'error': str(e)})
        else: self.respond(404, {'error': 'Not found'})

class CaptiveHandler(BaseHTTPRequestHandler):
    server_version = 'OshinHotspot'
    sys_version = ''
    def setup(self):
        super().setup(); self.connection.settimeout(10)
    def respond(self, code, data='', kind='application/json', location=None):
        body = (json.dumps(data) if kind == 'application/json' else data).encode()
        self.send_response(code)
        for k, v in {
            'Content-Type': kind + '; charset=utf-8',
            'Content-Length': str(len(body)),
            'Cache-Control': 'no-store'
        }.items():
            self.send_header(k, v)
        if location:
            self.send_header('Location', location)
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        client_ip = self.client_address[0]
        probes = ('/generate_204', '/gen_204', '/hotspot-detect.html', '/connecttest.txt', '/ncsi.txt', '/success.txt')
        clean_path = self.path.split('?')[0]

        if clean_path in probes:
            try:
                st = helper('status')
                guests = st.get('guests', {})
                if client_ip in guests and guests[client_ip].get('expires_at', 0) > time.time():
                    if '204' in clean_path:
                        self.send_response(204); self.end_headers(); return
                    self.respond(200, 'Success', 'text/plain'); return
            except Exception:
                pass
            self.respond(302, '', 'text/plain', location=f'http://{HOST}:{CAPTIVE_PORT}/guest')
            return

        if clean_path in ('/', '/guest'):
            guest_html = ROOT / 'guest.html'
            if guest_html.exists():
                self.respond(200, guest_html.read_text(), 'text/html')
            else:
                self.respond(200, '<h1>OshinWiFi Guest Hotspot</h1>', 'text/html')
            return

        if clean_path == '/api/guest/status':
            try:
                st = helper('status')
                guests = st.get('guests', {})
                session = guests.get(client_ip)
                is_auth = bool(session and session.get('expires_at', 0) > time.time())
                self.respond(200, {
                    'ip': client_ip,
                    'authorized': is_auth,
                    'session': session if is_auth else None,
                    'plans': [p for p in st.get('plans', []) if p.get('active', True)]
                })
            except Exception as e:
                self.respond(503, {'error': str(e)})
            return

        self.respond(302, '', 'text/plain', location=f'http://{HOST}:{CAPTIVE_PORT}/guest')

    def do_POST(self):
        client_ip = self.client_address[0]
        clean_path = self.path.split('?')[0]
        try:
            size = int(self.headers.get('Content-Length', '0'))
            data = json.loads(self.rfile.read(size)) if 0 < size <= 4096 else {}
        except Exception:
            self.respond(400, {'error': 'Invalid request'}); return

        if clean_path == '/api/guest/connect':
            try:
                st = helper('status')
                plans = {p['id']: p for p in st.get('plans', [])}
                vouchers = st.get('vouchers', {})
                chosen_plan = None

                voucher_code = str(data.get('voucher', '')).strip()
                plan_id = str(data.get('plan_id', '')).strip()

                if voucher_code:
                    if voucher_code not in vouchers or vouchers[voucher_code].get('used'):
                        self.respond(400, {'error': 'Invalid or already used voucher code'}); return
                    v_info = vouchers[voucher_code]
                    chosen_plan = plans.get(v_info['plan_id'])
                    if not chosen_plan:
                        self.respond(400, {'error': 'Voucher plan is no longer available'}); return
                    helper('delete_voucher', voucher_code)
                elif plan_id:
                    chosen_plan = plans.get(plan_id)
                    if not chosen_plan or not chosen_plan.get('active'):
                        self.respond(400, {'error': 'Selected plan is not available'}); return
                    if chosen_plan.get('type') == 'voucher':
                        self.respond(400, {'error': 'This plan requires a voucher code'}); return
                else:
                    self.respond(400, {'error': 'Choose a plan or enter a voucher code'}); return

                duration = int(chosen_plan.get('duration_minutes', 30))
                speed = int(chosen_plan.get('speed_limit', 0))
                res = helper('authorize_guest', client_ip, chosen_plan['id'], str(duration), str(speed))
                audit('Guest connected via hotspot', client_ip, f"{chosen_plan['name']} ({duration}m)")
                self.respond(200, {
                    'ok': True,
                    'plan_name': chosen_plan['name'],
                    'duration_minutes': duration,
                    'speed_limit': speed,
                    'session': res.get('session')
                })
            except Exception as e:
                self.respond(503, {'error': str(e)})
            return

        self.respond(404, {'error': 'Not found'})

def schedule_worker():
    while True:
        time.sleep(30)
        try:
            helper('check_guest_expiries')
            helper('apply_schedules')
        except Exception:
            pass

def main():
    global CONFIG
    CONFIG = json.loads(Path('/etc/oshin-dashboard/auth.json').read_text())
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain('/etc/oshin-dashboard/cert.pem', '/etc/oshin-dashboard/key.pem')

    threading.Thread(target=schedule_worker, daemon=True).start()

    try:
        captive_server = ThreadingHTTPServer((HOST, CAPTIVE_PORT), CaptiveHandler)
        threading.Thread(target=captive_server.serve_forever, daemon=True).start()
        print(f'Captive hotspot portal listening at http://{HOST}:{CAPTIVE_PORT}', flush=True)
    except Exception as e:
        print('Notice: Captive listener: ' + str(e), flush=True)

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print('Admin portal listening at ' + ORIGIN, flush=True)
    server.serve_forever()

if __name__ == '__main__':
    main()
