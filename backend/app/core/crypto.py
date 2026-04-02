"""API Key 加密工具 — Fernet 对称加密（AES-128-CBC + HMAC）。"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings

# 从 secret_key 派生 Fernet key（固定 32 bytes base64url）
_raw = hashlib.sha256(settings.secret_key.encode()).digest()
_FERNET_KEY = base64.urlsafe_b64encode(_raw)
_fernet = Fernet(_FERNET_KEY)


def encrypt_api_key(plain_text: str) -> str:
    """加密 API Key，返回 base64 密文。"""
    return _fernet.encrypt(plain_text.encode()).decode()


def decrypt_api_key(cipher_text: str) -> str:
    """解密 API Key，返回明文。"""
    return _fernet.decrypt(cipher_text.encode()).decode()
