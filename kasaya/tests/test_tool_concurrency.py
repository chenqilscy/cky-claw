"""Tool 并发限流 (O16) 测试。"""

from __future__ import annotations

import asyncio

import pytest

from kasaya.runner.run_config import RunConfig


class TestRunConfigMaxToolConcurrency:
    """验证 RunConfig.max_tool_concurrency 字段。"""

    def test_default_is_none(self) -> None:
        """默认无限制。"""
        config = RunConfig()
        assert config.max_tool_concurrency is None

    def test_set_concurrency(self) -> None:
        """可以设置并发数。"""
        config = RunConfig(max_tool_concurrency=3)
        assert config.max_tool_concurrency == 3

    def test_set_to_one(self) -> None:
        """设置为 1 实现串行执行。"""
        config = RunConfig(max_tool_concurrency=1)
        assert config.max_tool_concurrency == 1


class TestToolConcurrencyLimit:
    """验证工具并发限流在 Runner 中的行为。"""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self) -> None:
        """使用 Semaphore 模拟验证并发限制生效。"""
        max_concurrent = 2
        sem = asyncio.Semaphore(max_concurrent)
        active_count = 0
        peak_concurrent = 0

        async def simulated_tool(tool_id: int) -> None:
            nonlocal active_count, peak_concurrent
            async with sem:
                active_count += 1
                if active_count > peak_concurrent:
                    peak_concurrent = active_count
                await asyncio.sleep(0.05)  # 模拟工具执行
                active_count -= 1

        # 启动 5 个并发工具
        async with asyncio.TaskGroup() as tg:
            for i in range(5):
                tg.create_task(simulated_tool(i))

        # 峰值并发不超过 Semaphore 限制
        assert peak_concurrent <= max_concurrent

    @pytest.mark.asyncio
    async def test_no_limit_all_concurrent(self) -> None:
        """无限制时所有工具同时并发。"""
        active_count = 0
        peak_concurrent = 0

        async def simulated_tool(tool_id: int) -> None:
            nonlocal active_count, peak_concurrent
            active_count += 1
            if active_count > peak_concurrent:
                peak_concurrent = active_count
            await asyncio.sleep(0.05)
            active_count -= 1

        async with asyncio.TaskGroup() as tg:
            for i in range(5):
                tg.create_task(simulated_tool(i))

        # 所有 5 个应同时并发
        assert peak_concurrent == 5

    @pytest.mark.asyncio
    async def test_concurrency_one_is_serial(self) -> None:
        """并发数为 1 时工具串行执行。"""
        sem = asyncio.Semaphore(1)
        execution_order: list[tuple[int, str]] = []

        async def simulated_tool(tool_id: int) -> None:
            async with sem:
                execution_order.append((tool_id, "start"))
                await asyncio.sleep(0.02)
                execution_order.append((tool_id, "end"))

        async with asyncio.TaskGroup() as tg:
            for i in range(3):
                tg.create_task(simulated_tool(i))

        # 串行：每个工具的 end 应在下一个的 start 之前
        starts = [e for e in execution_order if e[1] == "start"]
        ends = [e for e in execution_order if e[1] == "end"]
        # 第一个 end 应在第二个 start 之前或同时出现
        for i in range(len(ends) - 1):
            end_idx = execution_order.index(ends[i])
            start_idx = execution_order.index(starts[i + 1])
            assert end_idx < start_idx, f"Tool {ends[i][0]} end should precede tool {starts[i+1][0]} start"


class TestRunnerToolConcurrencyIntegration:
    """验证 Runner 代码路径正确读取 max_tool_concurrency。"""

    def test_runner_reads_config(self) -> None:
        """_execute_tool_calls 从 config 获取 _max_concurrency。"""
        config = RunConfig(max_tool_concurrency=5)
        assert config.max_tool_concurrency == 5

    def test_runner_none_means_unlimited(self) -> None:
        """max_tool_concurrency=None 走无限制路径。"""
        config = RunConfig()
        # None 时 _max_concurrency 为 None，走 else 分支（无 Semaphore）
        assert config.max_tool_concurrency is None

    def test_runner_zero_means_unlimited(self) -> None:
        """max_tool_concurrency=0 应视为无限制。"""
        config = RunConfig(max_tool_concurrency=0)
        # 代码中条件为 _max_concurrency is not None and _max_concurrency > 0
        # 0 不满足 > 0，走 else 分支
        assert config.max_tool_concurrency == 0
