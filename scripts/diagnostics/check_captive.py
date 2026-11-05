#!/usr/bin/env python3
"""Read-only Ubuntu captive detection checks. Does not print configuration secrets."""
import argparse
import json
import shutil
import socket
import struct
import subprocess
import sys
from http.client import HTTPConnection


def command(title, args):
    print('\n' + title, flush=True)
    if not shutil.which(args[0]):
        print('Unavailable:', args[0])
        return
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=15)
        print((result.stdout + result.stderr).strip() or '(no output)')
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(type(exc).__name__, str(exc))


def check_dns(gateway):
    print('\nDNS connectivity-check lookup through gateway', flush=True)
    name = 'connectivitycheck.gstatic.com'
    question = b''.join(bytes([len(label)]) + label.encode() for label in name.split('.')) + b'\0'
    packet = struct.pack('!6H', 12345, 0x100, 1, 0, 0, 0) + question + struct.pack('!HH', 1, 1)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
            connection.settimeout(3)
            connection.sendto(packet, (gateway, 53))
            response, _ = connection.recvfrom(4096)
        identifier, flags, questions, answers, _, _ = struct.unpack('!6H', response[:12])
        ok = identifier == 12345 and flags & 0x8000 and flags & 15 == 0 and answers > 0
        print(f'{"PASS" if ok else "FAIL"}: {name}, DNS response code={flags & 15}, answers={answers}')
    except (OSError, struct.error) as exc:
        print('FAIL:', str(exc), '- check shared dnsmasq listening on gateway port 53')


def check_portal(gateway):
    print('\nPortal reachability and unauthenticated probe response', flush=True)
    for path in ('/health', '/guest', '/generate_204'):
        connection = HTTPConnection(gateway, 8088, timeout=5)
        try:
            connection.request('GET', path)
            response = connection.getresponse()
            response.read()
            print(path, 'HTTP', response.status, 'Location:', response.getheader('Location', '-'))
        except OSError as exc:
            print(path, 'FAIL:', str(exc))
        finally:
            connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gateway', default='192.168.16.2')
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        raise SystemExit('Run this diagnostic on the Ubuntu gateway, not Windows.')
    command('IPv4 addresses (confirm the downstream interface)', ['ip', '-br', '-4', 'addr'])
    command('Default route', ['ip', '-4', 'route', 'show', 'default'])
    command('Active network profiles', ['nmcli', '-t', '-f', 'NAME,DEVICE', 'connection', 'show', '--active'])
    command('DNS and portal listeners', ['ss', '-lntu', '( sport = :53 or sport = :8088 )'])
    command('HTTP/DNS redirect counters', ['nft', 'list', 'chain', 'inet', 'wifirouter', 'prerouting'])
    command('Portal exemptions (these clients will not be redirected)', ['nft', 'list', 'set', 'inet', 'wifirouter', 'whitelisted'])
    command('Active authorized clients', ['nft', 'list', 'set', 'inet', 'wifirouter', 'authenticated'])
    check_dns(args.gateway)
    check_portal(args.gateway)
    print('\nThese host checks do not prove guest-side redirection. On a NEW guest device, open')
    print('http://www.msftconnecttest.com/connecttest.txt - it should redirect to the login page.')
    print('If it does not, rerun this diagnostic and compare the redirect counters.')


if __name__ == '__main__':
    main()
