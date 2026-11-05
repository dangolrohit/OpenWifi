#!/usr/bin/python3 -I
"""Narrow root helper: manages inet oshin_dashboard, guest isolation, QoS, schedules, and captive portal."""
from datetime import datetime
try:
    import fcntl
except ImportError:
    fcntl = None
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time

STATE = Path('/var/lib/oshin-firewall/blocked.json')
METADATA = Path('/var/lib/oshin-firewall/metadata.json')
GUEST_STATE = Path('/var/lib/oshin-firewall/guests.json')
PLANS_STATE = Path('/var/lib/oshin-firewall/plans.json')
VOUCHERS_STATE = Path('/var/lib/oshin-firewall/vouchers.json')
DNS_LOG = Path('/var/log/oshin-dns.log')
NFT = '/usr/sbin/nft'

DEFAULT_PLANS = [
    {
        'id': 'starter',
        'name': 'Starter Free',
        'type': 'click',
        'duration_minutes': 30,
        'speed_limit': 2,
        'active': True,
        'description': 'Free 30 minutes light web access with agreement'
    },
    {
        'id': 'standard',
        'name': 'Standard 2-Hour',
        'type': 'voucher',
        'duration_minutes': 120,
        'speed_limit': 5,
        'active': True,
        'description': 'Standard 2-hour high-speed access via voucher code'
    },
    {
        'id': 'half_day',
        'name': 'Half-Day Pass',
        'type': 'voucher',
        'duration_minutes': 360,
        'speed_limit': 10,
        'active': True,
        'description': '6 hours of fast streaming and browsing access'
    },
    {
        'id': 'full_day',
        'name': 'Full-Day Pass',
        'type': 'voucher',
        'duration_minutes': 1440,
        'speed_limit': 15,
        'active': True,
        'description': '24 hours unlimited access for customers and guests'
    },
    {
        'id': 'vip',
        'name': 'VIP Premium',
        'type': 'voucher',
        'duration_minutes': 4320,
        'speed_limit': 25,
        'active': True,
        'description': '3-day unrestricted high-bandwidth VIP access'
    }
]

QUERY_RE = re.compile(
    r'(?:^(?P<timestamp>[A-Za-z]{3}\s+\d+\s+[\d:]+|\d{4}-\d{2}-\d{2}[T\s][\d:.]+[\w+-]*).*?)?'
    r'query\[(?P<type>[^\]]+)\]\s+(?P<domain>[^\s/]+)\s+from\s+(?P<client>\d+\.\d+\.\d+\.\d+)'
)

def valid_ip(value):
    ip = ipaddress.IPv4Address(value)
    if ip not in ipaddress.IPv4Network('192.168.16.0/24') or int(ip) % 256 in (0, 1, 2, 255):
        raise ValueError('Only client addresses 192.168.16.3–254 are allowed')
    return str(ip)

def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, timeout=10, **kwargs)

def get_dns_log_lines():
    for log_path in (Path('/var/log/dnsmasq.log'), Path('/var/log/oshin-dns.log'), Path('/var/log/syslog')):
        if log_path.exists():
            try:
                with log_path.open('r', encoding='utf-8', errors='replace') as f:
                    lines = [l for l in f.readlines() if 'query[' in l]
                    if lines:
                        return lines[-600:]
            except Exception:
                pass

    try:
        res = subprocess.run(
            ['/usr/bin/journalctl', '-u', 'NetworkManager', '-n', '500', '--no-pager'],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0 and 'query[' in res.stdout:
            return [l for l in res.stdout.splitlines() if 'query[' in l]
    except Exception:
        pass

    return []

def parse_dns_log(log_path, filter_ip=None, limit=300):
    lines = []
    if isinstance(log_path, (str, Path)):
        p = Path(log_path)
        if p.exists():
            try:
                with p.open('r', encoding='utf-8', errors='replace') as f:
                    lines = [l for l in f.readlines() if 'query[' in l]
            except Exception:
                pass
        if not lines:
            lines = get_dns_log_lines()
    elif isinstance(log_path, (list, tuple)):
        lines = log_path

    results = []
    for line in reversed(lines):
        line = line.strip()
        if not line or 'query[' not in line:
            continue
        m = QUERY_RE.search(line)
        if not m:
            continue
        client = m.group('client')
        if filter_ip and client != filter_ip:
            continue
        results.append({
            'time': m.group('timestamp') or '',
            'client': client,
            'domain': m.group('domain'),
            'type': m.group('type')
        })
        if len(results) >= limit:
            break
    return results

def is_schedule_active(schedule, now_time=None):
    if not isinstance(schedule, dict) or not schedule.get('enabled'):
        return False
    start_str = schedule.get('start', '')
    end_str = schedule.get('end', '')
    try:
        sh, sm = map(int, start_str.split(':'))
        eh, em = map(int, end_str.split(':'))
        if not (0 <= sh <= 23 and 0 <= sm <= 59 and 0 <= eh <= 23 and 0 <= em <= 59):
            return False
    except Exception:
        return False
    if sh == eh and sm == em:
        return False

    if now_time is None:
        now = datetime.now().time()
        now_minutes = now.hour * 60 + now.minute
    else:
        now_minutes = now_time.hour * 60 + now_time.minute

    start_minutes = sh * 60 + sm
    end_minutes = eh * 60 + em

    if start_minutes < end_minutes:
        return start_minutes <= now_minutes < end_minutes
    else:
        return now_minutes >= start_minutes or now_minutes < end_minutes

def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default

def save_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2))
    temp.chmod(0o600)
    temp.replace(path)

