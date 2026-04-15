"""数据导出 API — Token 用量 / 运行记录 CSV 导出。"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from collections.abc import Iterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission

router = APIRouter(prefix="/api/v1/export", tags=["export"])


def _sanitize_csv_cell(value: Any) -> str:
    """防止 CSV 注入 — 对以 =, +, -, @ 开头的值添加单引号前缀。"""
    s = str(value) if value is not None else ""
    if s and s[0] in ("=", "+", "-", "@"):
        return f"'{s}"
    return s


@router.get(
    "/token-usage",
    dependencies=[Depends(require_permission("token_usage", "read"))],
    summary="导出 Token 用量数据为 CSV",
)
async def export_token_usage(
    db: AsyncSession = Depends(get_db),
    agent_name: str | None = Query(None),
    user_id: UUID | None = Query(None),
    model: str | None = Query(None),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
) -> StreamingResponse:
    """导出 Token 用量明细为 CSV 文件。"""
    from app.services.token_usage import list_token_usage

    # 获取全量数据（最多 10000 条防止滥用）
    records, total = await list_token_usage(
        db,
        agent_name=agent_name,
        user_id=user_id,
        model=model,
        start_time=start_time,
        end_time=end_time,
        limit=10000,
        offset=0,
    )

    def generate() -> Iterator[str]:
        """流式生成 CSV 内容。"""
        buf = io.StringIO()
        writer = csv.writer(buf)

        # 表头
        headers = [
            "时间", "Agent", "模型", "Prompt Tokens",
            "Completion Tokens", "Total Tokens",
            "Prompt Cost", "Completion Cost", "Total Cost",
            "Session ID", "Trace ID",
        ]
        writer.writerow(headers)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)

        # 数据行
        for rec in records:
            row = [
                _sanitize_csv_cell(rec.timestamp.isoformat() if rec.timestamp else ""),
                _sanitize_csv_cell(rec.agent_name or ""),
                _sanitize_csv_cell(rec.model or ""),
                rec.prompt_tokens or 0,
                rec.completion_tokens or 0,
                rec.total_tokens or 0,
                f"{rec.prompt_cost:.6f}" if rec.prompt_cost else "0",
                f"{rec.completion_cost:.6f}" if rec.completion_cost else "0",
                f"{rec.total_cost:.6f}" if rec.total_cost else "0",
                _sanitize_csv_cell(str(rec.session_id) if rec.session_id else ""),
                _sanitize_csv_cell(rec.trace_id or ""),
            ]
            writer.writerow(row)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    filename = f"token_usage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


@router.get(
    "/runs",
    dependencies=[Depends(require_permission("traces", "read"))],
    summary="导出运行记录为 CSV",
)
async def export_runs(
    db: AsyncSession = Depends(get_db),
    agent_name: str | None = Query(None),
    session_id: UUID | None = Query(None),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
) -> StreamingResponse:
    """导出 Trace 运行记录为 CSV 文件。"""
    from app.services.trace import list_traces

    records, total = await list_traces(
        db,
        agent_name=agent_name,
        session_id=session_id,
        start_time=start_time,
        end_time=end_time,
        limit=10000,
        offset=0,
    )

    def generate() -> Iterator[str]:
        """流式生成 CSV 内容。"""
        buf = io.StringIO()
        writer = csv.writer(buf)

        headers = [
            "Trace ID", "Agent", "Session ID", "状态",
            "开始时间", "结束时间", "耗时(ms)",
            "Span 数",
        ]
        writer.writerow(headers)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)

        for rec in records:
            duration_ms = ""
            if rec.start_time and rec.end_time:
                duration_ms = str(int((rec.end_time - rec.start_time).total_seconds() * 1000))

            row = [
                _sanitize_csv_cell(str(rec.id)),
                _sanitize_csv_cell(getattr(rec, "agent_name", "") or ""),
                _sanitize_csv_cell(str(rec.session_id) if rec.session_id else ""),
                _sanitize_csv_cell(getattr(rec, "status", "") or ""),
                _sanitize_csv_cell(rec.start_time.isoformat() if rec.start_time else ""),
                _sanitize_csv_cell(rec.end_time.isoformat() if rec.end_time else ""),
                duration_ms,
                getattr(rec, "span_count", 0) or 0,
            ]
            writer.writerow(row)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    filename = f"runs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )
