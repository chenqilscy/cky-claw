"""配置缓存 — 简单 TTL 内存缓存 + 手动失效。"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 300  # 5 分钟


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl


class ConfigCache:
    """简单 TTL 内存缓存。

    - 写操作自动 invalidate 对应 key
    - 提供 invalidate / invalidate_prefix / clear 手动清除
    """

    def __init__(self, default_ttl: float = _DEFAULT_TTL) -> None:
        self._store: dict[str, _CacheEntry] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        self._store[key] = _CacheEntry(value, ttl if ttl is not None else self._default_ttl)

    def invalidate(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    def invalidate_prefix(self, prefix: str) -> int:
        """删除所有以 prefix 开头的缓存条目。"""
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._store[k]
        return len(keys_to_delete)

    def clear(self) -> int:
        """清除全部缓存。"""
        count = len(self._store)
        self._store.clear()
        logger.info("Config cache cleared (%d entries)", count)
        return count

    @property
    def size(self) -> int:
        return len(self._store)


# 全局单例
config_cache = ConfigCache()


def make_cache_key(entity_type: str, *parts: str) -> str:
    """构造缓存 key。"""
    return f"kasaya:{entity_type}:" + ":".join(parts)


def make_list_cache_key(entity_type: str, params: dict[str, Any] | None = None) -> str:
    """构造列表缓存 key（含参数哈希）。"""
    if params:
        raw = json.dumps(params, sort_keys=True, default=str)
        h = hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()[:8]
        return f"kasaya:{entity_type}:list:{h}"
    return f"kasaya:{entity_type}:list:all"
