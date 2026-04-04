"""TeamProtocol — 团队协作协议枚举。"""

from __future__ import annotations

from enum import Enum


class TeamProtocol(str, Enum):
    """Agent Team 协作协议。"""

    SEQUENTIAL = "sequential"
    """顺序执行：按 members 顺序依次运行，上一个输出作为下一个输入。"""

    PARALLEL = "parallel"
    """并行执行：所有 members 同时运行，汇总所有输出。"""

    COORDINATOR = "coordinator"
    """协调者模式：coordinator Agent 自主决定调用哪些 member（通过 as_tool）。"""
