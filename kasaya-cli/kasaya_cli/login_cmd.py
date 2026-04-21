"""登录命令。"""

from __future__ import annotations

import os
from typing import Annotated, Optional

import typer
from rich.console import Console

from kasaya_cli.client import KasayaClient

console = Console()


def login_command(
    username: Annotated[str, typer.Option("--username", "-u", help="用户名", prompt=True)],
    password: Annotated[str, typer.Option("--password", "-p", help="密码", prompt=True, hide_input=True)],
    url: Annotated[Optional[str], typer.Option("--url", help="Backend URL")] = None,
) -> None:
    """登录 Kasaya Backend 并获取 Token。"""
    client = KasayaClient(base_url=url)
    try:
        token = client.login(username, password)
    except RuntimeError as e:
        console.print(f"[bold red]登录失败: {e}[/bold red]")
        raise typer.Exit(code=1)

    console.print(f"[bold green]✓ 登录成功！[/bold green]")
    console.print(f"\n[dim]将以下环境变量添加到 shell 以复用 Token:[/dim]")
    console.print(f"  export KASAYA_TOKEN={token}")
    console.print(f"  export KASAYA_URL={client.base_url}")
