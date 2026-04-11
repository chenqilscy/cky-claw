"""Provider 管理命令。"""

from __future__ import annotations

from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from ckyclaw_cli.client import CkyClawClient

console = Console()
provider_app = typer.Typer(name="provider", help="Provider 管理命令")


@provider_app.command(name="list")
def list_providers(
    limit: Annotated[int, typer.Option("--limit", "-l", help="每页数量")] = 20,
    url: Annotated[Optional[str], typer.Option("--url", help="Backend URL")] = None,
    token: Annotated[Optional[str], typer.Option("--token", "-t", help="JWT Token")] = None,
) -> None:
    """列出所有 Provider。"""
    client = CkyClawClient(base_url=url, token=token)
    try:
        resp = client.list_providers(limit=limit)
    except RuntimeError as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        raise typer.Exit(code=1)

    providers = resp.get("data", [])
    total = resp.get("total", 0)

    if not providers:
        console.print("[dim]暂无 Provider。[/dim]")
        return

    table = Table(title=f"Provider 列表（{total} 条）")
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("名称", style="cyan")
    table.add_column("类型", style="green")
    table.add_column("状态", style="yellow")
    table.add_column("Base URL", style="dim")

    for p in providers:
        provider_id = str(p.get("id", ""))[:12]
        table.add_row(
            provider_id,
            p.get("name", "?"),
            p.get("provider_type", "?"),
            "启用" if p.get("is_enabled", True) else "禁用",
            p.get("base_url", "-") or "-",
        )

    console.print(table)


@provider_app.command(name="test")
def test_provider(
    provider_id: Annotated[str, typer.Argument(help="Provider ID")],
    url: Annotated[Optional[str], typer.Option("--url", help="Backend URL")] = None,
    token: Annotated[Optional[str], typer.Option("--token", "-t", help="JWT Token")] = None,
) -> None:
    """测试 Provider 连通性。"""
    client = CkyClawClient(base_url=url, token=token)
    try:
        resp = client.test_provider(provider_id)
    except RuntimeError as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        raise typer.Exit(code=1)

    success = resp.get("success", False)
    latency = resp.get("latency_ms", 0)
    model = resp.get("model_used", "?")

    if success:
        console.print(f"[bold green]✓ 连通性测试通过[/bold green]")
        console.print(f"  模型: {model}  延迟: {latency}ms")
    else:
        error = resp.get("error", "未知错误")
        console.print(f"[bold red]✗ 连通性测试失败: {error}[/bold red]")
        raise typer.Exit(code=1)
