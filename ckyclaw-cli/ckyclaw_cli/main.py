"""ckyclaw CLI 入口。"""

from __future__ import annotations

import typer

from ckyclaw_cli.chat import chat_command

app = typer.Typer(
    name="ckyclaw",
    help="CkyClaw CLI — 终端 Agent 交互工具",
    no_args_is_help=True,
)

app.command(name="chat", help="与 Agent 进行交互式对话")(chat_command)


@app.command()
def version() -> None:
    """显示版本信息。"""
    from ckyclaw_cli import __version__

    typer.echo(f"ckyclaw-cli v{__version__}")


if __name__ == "__main__":
    app()
