"""会话管理。"""

from ckyclaw_framework.session.history_trimmer import HistoryTrimConfig, HistoryTrimmer, HistoryTrimStrategy
from ckyclaw_framework.session.in_memory import InMemorySessionBackend
from ckyclaw_framework.session.session import Session, SessionBackend, SessionMetadata

__all__ = [
    "HistoryTrimConfig",
    "HistoryTrimStrategy",
    "HistoryTrimmer",
    "InMemorySessionBackend",
    "Session",
    "SessionBackend",
    "SessionMetadata",
]
