"""Hotspot plans, vouchers, and guest captive session endpoints."""
from typing import List
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ....db.session import get_db
from ....schemas.guest import (
    PlanSchema, VoucherCreateRequest, VoucherResponse,
    GuestSessionResponse, GuestConnectRequest
)
from ....services.guest_service import GuestService
from ...dependencies.auth import get_current_user
from ....models.user import User

router = APIRouter(prefix="/guests", tags=["Guest Management"])

@router.get("/plans", response_model=List[PlanSchema])
async def list_plans(db: AsyncSession = Depends(get_db)):
    """List all 5 hotspot access plans."""
    plans = await GuestService.get_plans(db)
    return [PlanSchema.model_validate(p) for p in plans]

@router.put("/plans", response_model=List[PlanSchema])
async def update_plans(
    plans_data: List[dict],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Update hotspot access plan parameters (duration, speed limits, descriptions)."""
    updated = await GuestService.update_plans(db, plans_data, actor=user.username)
    return [PlanSchema.model_validate(p) for p in updated]

@router.get("/vouchers", response_model=List[VoucherResponse])
async def list_vouchers(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List all generated access vouchers."""
    vouchers = await GuestService.list_vouchers(db)
    return [VoucherResponse.model_validate(v) for v in vouchers]

@router.post("/vouchers", response_model=VoucherResponse)
async def create_voucher(
    req: VoucherCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Generate a new 6-digit access voucher PIN."""
    v = await GuestService.create_voucher(db, req.plan_id, req.code, actor=user.username)
    return VoucherResponse.model_validate(v)

@router.delete("/vouchers/{code}")
async def delete_voucher(
    code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Delete an unused voucher code."""
    await GuestService.delete_voucher(db, code, actor=user.username)
    return {"ok": True, "message": "Voucher deleted"}

@router.get("/sessions", response_model=List[GuestSessionResponse])
async def list_active_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List active guest sessions with live countdowns and assigned plans."""
    sessions = await GuestService.list_active_sessions(db)
    return [GuestSessionResponse.model_validate(s) for s in sessions]

@router.post("/sessions/extend")
async def extend_guest_session(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Extend an active guest session by +X minutes."""
    ip = payload.get("ip")
    minutes = int(payload.get("minutes", 30))
    session = await GuestService.extend_session(db, ip, minutes, actor=user.username)
    return {"ok": True, "session": GuestSessionResponse.model_validate(session)}

@router.post("/sessions/revoke")
async def revoke_guest_session(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Immediately disconnect a guest session."""
    ip = payload.get("ip")
    await GuestService.revoke_session(db, ip, actor=user.username)
    return {"ok": True, "message": f"Session for {ip} revoked"}

# --- Public Endpoints for Captive Portal ---

@router.get("/status")
async def get_guest_status(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Public endpoint: returns whether the requesting client IP is authorized."""
    client_ip = request.client.host if request.client else "unknown"
    sessions = await GuestService.list_active_sessions(db)
    active_session = next((s for s in sessions if s.ip == client_ip), None)
    plans = await GuestService.get_plans(db)

    return {
        "ip": client_ip,
        "authorized": bool(active_session),
        "session": GuestSessionResponse.model_validate(active_session) if active_session else None,
        "plans": [PlanSchema.model_validate(p) for p in plans if p.is_active]
    }

@router.post("/connect")
async def guest_connect(
    req: GuestConnectRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Public endpoint: authorize client IP via Starter agreement or voucher code."""
    client_ip = request.client.host if request.client else "192.168.16.105"
    session = await GuestService.authorize_guest(db, client_ip, req.plan_id, req.voucher)
    return {
        "ok": True,
        "session": GuestSessionResponse.model_validate(session)
    }

