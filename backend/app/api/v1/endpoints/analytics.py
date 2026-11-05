"""Network usage analytics and CSV telemetry export endpoints."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from ....db.session import get_db
from ....services.analytics_service import AnalyticsService
from ...dependencies.auth import get_current_user
from ....models.user import User

router = APIRouter(prefix="/analytics", tags=["Usage Analytics"])

@router.get("/traffic")
async def get_traffic_analytics(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Retrieve historical bandwidth throughput samples for charts."""
    history = await AnalyticsService.get_traffic_history(db, hours)
    return {"history": history}

@router.get("/export")
async def export_traffic_csv(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Download historical bandwidth measurements as a CSV file."""
    csv_data = await AnalyticsService.export_csv(db, days)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=wifirouter-traffic.csv"}
    )

