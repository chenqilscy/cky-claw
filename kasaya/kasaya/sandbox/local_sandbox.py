"""本地沙箱 — 基于 subprocess + 临时目录。"""

from __future__ import annotations

import asyncio
import contextlib
import os
import tempfile
import time

from kasaya.sandbox.executor import SandboxExecutor, SandboxResult

# 语言 → 命令映射
_LANGUAGE_COMMANDS: dict[str, list[str]] = {
    "python": ["python", "-u"],
    "node": ["node"],
    "bash": ["bash"],
    "sh": ["sh"],
}

# 语言 → 文件后缀
_LANGUAGE_EXTENSIONS: dict[str, str] = {
    "python": ".py",
    "node": ".js",
    "bash": ".sh",
    "sh": ".sh",
}


class LocalSandbox(SandboxExecutor):
    """本地 subprocess 沙箱。

    通过创建临时目录、写入代码文件、subprocess 执行来实现基本隔离。
    适用于开发环境和 CI 场景。生产环境建议使用 DockerSandbox。
    """

    async def execute(self, code: str, *, language: str = "python") -> SandboxResult:
        """执行代码。"""
        cmd_base = _LANGUAGE_COMMANDS.get(language)
        if cmd_base is None:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=f"Unsupported language: {language}",
            )

        ext = _LANGUAGE_EXTENSIONS.get(language, ".txt")
        work_dir = self.config.work_dir or None
        tmp_dir = None

        try:
            if work_dir is None:
                tmp_dir = tempfile.mkdtemp(prefix="kasaya_sandbox_")
                work_dir = tmp_dir

            # 写入代码文件
            code_file = os.path.join(work_dir, f"main{ext}")
            with open(code_file, "w", encoding="utf-8") as f:
                f.write(code)

            # 构建环境变量
            env = os.environ.copy()
            env.update(self.config.env)
            # 安全限制：移除敏感变量
            for key in ("AWS_SECRET_ACCESS_KEY", "DATABASE_URL", "SECRET_KEY", "KASAYA_SECRET_KEY"):
                env.pop(key, None)

            if not self.config.network_enabled:
                # 在 Linux 上可通过 unshare 限制网络，但不是所有平台支持
                # 这里只是标记意图，实际限制需要 Docker 或 Linux namespace
                pass

            cmd = [*cmd_base, code_file]
            timeout = self.config.timeout if self.config.timeout > 0 else None

            start_time = time.monotonic()
            timed_out = False

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=work_dir,
                    env=env,
                )
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except TimeoutError:
                timed_out = True
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                stdout_bytes = b""
                stderr_bytes = b"Execution timed out"

            elapsed_ms = (time.monotonic() - start_time) * 1000

            # 截断输出防止内存爆炸（最大 1 MB）
            max_output = 1024 * 1024
            stdout_str = (stdout_bytes or b"").decode("utf-8", errors="replace")[:max_output]
            stderr_str = (stderr_bytes or b"").decode("utf-8", errors="replace")[:max_output]

            return SandboxResult(
                exit_code=proc.returncode if proc.returncode is not None and not timed_out else -1,
                stdout=stdout_str,
                stderr=stderr_str,
                timed_out=timed_out,
                duration_ms=elapsed_ms,
            )

        finally:
            # 清理临时目录
            if tmp_dir is not None:
                import shutil

                shutil.rmtree(tmp_dir, ignore_errors=True)

    async def cleanup(self) -> None:
        """本地沙箱无需额外清理。"""
        pass