def load_metadata():
    data = load_json(METADATA, {'devices': {}, 'captive_enabled': True})
    if 'devices' not in data:
        data['devices'] = {}
    if 'captive_enabled' not in data:
        data['captive_enabled'] = True
    return data

def save_metadata(data):
    save_json(METADATA, data)

def load_guests():
    return load_json(GUEST_STATE, {})

def save_guests(data):
    save_json(GUEST_STATE, data)

def load_plans():
    return load_json(PLANS_STATE, DEFAULT_PLANS)

def save_plans(data):
    save_json(PLANS_STATE, data)

def load_vouchers():
    return load_json(VOUCHERS_STATE, {})

def save_vouchers(data):
    save_json(VOUCHERS_STATE, data)

def apply_rules(blocked, metadata=None, guests=None):
    if metadata is None:
        metadata = load_metadata()
    if guests is None:
        guests = load_guests()

    devices_meta = metadata.get('devices', {})
    captive_enabled = metadata.get('captive_enabled', True)

    scheduled_blocks = set()
    customer_ips = set()
    whitelisted_ips = set()
    speed_limits = {}

    for ip, info in devices_meta.items():
        try:
            vip = valid_ip(ip)
        except ValueError:
            continue
        if is_schedule_active(info.get('schedule', {})):
            scheduled_blocks.add(vip)
        group = info.get('group', 'default')
        if group == 'customer':
            customer_ips.add(vip)
        elif group in ('family', 'staff'):
            whitelisted_ips.add(vip)

        limit_mbps = info.get('speed_limit', 0)
        if isinstance(limit_mbps, (int, float)) and limit_mbps > 0:
            speed_limits[vip] = int(limit_mbps * 125)

    # Active authenticated guests
    authenticated_ips = set()
    now_ts = time.time()
    for ip, s in guests.items():
        try:
            vip = valid_ip(ip)
            if s.get('expires_at', 0) > now_ts:
                authenticated_ips.add(vip)
                g_limit = s.get('speed_limit', 0)
                if isinstance(g_limit, (int, float)) and g_limit > 0 and vip not in speed_limits:
                    speed_limits[vip] = int(g_limit * 125)
        except ValueError:
            continue

    effective_blocks = set(blocked) | scheduled_blocks

    exists = run([NFT, 'list', 'table', 'inet', 'oshin_dashboard']).returncode == 0
    script = 'delete table inet oshin_dashboard\n' if exists else ''
    script += 'add table inet oshin_dashboard\n'
    script += 'add set inet oshin_dashboard blocked { type ipv4_addr; }\n'
    script += 'add set inet oshin_dashboard customers { type ipv4_addr; }\n'
    script += 'add set inet oshin_dashboard whitelisted { type ipv4_addr; }\n'
    script += 'add set inet oshin_dashboard authenticated { type ipv4_addr; }\n'

    # Input chain: Portal lockdown for customers (blocks access to admin port 8090)
    script += 'add chain inet oshin_dashboard input { type filter hook input priority -10; policy accept; }\n'
    script += 'add rule inet oshin_dashboard input iifname "enp1s0" ip saddr @customers tcp dport 8090 counter drop\n'

    # Prerouting NAT chain: Redirect unauthenticated HTTP traffic to captive portal port 8088
    script += 'add chain inet oshin_dashboard prerouting { type nat hook prerouting priority dstnat; policy accept; }\n'
    if captive_enabled:
        script += 'add rule inet oshin_dashboard prerouting iifname "enp1s0" ip saddr != @whitelisted ip saddr != @authenticated tcp dport 80 redirect to :8088\n'

    # Forward chain: Access blocks, client-to-client guest isolation, QoS, and captive enforcement
    script += 'add chain inet oshin_dashboard forward { type filter hook forward priority -10; policy accept; }\n'
    script += 'add rule inet oshin_dashboard forward iifname "enp1s0" ip saddr @blocked counter drop\n'
    script += 'add rule inet oshin_dashboard forward oifname "enp1s0" ip daddr @blocked counter drop\n'

    # Drop DNS-over-TLS (port 853) so client devices fallback to standard gateway DNS on port 53
    script += 'add rule inet oshin_dashboard forward iifname "enp1s0" tcp dport 853 counter drop\n'

    # Customer client-to-client isolation (customers cannot access other devices on LAN)
    script += 'add rule inet oshin_dashboard forward iifname "enp1s0" oifname "enp1s0" ip saddr @customers counter drop\n'
    script += 'add rule inet oshin_dashboard forward iifname "enp1s0" oifname "enp1s0" ip daddr @customers counter drop\n'

    # Speed limits (rate limiting) per IP
    for ip, rate_kb in sorted(speed_limits.items()):
        burst = max(100, int(rate_kb * 0.2))
        script += f'add rule inet oshin_dashboard forward iifname "enp1s0" ip saddr {ip} limit rate over {rate_kb} kbytes/second burst {burst} kbytes counter drop\n'
        script += f'add rule inet oshin_dashboard forward oifname "enp1s0" ip daddr {ip} limit rate over {rate_kb} kbytes/second burst {burst} kbytes counter drop\n'

    # Captive portal forward barrier: unauthenticated devices cannot forward packets to the internet
    if captive_enabled:
        script += 'add rule inet oshin_dashboard forward iifname "enp1s0" ip saddr @whitelisted accept\n'
        script += 'add rule inet oshin_dashboard forward iifname "enp1s0" ip saddr @authenticated accept\n'
        script += 'add rule inet oshin_dashboard forward iifname "enp1s0" counter drop\n'

    if effective_blocks:
        script += 'add element inet oshin_dashboard blocked { ' + ', '.join(sorted(valid_ip(x) for x in effective_blocks)) + ' }\n'
    if customer_ips:
        script += 'add element inet oshin_dashboard customers { ' + ', '.join(sorted(valid_ip(x) for x in customer_ips)) + ' }\n'
    if whitelisted_ips:
        script += 'add element inet oshin_dashboard whitelisted { ' + ', '.join(sorted(valid_ip(x) for x in whitelisted_ips)) + ' }\n'
    if authenticated_ips:
        script += 'add element inet oshin_dashboard authenticated { ' + ', '.join(sorted(valid_ip(x) for x in authenticated_ips)) + ' }\n'

    result = run([NFT, '-f', '-'], input=script)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())

