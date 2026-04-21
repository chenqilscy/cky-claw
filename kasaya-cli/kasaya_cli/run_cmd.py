"""kasaya run 子命令 — 运行 Agent 并输出结果。"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from kasaya_cli.client import KasayaClient

console = Console()


def run_command(
    agent_id: str = typer.Argument(help="Agent ID（UUID）"),
    message: str = typer.Argument(help="发送给 Agent 的消息"),
) -> None:
    """运行指定 Agent 并输出回复。"""
    client = KasayaClient()
    if not client.token:
        console.print("[red]未登录，请先执行 kasaya login 或设置 KASAYA_TOKEN 环境变量[/red]")
        raise typer.Exit(code=1)

    try:
        with console.status("Agent 运行中..."):
            result = client.run_agent(agent_id, message)
    except RuntimeError as e:
        console.print(f"[red]运行失败: {e}[/red]")
        raise typer.Exit(code=1) from e

    # 提取回复内容
    output = result.get("output", result.get("response", ""))
    if not output:
        # 尝试从 messages 中提取最后一条助手消息
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") in ("assistant", "agent"):
                output = msg.get("content", "")
                break

    if output:
        console.print(Panel(Markdown(output), title="Agent 回复", border_style="green"))
    else:
        console.print("[yellow]Agent 未返回回复内容[/yellow]")
        console.print(result)

    # 显示 token 用量（如有）
    usage = result.get("usage") or result.get("token_usage")
    if usage:
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        console.print(
            f"\n[dim]Token 用量: prompt={prompt_tokens}, completion={completion_tokens}, "
            f"total={prompt_tokens + completion_tokens}[/dim]"
        )
