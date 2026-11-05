"""Rollback and snapshot management for network configurations."""
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("wifirouter.rollback")

DEFAULT_SNAPSHOT_DIR = Path(os.environ.get("WIFIROUTER_SNAPSHOT_DIR", "/var/lib/wifirouter/snapshots"))

class RollbackManager:
    """Manages transactional snapshots of firewall, QoS, and routing states."""

    def __init__(self, snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR):
        self.snapshot_dir = snapshot_dir
        self.history: List[Dict[str, Any]] = []
        try:
            self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def create_snapshot(self, category: str, state_data: Dict[str, Any], label: str = "") -> str:
        """Create a timestamped snapshot of a state configuration."""
        snapshot_id = f"{category}_{int(time.time() * 1000)}"
        entry = {
            "id": snapshot_id,
            "category": category,
            "label": label or f"Snapshot of {category}",
            "timestamp": time.time(),
            "data": state_data
        }
        self.history.append(entry)
        if len(self.history) > 30:
            self.history.pop(0)

        snapshot_file = self.snapshot_dir / f"{snapshot_id}.json"
        try:
            snapshot_file.write_text(json.dumps(entry, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"Could not write snapshot to disk: {exc}")

        return snapshot_id

    def get_latest_snapshot(self, category: str) -> Optional[Dict[str, Any]]:
        """Retrieve the most recent snapshot for a category."""
        for entry in reversed(self.history):
            if entry.get("category") == category:
                return entry.get("data")
        return None

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all recent snapshots metadata."""
        return [
            {
                "id": e["id"],
                "category": e["category"],
                "label": e["label"],
                "timestamp": e["timestamp"]
            }
            for e in reversed(self.history)
        ]

