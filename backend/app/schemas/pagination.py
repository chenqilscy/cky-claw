"""通用分页响应基类。"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse[T](BaseModel):
    """标准分页响应。

    统一所有列表端点的分页字段名称和语义：
    - data: 当前页数据列表
    - total: 符合条件的总记录数
    - limit: 每页大小
    - offset: 偏移量（从 0 开始）
    """

    data: list[T] = Field(default_factory=list, description="当前页数据列表")
    total: int = Field(default=0, description="总记录数")
    limit: int = Field(default=20, description="每页大小")
    offset: int = Field(default=0, description="偏移量")
