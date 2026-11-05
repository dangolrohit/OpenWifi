"""Device management endpoints."""
from typing import List
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ....db.session import get_db
from ....schemas.device import DeviceResponse, DeviceUpdateRequest, DeviceBlockRequest
from ....services.device_service import DeviceService
from ...dependencies.auth import get_current_user
from ....models.user import User

router = APIRouter(prefix="/devices", tags=["Connected Devices"])

@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List all discovered devices with assigned nicknames, groups, and policies."""
    devices = await DeviceService.get_all_devices(db)
    return [DeviceResponse.model_validate(d) for d in devices]

@router.put("/{ip}", response_model=DeviceResponse)
async def update_device_settings(
    ip: str,
    req: DeviceUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Update device nickname, group (Family/Customer/Staff), speed limit, or schedule."""
    updates = req.model_dump(exclude_unset=True)
    dev = await DeviceService.update_device(db, ip, updates, actor=user.username)
    return DeviceResponse.model_validate(dev)

@router.post("/{ip}/block", response_model=DeviceResponse)
async def block_device(
    ip: str,
    req: DeviceBlockRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Block or unblock device internet access."""
    dev = await DeviceService.set_block(db, ip, req.blocked, actor=user.username)
    return DeviceResponse.model_validate(dev)

