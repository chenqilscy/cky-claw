"""审批 IM 通知服务 — 当审批请求创建时通过 IM 渠道推送通知。"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.models.im_channel import IMChannel
from app.services.channel_adapters import get_adapter

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _format_approval_message(
    agent_name: str,
    trigger: str,
    content: dict[str, Any],
    approval_id: str,
) -> str:
    """格式化审批通知消息文本。"""
    tool_name = content.get("tool_name", "未知工具")
    arguments = content.get("arguments", {})

    # 对可能包含敏感信息的参数进行脱敏
    _SENSITIVE_KEYS = {"password", "secret", "token", "api_key", "key", "credential", "auth"}
    safe_args = {}
    for k, v in (arguments if isinstance(arguments, dict) else {}).items():
        if any(s in k.lower() for s in _SENSITIVE_KEYS):
            safe_args[k] = "***"
        else:
            safe_args[k] = v

    # 构建参数摘要（最多 200 字符）
    args_str = str(safe_args) if safe_args else str(arguments)
    if len(args_str) > 200:
        args_str = args_str[:197] + "..."

    lines = [
        "🔔 Kasaya 审批通知",
        f"Agent: {agent_name}",
        f"触发: {trigger}",
        f"工具: {tool_name}",
        f"参数: {args_str}",
        f"审批 ID: {approval_id}",
        "",
        "请登录 Kasaya 平台进行审批操作。",
    ]
    return "\n".join(lines)


async def notify_approval_via_im(
    db: AsyncSession,
    *,
    agent_name: str,
    trigger: str,
    content: dict[str, Any],
    approval_id: str,
) -> int:
    """查找对应 Agent 绑定的 IM 渠道（notify_approvals=True），发送审批通知。

    返回成功发送的渠道数量。不抛出异常 — 发送失败仅记录日志。
    """
    # 查找启用了审批通知的 IM 渠道
    stmt = (
        select(IMChannel)
        .where(
            IMChannel.is_enabled.is_(True),
            IMChannel.is_deleted.is_(False),
            IMChannel.notify_approvals.is_(True),
        )
    )
    # 如果能匹配到 Agent，按 agent_name 查找绑定的渠道也需要关联查 agent 表
    # 这里采用"所有启用审批通知的渠道都通知"策略，用 agent_name 过滤在消息中体现
    result = await db.execute(stmt)
    channels: list[IMChannel] = list(result.scalars().all())

    if not channels:
        logger.debug("无启用审批通知的 IM 渠道，跳过通知")
        return 0

    message = _format_approval_message(agent_name, trigger, content, approval_id)
    sent_count = 0

    async def _send_one(channel: IMChannel) -> bool:
        """向单个渠道发送通知。"""
        adapter = get_adapter(channel.channel_type)
        if adapter is None:
            logger.warning("渠道 %s 的 channel_type '%s' 无可用适配器", channel.name, channel.channel_type)
            return False

        recipient_id = channel.approval_recipient_id
        if not recipient_id:
            logger.warning("渠道 %s 未配置 approval_recipient_id，跳过", channel.name)
            return False

        try:
            ok = await adapter.send_message(channel.app_config, recipient_id, message)
            if ok:
                logger.info("审批通知已发送到渠道 %s (recipient=%s)", channel.name, recipient_id)
            else:
                logger.warning("渠道 %s 发送审批通知返回失败", channel.name)
            return ok
        except Exception:
            logger.exception("渠道 %s 发送审批通知异常", channel.name)
            return False

    # 并发发送
    results = await asyncio.gather(*[_send_one(ch) for ch in channels], return_exceptions=True)
    for r in results:
        if r is True:
            sent_count += 1

    logger.info("审批通知完成: %d/%d 渠道成功", sent_count, len(channels))
    return sent_count
