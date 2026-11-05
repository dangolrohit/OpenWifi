"""Authentication service handling Argon2id verification, session lifecycle, and audit logs."""
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.config import settings
from ..core.security import hash_password, verify_password, generate_session_token, generate_csrf_token
from ..core.exceptions import AuthenticationError, ResourceNotFoundError
from ..models.user import User, UserSession
from ..models.audit import AuditLog

class AuthService:
    """Manages user authentication, session tokens, password changes, and audit records."""

    @staticmethod
    async def authenticate_user(db: AsyncSession, username: str, password: str, ip_address: str = "") -> Tuple[User, UserSession]:
        stmt = select(User).where(User.username == username, User.is_active == True)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            # Log failed attempt
            audit = AuditLog(
                event_type="LOGIN_FAILED",
                actor=username,
                ip_address=ip_address,
                description="Failed login attempt with invalid credentials",
                severity="warning"
            )
            db.add(audit)
            await db.commit()
            raise AuthenticationError("Invalid username or password")

        # Update last login
        user.last_login = datetime.now(timezone.utc)

        # Create session
        token = generate_session_token()
        csrf_token = generate_csrf_token()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)

        session = UserSession(
            token=token,
            csrf_token=csrf_token,
            user_id=user.id,
            ip_address=ip_address,
            expires_at=expires_at,
            is_active=True
        )
        db.add(session)

        # Log successful login
        audit = AuditLog(
            event_type="LOGIN_SUCCESS",
            actor=username,
            ip_address=ip_address,
            description="Administrator signed in successfully",
            severity="info"
        )
        db.add(audit)
        await db.commit()
        await db.refresh(session)
        await db.refresh(user)

        return user, session

    @staticmethod
    async def get_user_by_session_token(db: AsyncSession, token: str) -> Optional[Tuple[User, UserSession]]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(UserSession, User)
            .join(User, UserSession.user_id == User.id)
            .where(
                UserSession.token == token,
                UserSession.is_active == True,
                UserSession.expires_at > now,
                User.is_active == True
            )
        )
        res = await db.execute(stmt)
        row = res.first()
        if not row:
            return None
        return row[1], row[0]

    @staticmethod
    async def logout_session(db: AsyncSession, token: str, actor: str = "admin", ip_address: str = "") -> None:
        stmt = update(UserSession).where(UserSession.token == token).values(is_active=False)
        await db.execute(stmt)

        audit = AuditLog(
            event_type="LOGOUT",
            actor=actor,
            ip_address=ip_address,
            description="Administrator signed out",
            severity="info"
        )
        db.add(audit)
        await db.commit()

    @staticmethod
    async def change_password(db: AsyncSession, user_id: int, current_pw: str, new_pw: str, ip_address: str = "") -> None:
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            raise ResourceNotFoundError("User not found")

        if not verify_password(current_pw, user.password_hash):
            raise AuthenticationError("Current password incorrect")

        user.password_hash = hash_password(new_pw)
        audit = AuditLog(
            event_type="PASSWORD_CHANGED",
            actor=user.username,
            ip_address=ip_address,
            description="Administrator password updated",
            severity="info"
        )
        db.add(audit)
        await db.commit()

