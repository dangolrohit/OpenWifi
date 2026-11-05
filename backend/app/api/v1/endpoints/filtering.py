"""Firewall filtering, blocklist, and allowlist endpoints."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ....db.session import get_db
from ....integrations.agent_client import agent_client
from ....services.device_service import DeviceService
from ...dependencies.auth import get_current_user
from ....models.user import User

router = APIRouter(prefix="/filtering", tags=["Device Filtering"])

@router.get("/status")
async def get_filtering_status(
    user: User = Depends(get_current_user)
):
    """Retrieve active nftables sets, blocked IPs, and customer isolation rules."""
    return await agent_client.get_firewall_status()

@router.post("/block")
async def block_ip(
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Block a client IP address."""
    ip = payload.get("ip")
    if not ip:
        return {"error": "Missing IP"}
    await DeviceService.set_block(db, ip, True, actor=user.username)
    return {"ok": True, "ip": ip, "blocked": True}

@router.post("/unblock")
async def unblock_ip(
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Unblock a client IP address."""
    ip = payload.get("ip")
    if not ip:
        return {"error": "Missing IP"}
    await DeviceService.set_block(db, ip, False, actor=user.username)
    return {"ok": True, "ip": ip, "blocked": False}

