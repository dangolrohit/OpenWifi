import hashlib
import hmac
import time
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from starlette.requests import Request
from backend.app.models.base import Base
from backend.app.models.guest import HotspotPlan, Voucher, GuestSession
from backend.app.services.guest_service import GuestService
from backend.app.integrations.agent_client import agent_client, AgentUnavailableError
from backend.app.core.exceptions import ValidationError
from backend.app.core.config import settings
from backend.app.api.v1.endpoints.guests import guest_client_ip, limit_connect_attempts, _connect_attempts
from backend.app.schemas.guest import GuestConnectRequest
from fastapi import HTTPException

class GuestFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.db = async_sessionmaker(self.engine, expire_on_commit=False)()
        self.agent_patch = patch.object(agent_client, 'authorize_guest', new_callable=AsyncMock, return_value={'ok': True})
        self.authorize = self.agent_patch.start()
        await GuestService.get_plans(self.db)

    async def asyncTearDown(self):
        self.agent_patch.stop()
        await self.db.close()
        await self.engine.dispose()

    async def test_free_limits_repeat_click_and_expiry(self):
        session = await GuestService.authorize_guest(self.db, '192.168.16.110', 'starter')
        self.assertEqual(session.speed_limit_mbps, 1)
        self.assertEqual(session.expires_at - session.authorized_at, timedelta(minutes=30))
        self.authorize.assert_awaited_once_with('192.168.16.110', 'starter', 30, 1)
        again = await GuestService.authorize_guest(self.db, '192.168.16.110', 'starter')
        self.assertEqual(again.id, session.id)
        self.assertEqual(self.authorize.await_count, 1)
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await self.db.commit()
        with self.assertRaisesRegex(ValidationError, 'free session has ended'):
            await GuestService.authorize_guest(self.db, '192.168.16.110', 'starter')

    async def test_existing_free_plan_migrates(self):
        plan = (await self.db.execute(select(HotspotPlan).where(HotspotPlan.plan_id == 'starter'))).scalar_one()
        plan.speed_limit_mbps = 2
        await self.db.commit()
        plans = await GuestService.get_plans(self.db)
        self.assertEqual(next(p for p in plans if p.plan_id == 'starter').speed_limit_mbps, 1)

    async def test_voucher_applies_plan_and_cannot_be_reused(self):
        voucher = await GuestService.create_voucher(self.db, 'standard', '001234')
        session = await GuestService.authorize_guest(self.db, '192.168.16.111', voucher_code=voucher.code)
        self.assertEqual(session.speed_limit_mbps, 5)
        self.authorize.assert_awaited_once_with('192.168.16.111', 'standard', 120, 5)
        with self.assertRaises(ValidationError):
            await GuestService.authorize_guest(self.db, '192.168.16.112', voucher_code=voucher.code)

    async def test_unavailable_agent_does_not_consume_code(self):
        await GuestService.create_voucher(self.db, 'standard', '123456')
        self.authorize.side_effect = AgentUnavailableError('Agent offline')
        with self.assertRaises(AgentUnavailableError):
            await GuestService.authorize_guest(self.db, '192.168.16.111', voucher_code='123456')
        await self.db.rollback()
        voucher = (await self.db.execute(select(Voucher).where(Voucher.code == '123456'))).scalar_one()
        self.assertFalse(voucher.is_used)
        self.assertEqual(list((await self.db.execute(select(GuestSession))).scalars()), [])

    async def test_disabled_plan_code_and_paid_plan_bypass_rejected(self):
        await GuestService.create_voucher(self.db, 'standard', '123456')
        with self.assertRaises(ValidationError):
            await GuestService.authorize_guest(self.db, '192.168.16.111', 'standard')
        plan = (await self.db.execute(select(HotspotPlan).where(HotspotPlan.plan_id == 'standard'))).scalar_one()
        plan.is_active = False
        await self.db.commit()
        with self.assertRaises(ValidationError):
            await GuestService.authorize_guest(self.db, '192.168.16.111', voucher_code='123456')
        self.authorize.assert_not_awaited()

    async def test_invalid_codes_and_plan_rejected(self):
        for plan, code in [('standard', 'abc123'), ('standard', '12345'), ('standard', '1234567'), ('missing', '123456'), ('starter', '123456')]:
            with self.assertRaises(ValidationError):
                await GuestService.create_voucher(self.db, plan, code)

    async def test_upgrade_leaves_one_active_session(self):
        await GuestService.authorize_guest(self.db, '192.168.16.111', 'starter')
        await GuestService.create_voucher(self.db, 'standard', '123456')
        await GuestService.authorize_guest(self.db, '192.168.16.111', voucher_code='123456')
        active = await GuestService.list_active_sessions(self.db)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].plan_id, 'standard')

class CaptiveIdentityTests(unittest.TestCase):
    def request(self, headers):
        return Request({'type': 'http', 'headers': [(k.lower().encode(), v.encode()) for k,v in headers.items()], 'client': ('172.18.0.1', 1234)})

    def test_verified_proxy_ip_and_spoof_rejection(self):
        timestamp = str(int(time.time()))
        signature = hmac.new(b'secret', f'192.168.16.111|{timestamp}'.encode(), hashlib.sha256).hexdigest()
        headers = {'X-Captive-IP': '192.168.16.111', 'X-Captive-Time': timestamp, 'X-Captive-Signature': signature}
        with patch.object(settings, 'CAPTIVE_PROXY_SECRET', 'secret'):
            self.assertEqual(guest_client_ip(self.request(headers)), '192.168.16.111')
            headers['X-Captive-IP'] = '192.168.16.112'
            with self.assertRaises(HTTPException):
                guest_client_ip(self.request(headers))
        self.assertEqual(guest_client_ip(self.request({'X-Forwarded-For': '192.168.16.111'})), '172.18.0.1')

    def test_attempt_limit(self):
        _connect_attempts.clear()
        for _ in range(10):
            limit_connect_attempts('192.168.16.111')
        with self.assertRaises(HTTPException) as error:
            limit_connect_attempts('192.168.16.111')
        self.assertEqual(error.exception.status_code, 429)
        _connect_attempts.clear()

    def test_six_digit_schema_preserves_leading_zero(self):
        self.assertEqual(GuestConnectRequest(voucher='001234').voucher, '001234')
        with self.assertRaises(ValueError):
            GuestConnectRequest(voucher='12345')


    def test_portal_generated_identity_is_accepted(self):
        import importlib.util
        from pathlib import Path
        spec = importlib.util.spec_from_file_location('captive_test_server', Path(__file__).resolve().parents[3] / 'captive-portal' / 'server.py')
        portal = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(portal)
        with patch.object(portal, 'PROXY_SECRET', 'shared'), patch.object(settings, 'CAPTIVE_PROXY_SECRET', 'shared'):
            headers = portal.client_headers('192.168.16.120')
            self.assertEqual(guest_client_ip(self.request(headers)), '192.168.16.120')
