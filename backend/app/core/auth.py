"""认证工具 — JWT Token + 密码哈希。"""

from __future__ import annotations

from typing import Any

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# JWT 配置
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash 密码（bcrypt, cost=12）。"""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码（兼容 $2b$ 和 $2a$ 前缀）。"""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """创建 JWT access token。"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return str(jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM))


def decode_access_token(token: str) -> dict[str, Any] | None:
    """解码 JWT access token。返回 None 表示无效。"""
    try:
        payload: dict[str, Any] | None = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
