"""OAuth 请求/响应模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OAuthAuthorizeResponse(BaseModel):
    """OAuth 授权 URL 响应。"""

    authorize_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    """OAuth 回调请求。"""

    code: str
    state: str


class OAuthConnectionResponse(BaseModel):
    """OAuth 绑定信息响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    provider_user_id: str
    provider_username: str
    provider_email: str | None = None
    provider_avatar_url: str | None = None
    created_at: datetime
