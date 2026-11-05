#!/usr/bin/python3 -I
"""Narrow root helper: manages only inet oshin_dashboard, never other rules."""
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys

STATE = Path('/var/lib/oshin-firewall/blocked.json')
NFT = '/usr/sbin/nft'

def valid_ip(value):
    ip = ipaddress.IPv4Address(value)
    if ip not in ipaddress.IPv4Network('192.168.16.0/24') or int(ip) % 256 in (0, 1, 2, 255):
        raise ValueError('Only client addresses 192.168.16.3–254 are allowed')
    return str(ip)

def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, timeout=10, **kwargs)

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
    if not args or args[0] not in ('status', 'restore', 'block', 'unblock'):
        raise ValueError('Invalid action')
    action = args[0]
    if len(args) != (2 if action in ('block', 'unblock') else 1):
        raise ValueError('Invalid argument count')
    target = valid_ip(args[1]) if len(args) == 2 else None
    with (STATE.parent / 'lock').open('a') as lock:
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
