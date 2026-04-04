"""沙箱执行 Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SandboxExecRequest(BaseModel):
    """沙箱执行请求。"""

    code: str = Field(..., min_length=1, max_length=100_000, description="要执行的代码")
    language: str = Field("python", description="编程语言")
    timeout: int = Field(30, ge=1, le=300, description="超时（秒）")


class SandboxExecResponse(BaseModel):
    """沙箱执行响应。"""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_ms: float
