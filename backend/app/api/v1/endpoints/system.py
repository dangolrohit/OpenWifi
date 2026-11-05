"""System health supervisor, resource telemetry, and service monitor endpoints."""
from fastapi import APIRouter, Depends
from ....integrations.agent_client import agent_client
from ...dependencies.auth import get_current_user
from ....models.user import User

router = APIRouter(prefix="/system", tags=["System Monitoring"])

@router.get("/health")
async def get_system_health(user: User = Depends(get_current_user)):
    """Inspect CPU, RAM, disk usage, uptime, and service status (Docker, Cloudflare Tunnel, etc.)."""
    return await agent_client.get_system_health()

