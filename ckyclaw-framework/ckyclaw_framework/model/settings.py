"""ModelSettings — 模型参数配置。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelSettings:
    """模型参数配置。"""

    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    stop: list[str] | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    """模型特定参数"""
