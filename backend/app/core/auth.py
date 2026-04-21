"""认证工具 — JWT Token + 密码哈希 + Token 黑名单。"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# JWT 配置
ALGORITHM = "HS256"
REFRESH_TOKEN_EXPIRE_DAYS = 30
PASSWORD_RESET_EXPIRE_MINUTES = 30


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
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire, "type": "access"})
    return str(jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM))


def create_refresh_token(data: dict[str, Any]) -> str:
    """创建 JWT refresh token（30 天有效期）。"""
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return str(jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM))


def decode_access_token(token: str) -> dict[str, Any] | None:
    """解码 JWT access token。返回 None 表示无效。"""
    try:
        payload: dict[str, Any] | None = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def decode_refresh_token(token: str) -> dict[str, Any] | None:
    """解码 JWT refresh token，验证 type=refresh。"""
    payload = decode_access_token(token)
    if payload is None or payload.get("type") != "refresh":
        return None
    return payload


def generate_password_reset_token() -> str:
    """生成密码重置令牌（URL 安全随机串）。"""
    return secrets.token_urlsafe(32)


# --- Token 黑名单（Redis） ---

_TOKEN_BLACKLIST_PREFIX = "kasaya:token_blacklist:"
_RESET_TOKEN_PREFIX = "kasaya:password_reset:"


async def blacklist_token(token: str, expires_in_seconds: int) -> None:
    """将 token 加入 Redis 黑名单（过期后自动清理）。"""
    from app.core.redis import get_redis

    redis = await get_redis()
    key = f"{_TOKEN_BLACKLIST_PREFIX}{token}"
    await redis.setex(key, expires_in_seconds, "1")


async def is_token_blacklisted(token: str) -> bool:
    """检查 token 是否在黑名单中。"""
    from app.core.redis import get_redis

    redis = await get_redis()
    key = f"{_TOKEN_BLACKLIST_PREFIX}{token}"
    return bool(await redis.exists(key) > 0)


async def store_password_reset_token(email: str, token: str) -> None:
    """存储密码重置令牌到 Redis（30 分钟过期）。"""
    from app.core.redis import get_redis

    redis = await get_redis()
    key = f"{_RESET_TOKEN_PREFIX}{token}"
    await redis.setex(key, PASSWORD_RESET_EXPIRE_MINUTES * 60, email)


async def validate_password_reset_token(token: str) -> str | None:
    """验证密码重置令牌，返回邮箱或 None。原子消费（验证后删除）。"""
    from app.core.redis import get_redis

    redis = await get_redis()
    key = f"{_RESET_TOKEN_PREFIX}{token}"
    email: str | None = await redis.getdel(key)
    return email
