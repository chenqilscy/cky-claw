"""Guardrail 规则 CRUD 服务。"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.guardrail import GuardrailRule

VALID_TYPES = {"input", "output", "tool"}
VALID_MODES = {"regex", "keyword"}
MAX_PATTERN_LENGTH = 500


def _validate_config(mode: str, config: dict) -> None:
    """校验 config 与 mode 的匹配性。"""
    if mode == "regex":
        patterns = config.get("patterns", [])
        if not patterns:
            raise ValidationError("regex 模式必须提供 patterns 列表")
        for p in patterns:
            if not isinstance(p, str):
                raise ValidationError(f"pattern 必须是字符串，收到 {type(p).__name__}")
            if len(p) > MAX_PATTERN_LENGTH:
                raise ValidationError(f"pattern 长度不能超过 {MAX_PATTERN_LENGTH} 字符")
            try:
                re.compile(p)
            except re.error as e:
                raise ValidationError(f"无效的正则表达式 '{p}': {e}") from e
    elif mode == "keyword":
        keywords = config.get("keywords", [])
        if not keywords:
            raise ValidationError("keyword 模式必须提供 keywords 列表")
        for kw in keywords:
            if not isinstance(kw, str) or not kw.strip():
                raise ValidationError("keyword 必须是非空字符串")


async def create_guardrail_rule(
    db: AsyncSession,
    *,
    name: str,
    description: str = "",
    type_: str = "input",
    mode: str = "regex",
    config: dict | None = None,
) -> GuardrailRule:
    """创建 Guardrail 规则。"""
    if type_ not in VALID_TYPES:
        raise ValidationError(f"type 必须是 {VALID_TYPES} 之一")
    if mode not in VALID_MODES:
        raise ValidationError(f"mode 必须是 {VALID_MODES} 之一")

    config = config or {}
    _validate_config(mode, config)

    # 唯一性检查
    existing = (await db.execute(
        select(GuardrailRule).where(GuardrailRule.name == name)
    )).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"规则名 '{name}' 已存在")

    rule = GuardrailRule(
        name=name,
        description=description,
        type=type_,
        mode=mode,
        config=config,
    )
    db.add(rule)
    await db.flush()
    return rule


async def list_guardrail_rules(
    db: AsyncSession,
    *,
    type_filter: str | None = None,
    mode_filter: str | None = None,
    enabled_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[GuardrailRule], int]:
    """获取 Guardrail 规则列表。"""
    base = select(GuardrailRule)

    if type_filter is not None:
        base = base.where(GuardrailRule.type == type_filter)
    if mode_filter is not None:
        base = base.where(GuardrailRule.mode == mode_filter)
    if enabled_only:
        base = base.where(GuardrailRule.is_enabled == True)  # noqa: E712

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = base.order_by(GuardrailRule.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(data_stmt)).scalars().all()

    return list(rows), total


async def get_guardrail_rule(
    db: AsyncSession,
    rule_id: uuid.UUID,
) -> GuardrailRule:
    """获取单个 Guardrail 规则。"""
    stmt = select(GuardrailRule).where(GuardrailRule.id == rule_id)
    rule = (await db.execute(stmt)).scalar_one_or_none()
    if rule is None:
        raise NotFoundError(f"Guardrail 规则 '{rule_id}' 不存在")
    return rule


async def get_guardrail_rules_by_names(
    db: AsyncSession,
    names: list[str],
) -> list[GuardrailRule]:
    """根据名称列表批量获取已启用的 Guardrail 规则。"""
    if not names:
        return []
    stmt = select(GuardrailRule).where(
        GuardrailRule.name.in_(names),
        GuardrailRule.is_enabled == True,  # noqa: E712
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def update_guardrail_rule(
    db: AsyncSession,
    rule_id: uuid.UUID,
    *,
    description: str | None = None,
    type_: str | None = None,
    mode: str | None = None,
    config: dict | None = None,
    is_enabled: bool | None = None,
) -> GuardrailRule:
    """更新 Guardrail 规则。"""
    rule = await get_guardrail_rule(db, rule_id)

    if type_ is not None:
        if type_ not in VALID_TYPES:
            raise ValidationError(f"type 必须是 {VALID_TYPES} 之一")
        rule.type = type_

    if mode is not None:
        if mode not in VALID_MODES:
            raise ValidationError(f"mode 必须是 {VALID_MODES} 之一")
        rule.mode = mode

    effective_mode = mode or rule.mode
    if config is not None:
        _validate_config(effective_mode, config)
        rule.config = config

    if description is not None:
        rule.description = description
    if is_enabled is not None:
        rule.is_enabled = is_enabled

    await db.flush()
    return rule


async def delete_guardrail_rule(
    db: AsyncSession,
    rule_id: uuid.UUID,
) -> None:
    """删除 Guardrail 规则。"""
    rule = await get_guardrail_rule(db, rule_id)
    await db.delete(rule)
    await db.flush()
