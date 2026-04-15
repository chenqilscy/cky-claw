"""认证 API 路由。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.schemas.auth import (
    ChangePasswordRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services import auth as auth_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.user import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    data: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """注册新用户。"""
    user = await auth_service.register_user(db, data)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """用户登录，返回 JWT Token + Refresh Token。"""
    access_token, refresh_token = await auth_service.authenticate_user(db, data.username, data.password)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    user: User = Depends(get_current_user),
) -> UserResponse:
    """获取当前登录用户信息。"""
    return UserResponse.model_validate(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """使用 refresh_token 刷新 access_token（令牌轮转）。"""
    access_token, new_refresh = await auth_service.refresh_access_token(db, data.refresh_token)
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    _user: User = Depends(get_current_user),
) -> None:
    """服务端登出——将 token 加入黑名单。"""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    # 尝试从请求体读取 refresh_token
    refresh_token = None
    try:
        body = await request.json()
        refresh_token = body.get("refresh_token")
    except Exception:
        pass
    await auth_service.logout_user(token, refresh_token)


@router.put("/password", status_code=204)
async def change_password(
    data: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """修改密码（需当前密码验证）。"""
    await auth_service.change_password(db, user, data.current_password, data.new_password)


@router.post("/password-reset/request", status_code=200)
async def request_password_reset(
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """请求密码重置——提交邮箱获取重置令牌。

    注意：生产环境应通过邮件发送 token，此处直接返回。
    安全考虑：即使邮箱不存在也返回成功，防止邮箱枚举。
    """
    token = await auth_service.request_password_reset(db, data.email)
    return {"message": "如果该邮箱已注册，重置令牌已生成", "reset_token": token}


@router.post("/password-reset/confirm", status_code=204)
async def confirm_password_reset(
    data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
) -> None:
    """确认密码重置——使用令牌设置新密码。"""
    await auth_service.confirm_password_reset(db, data.token, data.new_password)
