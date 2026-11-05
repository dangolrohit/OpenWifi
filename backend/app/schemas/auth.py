"""Authentication and user schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)

class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True

class LoginResponse(BaseModel):
    ok: bool = True
    token: str
    csrf_token: str
    user: UserResponse

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

