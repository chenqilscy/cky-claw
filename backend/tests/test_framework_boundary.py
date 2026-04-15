"""Framework/Backend 依赖边界守卫测试。

确保 ckyclaw_framework 不会导入 backend 的任何模块（app.*），
保障 Framework 可作为独立 pip 包发布。
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

_FRAMEWORK_ROOT = Path(__file__).resolve().parents[1] / ".." / "ckyclaw-framework" / "ckyclaw_framework"


def _iter_python_files(root: Path):
    """遍历所有 .py 文件。"""
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f.endswith(".py"):
                yield Path(dirpath) / f


class TestFrameworkBoundary:
    """Framework 包独立性守卫。"""

    def test_no_reverse_imports_from_app(self) -> None:
        """ckyclaw_framework 不得包含 'from app' 或 'import app' 导入。"""
        violations: list[str] = []
        framework_root = _FRAMEWORK_ROOT.resolve()

        if not framework_root.exists():
            pytest.skip(f"Framework 目录不存在: {framework_root}")

        for py_file in _iter_python_files(framework_root):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError:
                continue

            rel_path = py_file.relative_to(framework_root)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module == "app" or node.module.startswith("app."):
                        violations.append(f"{rel_path}:{node.lineno} — from {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "app" or alias.name.startswith("app."):
                            violations.append(f"{rel_path}:{node.lineno} — import {alias.name}")

        assert violations == [], (
            f"Framework 存在 {len(violations)} 处反向依赖:\n" + "\n".join(violations)
        )

    def test_no_backend_specific_imports(self) -> None:
        """ckyclaw_framework 不得导入 backend 专有库（fastapi/uvicorn/alembic）。"""
        forbidden = {"fastapi", "uvicorn", "alembic", "starlette"}
        violations: list[str] = []
        framework_root = _FRAMEWORK_ROOT.resolve()

        if not framework_root.exists():
            pytest.skip(f"Framework 目录不存在: {framework_root}")

        for py_file in _iter_python_files(framework_root):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError:
                continue

            rel_path = py_file.relative_to(framework_root)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    top_module = node.module.split(".")[0]
                    if top_module in forbidden:
                        violations.append(f"{rel_path}:{node.lineno} — from {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        top_module = alias.name.split(".")[0]
                        if top_module in forbidden:
                            violations.append(f"{rel_path}:{node.lineno} — import {alias.name}")

        assert violations == [], (
            "Framework 导入了 Backend 专有库:\n" + "\n".join(violations)
        )

    def test_framework_has_no_sqlalchemy_hard_dependency(self) -> None:
        """Framework 核心 __init__.py 不得硬导入 SQLAlchemy。"""
        init_file = _FRAMEWORK_ROOT.resolve() / "__init__.py"
        if not init_file.exists():
            pytest.skip("Framework __init__.py 不存在")

        tree = ast.parse(init_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("sqlalchemy"), (
                    f"__init__.py 硬导入 SQLAlchemy: {node.module}"
                )
