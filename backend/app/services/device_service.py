"""Device management service orchestrating DB persistence and agent firewall sync."""
from datetime import datetime, timezone, timedelta, time as dtime
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.device import Device
from ..models.guest import HotspotPlan, GuestSession
from ..models.audit import AuditLog
from ..integrations.agent_client import agent_client
from .guest_service import GuestService

class DeviceService:
    """Synchronizes detected devices with persistent configuration, groups, and policies."""

    @staticmethod
    def _is_curfew_active(start_str: str, end_str: str, now_time: Optional[dtime] = None) -> bool:
        """Evaluate if current time is inside curfew window."""
        try:
            sh, sm = map(int, start_str.split(":"))
            eh, em = map(int, end_str.split(":"))
        except Exception:
            return False

        now = now_time or datetime.now().time()
        now_min = now.hour * 60 + now.minute
        start_min = sh * 60 + sm
        end_min = eh * 60 + em

        if start_min < end_min:
            return start_min <= now_min < end_min
        return now_min >= start_min or now_min < end_min

    @staticmethod
    def _enrich_device(dev: Device, plans: Dict[str, HotspotPlan], session: Optional[GuestSession], now_utc: datetime):
        """Enrich a Device object with live plan information, internet status, and policy descriptions."""
        curfew_active = dev.schedule_enabled and DeviceService._is_curfew_active(dev.schedule_start, dev.schedule_end)

        if dev.is_blocked:
            dev.plan_id = None
            dev.plan_name = "Blocked"
            dev.internet_status = "blocked"
            dev.internet_label = "Access Blocked"
            dev.time_remaining_sec = 0
            dev.time_remaining_str = "Blocked"
            dev.session_expires_at = None
            dev.is_internet_active = False
            dev.policy_desc = "Drop all packets · Blocked by Admin"
        elif curfew_active:
            dev.plan_id = None
            dev.plan_name = "Curfew Active"
            dev.internet_status = "curfew"
            dev.internet_label = f"Curfew Active ({dev.schedule_start}–{dev.schedule_end})"
            dev.time_remaining_sec = 0
            dev.time_remaining_str = "Curfew Restricted"
            dev.session_expires_at = None
            dev.is_internet_active = False
            dev.policy_desc = f"Curfew enforced from {dev.schedule_start} to {dev.schedule_end} · Internet Paused"
        elif dev.group in ("family", "staff"):
            dev.plan_id = "family"
            dev.plan_name = f"{dev.group.capitalize()} Whitelist"
            dev.internet_status = "unlimited"
            dev.internet_label = "Internet Active (Whitelisted)"
            dev.time_remaining_sec = None
            dev.time_remaining_str = "Permanent / Unlimited"
            dev.session_expires_at = None
            dev.is_internet_active = True
            dev.policy_desc = f"{dev.speed_limit_mbps} Mbps Limit" if dev.speed_limit_mbps > 0 else "Unlimited Speed · Captive Bypassed"
        elif session:
            expiry = session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at
            plan = plans.get(session.plan_id)
            plan_title = plan.name if plan else session.plan_id.capitalize()

            if session.is_active and expiry > now_utc:
                rem_sec = max(0, int((expiry - now_utc).total_seconds()))
                rem_mins = rem_sec // 60
                rem_hours = rem_mins // 60
                time_str = f"{rem_hours}h {rem_mins % 60}m left" if rem_hours > 0 else f"{rem_mins}m left"

                dev.plan_id = session.plan_id
                dev.plan_name = plan_title
                dev.internet_status = "active"
                dev.internet_label = f"Internet Active · {time_str}"
                dev.time_remaining_sec = rem_sec
                dev.time_remaining_str = time_str
                dev.session_expires_at = expiry
                dev.is_internet_active = True
                eff_speed = dev.speed_limit_mbps or session.speed_limit_mbps
                dev.policy_desc = f"{eff_speed} Mbps Plan Limit · Active until {expiry.strftime('%H:%M')}"
            else:
                dev.plan_id = session.plan_id
                dev.plan_name = f"{plan_title} (Expired)"
                dev.internet_status = "expired"
                dev.internet_label = "Time Exceeded / Expired"
                dev.time_remaining_sec = 0
                dev.time_remaining_str = "0m (Expired)"
                dev.session_expires_at = expiry
                dev.is_internet_active = False
                dev.policy_desc = f"Plan duration exceeded at {expiry.strftime('%H:%M')} · Voucher required"
        else:
            dev.plan_id = None
            dev.plan_name = "No Plan (Captive Portal)"
            dev.internet_status = "unauthorized"
            dev.internet_label = "Portal Login Required"
            dev.time_remaining_sec = 0
            dev.time_remaining_str = "Not Authenticated"
            dev.session_expires_at = None
            dev.is_internet_active = False
            dev.policy_desc = "Connected to Wi-Fi · Captive portal agreement or voucher required"

    @staticmethod
    async def get_all_devices(db: AsyncSession) -> List[Device]:
        """Fetch all known devices from database merged with live discovery and plan status."""
        discovered = await agent_client.discover_devices()
        now = datetime.now(timezone.utc)

        # Map discovered devices by IP/MAC
        for d in discovered:
            ip = d.get("ip")
            mac = d.get("mac", "")
            if not ip:
                continue

            stmt = select(Device).where(Device.ip == ip)
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()

            if existing:
                existing.status = d.get("status", "REACHABLE")
                existing.last_seen = now
                if mac and not existing.mac:
                    existing.mac = mac
                if d.get("hostname") and not existing.hostname:
                    existing.hostname = d["hostname"]
                if d.get("vendor") and not existing.vendor:
                    existing.vendor = d["vendor"]
            else:
                new_dev = Device(
                    mac=mac or f"unknown-{ip}",
                    ip=ip,
                    hostname=d.get("hostname", ""),
                    nickname="",
                    vendor=d.get("vendor", ""),
                    group="default",
                    is_blocked=False,
                    speed_limit_mbps=0,
                    status=d.get("status", "REACHABLE"),
                    first_seen=now,
                    last_seen=now
                )
                db.add(new_dev)

        await db.commit()

        # Query all devices
        stmt = select(Device).order_by(Device.last_seen.desc())
        res = await db.execute(stmt)
        devices = list(res.scalars().all())

        # Fetch plans and latest guest sessions to enrich devices
        plans_list = await GuestService.get_plans(db)
        plans = {p.plan_id: p for p in plans_list}

        stmt_sess = select(GuestSession).order_by(GuestSession.id.desc())
        res_sess = await db.execute(stmt_sess)
        all_sessions = res_sess.scalars().all()
        latest_session_by_ip: Dict[str, GuestSession] = {}
        for s in all_sessions:
            if s.ip not in latest_session_by_ip:
                latest_session_by_ip[s.ip] = s

        for dev in devices:
            session = latest_session_by_ip.get(dev.ip)
            DeviceService._enrich_device(dev, plans, session, now)

        return devices

    @staticmethod
    async def update_device(db: AsyncSession, ip: str, updates: Dict[str, Any], actor: str = "admin") -> Device:
        """Update device nickname, group, QoS limit, or schedule."""
        stmt = select(Device).where(Device.ip == ip)
        res = await db.execute(stmt)
        dev = res.scalar_one_or_none()

        if not dev:
            dev = Device(mac=f"unknown-{ip}", ip=ip, group="default")
            db.add(dev)

        if "nickname" in updates and updates["nickname"] is not None:
            dev.nickname = updates["nickname"]
        if "group" in updates and updates["group"] is not None:
            dev.group = updates["group"]
            await agent_client.set_group(ip, dev.group)
        if "speed_limit_mbps" in updates and updates["speed_limit_mbps"] is not None:
            dev.speed_limit_mbps = updates["speed_limit_mbps"]
            await agent_client.set_speed_limit(ip, dev.speed_limit_mbps)
        if "is_trusted" in updates and updates["is_trusted"] is not None:
            dev.is_trusted = updates["is_trusted"]
        if "schedule" in updates and updates["schedule"] is not None:
            sched = updates["schedule"]
            dev.schedule_enabled = bool(sched.get("enabled", False))
            dev.schedule_start = sched.get("start", "22:00")
            dev.schedule_end = sched.get("end", "06:00")

        # Plan Assignment or Extension
        plans_list = await GuestService.get_plans(db)
        plans = {p.plan_id: p for p in plans_list}

        if updates.get("assign_plan_id"):
            pid = updates["assign_plan_id"]
            if pid == "revoke":
                await GuestService.revoke_session(db, ip, actor=actor)
            elif pid in ("family", "staff"):
                dev.group = pid
                await agent_client.set_group(ip, pid)
            elif pid in plans:
                target_plan = plans[pid]
                now_utc = datetime.now(timezone.utc)
                exp_utc = now_utc + timedelta(minutes=target_plan.duration_minutes)
                await db.execute(update(GuestSession).where(GuestSession.ip == ip).values(is_active=False))
                new_session = GuestSession(
                    ip=ip,
                    mac=dev.mac,
                    plan_id=target_plan.plan_id,
                    speed_limit_mbps=target_plan.speed_limit_mbps,
                    authorized_at=now_utc,
                    expires_at=exp_utc,
                    is_active=True
                )
                db.add(new_session)
                await agent_client.authorize_guest(
                    ip, target_plan.plan_id, target_plan.duration_minutes, target_plan.speed_limit_mbps
                )

        if updates.get("extend_minutes"):
            try:
                await GuestService.extend_session(db, ip, additional_minutes=int(updates["extend_minutes"]), actor=actor)
            except Exception:
                pass

        if updates.get("revoke_internet"):
            await GuestService.revoke_session(db, ip, actor=actor)

        audit = AuditLog(
            event_type="DEVICE_UPDATED",
            actor=actor,
            ip_address=ip,
            description=f"Updated settings for {ip} (nickname: '{dev.nickname}', group: '{dev.group}', QoS: {dev.speed_limit_mbps} Mbps)",
            severity="info"
        )
        db.add(audit)
        await db.commit()
        await db.refresh(dev)

        # Enrich updated dev before returning
        stmt_sess = select(GuestSession).where(GuestSession.ip == ip).order_by(GuestSession.id.desc()).limit(1)
        res_sess = await db.execute(stmt_sess)
        latest_sess = res_sess.scalar_one_or_none()
        DeviceService._enrich_device(dev, plans, latest_sess, datetime.now(timezone.utc))

        return dev

    @staticmethod
    async def set_block(db: AsyncSession, ip: str, blocked: bool, actor: str = "admin") -> Device:
        """Block or unblock internet access for a device."""
        stmt = select(Device).where(Device.ip == ip)
        res = await db.execute(stmt)
        dev = res.scalar_one_or_none()

        if not dev:
            dev = Device(mac=f"unknown-{ip}", ip=ip, group="default")
            db.add(dev)

        dev.is_blocked = blocked
        await agent_client.set_block(ip, blocked)

        audit = AuditLog(
            event_type="DEVICE_BLOCKED" if blocked else "DEVICE_UNBLOCKED",
            actor=actor,
            ip_address=ip,
            description=f"Internet access {'blocked' if blocked else 'unblocked'} for {ip} ({dev.nickname or dev.hostname or 'Unknown'})",
            severity="warning" if blocked else "info"
        )
        db.add(audit)
        await db.commit()
        await db.refresh(dev)

        plans_list = await GuestService.get_plans(db)
        plans = {p.plan_id: p for p in plans_list}
        stmt_sess = select(GuestSession).where(GuestSession.ip == ip).order_by(GuestSession.id.desc()).limit(1)
        res_sess = await db.execute(stmt_sess)
        latest_sess = res_sess.scalar_one_or_none()
        DeviceService._enrich_device(dev, plans, latest_sess, datetime.now(timezone.utc))

        return dev
