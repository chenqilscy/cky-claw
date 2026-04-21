"""CostRouter 成本路由单元测试。"""

from __future__ import annotations

import pytest

from kasaya.model.cost_router import (
    CostRouter,
    ModelTier,
    ProviderCandidate,
    classify_complexity,
)

# ═══════════════════════════════════════════════════════════════════
# classify_complexity 分类器测试
# ═══════════════════════════════════════════════════════════════════


class TestClassifyComplexity:
    """基于规则的复杂度分类器。"""

    def test_simple_short_text(self) -> None:
        """短文本分类为 SIMPLE。"""
        assert classify_complexity("你好") == ModelTier.SIMPLE

    def test_simple_greeting(self) -> None:
        """简单问候分类为 SIMPLE。"""
        assert classify_complexity("今天天气怎么样？") == ModelTier.SIMPLE

    def test_moderate_medium_text(self) -> None:
        """中等长度无特殊关键词 → MODERATE。"""
        text = (
            "请帮我写一段关于人工智能发展历史的介绍文章，要求涵盖从上世纪50年代到现在的主要里程碑事件，"
            "包括图灵测试的提出、专家系统的兴起、神经网络的复兴和大语言模型的突破等关键节点，字数在500字左右。"
        )
        assert classify_complexity(text) == ModelTier.MODERATE

    def test_complex_code(self) -> None:
        """包含 code 关键词 → COMPLEX。"""
        assert classify_complexity("请帮我写一段 Python 代码实现冒泡排序") == ModelTier.COMPLEX

    def test_complex_debug(self) -> None:
        """包含 debug 关键词 → COMPLEX。"""
        assert classify_complexity("请帮我调试这个函数") == ModelTier.COMPLEX

    def test_complex_refactor(self) -> None:
        """包含重构关键词 → COMPLEX。"""
        assert classify_complexity("请重构这段代码使其更简洁") == ModelTier.COMPLEX

    def test_reasoning_math(self) -> None:
        """包含数学关键词 → REASONING。"""
        assert classify_complexity("请证明勾股定理") == ModelTier.REASONING

    def test_reasoning_algorithm(self) -> None:
        """包含 algorithm 关键词 → REASONING。"""
        assert classify_complexity("describe the algorithm for Dijkstra shortest path") == ModelTier.REASONING

    def test_reasoning_strategy(self) -> None:
        """包含策略关键词 → REASONING。"""
        assert classify_complexity("请帮我制定一个策略来优化这个流程") == ModelTier.REASONING

    def test_multimodal_image(self) -> None:
        """包含图片关键词 → MULTIMODAL。"""
        assert classify_complexity("请描述这张图片的内容") == ModelTier.MULTIMODAL

    def test_multimodal_screenshot(self) -> None:
        """包含截图关键词 → MULTIMODAL。"""
        assert classify_complexity("请分析这个截图中的 UI 问题") == ModelTier.MULTIMODAL

    def test_multimodal_priority(self) -> None:
        """MULTIMODAL 优先于其他关键词。"""
        assert classify_complexity("请帮我分析这张图片中的数学推理") == ModelTier.MULTIMODAL

    def test_empty_string(self) -> None:
        """空字符串 → SIMPLE。"""
        assert classify_complexity("") == ModelTier.SIMPLE

    def test_case_insensitive(self) -> None:
        """关键词大小写不敏感。"""
        assert classify_complexity("Please write some CODE") == ModelTier.COMPLEX


# ═══════════════════════════════════════════════════════════════════
# CostRouter 推荐测试
# ═══════════════════════════════════════════════════════════════════


