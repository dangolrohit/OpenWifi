"""Audit logging query and filter service."""
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.audit import AuditLog

class AuditService:
    """Manages system security audit logs and event queries."""

    @staticmethod
    async def get_logs(db: AsyncSession, limit: int = 100, event_type: Optional[str] = None) -> List[AuditLog]:
        """Fetch audit log records with optional event filtering."""
        stmt = select(AuditLog)
        if event_type:
            stmt = stmt.where(AuditLog.event_type == event_type)
        stmt = stmt.order_by(AuditLog.recorded_at.desc()).limit(limit)

        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def log_event(
        db: AsyncSession,
        event_type: str,
        actor: str = "system",
        ip_address: str = "",
        description: str = "",
        severity: str = "info"
    ) -> AuditLog:
        """Create a persistent audit log entry."""
        entry = AuditLog(
            event_type=event_type,
            actor=actor,
            ip_address=ip_address,
            description=description,
            severity=severity
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry

