"""Crypto 边界测试 — Fernet 加解密异常路径。"""

from __future__ import annotations

import pytest
from cryptography.fernet import InvalidToken

from app.core.crypto import decrypt_api_key, encrypt_api_key


class TestEncryptDecrypt:
    """encrypt_api_key / decrypt_api_key 边界条件。"""

    def test_round_trip(self) -> None:
        """正常加密→解密应还原明文。"""
        plain = "sk-test-api-key-12345"
        cipher = encrypt_api_key(plain)
        assert cipher != plain
        assert decrypt_api_key(cipher) == plain

    def test_unicode_key(self) -> None:
        """Unicode API key 应正确加解密。"""
        plain = "密钥🔑test"
        cipher = encrypt_api_key(plain)
        assert decrypt_api_key(cipher) == plain

    def test_empty_string(self) -> None:
        """空字符串加密→解密应还原。"""
        cipher = encrypt_api_key("")
        assert decrypt_api_key(cipher) == ""

    def test_long_key(self) -> None:
        """长 key（1000 字符）应正确处理。"""
        plain = "x" * 1000
        cipher = encrypt_api_key(plain)
        assert decrypt_api_key(cipher) == plain

    def test_decrypt_corrupted_cipher_raises(self) -> None:
        """损坏的密文应抛出 InvalidToken。"""
        with pytest.raises(InvalidToken):
            decrypt_api_key("this-is-not-valid-fernet-token")

    def test_decrypt_truncated_cipher_raises(self) -> None:
        """截断的密文应抛出异常。"""
        cipher = encrypt_api_key("test")
        truncated = cipher[:10]
        with pytest.raises(Exception):
            decrypt_api_key(truncated)

    def test_decrypt_empty_string_raises(self) -> None:
        """空密文应抛出异常。"""
        with pytest.raises(Exception):
            decrypt_api_key("")

    def test_each_encryption_unique(self) -> None:
        """同一明文两次加密应产生不同密文（Fernet 使用随机 IV）。"""
        plain = "test-key"
        cipher1 = encrypt_api_key(plain)
        cipher2 = encrypt_api_key(plain)
        assert cipher1 != cipher2
        # 但都能解回同一明文
        assert decrypt_api_key(cipher1) == plain
        assert decrypt_api_key(cipher2) == plain
