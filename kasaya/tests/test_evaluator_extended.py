"""Evaluator 扩展测试 — 覆盖 Is/IsNot/NotIn/LtE/GtE / Tuple / 属性非 dict 等路径。"""

from __future__ import annotations

import pytest

from kasaya.workflow.evaluator import UnsafeExpressionError, evaluate


class TestEvaluatorComparisonOps:
    """覆盖各个比较运算符。"""

    def test_less_than_or_equal(self) -> None:
        assert evaluate("x <= 5", {"x": 5}) is True
        assert evaluate("x <= 5", {"x": 6}) is False

    def test_greater_than_or_equal(self) -> None:
        assert evaluate("x >= 5", {"x": 5}) is True
        assert evaluate("x >= 5", {"x": 4}) is False

    def test_is_none(self) -> None:
        assert evaluate("x is None", {"x": None}) is True
        assert evaluate("x is None", {"x": 0}) is False

    def test_is_not_none(self) -> None:
        assert evaluate("x is not None", {"x": 42}) is True
        assert evaluate("x is not None", {"x": None}) is False

    def test_in_list(self) -> None:
        assert evaluate("x in [1, 2, 3]", {"x": 2}) is True
        assert evaluate("x in [1, 2, 3]", {"x": 4}) is False

    def test_not_in_list(self) -> None:
        assert evaluate("x not in [1, 2, 3]", {"x": 4}) is True
        assert evaluate("x not in [1, 2, 3]", {"x": 2}) is False

    def test_not_in_string(self) -> None:
        assert evaluate("'abc' not in text", {"text": "hello"}) is True
        assert evaluate("'abc' not in text", {"text": "abcdef"}) is False

    def test_chained_comparison(self) -> None:
        """链式比较 1 < x < 10。"""
        assert evaluate("1 < x < 10", {"x": 5}) is True
        assert evaluate("1 < x < 10", {"x": 15}) is False


class TestEvaluatorTupleLiteral:

    def test_tuple_literal(self) -> None:
        """元组字面量求值。"""
        result = evaluate("(1, 2, 3)", {})
        assert result == [1, 2, 3]  # ast.Tuple 被求值为 list

    def test_in_tuple(self) -> None:
        assert evaluate("x in (1, 2, 3)", {"x": 2}) is True
        assert evaluate("x in (1, 2, 3)", {"x": 4}) is False


class TestEvaluatorAttributeAccess:

    def test_attribute_on_non_dict_returns_none(self) -> None:
        """对非 dict 值做属性访问返回 None。"""
        result = evaluate("x.y", {"x": "not_a_dict"})
        assert result is None

    def test_attribute_on_none(self) -> None:
        result = evaluate("x.y", {"x": None})
        assert result is None

    def test_missing_attribute_key(self) -> None:
        """dict 中缺少属性键返回 None。"""
        result = evaluate("x.z", {"x": {"y": 1}})
        assert result is None


class TestEvaluatorBoolOps:

    def test_and_short_circuit_false(self) -> None:
        """and 短路：第一个为 False 则不评估后续。"""
        result = evaluate("False and True", {})
        assert result is False

    def test_or_short_circuit_true(self) -> None:
        """or 短路：第一个为 True 则不评估后续。"""
        result = evaluate("True or False", {})
        assert result is True

    def test_multiple_and(self) -> None:
        result = evaluate("True and True and False", {})
        assert result is False

    def test_multiple_or(self) -> None:
        result = evaluate("False or False or True", {})
        assert result is True


class TestEvaluatorUnaryOps:

    def test_unary_minus(self) -> None:
        result = evaluate("-5", {})
        assert result == -5

    def test_not_true(self) -> None:
        result = evaluate("not True", {})
        assert result is False

    def test_not_false(self) -> None:
        result = evaluate("not False", {})
        assert result is True


class TestEvaluatorComplexPaths:
    """覆盖 _eval_node 中更多分支。"""

    def test_ge_operator(self) -> None:
        """GtE 路径。"""
        assert evaluate("10 >= 10", {}) is True

    def test_le_operator(self) -> None:
        """LtE 路径。"""
        assert evaluate("5 <= 10", {}) is True

    def test_is_operator(self) -> None:
        """Is 路径。"""
        assert evaluate("x is None", {"x": None}) is True

    def test_is_not_operator(self) -> None:
        """IsNot 路径。"""
        assert evaluate("x is not None", {"x": 42}) is True

    def test_not_in_eval(self) -> None:
        """NotIn 路径。"""
        assert evaluate("5 not in [1, 2, 3]", {}) is True

    def test_eval_list_literal(self) -> None:
        """ast.List eval 路径。"""
        result = evaluate("[1, 'a', True]", {})
        assert result == [1, "a", True]

    def test_eval_tuple_literal(self) -> None:
        """ast.Tuple eval 路径。"""
        result = evaluate("(1, 2)", {})
        assert result == [1, 2]

    def test_attribute_on_dict(self) -> None:
        """ast.Attribute eval 路径 — dict 访问。"""
        result = evaluate("data.key", {"data": {"key": "value"}})
        assert result == "value"

    def test_attribute_on_int(self) -> None:
        """ast.Attribute eval 路径 — 非 dict 返回 None。"""
        result = evaluate("data.key", {"data": 42})
        assert result is None


class TestEvaluatorSafety:

    def test_dict_comprehension_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            evaluate("{k: v for k, v in {}}", {})

    def test_set_literal_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            evaluate("{1, 2, 3}", {})

    def test_walrus_operator_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            evaluate("(x := 5)", {})

    def test_subscript_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            evaluate("x[0]", {"x": [1, 2, 3]})

    def test_f_string_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            evaluate("f'{x}'", {"x": "hello"})
