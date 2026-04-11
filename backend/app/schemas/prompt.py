"""Prompt 模板相关请求/响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PromptPreviewRequest(BaseModel):
    """Prompt 渲染预览请求。"""

    variables: dict[str, Any] = Field(default_factory=dict, description="变量名到值的映射")


class PromptPreviewResponse(BaseModel):
    """Prompt 渲染预览响应。"""

    rendered: str = Field(..., description="渲染后的 Prompt 文本")
    warnings: list[str] = Field(default_factory=list, description="渲染警告")


class PromptValidateRequest(BaseModel):
    """Prompt 模板校验请求。"""

    instructions: str = Field(..., description="包含 {{variable}} 的模板文本")
    variables: list[dict[str, Any]] = Field(default_factory=list, description="变量定义列表")


class PromptValidateResponse(BaseModel):
    """Prompt 模板校验响应。"""

    valid: bool = Field(..., description="是否校验通过")
    errors: list[str] = Field(default_factory=list, description="错误列表")
    warnings: list[str] = Field(default_factory=list, description="警告列表")
    referenced_variables: list[str] = Field(default_factory=list, description="模板中引用的变量")
