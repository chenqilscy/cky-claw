"""ckyclaw CLI 入口。"""

from __future__ import annotations

import typer

from ckyclaw_cli.agent_cmd import agent_app
from ckyclaw_cli.chat import chat_command
from ckyclaw_cli.login_cmd import login_command
from ckyclaw_cli.provider_cmd import provider_app
from ckyclaw_cli.run_cmd import run_command

app = typer.Typer(
    name="ckyclaw",
    help="CkyClaw CLI — 终端 Agent 交互工具",
    no_args_is_help=True,
)

app.command(name="chat", help="与 Agent 进行交互式对话")(chat_command)
app.command(name="login", help="登录 CkyClaw Backend")(login_command)
app.command(name="run", help="运行指定 Agent 并输出回复")(run_command)
app.add_typer(agent_app, name="agent")
app.add_typer(provider_app, name="provider")


@app.command()
def version() -> None:
    """显示版本信息。"""
    from ckyclaw_cli import __version__

    typer.echo(f"ckyclaw-cli v{__version__}")


if __name__ == "__main__":
    app()
