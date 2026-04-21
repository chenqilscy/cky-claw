"""Sandbox 沙箱隔离测试。"""

from __future__ import annotations

import pytest

from kasaya.sandbox.config import SandboxConfig
from kasaya.sandbox.executor import SandboxExecutor, SandboxResult
from kasaya.sandbox.local_sandbox import LocalSandbox

# ---------------------------------------------------------------------------
# SandboxConfig 测试
# ---------------------------------------------------------------------------


class TestSandboxConfig:
    def test_defaults(self) -> None:
        cfg = SandboxConfig()
        assert cfg.timeout == 30
        assert cfg.memory_limit_mb == 256
        assert cfg.cpu_limit == 1.0
        assert cfg.network_enabled is False
        assert cfg.image == "python:3.12-slim"
        assert cfg.work_dir == ""
        assert cfg.env == {}

    def test_custom(self) -> None:
        cfg = SandboxConfig(timeout=10, memory_limit_mb=512, network_enabled=True, env={"FOO": "bar"})
        assert cfg.timeout == 10
        assert cfg.memory_limit_mb == 512
        assert cfg.network_enabled is True
        assert cfg.env == {"FOO": "bar"}

    def test_frozen(self) -> None:
        cfg = SandboxConfig()
        with pytest.raises(AttributeError):
            cfg.timeout = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SandboxResult 测试
# ---------------------------------------------------------------------------


class TestSandboxResult:
    def test_defaults(self) -> None:
        r = SandboxResult(exit_code=0, stdout="ok", stderr="")
        assert r.timed_out is False
        assert r.duration_ms == 0.0

    def test_timed_out(self) -> None:
        r = SandboxResult(exit_code=-1, stdout="", stderr="timeout", timed_out=True, duration_ms=5000.0)
        assert r.timed_out is True


# ---------------------------------------------------------------------------
# SandboxExecutor 抽象测试
# ---------------------------------------------------------------------------


class TestSandboxExecutor:
    def test_abstract(self) -> None:
        with pytest.raises(TypeError):
            SandboxExecutor()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# LocalSandbox 集成测试
# ---------------------------------------------------------------------------


class TestLocalSandbox:
    @pytest.mark.asyncio
    async def test_hello_world(self) -> None:
        sandbox = LocalSandbox()
        result = await sandbox.execute('print("hello sandbox")')
        assert result.exit_code == 0
        assert "hello sandbox" in result.stdout
        assert result.timed_out is False
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_stderr(self) -> None:
        sandbox = LocalSandbox()
        result = await sandbox.execute('import sys; sys.stderr.write("err msg")')
        assert result.exit_code == 0
        assert "err msg" in result.stderr

    @pytest.mark.asyncio
    async def test_exit_code(self) -> None:
        sandbox = LocalSandbox()
        result = await sandbox.execute('raise SystemExit(42)')
        assert result.exit_code == 42

    @pytest.mark.asyncio
    async def test_syntax_error(self) -> None:
        sandbox = LocalSandbox()
        result = await sandbox.execute('def foo(')
        assert result.exit_code != 0
        assert "SyntaxError" in result.stderr

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        cfg = SandboxConfig(timeout=1)
        sandbox = LocalSandbox(config=cfg)
        result = await sandbox.execute('import time; time.sleep(10)')
        assert result.timed_out is True
        assert result.exit_code == -1

    @pytest.mark.asyncio
    async def test_unsupported_language(self) -> None:
        sandbox = LocalSandbox()
        result = await sandbox.execute('code', language="rust")
        assert result.exit_code == -1
        assert "Unsupported language" in result.stderr

    @pytest.mark.asyncio
    async def test_env_vars(self) -> None:
        cfg = SandboxConfig(env={"TEST_SANDBOX_VAR": "hello123"})
        sandbox = LocalSandbox(config=cfg)
        result = await sandbox.execute('import os; print(os.environ.get("TEST_SANDBOX_VAR", ""))')
        assert result.exit_code == 0
        assert "hello123" in result.stdout

    @pytest.mark.asyncio
    async def test_custom_work_dir(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = SandboxConfig(work_dir=tmpdir)
            sandbox = LocalSandbox(config=cfg)
            result = await sandbox.execute('import os; print(os.getcwd())')
            assert result.exit_code == 0
            # 工作目录应该包含临时目录路径
            assert tmpdir.replace("\\", "/") in result.stdout.strip().replace("\\", "/") or \
                   tmpdir in result.stdout.strip()

    @pytest.mark.asyncio
    async def test_sensitive_env_removed(self) -> None:
        """验证敏感环境变量被移除。"""
        import os

        os.environ["KASAYA_SECRET_KEY"] = "super-secret"
        try:
            sandbox = LocalSandbox()
            result = await sandbox.execute(
                'import os; print(os.environ.get("KASAYA_SECRET_KEY", "MISSING"))'
            )
            assert result.exit_code == 0
            assert "MISSING" in result.stdout
        finally:
            os.environ.pop("KASAYA_SECRET_KEY", None)

    @pytest.mark.asyncio
    async def test_cleanup(self) -> None:
        sandbox = LocalSandbox()
        await sandbox.cleanup()  # 无异常即可

    @pytest.mark.asyncio
    async def test_multiline_output(self) -> None:
        code = 'for i in range(5): print(f"line {i}")'
        sandbox = LocalSandbox()
        result = await sandbox.execute(code)
        assert result.exit_code == 0
        assert "line 0" in result.stdout
        assert "line 4" in result.stdout
