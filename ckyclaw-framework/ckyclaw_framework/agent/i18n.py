"""Agent 国际化支持 — 多语言 Instructions 管理。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LocalizedInstructions:
    """Agent 的多语言 Instructions 容器。

    存储多个语言版本的 Instructions 文本，并提供按优先级的 locale 解析。
    """

    default_locale: str = "zh-CN"
    """默认语言标识（BCP 47 格式）"""

    instructions: dict[str, str] = field(default_factory=dict)
    """语言标识 → Instructions 全文映射。示例: {"zh-CN": "你是...", "en-US": "You are..."}"""

    def resolve(self, locale: str) -> str:
        """按优先级解析 Instructions。

        解析顺序：精确匹配 → 语言级匹配（zh-TW → zh-CN）→ 默认语言。

        Args:
            locale: 请求的语言标识（BCP 47 格式）

        Returns:
            匹配到的 Instructions 文本。若默认语言也不存在则返回空字符串。
        """
        # 1. 精确匹配
        if locale in self.instructions:
            return self.instructions[locale]
        # 2. 语言级匹配（取 locale 的语言前缀）
        lang = locale.split("-")[0]
        for key in self.instructions:
            if key.startswith(lang + "-") or key == lang:
                return self.instructions[key]
        # 3. 回退到默认语言
        return self.instructions.get(self.default_locale, "")
