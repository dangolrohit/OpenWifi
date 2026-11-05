"""Bandwidth QoS and traffic control endpoints."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ....db.session import get_db
from ....integrations.agent_client import agent_client
from ....services.device_service import DeviceService
from ...dependencies.auth import get_current_user
from ....models.user import User

router = APIRouter(prefix="/bandwidth", tags=["Bandwidth Control"])

@router.get("/live")
async def get_live_bandwidth(user: User = Depends(get_current_user)):
    """Fetch current real-time upload and download throughput rates."""
    return await agent_client.get_bandwidth()

@router.post("/shape")
async def apply_bandwidth_shaping(
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Apply Linux Traffic Control or nftables rate limiting to an IP."""
    ip = payload.get("ip")
    speed_mbps = int(payload.get("speed_limit_mbps", 0))
    if not ip:
        return {"error": "Missing IP"}

    await DeviceService.update_device(db, ip, {"speed_limit_mbps": speed_mbps}, actor=user.username)
    res = await agent_client.set_speed_limit(ip, speed_mbps)
    return res

