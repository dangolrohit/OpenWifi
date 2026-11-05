"""Hotspot plan management, voucher lifecycle, and guest session tracking."""
import re
from ipaddress import IPv4Address, IPv4Network
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.security import generate_voucher_code
from ..core.exceptions import ValidationError, ResourceNotFoundError
from ..models.guest import HotspotPlan, Voucher, GuestSession
from ..models.audit import AuditLog
from ..integrations.agent_client import agent_client

DEFAULT_PLANS = [
    {
        "plan_id": "starter",
        "name": "Starter Plan (Free)",
        "type": "click",
        "duration_minutes": 30,
        "speed_limit_mbps": 1,
        "is_active": True,
        "description": "Free 30 minutes light web access with agreement"
    },
    {
        "plan_id": "standard",
        "name": "Standard 2-Hour",
        "type": "voucher",
        "duration_minutes": 120,
        "speed_limit_mbps": 5,
        "is_active": True,
        "description": "Standard 2-hour high-speed access via voucher code"
    },
    {
        "plan_id": "half_day",
        "name": "Half-Day Pass",
        "type": "voucher",
        "duration_minutes": 360,
        "speed_limit_mbps": 10,
        "is_active": True,
        "description": "6 hours of fast streaming and browsing access"
    },
    {
        "plan_id": "full_day",
        "name": "Full-Day Pass",
        "type": "voucher",
        "duration_minutes": 1440,
        "speed_limit_mbps": 15,
        "is_active": True,
        "description": "24 hours unlimited access for customers and guests"
    },
    {
        "plan_id": "vip",
        "name": "VIP Premium",
        "type": "voucher",
        "duration_minutes": 4320,
        "speed_limit_mbps": 25,
        "is_active": True,
        "description": "3-day unrestricted high-bandwidth VIP access"
    }
]

