"""意图检测 API — 测试意图飘移检测能力。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.deps import get_current_user
from kasaya.intent import IntentSignal, KeywordIntentDetector
from kasaya.model.message import Message, MessageRole

router = APIRouter(prefix="/api/v1/intent", tags=["intent"])

_detector = KeywordIntentDetector()


# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------


class DetectRequest(BaseModel):
    """意图飘移检测请求。"""

    original_intent: str = Field(..., min_length=1, max_length=5000, description="原始意图文本")
    current_message: str = Field(..., min_length=1, max_length=5000, description="当前消息文本")
    threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="飘移阈值")


class DetectResponse(BaseModel):
    """意图飘移检测响应。"""

    original_keywords: list[str] = Field(description="原始意图关键词")
    current_keywords: list[str] = Field(description="当前消息关键词")
    drift_score: float = Field(description="飘移分数 0.0~1.0")
    is_drifted: bool = Field(description="是否判定为飘移")
    threshold: float = Field(description="使用的阈值")


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@router.post("/detect", response_model=DetectResponse, summary="检测意图飘移")
async def detect_intent_drift(
    req: DetectRequest,
    _user: object = Depends(get_current_user),
) -> DetectResponse:
    """将原始意图和当前消息构造为消息序列，调用 KeywordIntentDetector 检测飘移。"""
    messages = [
        Message(role=MessageRole.USER, content=req.original_intent),
        Message(role=MessageRole.USER, content=req.current_message),
    ]
    signal: IntentSignal = await _detector.detect(messages, threshold=req.threshold)
    return DetectResponse(
        original_keywords=sorted(signal.original_keywords),
        current_keywords=sorted(signal.current_keywords),
        drift_score=signal.drift_score,
        is_drifted=signal.is_drifted,
        threshold=req.threshold,
    )
