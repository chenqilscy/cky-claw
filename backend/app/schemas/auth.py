"""认证请求/响应模型。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,62}[a-zA-Z0-9]$")


class UserRegister(BaseModel):
    """注册请求体。"""

    username: str = Field(..., min_length=3, max_length=64, description="用户名")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=128, description="密码")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not _USERNAME_PATTERN.match(v):
            raise ValueError("用户名只能包含字母、数字、下划线和连字符，且以字母或数字开头结尾，长度 3-64")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("邮箱格式无效")
        return v.lower()


class UserLogin(BaseModel):
    """登录请求体。"""

    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """Token 响应。"""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int


class UserResponse(BaseModel):
    """用户信息响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    role: str
    role_id: uuid.UUID | None = None
    avatar_url: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ChangePasswordRequest(BaseModel):
    """修改密码请求体。"""

    current_password: str = Field(..., description="当前密码")
    new_password: str = Field(..., min_length=6, max_length=128, description="新密码")


class RefreshTokenRequest(BaseModel):
    """刷新 Token 请求体。"""

    refresh_token: str = Field(..., description="Refresh Token")


class PasswordResetRequest(BaseModel):
    """密码重置请求——提交邮箱。"""

    email: str = Field(..., description="注册邮箱")


class PasswordResetConfirm(BaseModel):
    """密码重置确认——设置新密码。"""

    token: str = Field(..., description="重置令牌")
    new_password: str = Field(..., min_length=6, max_length=128, description="新密码")
