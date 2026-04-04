"""AlertRule / AlertEvent 服务 — 告警规则 CRUD + 阈值检测。"""

from __future__ import annotations

from typing import Any

import logging
import operator as op_module
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertEvent, AlertRule
from app.schemas.alert import AlertRuleCreate, AlertRuleUpdate

logger = logging.getLogger(__name__)

# 运算符映射
_OPERATOR_MAP = {
    ">": op_module.gt,
    ">=": op_module.ge,
    "<": op_module.lt,
    "<=": op_module.le,
    "==": op_module.eq,
}


# ---------------------------------------------------------------------------
# AlertRule CRUD
# ---------------------------------------------------------------------------


async def list_alert_rules(
    db: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    is_enabled: bool | None = None,
    severity: str | None = None,
    org_id: uuid.UUID | None = None,
) -> tuple[list[AlertRule], int]:
    """分页获取告警规则列表。"""
    q = select(AlertRule).where(AlertRule.is_deleted == False)  # noqa: E712

    if is_enabled is not None:
        q = q.where(AlertRule.is_enabled == is_enabled)
    if severity is not None:
        q = q.where(AlertRule.severity == severity)
    if org_id is not None:
        q = q.where(AlertRule.org_id == org_id)

    count_q = select(func.count()).select_from(q.subquery())
    total = await db.scalar(count_q) or 0
    result = await db.execute(q.order_by(AlertRule.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total


async def get_alert_rule(
    db: AsyncSession,
    rule_id: uuid.UUID,
    *,
    org_id: uuid.UUID | None = None,
) -> AlertRule | None:
    """按 ID 获取告警规则。传入 org_id 时强制租户隔离。"""
    q = select(AlertRule).where(AlertRule.id == rule_id, AlertRule.is_deleted == False)  # noqa: E712
    if org_id is not None:
        q = q.where(AlertRule.org_id == org_id)
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def create_alert_rule(
    db: AsyncSession,
    data: AlertRuleCreate,
    *,
    org_id: uuid.UUID | None = None,
) -> AlertRule:
    """创建告警规则。"""
    rule = AlertRule(
        name=data.name,
        description=data.description,
        metric=data.metric,
        operator=data.operator,
        threshold=data.threshold,
        window_minutes=data.window_minutes,
        agent_name=data.agent_name,
        severity=data.severity,
        cooldown_minutes=data.cooldown_minutes,
        notification_config=data.notification_config,
        org_id=org_id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def update_alert_rule(db: AsyncSession, rule: AlertRule, data: AlertRuleUpdate) -> AlertRule:
    """更新告警规则。"""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)
    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_alert_rule(db: AsyncSession, rule: AlertRule) -> None:
    """软删除告警规则。"""
    rule.is_deleted = True
    rule.deleted_at = datetime.now(timezone.utc)
    await db.commit()


# ---------------------------------------------------------------------------
# AlertEvent 查询
# ---------------------------------------------------------------------------


async def list_alert_events(
    db: AsyncSession,
    *,
    rule_id: uuid.UUID | None = None,
    severity: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[AlertEvent], int]:
    """分页查询告警事件。"""
    q = select(AlertEvent)
    if rule_id is not None:
        q = q.where(AlertEvent.rule_id == rule_id)
    if severity is not None:
        q = q.where(AlertEvent.severity == severity)

    count_q = select(func.count()).select_from(q.subquery())
    total = await db.scalar(count_q) or 0
    result = await db.execute(q.order_by(AlertEvent.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total


# ---------------------------------------------------------------------------
# 阈值检测引擎
# ---------------------------------------------------------------------------

# 指标到 SQL 的映射
_METRIC_SQL: dict[str, str] = {
    "error_rate": """
        SELECT COALESCE(
            CAST(SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS FLOAT)
            / NULLIF(COUNT(*), 0) * 100,
            0
        ) AS val
        FROM trace_records
        WHERE created_at >= :since {agent_filter}
    """,
    "avg_duration_ms": """
        SELECT COALESCE(AVG(duration_ms), 0) AS val
        FROM trace_records
        WHERE created_at >= :since {agent_filter}
    """,
    "total_cost": """
        SELECT COALESCE(SUM(total_cost), 0) AS val
        FROM token_usage_logs
        WHERE timestamp >= :since {agent_filter}
    """,
    "total_tokens": """
        SELECT COALESCE(SUM(total_tokens), 0) AS val
        FROM token_usage_logs
        WHERE timestamp >= :since {agent_filter}
    """,
    "trace_count": """
        SELECT COUNT(*) AS val
        FROM trace_records
        WHERE created_at >= :since {agent_filter}
    """,
}


async def _compute_metric(
    db: AsyncSession,
    metric: str,
    window_minutes: int,
    agent_name: str | None,
) -> float:
    """计算指定指标在时间窗口内的值。"""
    sql_template = _METRIC_SQL.get(metric)
    if sql_template is None:
        return 0.0

    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    agent_filter = ""
    params: dict[str, Any] = {"since": since}

    if agent_name is not None:
        agent_filter = "AND agent_name = :agent_name"
        params["agent_name"] = agent_name

    sql = sql_template.replace("{agent_filter}", agent_filter)
    try:
        result = await db.execute(text(sql), params)
    except Exception:
        logger.exception("指标查询失败: metric=%s", metric)
        return 0.0
    row = result.one_or_none()
    return float(row[0]) if row else 0.0


async def evaluate_rule(
    db: AsyncSession,
    rule: AlertRule,
    *,
    auto_commit: bool = True,
) -> AlertEvent | None:
    """评估单条告警规则，触发时创建 AlertEvent。

    Args:
        db: 数据库会话
        rule: 告警规则
        auto_commit: 是否自动提交。批量评估时设为 False 由调用方统一提交。

    Returns:
        触发时返回 AlertEvent，否则 None
    """
    # 冷却检查
    if rule.last_triggered_at is not None:
        cooldown_until = rule.last_triggered_at + timedelta(minutes=rule.cooldown_minutes)
        if datetime.now(timezone.utc) < cooldown_until:
            return None

    metric_value = await _compute_metric(db, rule.metric, rule.window_minutes, rule.agent_name)

    compare_fn = _OPERATOR_MAP.get(rule.operator)
    if compare_fn is None:
        return None

    if not compare_fn(metric_value, rule.threshold):
        return None

    # 触发告警
    agent_desc = f" (Agent: {rule.agent_name})" if rule.agent_name else ""
    message = (
        f"告警触发：{rule.name} — "
        f"{rule.metric} = {metric_value:.2f} {rule.operator} {rule.threshold}{agent_desc}"
    )

    event = AlertEvent(
        rule_id=rule.id,
        metric_value=metric_value,
        threshold=rule.threshold,
        severity=rule.severity,
        agent_name=rule.agent_name,
        message=message,
    )
    db.add(event)
    rule.last_triggered_at = datetime.now(timezone.utc)

    if auto_commit:
        await db.commit()
        await db.refresh(event)

    logger.warning("告警: %s", message)
    return event


async def evaluate_all_rules(db: AsyncSession) -> list[AlertEvent]:
    """评估所有启用的告警规则，批量提交。"""
    result = await db.execute(
        select(AlertRule).where(
            AlertRule.is_enabled == True,  # noqa: E712
            AlertRule.is_deleted == False,  # noqa: E712
        )
    )
    rules = list(result.scalars().all())

    events = []
    for rule in rules:
        try:
            event = await evaluate_rule(db, rule, auto_commit=False)
            if event is not None:
                events.append(event)
        except Exception:
            logger.exception("评估规则 %s 失败", rule.id)

    if events:
        await db.commit()
        for event in events:
            await db.refresh(event)

    return events
