"""沙箱执行 API 路由。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.schemas.sandbox import SandboxExecRequest, SandboxExecResponse
from ckyclaw_framework.sandbox import LocalSandbox, SandboxConfig

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/api/v1/sandbox", tags=["sandbox"])


@router.post("/execute", response_model=SandboxExecResponse)
async def execute_code(
    data: SandboxExecRequest,
    _user: User = Depends(get_current_user),
) -> SandboxExecResponse:
    """在沙箱中执行代码。"""
    config = SandboxConfig(timeout=data.timeout, network_enabled=False)
    sandbox = LocalSandbox(config=config)
    try:
        result = await sandbox.execute(data.code, language=data.language)
        return SandboxExecResponse(
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=result.timed_out,
            duration_ms=result.duration_ms,
        )
    finally:
        await sandbox.cleanup()
