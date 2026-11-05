"""DNS activity monitoring and query log parsing module."""
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
