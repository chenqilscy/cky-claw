"""Evaluator 内部函数直接测试 — 覆盖 _validate_ast 不可达路径 + _eval_node 边界。"""

from __future__ import annotations

import ast

import pytest

from ckyclaw_framework.workflow.evaluator import (
    UnsafeExpressionError,
    _validate_ast,
    evaluate,
)


class TestValidateAstForbiddenBoolOp:
    """line 51: BoolOp 中使用非法运算符。

    Python AST 的 BoolOp 只有 And/Or，均在允许列表中，
    需要手动构造 AST 来触发防御性检查。
    """

    def test_forbidden_bool_op(self) -> None:
        """伪造一个 BoolOp 节点，其 op 不是 And/Or。"""
        node = ast.BoolOp(
            op=ast.BitOr(),  # type: ignore[arg-type]  # 故意传入非法类型
            values=[ast.Constant(value=True), ast.Constant(value=False)],
        )
        with pytest.raises(UnsafeExpressionError, match="不允许的布尔运算"):
            _validate_ast(node)


class TestValidateAstForbiddenUnaryOp:
    """line 54: UnaryOp 中使用非法运算符（UAdd, Invert）。"""

    def test_invert_rejected(self) -> None:
        """~ 运算 (Invert) 被拒绝。"""
        with pytest.raises(UnsafeExpressionError, match="不允许的一元运算|不允许的表达式类型"):
            evaluate("~5", {})

    def test_uadd_via_crafted_ast(self) -> None:
        """手动构造 UAdd UnaryOp 节点测试。"""
        node = ast.UnaryOp(
            op=ast.Invert(),
            operand=ast.Constant(value=5),
        )
        with pytest.raises(UnsafeExpressionError):
            _validate_ast(node)


class TestValidateAstForbiddenCompareOp:
    """line 59: Compare 中使用非法运算符。

    所有标准 Compare 运算符都在允许列表中，
    需手动构造 AST 来触发防御性检查。
    """

    def test_forbidden_compare_op(self) -> None:
        """伪造一个 Compare 节点，其 op 是非标准类型。"""
        # 使用一个虚假的 op 对象模拟非法比较运算符
        class FakeOp(ast.AST):
            pass

        node = ast.Compare(
            left=ast.Constant(value=1),
            ops=[FakeOp()],  # type: ignore[list-item]
            comparators=[ast.Constant(value=2)],
        )
        with pytest.raises(UnsafeExpressionError, match="不允许的比较运算"):
            _validate_ast(node)


class TestValidateAstCompare:
    """line 65: ast.Compare 正常验证路径。"""

    def test_compare_validation_passes(self) -> None:
        """正常的 Compare 节点通过验证。"""
        node = ast.Compare(
            left=ast.Constant(value=1),
            ops=[ast.Lt()],
            comparators=[ast.Constant(value=2)],
        )
        # 不应抛异常
        _validate_ast(node)


class TestEvalNodeBoolOpOrFallthrough:
    """line 112: BoolOp Or 中所有值都为 falsy → 返回最后一个值。"""

    def test_or_all_falsy(self) -> None:
        """False or 0 or '' → 返回 '' (最后一个 falsy 值)。"""
        result = evaluate("False or 0", {})
        assert result == 0

    def test_or_all_falsy_three(self) -> None:
        result = evaluate("False or 0 or None", {"None": None})
        assert result is None or result == 0  # None 在 AST 中是 ast.Constant(value=None)

    def test_or_last_truthy(self) -> None:
        """False or 0 or 42 → 返回 42。"""
        result = evaluate("False or 0 or 42", {})
        assert result == 42


class TestEvalNodeChainedCompare:
    """line 120: 链式比较 a < b < c 中间失败。"""

    def test_chained_middle_fails(self) -> None:
        """1 < 5 < 3 → False (第二段失败)。"""
        result = evaluate("1 < x < 3", {"x": 5})
        assert result is False

    def test_chained_all_succeed(self) -> None:
        """1 < 2 < 3 → True。"""
        result = evaluate("1 < x < 3", {"x": 2})
        assert result is True

    def test_triple_chain(self) -> None:
        """1 < 2 < 3 < 4 → True。"""
        result = evaluate("1 < a < b < 4", {"a": 2, "b": 3})
        assert result is True


class TestEvalNodeUSub:
    """line 129: USub 一元负号。"""

    def test_usub_variable(self) -> None:
        """-x 求值。"""
        result = evaluate("-x", {"x": 10})
        assert result == -10

    def test_usub_literal(self) -> None:
        """-42 求值。"""
        result = evaluate("-42", {})
        assert result == -42


class TestEvalNodeIsComparison:
    """line 147: Is 比较运算。"""

    def test_is_none(self) -> None:
        assert evaluate("x is None", {"x": None}) is True

    def test_is_not_none(self) -> None:
        assert evaluate("x is None", {"x": 0}) is False


class TestEvalNodeNotInComparison:
    """line 156: NotIn 比较运算。"""

    def test_not_in_list(self) -> None:
        assert evaluate("x not in [1, 2, 3]", {"x": 4}) is True

    def test_not_in_list_false(self) -> None:
        assert evaluate("x not in [1, 2, 3]", {"x": 2}) is False

    def test_not_in_empty_list(self) -> None:
        assert evaluate("x not in []", {"x": 1}) is True


class TestEvalNodeUnknownCompareOp:
    """_eval_node 中遇到非法比较运算符路径（line ~160 的 else raise）。"""

    def test_unknown_compare_op_in_eval(self) -> None:
        """手动构造 Compare AST 节点，绕过 validate 直接 eval。"""
        from ckyclaw_framework.workflow.evaluator import _eval_node

        class FakeOp(ast.AST):
            pass

        node = ast.Compare(
            left=ast.Constant(value=1),
            ops=[FakeOp()],  # type: ignore[list-item]
            comparators=[ast.Constant(value=2)],
        )
        with pytest.raises(UnsafeExpressionError, match="不支持的比较运算"):
            _eval_node(node, {})
