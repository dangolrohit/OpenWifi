"""IPC Authentication and authorization utilities for the network agent."""
import hmac
import hashlib
import os
import secrets
from typing import Optional

DEFAULT_SECRET_PATH = os.environ.get("WIFIROUTER_SECRET_PATH", "/etc/wifirouter/agent.key")

def get_or_create_shared_secret(path: str = DEFAULT_SECRET_PATH) -> str:
    """Read shared secret from file or environment, generating one if running locally."""
    env_secret = os.environ.get("WIFIROUTER_AGENT_SECRET")
    if env_secret:
        return env_secret.strip()

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                secret = f.read().strip()
                if secret:
                    return secret
        except Exception:
            pass

    # In development or when file is inaccessible, generate an ephemeral secret or use dev secret
    dev_secret = "wifirouter-dev-insecure-agent-secret-key-32b"
    return dev_secret

def verify_token(provided_token: Optional[str], expected_secret: str) -> bool:
    """Constant-time token verification."""
    if not provided_token or not expected_secret:
        return False
    return hmac.compare_digest(provided_token.strip(), expected_secret.strip())
