"""成本路由 — 基于规则的任务复杂度分类与模型选择。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ModelTier(StrEnum):
    """模型层级枚举。"""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    REASONING = "reasoning"
    MULTIMODAL = "multimodal"


# ---------------------------------------------------------------------------
# 规则分类器
# ---------------------------------------------------------------------------

# 关键词 → 层级映射（按优先级从高到低检查）
_REASONING_KEYWORDS = frozenset({
    "推理", "数学", "math", "proof", "证明", "算法", "algorithm",
    "逻辑", "logic", "分析", "analysis", "策略", "strategy",
    "优化", "optimize", "规划", "planning", "复杂",
})

_COMPLEX_KEYWORDS = frozenset({
    "代码", "code", "编程", "program", "架构", "architecture",
    "设计", "design", "重构", "refactor", "调试", "debug",
    "翻译", "translate", "摘要", "summary", "文档", "document",
    "review", "审查",
})

_MULTIMODAL_KEYWORDS = frozenset({
    "图片", "image", "图像", "picture", "视觉", "vision",
    "截图", "screenshot", "照片", "photo", "视频", "video",
    "OCR", "描述图片", "看图",
})

# 简单任务一般很短且无特殊关键词（中文字符信息密度高，阈值相应降低）
_SIMPLE_MAX_LENGTH = 50

# 层级优先级排序（数值越大层级越高）
_TIER_ORDER: dict[ModelTier, int] = {
    ModelTier.SIMPLE: 0,
    ModelTier.MODERATE: 1,
    ModelTier.COMPLEX: 2,
    ModelTier.REASONING: 3,
    ModelTier.MULTIMODAL: 4,
}


def classify_complexity(text: str) -> ModelTier:
    """基于关键词和文本长度的规则分类器。

    优先级：MULTIMODAL > REASONING > COMPLEX > MODERATE > SIMPLE
    """
    lower = text.lower()

    # 多模态检测优先
    if any(kw in lower for kw in _MULTIMODAL_KEYWORDS):
        return ModelTier.MULTIMODAL

    # 推理关键词
    if any(kw in lower for kw in _REASONING_KEYWORDS):
        return ModelTier.REASONING

    # 复杂任务关键词
    if any(kw in lower for kw in _COMPLEX_KEYWORDS):
        return ModelTier.COMPLEX

    # 短文本 → 简单任务
    if len(text.strip()) <= _SIMPLE_MAX_LENGTH:
        return ModelTier.SIMPLE

    # 默认中等
    return ModelTier.MODERATE


# ---------------------------------------------------------------------------
# Provider 选择
# ---------------------------------------------------------------------------

@dataclass
class ProviderCandidate:
    """Provider 候选项（从后端获取的模型信息）。"""

    name: str
    model_tier: ModelTier
    capabilities: list[str] = field(default_factory=list)
    is_enabled: bool = True


@dataclass
class CostRouter:
    """成本路由器 — 根据任务复杂度选择最优 Provider。"""

    candidates: list[ProviderCandidate] = field(default_factory=list)

    def classify(self, text: str) -> ModelTier:
        """对输入文本进行复杂度分类。"""
        return classify_complexity(text)

    def recommend(
        self,
        text: str,
        required_capabilities: list[str] | None = None,
    ) -> ProviderCandidate | None:
        """推荐最适合的 Provider。

        1. 对输入文本分类得到目标层级
        2. 从候选列表中筛选启用的、层级匹配的 Provider
        3. 如果指定了 required_capabilities，进一步过滤
        4. 层级精确匹配优先；无精确匹配则向上升级
        """
        target_tier = self.classify(text)
        return self._select(target_tier, required_capabilities)

    def recommend_by_tier(
        self,
        tier: ModelTier,
        required_capabilities: list[str] | None = None,
    ) -> ProviderCandidate | None:
        """按指定层级推荐 Provider（跳过分类）。"""
        return self._select(tier, required_capabilities)

    def _select(
        self,
        target_tier: ModelTier,
        required_capabilities: list[str] | None = None,
    ) -> ProviderCandidate | None:
        """内部选择逻辑。"""
        enabled = [c for c in self.candidates if c.is_enabled]
        if not enabled:
            return None

        # 按能力过滤
        if required_capabilities:
            req_set = set(required_capabilities)
            enabled = [c for c in enabled if req_set.issubset(set(c.capabilities))]
            if not enabled:
                return None

        # 精确匹配
        exact = [c for c in enabled if c.model_tier == target_tier]
        if exact:
            return exact[0]

        target_order = _TIER_ORDER.get(target_tier, 1)

        # 优先选择比目标层级高的（向上升级）
        higher = [c for c in enabled if _TIER_ORDER.get(c.model_tier, 1) >= target_order]
        if higher:
            higher.sort(key=lambda c: _TIER_ORDER.get(c.model_tier, 1))
            return higher[0]

        # 所有候选层级都低于目标 → 降级兜底，返回最高层级的候选
        enabled.sort(key=lambda c: _TIER_ORDER.get(c.model_tier, 1), reverse=True)
        return enabled[0] if enabled else None
