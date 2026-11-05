"""Device management service orchestrating DB persistence and agent firewall sync."""
from datetime import datetime, timezone, time as dtime
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.device import Device
from ..models.audit import AuditLog
from ..integrations.agent_client import agent_client

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
    async def get_all_devices(db: AsyncSession) -> List[Device]:
        """Fetch all known devices from database merged with live discovery."""
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
        return list(res.scalars().all())

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
        return dev

