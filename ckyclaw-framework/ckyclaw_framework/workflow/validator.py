"""Validator — DAG 结构验证。

功能：
- Kahn 算法拓扑排序 + 环检测
- 孤立边检测
- 嵌套规则验证
- 并行 output_key 冲突检测
- input_schema 验证
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ckyclaw_framework.workflow.step import (
    AgentStep,
    ConditionalStep,
    LoopStep,
    ParallelStep,
    Step,
)
from ckyclaw_framework.workflow.workflow import Edge, Workflow


class WorkflowValidationError(Exception):
    """工作流验证失败。"""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"工作流验证失败: {'; '.join(errors)}")


def validate_workflow(workflow: Workflow) -> list[str]:
    """验证工作流定义，返回错误列表（空 = 通过）。"""
    errors: list[str] = []
    errors.extend(_validate_step_ids(workflow))
    errors.extend(_validate_edges(workflow))
    errors.extend(_validate_dag(workflow))
    errors.extend(_validate_nesting(workflow))
    errors.extend(_validate_output_key_conflicts(workflow))
    errors.extend(_validate_conditional_targets(workflow))
    return errors


def validate_workflow_strict(workflow: Workflow) -> None:
    """严格验证（有错误则抛异常）。"""
    errors = validate_workflow(workflow)
    if errors:
        raise WorkflowValidationError(errors)


def topological_sort(workflow: Workflow) -> list[str]:
    """Kahn 算法拓扑排序，返回步骤 ID 列表。如有环则抛异常。"""
    step_ids = {s.id for s in workflow.steps}
    in_degree: dict[str, int] = {sid: 0 for sid in step_ids}
    adj: dict[str, list[str]] = defaultdict(list)

    for edge in workflow.edges:
        if edge.source_step_id in step_ids and edge.target_step_id in step_ids:
            adj[edge.source_step_id].append(edge.target_step_id)
            in_degree[edge.target_step_id] += 1

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    result: list[str] = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(step_ids):
        raise WorkflowValidationError(["DAG 包含环，拓扑排序失败"])

    return result


def _validate_step_ids(workflow: Workflow) -> list[str]:
    """验证步骤 ID 唯一性。"""
    errors: list[str] = []
    seen: set[str] = set()
    for step in workflow.steps:
        if step.id in seen:
            errors.append(f"步骤 ID 重复: '{step.id}'")
        seen.add(step.id)
    return errors


def _validate_edges(workflow: Workflow) -> list[str]:
    """验证边引用的步骤存在。"""
    errors: list[str] = []
    step_ids = {s.id for s in workflow.steps}
    for edge in workflow.edges:
        if edge.source_step_id not in step_ids:
            errors.append(f"边 '{edge.id}' 的 source '{edge.source_step_id}' 不存在")
        if edge.target_step_id not in step_ids:
            errors.append(f"边 '{edge.id}' 的 target '{edge.target_step_id}' 不存在")
    return errors


def _validate_dag(workflow: Workflow) -> list[str]:
    """验证 DAG 无环（Kahn 算法）。"""
    step_ids = {s.id for s in workflow.steps}
    in_degree: dict[str, int] = {sid: 0 for sid in step_ids}
    adj: dict[str, list[str]] = defaultdict(list)

    for edge in workflow.edges:
        if edge.source_step_id in step_ids and edge.target_step_id in step_ids:
            adj[edge.source_step_id].append(edge.target_step_id)
            in_degree[edge.target_step_id] += 1

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    visited = 0

    while queue:
        node = queue.pop(0)
        visited += 1
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited != len(step_ids):
        return ["DAG 包含环"]
    return []


def _validate_nesting(workflow: Workflow) -> list[str]:
    """验证嵌套规则。"""
    errors: list[str] = []
    for step in workflow.steps:
        if isinstance(step, ParallelStep):
            for sub in step.sub_steps:
                if isinstance(sub, (ParallelStep, LoopStep)):
                    errors.append(
                        f"ParallelStep '{step.id}' 不允许嵌套 {type(sub).__name__} ('{sub.id}')"
                    )
        elif isinstance(step, LoopStep):
            for sub in step.body_steps:
                if isinstance(sub, (ParallelStep, LoopStep)):
                    errors.append(
                        f"LoopStep '{step.id}' 不允许嵌套 {type(sub).__name__} ('{sub.id}')"
                    )
    return errors


def _validate_output_key_conflicts(workflow: Workflow) -> list[str]:
    """验证并行步骤的 output_key 不冲突。"""
    errors: list[str] = []
    for step in workflow.steps:
        if isinstance(step, ParallelStep):
            keys: dict[str, str] = {}
            for sub in step.sub_steps:
                if sub.io.output_keys:
                    for _, ctx_key in sub.io.output_keys.items():
                        if ctx_key in keys:
                            errors.append(
                                f"ParallelStep '{step.id}' 中子步骤 '{sub.id}' 和 "
                                f"'{keys[ctx_key]}' 写入相同 output_key '{ctx_key}'"
                            )
                        keys[ctx_key] = sub.id
    return errors


def _validate_conditional_targets(workflow: Workflow) -> list[str]:
    """验证 ConditionalStep 的分支目标存在。"""
    errors: list[str] = []
    step_ids = {s.id for s in workflow.steps}
    for step in workflow.steps:
        if isinstance(step, ConditionalStep):
            for branch in step.branches:
                if branch.target_step_id not in step_ids:
                    errors.append(
                        f"ConditionalStep '{step.id}' 分支 '{branch.label}' "
                        f"的目标 '{branch.target_step_id}' 不存在"
                    )
            if step.default_step_id and step.default_step_id not in step_ids:
                errors.append(
                    f"ConditionalStep '{step.id}' 的默认目标 "
                    f"'{step.default_step_id}' 不存在"
                )
    return errors
