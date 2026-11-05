#!/usr/bin/python3 -I
"""Narrow root helper: manages inet oshin_dashboard, guest isolation, QoS, and schedules."""
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
import subprocess
import sys

STATE = Path('/var/lib/oshin-firewall/blocked.json')
METADATA = Path('/var/lib/oshin-firewall/metadata.json')
DNS_LOG = Path('/var/log/oshin-dns.log')
NFT = '/usr/sbin/nft'

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

def parse_dns_log(log_path, filter_ip=None, limit=300):
    if not log_path.exists():
        return []
    try:
        with log_path.open('r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception:
        return []

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

def load_metadata():
    if METADATA.exists():
        try:
            data = json.loads(METADATA.read_text())
            if isinstance(data, dict) and 'devices' in data:
                return data
        except Exception:
            pass
    return {'devices': {}}

def save_metadata(data):
    temp = METADATA.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2))
    temp.chmod(0o600)
    temp.replace(METADATA)

def apply_rules(blocked, metadata=None):
    if metadata is None:
        metadata = load_metadata()
    devices_meta = metadata.get('devices', {})

    scheduled_blocks = set()
    customer_ips = set()
    speed_limits = {}

    for ip, info in devices_meta.items():
        try:
            vip = valid_ip(ip)
        except ValueError:
            continue
        if is_schedule_active(info.get('schedule', {})):
            scheduled_blocks.add(vip)
        if info.get('group') == 'customer':
            customer_ips.add(vip)
        limit_mbps = info.get('speed_limit', 0)
        if isinstance(limit_mbps, (int, float)) and limit_mbps > 0:
            speed_limits[vip] = int(limit_mbps * 125)

    effective_blocks = set(blocked) | scheduled_blocks

    exists = run([NFT, 'list', 'table', 'inet', 'oshin_dashboard']).returncode == 0
    script = 'delete table inet oshin_dashboard\n' if exists else ''
    script += 'add table inet oshin_dashboard\n'
    script += 'add set inet oshin_dashboard blocked { type ipv4_addr; }\n'
    script += 'add set inet oshin_dashboard customers { type ipv4_addr; }\n'

    # Input chain: Portal lockdown for customers (blocks access to admin port 8090)
    script += 'add chain inet oshin_dashboard input { type filter hook input priority -10; policy accept; }\n'
    script += 'add rule inet oshin_dashboard input iifname "enp1s0" ip saddr @customers tcp dport 8090 counter drop\n'

    # Forward chain: Access blocks, client-to-client guest isolation, and QoS rate-limiting
    script += 'add chain inet oshin_dashboard forward { type filter hook forward priority -10; policy accept; }\n'
    script += 'add rule inet oshin_dashboard forward iifname "enp1s0" ip saddr @blocked counter drop\n'
    script += 'add rule inet oshin_dashboard forward oifname "enp1s0" ip daddr @blocked counter drop\n'

    # Customer client-to-client isolation (customers cannot access other devices on LAN)
    script += 'add rule inet oshin_dashboard forward iifname "enp1s0" oifname "enp1s0" ip saddr @customers counter drop\n'
    script += 'add rule inet oshin_dashboard forward iifname "enp1s0" oifname "enp1s0" ip daddr @customers counter drop\n'

    # Speed limits (rate limiting) per IP
    for ip, rate_kb in sorted(speed_limits.items()):
        burst = max(100, int(rate_kb * 0.2))
        script += f'add rule inet oshin_dashboard forward iifname "enp1s0" ip saddr {ip} limit rate over {rate_kb} kbytes/second burst {burst} kbytes counter drop\n'
        script += f'add rule inet oshin_dashboard forward oifname "enp1s0" ip daddr {ip} limit rate over {rate_kb} kbytes/second burst {burst} kbytes counter drop\n'

    if effective_blocks:
        script += 'add element inet oshin_dashboard blocked { ' + ', '.join(sorted(valid_ip(x) for x in effective_blocks)) + ' }\n'
    if customer_ips:
        script += 'add element inet oshin_dashboard customers { ' + ', '.join(sorted(valid_ip(x) for x in customer_ips)) + ' }\n'

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
    allowed_actions = ('status', 'restore', 'block', 'unblock', 'activity', 'clear_activity', 'set_device', 'apply_schedules')
    if not args or args[0] not in allowed_actions:
        raise ValueError('Invalid action')
    action = args[0]
    if action in ('block', 'unblock'):
        if len(args) != 2:
            raise ValueError('Invalid argument count')
    elif action == 'set_device':
        if len(args) != 3:
            raise ValueError('Invalid argument count')
    elif action == 'activity':
        if len(args) not in (1, 2):
            raise ValueError('Invalid argument count')
    else:
        if len(args) != 1:
            raise ValueError('Invalid argument count')

    if action == 'activity':
        target = valid_ip(args[1]) if len(args) == 2 and args[1] != 'all' else None
        log_path = DNS_LOG if DNS_LOG.exists() else Path('/var/log/dnsmasq.log')
        queries = parse_dns_log(log_path, filter_ip=target, limit=300)
        print(json.dumps({'queries': queries, 'log_exists': log_path.exists()}))
        return

    if action == 'clear_activity':
        if DNS_LOG.exists():
            DNS_LOG.write_text('')
        dnsmasq_fallback = Path('/var/log/dnsmasq.log')
        if dnsmasq_fallback.exists():
            dnsmasq_fallback.write_text('')
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
            'scheduled_active': sorted(active_schedules)
        }))

if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
