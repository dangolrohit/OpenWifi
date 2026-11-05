"""Authentication endpoints."""
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from ....core.config import settings
from ....db.session import get_db
from ....schemas.auth import LoginRequest, LoginResponse, UserResponse, ChangePasswordRequest
from ....services.auth_service import AuthService
from ...dependencies.auth import get_current_user, get_current_user_and_session
from ....models.user import User, UserSession

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate administrator credentials and establish secure HttpOnly session."""
    client_ip = request.client.host if request.client else "unknown"
    user, session = await AuthService.authenticate_user(db, req.username, req.password, client_ip)

    # Set secure HttpOnly cookie
    response.set_cookie(
        key="oshin_session",
        value=session.token,
        max_age=settings.SESSION_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=False,  # Set to True when TLS termination is enabled in production
        samesite="lax",
        path="/"
    )

    return LoginResponse(
        ok=True,
        token=session.token,
        csrf_token=session.csrf_token,
        user=UserResponse.model_validate(user)
    )

@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    auth_data: tuple[User, UserSession] = Depends(get_current_user_and_session)
):
    """Invalidate current session token and clear authentication cookie."""
    user, session = auth_data
    client_ip = request.client.host if request.client else "unknown"
    await AuthService.logout_session(db, session.token, user.username, client_ip)
    response.delete_cookie(key="oshin_session", path="/")
    return {"ok": True, "message": "Signed out successfully"}

@router.get("/me", response_model=LoginResponse)
async def get_me(
    auth_data: tuple[User, UserSession] = Depends(get_current_user_and_session)
):
    """Retrieve current authenticated user profile and session CSRF token."""
    user, session = auth_data
    return LoginResponse(
        ok=True,
        token=session.token,
        csrf_token=session.csrf_token,
        user=UserResponse.model_validate(user)
    )

@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Change current user password."""
    client_ip = request.client.host if request.client else "unknown"
    await AuthService.change_password(db, user.id, req.current_password, req.new_password, client_ip)
    return {"ok": True, "message": "Password changed successfully"}

