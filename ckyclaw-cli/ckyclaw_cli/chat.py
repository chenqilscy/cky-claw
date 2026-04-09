"""交互式 Agent 对话命令。"""

from __future__ import annotations

import asyncio
import sys
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from ckyclaw_framework import Agent, Runner

console = Console()


def chat_command(
    model: Annotated[str, typer.Option("--model", "-m", help="LLM 模型名称")] = "gpt-4o-mini",
    instructions: Annotated[str, typer.Option("--instructions", "-i", help="Agent 系统指令")] = "你是一个有帮助的 AI 助手。用中文回答。",
    name: Annotated[str, typer.Option("--name", "-n", help="Agent 名称")] = "ckyclaw-chat",
    max_turns: Annotated[int, typer.Option("--max-turns", help="最大对话轮数")] = 10,
    provider_key: Annotated[Optional[str], typer.Option("--api-key", "-k", help="LLM API Key（默认读取环境变量）")] = None,
) -> None:
    """与 Agent 进行交互式对话。支持多轮对话和流式输出。"""
    asyncio.run(_chat_loop(model, instructions, name, max_turns, provider_key))


async def _chat_loop(
    model: str,
    instructions: str,
    name: str,
    max_turns: int,
    provider_key: str | None,
) -> None:
    """异步对话主循环。"""
    agent = Agent(name=name, instructions=instructions, model=model)

    console.print(
        Panel(
            f"[bold cyan]CkyClaw Chat[/bold cyan]\n"
            f"模型: [green]{model}[/green]  Agent: [green]{name}[/green]\n"
            f"输入 [bold red]exit[/bold red] 或 [bold red]quit[/bold red] 退出，"
            f"[bold yellow]clear[/bold yellow] 清空历史",
            title="🤖 ckyclaw",
            border_style="cyan",
        )
    )

    history: list[dict[str, str]] = []

    while True:
        try:
            user_input = _get_input()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]再见！[/dim]")
            break

        if not user_input.strip():
            continue

        cmd = user_input.strip().lower()
        if cmd in ("exit", "quit", "/exit", "/quit"):
            console.print("[dim]再见！[/dim]")
            break
        if cmd in ("clear", "/clear"):
            history.clear()
            console.print("[dim]历史已清空。[/dim]")
            continue

        history.append({"role": "user", "content": user_input})

        try:
            result = await Runner.run(
                agent,
                input=history,
                max_turns=max_turns,
            )
            output = result.final_output or "(无输出)"
        except Exception as e:
            output = f"[错误] {e}"
            console.print(f"[bold red]{output}[/bold red]")
            continue

        history.append({"role": "assistant", "content": output})

        console.print()
        console.print(Panel(Markdown(output), title=f"[bold green]{name}[/bold green]", border_style="green"))
        console.print()

        if result.token_usage:
            usage = result.token_usage
            console.print(
                Text(
                    f"  tokens: {usage.prompt_tokens} prompt + {usage.completion_tokens} completion = {usage.total_tokens} total",
                    style="dim",
                )
            )


def _get_input() -> str:
    """读取用户输入，支持多行（以空行结束）。"""
    try:
        line = console.input("[bold blue]You>[/bold blue] ")
    except EOFError:
        raise
    return line
