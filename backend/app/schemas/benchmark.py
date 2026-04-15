"""Benchmark 评测请求/响应模型。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

# ─── Suite ───

class BenchmarkSuiteCreate(BaseModel):
    """创建评测套件。"""

    name: str = Field(..., max_length=120)
    description: str = Field("", max_length=2000)
    agent_name: str = Field("", max_length=120)
    model: str = Field("", max_length=120)
    config: dict | None = None
    tags: list[str] | None = None


class BenchmarkSuiteUpdate(BaseModel):
    """更新评测套件。"""

    name: str | None = Field(None, max_length=120)
    description: str | None = Field(None, max_length=2000)
    agent_name: str | None = Field(None, max_length=120)
    model: str | None = Field(None, max_length=120)
    config: dict | None = None
    tags: list[str] | None = None


class BenchmarkSuiteResponse(BaseModel):
    """评测套件响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    agent_name: str
    model: str
    config: dict | None
    tags: list | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class BenchmarkSuiteListResponse(BaseModel):
    """套件列表响应。"""

    data: list[BenchmarkSuiteResponse]
    total: int


# ─── Run ───

class BenchmarkRunCreate(BaseModel):
    """创建评测运行（通常由系统内部调用）。"""

    suite_id: uuid.UUID


class BenchmarkRunUpdate(BaseModel):
    """更新运行结果。"""

    status: str | None = Field(None, pattern="^(pending|running|completed|failed)$")
    total_cases: int | None = None
    passed_cases: int | None = None
    failed_cases: int | None = None
    error_cases: int | None = None
    overall_score: float | None = None
    pass_rate: float | None = None
    total_latency_ms: float | None = None
    total_tokens: int | None = None
    dimension_summaries: dict | None = None
    report: dict | None = None


class BenchmarkRunResponse(BaseModel):
    """评测运行响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    suite_id: uuid.UUID
    status: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    error_cases: int
    overall_score: float
    pass_rate: float
    total_latency_ms: float
    total_tokens: int
    dimension_summaries: dict | None
    report: dict | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BenchmarkRunListResponse(BaseModel):
    """运行列表响应。"""

    data: list[BenchmarkRunResponse]
    total: int


# ─── Dashboard ───

class BenchmarkDashboard(BaseModel):
    """Benchmark 仪表盘汇总。"""

    total_suites: int
    total_runs: int
    completed_runs: int
    avg_score: float
    avg_pass_rate: float
