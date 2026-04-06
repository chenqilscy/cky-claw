"""Intent Detection — Agent 意图检测与飘移处理。

在多轮对话中自动检测用户意图是否偏离初始主题，当飘移分数超过阈值时触发回调。

典型用法::

    from ckyclaw_framework.intent import KeywordIntentDetector

    detector = KeywordIntentDetector()
    config = RunConfig(intent_detector=detector, drift_threshold=0.6)
    result = await Runner.run(agent, "帮我写一个排序算法", config=config)
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ckyclaw_framework.model.message import Message, MessageRole


@dataclass(frozen=True)
class IntentSignal:
    """意图检测结果信号。"""

    original_keywords: frozenset[str] = field(default_factory=frozenset)
    """原始意图提取的关键词"""

    current_keywords: frozenset[str] = field(default_factory=frozenset)
    """最近消息提取的关键词"""

    drift_score: float = 0.0
    """飘移分数 0.0（完全一致）~1.0（完全偏离）。"""

    is_drifted: bool = False
    """是否判定为飘移。"""


class IntentDetector(ABC):
    """意图检测器抽象接口。"""

    @abstractmethod
    async def detect(
        self,
        messages: list[Message],
        *,
        threshold: float = 0.6,
    ) -> IntentSignal:
        """分析消息历史并判断是否发生意图飘移。

        Args:
            messages: 完整消息历史
            threshold: 飘移阈值（0~1），分数超过此值判定为飘移

        Returns:
            IntentSignal 信号
        """


# ---------------------------------------------------------------------------
# 停用词（中英文混合，轻量级）
# ---------------------------------------------------------------------------

_STOP_WORDS: frozenset[str] = frozenset({
    # 中文
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "他", "她", "它", "们", "那", "么", "什么", "吗", "啊", "吧", "呢",
    "可以", "能", "把", "被", "让", "从", "这个", "那个", "这些", "那些", "如何",
    "怎么", "为什么", "哪个", "哪些", "帮", "帮我", "请", "请问",
    # 英文
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "and", "but", "or",
    "not", "no", "so", "if", "then", "than", "too", "very", "just",
    "about", "it", "this", "that", "he", "she", "they", "we", "you", "i",
    "me", "my", "your", "his", "her", "its", "our", "their", "what",
    "which", "who", "how", "when", "where", "why", "please", "help",
})


def _extract_keywords(text: str, max_keywords: int = 20) -> frozenset[str]:
    """从文本中提取关键词（去停用词 + 去短标点）。

    中文采用 bigram（二元组）切分，英文按空格分词。
    """
    tokens: list[str] = []
    # 英文单词
    for word in re.findall(r"[a-zA-Z]+", text.lower()):
        if word not in _STOP_WORDS and len(word) > 1:
            tokens.append(word)
    # 中文 bigram
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", text)
    for run in chinese_runs:
        for i in range(len(run) - 1):
            bigram = run[i : i + 2]
            if bigram not in _STOP_WORDS:
                tokens.append(bigram)
        # 单字中文词（长度为 1 的 run）跳过
    return frozenset(tokens[:max_keywords])


def _compute_drift_score(
    original: frozenset[str], current: frozenset[str]
) -> float:
    """计算关键词集合的飘移分数。

    使用 1 - Jaccard 系数。两集合完全一样返回 0，完全不同返回 1。
    """
    if not original and not current:
        return 0.0
    if not original or not current:
        return 1.0
    intersection = original & current
    union = original | current
    jaccard = len(intersection) / len(union)
    return round(1.0 - jaccard, 4)


class KeywordIntentDetector(IntentDetector):
    """基于关键词重叠度的轻量意图飘移检测器。

    算法：
    1. 从首条 user 消息提取关键词作为原始意图
    2. 从最近 N 条 user 消息提取关键词作为当前意图
    3. 计算 1 - Jaccard(原始, 当前) 作为飘移分数
    4. 分数 >= threshold 时判定飘移
    """

    def __init__(self, recent_window: int = 3) -> None:
        """初始化检测器。

        Args:
            recent_window: 提取当前意图使用的最近 user 消息数量
        """
        self._recent_window = max(1, recent_window)

    async def detect(
        self,
        messages: list[Message],
        *,
        threshold: float = 0.6,
    ) -> IntentSignal:
        """检测消息历史中的意图飘移。"""
        user_messages = [m for m in messages if m.role == MessageRole.USER and m.content]

        if len(user_messages) < 2:
            # 只有 0-1 条 user 消息，无法判断飘移
            return IntentSignal()

        # 原始意图：首条 user 消息
        original_kw = _extract_keywords(user_messages[0].content)
        # 当前意图：最近 N 条 user 消息
        recent = user_messages[-self._recent_window :]
        current_text = " ".join(m.content for m in recent)
        current_kw = _extract_keywords(current_text)

        drift_score = _compute_drift_score(original_kw, current_kw)

        return IntentSignal(
            original_keywords=original_kw,
            current_keywords=current_kw,
            drift_score=drift_score,
            is_drifted=drift_score >= threshold,
        )
