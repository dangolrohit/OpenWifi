"""Network input validation and safety checks."""
import ipaddress
import re
from typing import Optional, Set

INTERFACE_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-\.]{2,16}$")
MAC_ADDRESS_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")
TIME_HHMM_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")

# Sensitive ports and subnets that must never be blocked on the host
PROTECTED_PORTS = {22, 53, 67, 68, 8088, 8090, 8091, 51820}  # SSH, DNS, DHCP, Captive, Admin, Agent, Wireguard/Tailscale

class NetworkValidationError(ValueError):
    """Raised when a network parameter fails safety validation."""
    pass

def validate_ipv4(ip_str: str, subnet: Optional[str] = None) -> str:
    """Validate that ip_str is a valid IPv4 address, optionally within a subnet."""
    try:
        ip = ipaddress.IPv4Address(ip_str.strip())
    except (ValueError, AttributeError) as exc:
        raise NetworkValidationError(f"Invalid IPv4 address: {ip_str}") from exc

    if ip.is_loopback or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        raise NetworkValidationError(f"Reserved or loopback IP not allowed: {ip_str}")

    if subnet:
        try:
            net = ipaddress.IPv4Network(subnet, strict=False)
            if ip not in net:
                raise NetworkValidationError(f"IP {ip_str} is outside permitted subnet {subnet}")
            if ip == net.network_address or ip == net.broadcast_address:
                raise NetworkValidationError(f"Network or broadcast address not allowed: {ip_str}")
        except ValueError as exc:
            raise NetworkValidationError(f"Invalid subnet restriction: {subnet}") from exc

    return str(ip)

def validate_mac(mac_str: str) -> str:
    """Validate a standard 6-byte MAC address."""
    clean = mac_str.strip().lower()
    if not MAC_ADDRESS_RE.match(clean):
        raise NetworkValidationError(f"Invalid MAC address: {mac_str}")
    return clean

def validate_interface_name(iface: str) -> str:
    """Validate Linux network interface name."""
    clean = iface.strip()
    if not INTERFACE_NAME_RE.match(clean):
        raise NetworkValidationError(f"Invalid network interface name: {iface}")
    return clean

def validate_speed_limit(mbps: int) -> int:
    """Validate speed limit in Mbps (0 = unlimited, up to 10,000 Mbps)."""
    if not isinstance(mbps, int) or mbps < 0 or mbps > 10000:
        raise NetworkValidationError("Speed limit must be an integer between 0 and 10000 Mbps")
    return mbps

def validate_time_hhmm(time_str: str) -> str:
    """Validate a 24-hour time string in HH:MM format."""
    clean = time_str.strip()
    if not TIME_HHMM_RE.match(clean):
        raise NetworkValidationError(f"Invalid time format (expected HH:MM): {time_str}")
    return clean

def check_host_protection(ip_str: str, host_ips: Set[str]) -> None:
    """Ensure that the host's own IP addresses are never targeted for blocking or isolation."""
    ip = validate_ipv4(ip_str)
    if ip in host_ips or ip in {"127.0.0.1", "192.168.16.2", "192.168.16.1"}:
        raise NetworkValidationError(f"Cannot apply block policy to host or gateway IP: {ip}")
