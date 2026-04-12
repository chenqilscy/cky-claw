"""Auth 安全边界测试 — JWT 解码 / 密码验证 / Token 黑名单 / 依赖注入安全路径。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt

from app.core.auth import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.core.config import settings


class TestDecodeAccessTokenEdgeCases:
    """decode_access_token 各种非法输入。"""

    def test_expired_token(self) -> None:
        """过期 token 解码应返回 None。"""
        token = create_access_token(
            {"sub": str(uuid.uuid4())},
            expires_delta=timedelta(seconds=-10),
        )
        assert decode_access_token(token) is None

    def test_wrong_secret_key(self) -> None:
        """使用错误密钥签名的 token 应返回 None。"""
        payload = {"sub": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) + timedelta(hours=1), "type": "access"}
        token = jwt.encode(payload, "wrong-secret-key", algorithm=ALGORITHM)
        assert decode_access_token(token) is None

    def test_malformed_token(self) -> None:
        """格式错误的字符串应返回 None。"""
        assert decode_access_token("not.a.valid.jwt") is None

    def test_empty_string(self) -> None:
        """空字符串应返回 None。"""
        assert decode_access_token("") is None

    def test_none_sub_claim(self) -> None:
        """缺少 sub claim 的 token 能解码但 payload 中无 sub。"""
        token = create_access_token({})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload.get("sub") is None

    def test_valid_token(self) -> None:
        """正常 token 解码成功。"""
        uid = str(uuid.uuid4())
        token = create_access_token({"sub": uid})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == uid
        assert payload["type"] == "access"


class TestDecodeRefreshTokenEdgeCases:
    """decode_refresh_token 边界。"""

    def test_access_token_not_accepted(self) -> None:
        """access token 不应被接受为 refresh token。"""
        token = create_access_token({"sub": str(uuid.uuid4())})
        assert decode_refresh_token(token) is None

    def test_valid_refresh_token(self) -> None:
        """合法的 refresh token 应解码成功。"""
        uid = str(uuid.uuid4())
        token = create_refresh_token({"sub": uid})
        payload = decode_refresh_token(token)
        assert payload is not None
        assert payload["type"] == "refresh"

    def test_expired_refresh_token(self) -> None:
        """过期的 refresh token 应返回 None。"""
        payload_data = {"sub": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) - timedelta(days=1), "type": "refresh"}
        token = jwt.encode(payload_data, settings.secret_key, algorithm=ALGORITHM)
        assert decode_refresh_token(token) is None

    def test_tampered_type_claim(self) -> None:
        """type 被篡改为非 refresh 应返回 None。"""
        payload_data = {"sub": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) + timedelta(hours=1), "type": "tampered"}
        token = jwt.encode(payload_data, settings.secret_key, algorithm=ALGORITHM)
        assert decode_refresh_token(token) is None


class TestPasswordEdgeCases:
    """hash_password / verify_password 边界条件。"""

    def test_hash_and_verify_normal(self) -> None:
        """正常密码哈希和验证。"""
        hashed = hash_password("myP@ssw0rd")
        assert verify_password("myP@ssw0rd", hashed) is True

    def test_wrong_password(self) -> None:
        """错误密码应返回 False。"""
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_corrupted_hash(self) -> None:
        """损坏的 bcrypt hash 应返回 False（不抛异常）。"""
        assert verify_password("test", "not-a-valid-hash") is False

    def test_empty_password_vs_hash(self) -> None:
        """空密码不应匹配任何 hash。"""
        hashed = hash_password("some-password")
        assert verify_password("", hashed) is False

    def test_unicode_password(self) -> None:
        """Unicode 密码（中文、emoji）应正确哈希验证。"""
        pwd = "密码🔑安全"
        hashed = hash_password(pwd)
        assert verify_password(pwd, hashed) is True

    def test_long_password_raises(self) -> None:
        """超长密码（>72 字节）bcrypt 应抛出 ValueError。"""
        pwd = "a" * 256
        with pytest.raises(ValueError, match="password cannot be longer than 72 bytes"):
            hash_password(pwd)


class TestTokenBlacklist:
    """Token 黑名单 Redis 操作边界。"""

    @pytest.mark.asyncio
    async def test_blacklist_token(self) -> None:
        """Token 加入黑名单后应可检测。"""
        from app.core.auth import blacklist_token, is_token_blacklisted

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)

        with patch("app.core.redis.get_redis", new_callable=AsyncMock, return_value=mock_redis):
            await blacklist_token("test-token", 3600)
            mock_redis.setex.assert_awaited_once()

            result = await is_token_blacklisted("test-token")
            assert result is True

    @pytest.mark.asyncio
    async def test_non_blacklisted_token(self) -> None:
        """未加入黑名单的 token 应返回 False。"""
        from app.core.auth import is_token_blacklisted

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)

        with patch("app.core.redis.get_redis", new_callable=AsyncMock, return_value=mock_redis):
            result = await is_token_blacklisted("fresh-token")
            assert result is False


class TestGetCurrentUserEdgeCases:
    """get_current_user 依赖注入 — 各种 401 场景。"""

    def test_missing_auth_header_returns_403(self) -> None:
        """缺少 Authorization header 应返回 403（HTTPBearer 默认行为）。"""
        from fastapi.testclient import TestClient
        from app.main import app

        # 临时移除 autouse 的依赖覆盖
        original = app.dependency_overrides.copy()
        app.dependency_overrides.clear()
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/agents")
            assert resp.status_code in (401, 403)
        finally:
            app.dependency_overrides.update(original)

    def test_invalid_jwt_returns_401(self) -> None:
        """无效 JWT 字符串应返回 401。"""
        from fastapi.testclient import TestClient
        from app.main import app

        original = app.dependency_overrides.copy()
        app.dependency_overrides.clear()
        try:
            client = TestClient(app)
            resp = client.get(
                "/api/v1/agents",
                headers={"Authorization": "Bearer invalid.jwt.token"},
            )
            assert resp.status_code == 401
            body = resp.json()
            assert body["detail"]["code"] == "UNAUTHORIZED"
        finally:
            app.dependency_overrides.update(original)

    def test_expired_jwt_returns_401(self) -> None:
        """过期 JWT 应返回 401。"""
        from fastapi.testclient import TestClient
        from app.main import app

        expired_token = create_access_token(
            {"sub": str(uuid.uuid4())},
            expires_delta=timedelta(seconds=-10),
        )

        original = app.dependency_overrides.copy()
        app.dependency_overrides.clear()
        try:
            client = TestClient(app)
            resp = client.get(
                "/api/v1/agents",
                headers={"Authorization": f"Bearer {expired_token}"},
            )
            assert resp.status_code == 401
        finally:
            app.dependency_overrides.update(original)