def save(blocked):
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(sorted(blocked)))
    temp.chmod(0o600)
    temp.replace(STATE)

def main(args):
    if os.geteuid() != 0:
        raise ValueError('Run through the installed sudo helper')
    allowed_actions = (
        'status', 'restore', 'block', 'unblock', 'activity', 'clear_activity',
        'set_device', 'apply_schedules', 'authorize_guest', 'revoke_guest',
        'check_guest_expiries', 'set_plans', 'create_voucher', 'delete_voucher',
        'toggle_captive'
    )
    if not args or args[0] not in allowed_actions:
        raise ValueError('Invalid action')
    action = args[0]

    if action in ('block', 'unblock', 'revoke_guest', 'delete_voucher', 'set_plans', 'toggle_captive'):
        if len(args) != 2:
            raise ValueError('Invalid argument count')
    elif action == 'set_device':
        if len(args) != 3:
            raise ValueError('Invalid argument count')
    elif action == 'create_voucher':
        if len(args) not in (2, 3):
            raise ValueError('Invalid argument count')
    elif action == 'authorize_guest':
        if len(args) not in (4, 5):
            raise ValueError('Invalid argument count')
    elif action == 'activity':
        if len(args) not in (1, 2):
            raise ValueError('Invalid argument count')
    else:
        if len(args) != 1:
            raise ValueError('Invalid argument count')

    if action == 'activity':
        target = valid_ip(args[1]) if len(args) == 2 and args[1] != 'all' else None
        log_path = Path('/var/log/dnsmasq.log') if Path('/var/log/dnsmasq.log').exists() else DNS_LOG
        queries = parse_dns_log(log_path, filter_ip=target, limit=300)
        has_logs = bool(queries) or Path('/var/log/dnsmasq.log').exists() or DNS_LOG.exists()
        print(json.dumps({'queries': queries, 'log_exists': has_logs}))
        return

    if action == 'clear_activity':
        for p in (DNS_LOG, Path('/var/log/dnsmasq.log')):
            if p.exists():
                try:
                    p.write_text('')
                except Exception:
                    pass
        print(json.dumps({'ok': True}))
        return

    if action == 'set_device':
        target = valid_ip(args[1])
        try:
            payload = json.loads(args[2])
            if not isinstance(payload, dict):
                raise ValueError()
        except Exception:
            raise ValueError('Invalid device payload JSON')

        name = str(payload.get('name', ''))[:64]
        group = payload.get('group', 'default')
        if group not in ('family', 'customer', 'staff', 'default'):
            raise ValueError('Group must be family, customer, staff, or default')
        try:
            speed_limit = max(0, int(payload.get('speed_limit', 0)))
        except (ValueError, TypeError):
            raise ValueError('Speed limit must be a positive number or 0')

        schedule = payload.get('schedule', {})
        if not isinstance(schedule, dict):
            schedule = {'enabled': False}
        else:
            sched_enabled = bool(schedule.get('enabled', False))
            start_str = str(schedule.get('start', '22:00'))
            end_str = str(schedule.get('end', '06:00'))
            try:
                sh, sm = map(int, start_str.split(':'))
                eh, em = map(int, end_str.split(':'))
                if not (0 <= sh <= 23 and 0 <= sm <= 59 and 0 <= eh <= 23 and 0 <= em <= 59):
                    raise ValueError()
                schedule = {'enabled': sched_enabled, 'start': f'{sh:02d}:{sm:02d}', 'end': f'{eh:02d}:{em:02d}'}
            except Exception:
                raise ValueError('Invalid schedule time format. Use HH:MM')

        with (STATE.parent / 'lock').open('a') as lock:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_EX)
            metadata = load_metadata()
            metadata.setdefault('devices', {})[target] = {
                'name': name,
                'group': group,
                'speed_limit': speed_limit,
                'schedule': schedule
            }
            blocked = set(json.loads(STATE.read_text())) if STATE.exists() else set()
            blocked = {valid_ip(x) for x in blocked}
            apply_rules(blocked, metadata)
            save_metadata(metadata)
            active_schedules = [ip for ip, d in metadata['devices'].items() if is_schedule_active(d.get('schedule', {}))]
            print(json.dumps({'ok': True, 'metadata': metadata, 'scheduled_active': sorted(active_schedules)}))
        return

    if action == 'toggle_captive':
        enable = args[1].lower() in ('1', 'true', 'on')
        with (STATE.parent / 'lock').open('a') as lock:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_EX)
            metadata = load_metadata()
            metadata['captive_enabled'] = enable
            save_metadata(metadata)
            blocked = set(json.loads(STATE.read_text())) if STATE.exists() else set()
            blocked = {valid_ip(x) for x in blocked}
            apply_rules(blocked, metadata)
            print(json.dumps({'ok': True, 'captive_enabled': enable}))
        return

    if action == 'set_plans':
        try:
            plans_data = json.loads(args[1])
            if not isinstance(plans_data, list):
                raise ValueError()
        except Exception:
            raise ValueError('Invalid plans payload JSON')
        with (STATE.parent / 'lock').open('a') as lock:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_EX)
            save_plans(plans_data)
            print(json.dumps({'ok': True, 'plans': plans_data}))
        return

    if action == 'create_voucher':
        plan_id = args[1]
        code = args[2] if len(args) == 3 else ''.join(secrets.choice('0123456789') for _ in range(6))
        with (STATE.parent / 'lock').open('a') as lock:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_EX)
            vouchers = load_vouchers()
            vouchers[code] = {
                'code': code,
                'plan_id': plan_id,
                'created_at': time.time(),
                'used': False,
                'used_by': None,
                'used_at': None
            }
            save_vouchers(vouchers)
            print(json.dumps({'ok': True, 'voucher': vouchers[code]}))
        return

    if action == 'delete_voucher':
        code = args[1]
        with (STATE.parent / 'lock').open('a') as lock:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_EX)
            vouchers = load_vouchers()
            vouchers.pop(code, None)
            save_vouchers(vouchers)
            print(json.dumps({'ok': True}))
        return

    if action == 'authorize_guest':
        client = valid_ip(args[1])
        plan_id = args[2]
        duration = int(args[3]) # minutes
        speed = int(args[4]) if len(args) == 5 else 0
        now_ts = time.time()
        expires_at = now_ts + (duration * 60)
        with (STATE.parent / 'lock').open('a') as lock:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_EX)
            guests = load_guests()
            guests[client] = {
                'ip': client,
                'plan_id': plan_id,
                'speed_limit': speed,
                'authorized_at': now_ts,
                'expires_at': expires_at
            }
            save_guests(guests)
            metadata = load_metadata()
            blocked = set(json.loads(STATE.read_text())) if STATE.exists() else set()
            blocked = {valid_ip(x) for x in blocked}
            apply_rules(blocked, metadata, guests)
            print(json.dumps({'ok': True, 'session': guests[client]}))
        return

    if action == 'revoke_guest':
        client = valid_ip(args[1])
        with (STATE.parent / 'lock').open('a') as lock:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_EX)
            guests = load_guests()
            guests.pop(client, None)
            save_guests(guests)
            metadata = load_metadata()
            blocked = set(json.loads(STATE.read_text())) if STATE.exists() else set()
            blocked = {valid_ip(x) for x in blocked}
            apply_rules(blocked, metadata, guests)
            print(json.dumps({'ok': True}))
        return

    if action == 'check_guest_expiries':
        now_ts = time.time()
        with (STATE.parent / 'lock').open('a') as lock:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_EX)
            guests = load_guests()
            expired = [ip for ip, s in guests.items() if s.get('expires_at', 0) <= now_ts]
            if expired:
                for ip in expired:
                    guests.pop(ip, None)
                save_guests(guests)
                metadata = load_metadata()
                blocked = set(json.loads(STATE.read_text())) if STATE.exists() else set()
                blocked = {valid_ip(x) for x in blocked}
                apply_rules(blocked, metadata, guests)
            print(json.dumps({'ok': True, 'expired_count': len(expired), 'active_count': len(guests)}))
        return

    if action == 'apply_schedules':
        with (STATE.parent / 'lock').open('a') as lock:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_EX)
            metadata = load_metadata()
            blocked = set(json.loads(STATE.read_text())) if STATE.exists() else set()
            blocked = {valid_ip(x) for x in blocked}
            apply_rules(blocked, metadata)
            active_schedules = [ip for ip, d in metadata.get('devices', {}).items() if is_schedule_active(d.get('schedule', {}))]
            print(json.dumps({'ok': True, 'scheduled_active': sorted(active_schedules)}))
        return

    target = valid_ip(args[1]) if len(args) == 2 else None
    with (STATE.parent / 'lock').open('a') as lock:
        if fcntl:
            fcntl.flock(lock, fcntl.LOCK_EX)
        blocked = set(json.loads(STATE.read_text())) if STATE.exists() else set()
        blocked = {valid_ip(x) for x in blocked}
        metadata = load_metadata()
        active_schedules = [ip for ip, d in metadata.get('devices', {}).items() if is_schedule_active(d.get('schedule', {}))]
        if action == 'status':
            active = run([NFT, '-j', 'list', 'set', 'inet', 'oshin_dashboard', 'blocked'])
            if active.returncode:
                raise RuntimeError('Dashboard firewall is missing; run sudo systemctl restart oshin-firewall')
            actual = set()
            for item in json.loads(active.stdout)['nftables']:
                if 'set' in item:
                    actual.update(item['set'].get('elem', []))
            effective = blocked | set(active_schedules)
            if actual != effective:
                raise RuntimeError('Saved and live rules differ; restart oshin-firewall')
        else:
            old = blocked.copy()
            if action == 'block': blocked.add(target)
            if action == 'unblock': blocked.discard(target)
            apply_rules(blocked, metadata)
            try:
                save(blocked)
            except Exception:
                apply_rules(old, metadata)
                raise
        print(json.dumps({
            'blocked': sorted(blocked),
            'metadata': metadata,
            'scheduled_active': sorted(active_schedules),
            'guests': load_guests(),
            'plans': load_plans(),
            'vouchers': load_vouchers()
        }))

if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
