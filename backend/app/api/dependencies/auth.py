"""FastAPI authentication dependencies and permission guards."""
from typing import Optional
from fastapi import Cookie, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.exceptions import AuthenticationError, PermissionDeniedError
from ...core.permissions import UserRole
from ...db.session import get_db
from ...models.user import User, UserSession
from ...services.auth_service import AuthService

async def get_current_user_and_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
    oshin_session: Optional[str] = Cookie(None),
    authorization: Optional[str] = Header(None)
) -> tuple[User, UserSession]:
    """Extract and validate session token from cookie or Authorization header."""
    token = oshin_session
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]

    if not token:
        raise AuthenticationError("Authentication required. Please sign in.")

    result = await AuthService.get_user_by_session_token(db, token)
    if not result:
        raise AuthenticationError("Session expired or invalid. Please sign in again.")

    user, session = result

    # CSRF verification for state-mutating HTTP methods
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        csrf_header = request.headers.get("X-CSRF-Token")
        if not csrf_header or csrf_header != session.csrf_token:
            # If using Bearer authorization header, CSRF can be relaxed, otherwise enforce
            if not (authorization and authorization.startswith("Bearer ")):
                raise PermissionDeniedError("Invalid CSRF token")

    return user, session

async def get_current_user(
    auth_data: tuple[User, UserSession] = Depends(get_current_user_and_session)
) -> User:
    """Dependency returning the authenticated User."""
    return auth_data[0]

def require_role(min_role: UserRole):
    """Dependency factory checking required user role."""
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if min_role == UserRole.SUPER_ADMIN and user.role != UserRole.SUPER_ADMIN:
            raise PermissionDeniedError("Super Administrator privileges required")
        if min_role == UserRole.ADMIN and user.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
            raise PermissionDeniedError("Administrator privileges required")
        return user
    return role_checker

