"""Agent 管理命令。"""

from __future__ import annotations

from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from kasaya_cli.client import KasayaClient

console = Console()
agent_app = typer.Typer(name="agent", help="Agent 管理命令")


def _get_client() -> KasayaClient:
    """获取已认证的 API 客户端。"""
    return KasayaClient()


@agent_app.command(name="list")
def list_agents(
    limit: Annotated[int, typer.Option("--limit", "-l", help="每页数量")] = 20,
    offset: Annotated[int, typer.Option("--offset", help="偏移量")] = 0,
    url: Annotated[Optional[str], typer.Option("--url", help="Backend URL")] = None,
    token: Annotated[Optional[str], typer.Option("--token", "-t", help="JWT Token")] = None,
) -> None:
    """列出所有 Agent。"""
    client = KasayaClient(base_url=url, token=token)
    try:
        resp = client.list_agents(limit=limit, offset=offset)
    except RuntimeError as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        raise typer.Exit(code=1)

    agents = resp.get("data", [])
    total = resp.get("total", 0)

    if not agents:
        console.print("[dim]暂无 Agent。[/dim]")
        return

    table = Table(title=f"Agent 列表（{total} 条）")
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("名称", style="cyan")
    table.add_column("模型", style="green")
    table.add_column("状态", style="yellow")
    table.add_column("创建时间", style="dim")

    for a in agents:
        agent_id = str(a.get("id", ""))[:12]
        table.add_row(
            agent_id,
            a.get("name", "?"),
            a.get("model", "?"),
            "启用" if a.get("is_active", True) else "禁用",
            str(a.get("created_at", ""))[:19],
        )

    console.print(table)


@agent_app.command(name="get")
def get_agent(
    agent_id: Annotated[str, typer.Argument(help="Agent ID")],
    url: Annotated[Optional[str], typer.Option("--url", help="Backend URL")] = None,
    token: Annotated[Optional[str], typer.Option("--token", "-t", help="JWT Token")] = None,
) -> None:
    """查看单个 Agent 详情。"""
    client = KasayaClient(base_url=url, token=token)
    try:
        agent = client.get_agent(agent_id)
    except RuntimeError as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        raise typer.Exit(code=1)

    console.print(f"[bold cyan]Agent: {agent.get('name', '?')}[/bold cyan]")
    console.print(f"  ID:      {agent.get('id', '?')}")
    console.print(f"  模型:    {agent.get('model', '?')}")
    console.print(f"  指令:    {str(agent.get('instructions', ''))[:100]}...")
    console.print(f"  状态:    {'启用' if agent.get('is_active', True) else '禁用'}")
    console.print(f"  创建时间: {agent.get('created_at', '?')}")
