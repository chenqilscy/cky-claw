"""OAuth 2.0 认证路由。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.oauth_providers import list_available_providers
from app.schemas.auth import TokenResponse
from app.schemas.oauth import OAuthAuthorizeResponse, OAuthCallbackRequest, OAuthConnectionResponse
from app.services import oauth_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.user import User

router = APIRouter(prefix="/api/v1/auth/oauth", tags=["oauth"])


@router.get("/providers")
async def get_available_providers() -> dict[str, list[str]]:
    """获取已配置的 OAuth Provider 列表。"""
    return {"providers": list_available_providers()}


@router.get("/{provider}/authorize", response_model=OAuthAuthorizeResponse)
async def authorize(provider: str) -> OAuthAuthorizeResponse:
    """获取 OAuth 授权跳转 URL。"""
    authorize_url, state = await oauth_service.generate_authorize_url(provider)
    return OAuthAuthorizeResponse(authorize_url=authorize_url, state=state)


@router.get("/{provider}/callback", response_model=TokenResponse)
async def callback(
    provider: str,
    code: str = Query(..., description="OAuth 授权码"),
    state: str = Query(..., description="CSRF state 参数"),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """OAuth 回调端点 — 验证授权码，返回 JWT Token。"""
    access_token = await oauth_service.handle_oauth_callback(db, provider, code, state)
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/{provider}/bind", response_model=OAuthConnectionResponse)
async def bind_oauth(
    provider: str,
    data: OAuthCallbackRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OAuthConnectionResponse:
    """将 OAuth 账号绑定到当前用户。"""
    conn = await oauth_service.bind_oauth_to_user(db, user, provider, data.code, data.state)
    return OAuthConnectionResponse.model_validate(conn)


@router.get("/connections", response_model=list[OAuthConnectionResponse])
async def get_connections(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OAuthConnectionResponse]:
    """获取当前用户的 OAuth 绑定列表。"""
    connections = await oauth_service.get_user_connections(db, user.id)
    return [OAuthConnectionResponse.model_validate(c) for c in connections]


@router.delete("/{provider}/unbind", status_code=204)
async def unbind(
    provider: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """解绑 OAuth 账号。"""
    await oauth_service.unbind_oauth(db, user, provider)