class GuestService:
    """Orchestrates hotspot plans, vouchers, and guest authorizations."""

    @staticmethod
    async def get_plans(db: AsyncSession) -> List[HotspotPlan]:
        """Fetch all plans, seeding defaults if table is empty."""
        stmt = select(HotspotPlan).order_by(HotspotPlan.id.asc())
        res = await db.execute(stmt)
        plans = list(res.scalars().all())

        if not plans:
            for p_def in DEFAULT_PLANS:
                p = HotspotPlan(**p_def)
                db.add(p)
            await db.commit()
            res = await db.execute(stmt)
            plans = list(res.scalars().all())

        # The free tier is a fixed product rule, including existing installations.
        starter = next((p for p in plans if p.plan_id == "starter"), None)
        if starter and (starter.duration_minutes != 30 or starter.speed_limit_mbps != 1 or starter.type != "click"):
            starter.duration_minutes = 30
            starter.speed_limit_mbps = 1
            starter.type = "click"
            await db.commit()
        return plans

    @staticmethod
    async def update_plans(db: AsyncSession, updated_plans: List[Dict[str, Any]], actor: str = "admin") -> List[HotspotPlan]:
        """Update configurations for all 5 plans."""
        for p_data in updated_plans:
            pid = p_data.get("plan_id")
            if not pid:
                continue
            stmt = select(HotspotPlan).where(HotspotPlan.plan_id == pid)
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()

            if existing:
                if "duration_minutes" in p_data and not 1 <= int(p_data["duration_minutes"]) <= 43200:
                    raise ValidationError("Plan duration must be 1 to 43200 minutes")
                if "speed_limit_mbps" in p_data and not 1 <= int(p_data["speed_limit_mbps"]) <= 10000:
                    raise ValidationError("Plan speed must be 1 to 10000 Mbps")
                if "name" in p_data: existing.name = p_data["name"]
                if "duration_minutes" in p_data: existing.duration_minutes = int(p_data["duration_minutes"])
                if "speed_limit_mbps" in p_data: existing.speed_limit_mbps = int(p_data["speed_limit_mbps"])
                if "is_active" in p_data: existing.is_active = bool(p_data["is_active"])
                if "description" in p_data: existing.description = p_data["description"]

        audit = AuditLog(
            event_type="PLANS_UPDATED",
            actor=actor,
            description="Hotspot access plans updated by administrator",
            severity="info"
        )
        db.add(audit)
        await db.commit()
        return await GuestService.get_plans(db)

    @staticmethod
    async def create_voucher(db: AsyncSession, plan_id: str, custom_code: Optional[str] = None, actor: str = "admin") -> Voucher:
        """Generate a new voucher PIN."""
        plans = {p.plan_id: p for p in await GuestService.get_plans(db)}
        plan = plans.get(plan_id)
        if not plan or not plan.is_active or plan.type != "voucher":
            raise ValidationError("Choose an active voucher plan")
        code = custom_code.strip() if custom_code else generate_voucher_code(6)
        if not re.fullmatch(r"[0-9]{6}", code):
            raise ValidationError("Access code must contain exactly six digits")

        stmt = select(Voucher).where(Voucher.code == code)
        res = await db.execute(stmt)
        if res.scalar_one_or_none():
            raise ValidationError(f"Voucher code '{code}' already exists")

        voucher = Voucher(
            code=code,
            plan_id=plan_id,
            is_used=False
        )
        db.add(voucher)

        audit = AuditLog(
            event_type="VOUCHER_CREATED",
            actor=actor,
            description=f"Created voucher code '{code}' for plan '{plan_id}'",
            severity="info"
        )
        db.add(audit)
        await db.commit()
        await db.refresh(voucher)
        return voucher

    @staticmethod
    async def list_vouchers(db: AsyncSession) -> List[Voucher]:
        """List all active and recent vouchers."""
        stmt = select(Voucher).order_by(Voucher.created_at.desc())
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def delete_voucher(db: AsyncSession, code: str, actor: str = "admin") -> None:
        """Delete an unused voucher."""
        stmt = select(Voucher).where(Voucher.code == code)
        res = await db.execute(stmt)
        v = res.scalar_one_or_none()
        if not v:
            raise ResourceNotFoundError("Voucher not found")

        await db.delete(v)
        audit = AuditLog(
            event_type="VOUCHER_DELETED",
            actor=actor,
            description=f"Deleted voucher code '{code}'",
            severity="info"
        )
        db.add(audit)
        await db.commit()

    @staticmethod
    async def authorize_guest(db: AsyncSession, client_ip: str, plan_id: Optional[str] = None, voucher_code: Optional[str] = None) -> GuestSession:
        """Authorize a guest via Starter click agreement or voucher redemption."""
        try:
            address = IPv4Address(client_ip)
            if address not in IPv4Network("192.168.16.0/24") or address.packed[-1] in (0, 1, 2, 255):
                raise ValueError()
        except ValueError:
            raise ValidationError("Connect to the guest Wi-Fi network before requesting access")
        plans = {p.plan_id: p for p in await GuestService.get_plans(db)}
        chosen_plan = None
        voucher = None

        if voucher_code:
            v_code = voucher_code.strip()
            if not re.fullmatch(r"[0-9]{6}", v_code):
                raise ValidationError("Access code must contain exactly six digits")
            stmt = select(Voucher).where(Voucher.code == v_code).with_for_update()
            res = await db.execute(stmt)
            voucher = res.scalar_one_or_none()

            if not voucher or voucher.is_used:
                raise ValidationError("Invalid or already used voucher code")

            chosen_plan = plans.get(voucher.plan_id)
            if not chosen_plan or not chosen_plan.is_active:
                raise ValidationError("Voucher's associated plan is not available")

            # Claim atomically so simultaneous redemptions cannot both succeed.
            claimed = await db.execute(update(Voucher).where(
                Voucher.id == voucher.id, Voucher.is_used == False
            ).values(is_used=True, used_by_ip=client_ip, used_at=datetime.now(timezone.utc)))
            if claimed.rowcount != 1:
                raise ValidationError("Invalid or already used voucher code")
        elif plan_id:
            chosen_plan = plans.get(plan_id)
            if not chosen_plan or not chosen_plan.is_active:
                raise ValidationError("Selected plan is not available")
            if chosen_plan.plan_id != "starter" or chosen_plan.type != "click":
                raise ValidationError("This plan requires an access voucher PIN")
            # Serialize free activations per plan in PostgreSQL before checking history.
            await db.execute(select(HotspotPlan).where(HotspotPlan.plan_id == "starter").with_for_update())
            previous = (await db.execute(select(GuestSession).where(
                GuestSession.ip == client_ip, GuestSession.plan_id == "starter"
            ).order_by(GuestSession.id.desc()).limit(1))).scalar_one_or_none()
            if previous:
                expiry = previous.expires_at.replace(tzinfo=timezone.utc) if previous.expires_at.tzinfo is None else previous.expires_at
                if previous.is_active and expiry > datetime.now(timezone.utc):
                    return previous
                raise ValidationError("Your free session has ended. Enter an access code to continue.")
        else:
            raise ValidationError("Please choose a plan or enter an access voucher")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=chosen_plan.duration_minutes)

        # Notify network agent
        await agent_client.authorize_guest(
            client_ip,
            chosen_plan.plan_id,
            chosen_plan.duration_minutes,
            chosen_plan.speed_limit_mbps
        )

        await db.execute(update(GuestSession).where(GuestSession.ip == client_ip).values(is_active=False))
        session = GuestSession(
            ip=client_ip,
            plan_id=chosen_plan.plan_id,
            voucher_code=voucher_code.strip() if voucher_code else None,
            speed_limit_mbps=chosen_plan.speed_limit_mbps,
            authorized_at=now,
            expires_at=expires_at,
            is_active=True
        )
        db.add(session)

        audit = AuditLog(
            event_type="GUEST_CONNECTED",
            actor=client_ip,
            ip_address=client_ip,
            description=f"Guest connected via '{chosen_plan.name}' ({chosen_plan.duration_minutes}m, {chosen_plan.speed_limit_mbps} Mbps)",
            severity="info"
        )
        db.add(audit)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def list_active_sessions(db: AsyncSession) -> List[GuestSession]:
        """Fetch all active guest sessions with expiry status."""
        now = datetime.now(timezone.utc)
        stmt = select(GuestSession).where(GuestSession.is_active == True, GuestSession.expires_at > now).order_by(GuestSession.expires_at.asc())
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def extend_session(db: AsyncSession, ip: str, additional_minutes: int = 30, actor: str = "admin") -> GuestSession:
        """Add more time to an active guest session."""
        now = datetime.now(timezone.utc)
        stmt = select(GuestSession).where(GuestSession.ip == ip, GuestSession.is_active == True).order_by(GuestSession.id.desc()).limit(1)
        res = await db.execute(stmt)
        session = res.scalar_one_or_none()

        if not session:
            raise ResourceNotFoundError(f"Active session for {ip} not found")

        if not 1 <= additional_minutes <= 43200:
            raise ValidationError("Extension must be 1 to 43200 minutes")
        expiry = session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at
        base_time = max(now, expiry)
        session.expires_at = base_time + timedelta(minutes=additional_minutes)

        # Sync with agent
        remaining_minutes = max(1, int((session.expires_at - now).total_seconds() / 60))
        await agent_client.authorize_guest(ip, session.plan_id, remaining_minutes, session.speed_limit_mbps)

        audit = AuditLog(
            event_type="GUEST_EXTENDED",
            actor=actor,
            ip_address=ip,
            description=f"Extended guest session for {ip} by +{additional_minutes} minutes",
            severity="info"
        )
        db.add(audit)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def revoke_session(db: AsyncSession, ip: str, actor: str = "admin") -> None:
        """Immediately disconnect an authorized guest."""
        stmt = update(GuestSession).where(GuestSession.ip == ip).values(is_active=False)
        await db.execute(stmt)
        await agent_client.revoke_guest(ip)

        audit = AuditLog(
            event_type="GUEST_REVOKED",
            actor=actor,
            ip_address=ip,
            description=f"Revoked guest session for {ip}",
            severity="warning"
        )
        db.add(audit)
        await db.commit()

