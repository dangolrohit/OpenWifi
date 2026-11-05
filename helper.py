#!/usr/bin/python3 -I
"""Narrow root helper: manages inet oshin_dashboard and parses DNS query activity."""
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

def apply_rules(blocked):
    exists = run([NFT, 'list', 'table', 'inet', 'oshin_dashboard']).returncode == 0
    script = 'delete table inet oshin_dashboard\n' if exists else ''
    script += 'add table inet oshin_dashboard\n'
    script += 'add set inet oshin_dashboard blocked { type ipv4_addr; }\n'
    script += 'add chain inet oshin_dashboard forward { type filter hook forward priority -10; policy accept; }\n'
    script += 'add rule inet oshin_dashboard forward iifname "enp1s0" ip saddr @blocked counter drop\n'
    script += 'add rule inet oshin_dashboard forward oifname "enp1s0" ip daddr @blocked counter drop\n'
    if blocked:
        script += 'add element inet oshin_dashboard blocked { ' + ', '.join(sorted(valid_ip(x) for x in blocked)) + ' }\n'
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
    allowed_actions = ('status', 'restore', 'block', 'unblock', 'activity', 'clear_activity')
    if not args or args[0] not in allowed_actions:
        raise ValueError('Invalid action')
    action = args[0]
    if action in ('block', 'unblock'):
        if len(args) != 2:
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

    target = valid_ip(args[1]) if len(args) == 2 else None
    with (STATE.parent / 'lock').open('a') as lock:
        if fcntl:
            fcntl.flock(lock, fcntl.LOCK_EX)
        blocked = set(json.loads(STATE.read_text())) if STATE.exists() else set()
        blocked = {valid_ip(x) for x in blocked}
        if action == 'status':
            active = run([NFT, '-j', 'list', 'set', 'inet', 'oshin_dashboard', 'blocked'])
            if active.returncode:
                raise RuntimeError('Dashboard firewall is missing; run sudo systemctl restart oshin-firewall')
            actual = set()
            for item in json.loads(active.stdout)['nftables']:
                if 'set' in item:
                    actual.update(item['set'].get('elem', []))
            if actual != blocked:
                raise RuntimeError('Saved and live rules differ; restart oshin-firewall')
        else:
            old = blocked.copy()
            if action == 'block': blocked.add(target)
            if action == 'unblock': blocked.discard(target)
            apply_rules(blocked)
            try:
                save(blocked)
            except Exception:
                apply_rules(old)
                raise
        print(json.dumps({'blocked': sorted(blocked)}))

if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