class TestCostRouter:
    """CostRouter 推荐逻辑。"""

    def _make_candidates(self) -> list[ProviderCandidate]:
        return [
            ProviderCandidate(name="gpt-4o-mini", model_tier=ModelTier.SIMPLE, capabilities=["text", "function_calling"]),
            ProviderCandidate(name="gpt-4o", model_tier=ModelTier.MODERATE, capabilities=["text", "code", "function_calling"]),
            ProviderCandidate(name="claude-3-opus", model_tier=ModelTier.COMPLEX, capabilities=["text", "code", "reasoning"]),
            ProviderCandidate(name="o1-pro", model_tier=ModelTier.REASONING, capabilities=["text", "reasoning"]),
            ProviderCandidate(name="gpt-4o-vision", model_tier=ModelTier.MULTIMODAL, capabilities=["text", "vision"]),
        ]

    def test_recommend_simple(self) -> None:
        """简单文本推荐 SIMPLE Provider。"""
        router = CostRouter(candidates=self._make_candidates())
        result = router.recommend("你好")
        assert result is not None
        assert result.name == "gpt-4o-mini"

    def test_recommend_complex(self) -> None:
        """包含代码关键词推荐 COMPLEX Provider。"""
        router = CostRouter(candidates=self._make_candidates())
        result = router.recommend("帮我写 Python 代码")
        assert result is not None
        assert result.name == "claude-3-opus"

    def test_recommend_with_capability(self) -> None:
        """过滤需要 vision 能力的 Provider。"""
        router = CostRouter(candidates=self._make_candidates())
        result = router.recommend("请描述这张图片", required_capabilities=["vision"])
        assert result is not None
        assert result.name == "gpt-4o-vision"

    def test_recommend_no_candidates(self) -> None:
        """无候选 Provider 返回 None。"""
        router = CostRouter(candidates=[])
        result = router.recommend("你好")
        assert result is None

    def test_recommend_capability_filter_no_match(self) -> None:
        """能力不匹配返回 None。"""
        router = CostRouter(candidates=[
            ProviderCandidate(name="simple", model_tier=ModelTier.SIMPLE, capabilities=["text"]),
        ])
        result = router.recommend("你好", required_capabilities=["vision"])
        assert result is None

    def test_recommend_fallback_upgrade(self) -> None:
        """精确匹配缺失时向上升级。"""
        # 只有 COMPLEX 和 REASONING，没有 SIMPLE
        router = CostRouter(candidates=[
            ProviderCandidate(name="complex", model_tier=ModelTier.COMPLEX, capabilities=["text"]),
            ProviderCandidate(name="reasoning", model_tier=ModelTier.REASONING, capabilities=["text"]),
        ])
        result = router.recommend("你好")  # 分类为 SIMPLE
        assert result is not None
        assert result.name == "complex"  # 升级到最低可用层级

    def test_recommend_disabled_filtered(self) -> None:
        """禁用的 Provider 被过滤。"""
        router = CostRouter(candidates=[
            ProviderCandidate(name="disabled", model_tier=ModelTier.SIMPLE, is_enabled=False),
            ProviderCandidate(name="enabled", model_tier=ModelTier.MODERATE, is_enabled=True),
        ])
        result = router.recommend("你好")
        assert result is not None
        assert result.name == "enabled"

    def test_recommend_by_tier(self) -> None:
        """按指定层级推荐。"""
        router = CostRouter(candidates=self._make_candidates())
        result = router.recommend_by_tier(ModelTier.REASONING)
        assert result is not None
        assert result.name == "o1-pro"

    def test_classify_method(self) -> None:
        """CostRouter.classify 方法。"""
        router = CostRouter()
        assert router.classify("你好") == ModelTier.SIMPLE
        assert router.classify("请帮我写代码") == ModelTier.COMPLEX


# ═══════════════════════════════════════════════════════════════════
# ModelTier 枚举测试
# ═══════════════════════════════════════════════════════════════════


class TestModelTier:
    """ModelTier 枚举值。"""

    def test_all_values(self) -> None:
        assert ModelTier.SIMPLE.value == "simple"
        assert ModelTier.MODERATE.value == "moderate"
        assert ModelTier.COMPLEX.value == "complex"
        assert ModelTier.REASONING.value == "reasoning"
        assert ModelTier.MULTIMODAL.value == "multimodal"

    def test_from_string(self) -> None:
        assert ModelTier("simple") == ModelTier.SIMPLE
        assert ModelTier("reasoning") == ModelTier.REASONING

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            ModelTier("mega")


# ═══════════════════════════════════════════════════════════════════
# ProviderCandidate 数据类测试
# ═══════════════════════════════════════════════════════════════════


class TestProviderCandidate:
    """ProviderCandidate 数据类。"""

    def test_defaults(self) -> None:
        c = ProviderCandidate(name="test", model_tier=ModelTier.SIMPLE)
        assert c.capabilities == []
        assert c.is_enabled is True

    def test_custom_fields(self) -> None:
        c = ProviderCandidate(
            name="test", model_tier=ModelTier.COMPLEX,
            capabilities=["text", "code"], is_enabled=False,
        )
        assert c.capabilities == ["text", "code"]
        assert c.is_enabled is False
