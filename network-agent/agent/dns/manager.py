"""DNS activity monitoring and query log parsing module."""
from collections import deque
from ipaddress import IPv4Address
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..simulation.mock_provider import is_simulation_required

logger = logging.getLogger("wifirouter.dns")

QUERY_RE = re.compile(
    r'(?:^(?P<timestamp>[A-Za-z]{3}\s+\d+\s+[\d:]+|\d{4}-\d{2}-\d{2}[T\s][\d:.]+[\w+-]*).*?)?'
    r'query\[(?P<type>[^\]]+)\]\s+(?P<domain>[^\s/]+)\s+from\s+(?P<client>\d+\.\d+\.\d+\.\d+)'
)

LOG_PATHS = [
    Path("/var/log/dnsmasq.log"),
    Path("/var/log/oshin-dns.log"),
    Path("/var/log/syslog")
]

class DnsActivityManager:
    """Parses domain lookup activity from dnsmasq query logs."""

    def __init__(self):
        self.simulated = is_simulation_required()

    def get_recent_queries(self, client_ip: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        """Extract recent DNS queries, optionally filtered by client IP."""
        if self.simulated:
            # Return realistic simulated DNS lookups
            sim_domains = [
                ("youtube.com", "A", "192.168.16.101"),
                ("googlevideo.com", "HTTPS", "192.168.16.101"),
                ("instagram.com", "A", "192.168.16.105"),
                ("graph.instagram.com", "AAAA", "192.168.16.105"),
                ("netflix.com", "HTTPS", "192.168.16.102"),
                ("api.github.com", "A", "192.168.16.103"),
                ("whatsapp.net", "A", "192.168.16.106"),
                ("connectivitycheck.gstatic.com", "A", "192.168.16.105"),
            ]
            results = []
            for dom, qtype, cip in sim_domains:
                if not client_ip or client_ip == cip:
                    results.append({
                        "timestamp": "Today",
                        "client": cip,
                        "domain": dom,
                        "type": qtype,
                        "simulated": True
                    })
            return results[:limit]

        lines: List[str] = []
        for lp in LOG_PATHS:
            if lp.exists():
                try:
                    with lp.open("r", encoding="utf-8", errors="replace") as f:
                        recent = [l for l in f.readlines() if "query[" in l]
                        if recent:
                            lines = recent[-800:]
                            break
                except Exception:
                    pass

        if not lines:
            try:
                res = subprocess.run(
                    ["/usr/bin/journalctl", "-u", "NetworkManager", "-n", "400", "--no-pager"],
                    capture_output=True, text=True, timeout=5
                )
                if res.returncode == 0:
                    lines = [l for l in res.stdout.splitlines() if "query[" in l]
            except Exception:
                pass

        results = []
        for line in reversed(lines):
            m = QUERY_RE.search(line)
            if not m:
                continue
            cip = m.group("client")
            if client_ip and client_ip != cip:
                continue
            results.append({
                "timestamp": m.group("timestamp") or "Recent",
                "client": cip,
                "domain": m.group("domain"),
                "type": m.group("type"),
                "simulated": False
            })
            if len(results) >= limit:
                break

        return results

    def get_device_activity(self, client_ip: str, page: int = 1) -> Dict[str, Any]:
        """Page individual lookups from the retained active log, newest first."""
        client_ip = str(IPv4Address(client_ip))
        if not 1 <= page <= 100000:
            raise ValueError("Page must be between 1 and 100000")
        page_size = 20
        offset = (page - 1) * page_size

        def result(rows, total, available):
            return {"queries": rows, "total": total, "page": page,
                    "page_size": page_size, "has_more": offset + page_size < total,
                    "log_available": available, "simulated": self.simulated}

        if self.simulated:
            rows = self.get_recent_queries(client_ip)
            return result(rows[offset:offset + page_size], len(rows), True)

        def collect(lines):
            # Do not truncate globally before filtering: quiet devices can have
            # requests older than the latest 800 lookups from busy devices.
            recent = deque(maxlen=offset + page_size)
            total = 0
            for line in lines:
                match = QUERY_RE.search(line)
                if not match or match.group("client") != client_ip:
                    continue
                total += 1
                recent.append({"timestamp": match.group("timestamp") or "Recent",
                               "client": client_ip, "domain": match.group("domain"),
                               "type": match.group("type"), "simulated": False})
            rows = list(reversed(recent))
            return result(rows[offset:offset + page_size], total, True)

        for path in LOG_PATHS:
            if path.exists():
                with path.open("r", encoding="utf-8", errors="replace") as stream:
                    data = collect(stream)
                if data["total"]:
                    return data
        # Journal fallback is limited to retained NetworkManager journal entries.
        proc = subprocess.run(
            ["/usr/bin/journalctl", "-u", "NetworkManager", "--no-pager", "-o", "short-iso"],
            capture_output=True, text=True, timeout=10)
        if proc.returncode:
            if any(path.exists() for path in LOG_PATHS):
                return result([], 0, True)
            raise RuntimeError("DNS logs are unavailable. Check dnsmasq query logging on Ubuntu.")
        data = collect(proc.stdout.splitlines())
        data["log_available"] = any(path.exists() for path in LOG_PATHS) or bool(data["total"])
        return data

    def clear_logs(self) -> Dict[str, Any]:
        """Truncate active query log file."""
        if self.simulated:
            return {"ok": True, "simulated": True}

        cleared = False
        for lp in LOG_PATHS:
            if lp.exists():
                try:
                    lp.write_text("", encoding="utf-8")
                    cleared = True
                except Exception:
                    pass
        return {"ok": cleared, "simulated": False}

