"""Dashboard telemetry and overview endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ....db.session import get_db
from ....integrations.agent_client import agent_client
from ....services.device_service import DeviceService
from ....services.guest_service import GuestService
from ...dependencies.auth import get_current_user
from ....models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Fetch high-level overview metrics, bandwidth, active devices, and system health."""
    agent_summary = await agent_client.get_summary()
    devices = await DeviceService.get_all_devices(db)
    active_guests = await GuestService.list_active_sessions(db)

    family_count = sum(1 for d in devices if d.group == "family")
    customer_count = sum(1 for d in devices if d.group == "customer")
    blocked_count = sum(1 for d in devices if d.is_blocked)

    return {
        "bandwidth": agent_summary.get("bandwidth", {}),
        "wifi": agent_summary.get("wifi", {}),
        "health": agent_summary.get("health", {}),
        "devices": {
            "total": len(devices),
            "family": family_count,
            "customer": customer_count,
            "blocked": blocked_count,
            "active_guests": len(active_guests)
        },
        "timestamp": agent_summary.get("timestamp")
    }

