"""Audit logs and DNS activity monitoring endpoints."""
from ipaddress import IPv4Address
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ....db.session import get_db
from ....integrations.agent_client import agent_client, AgentUnavailableError
from ....schemas.network import AuditLogItem
from ....services.audit_service import AuditService
from ...dependencies.auth import get_current_user
from ....models.user import User

router = APIRouter(prefix="/logs", tags=["Logs & Audit"])

@router.get("/audit", response_model=List[AuditLogItem])
async def list_audit_logs(
    limit: int = 100,
    event_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List system security and administrative audit events."""
    logs = await AuditService.get_logs(db, limit, event_type)
    return [AuditLogItem.model_validate(l) for l in logs]

@router.get("/dns")
async def get_dns_activity(
    client: Optional[str] = None,
    limit: int = 200,
    user: User = Depends(get_current_user)
):
    """Query recent website and domain lookups observed by gateway DNS."""
    queries = await agent_client.get_dns_activity(client, limit)
    return {"queries": queries}

@router.get("/dns/device-activity")
async def get_device_activity(
    client: IPv4Address,
    page: int = Query(1, ge=1, le=100000),
    user: User = Depends(get_current_user)
):
    """Individual DNS lookups for a device IP, 20 per page."""
    try:
        return await agent_client.get_device_activity(str(client), page)
    except AgentUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/dns/clear")
async def clear_dns_activity(user: User = Depends(get_current_user)):
    """Clear gateway DNS activity logs."""
    return await agent_client.clear_dns_activity()

