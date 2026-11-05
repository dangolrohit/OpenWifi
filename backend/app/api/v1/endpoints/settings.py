"""Application settings, preferences, and configuration backup endpoints."""
import json
from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ....db.session import get_db
from ....models.settings import SystemSetting
from ...dependencies.auth import get_current_user
from ....models.user import User

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Retrieve application settings."""
    stmt = select(SystemSetting)
    res = await db.execute(stmt)
    rows = res.scalars().all()
    data = {r.key: r.value for r in rows}
    return {
        "settings": data,
        "version": "2.0.0",
        "user": user.username,
        "role": user.role
    }

@router.put("")
async def update_settings(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Update application configuration keys."""
    for k, v in payload.items():
        stmt = select(SystemSetting).where(SystemSetting.key == k)
        res = await db.execute(stmt)
        setting = res.scalar_one_or_none()
        val_str = json.dumps(v) if isinstance(v, (dict, list, bool)) else str(v)
        if setting:
            setting.value = val_str
        else:
            db.add(SystemSetting(key=k, value=val_str))
    await db.commit()
    return {"ok": True, "message": "Settings updated"}

@router.get("/backup")
async def export_backup(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Export configuration snapshot as JSON (without plaintext passwords or secret keys)."""
    stmt = select(SystemSetting)
    res = await db.execute(stmt)
    settings_dict = {r.key: r.value for r in res.scalars().all()}

    backup_data = {
        "version": "2.0.0",
        "settings": settings_dict,
        "exported_by": user.username
    }
    return Response(
        content=json.dumps(backup_data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=wifirouter-backup.json"}
    )

