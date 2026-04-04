"""Evaluator — 安全条件表达式求值。

仅允许：比较运算（==, !=, >, <, >=, <=）、布尔运算（and, or, not）、
字面量（str, int, float, bool, None）。
支持 dot-separated dict key path：a.b.c → context["a"]["b"]["c"]。
"""

from __future__ import annotations

import ast
from typing import Any


class UnsafeExpressionError(Exception):
    """不安全的表达式。"""

    pass


_ALLOWED_COMPARE_OPS = (
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.Is, ast.IsNot, ast.In, ast.NotIn,
)

_ALLOWED_BOOL_OPS = (ast.And, ast.Or)
_ALLOWED_UNARY_OPS = (ast.Not, ast.USub)


def evaluate(expression: str, context: dict[str, Any]) -> Any:
    """安全求值条件表达式。

    支持：
    - 字面量：'hello', 42, 3.14, True, False, None
    - 变量引用：key → context["key"]
    - 路径引用：a.b.c → context["a"]["b"]["c"]
    - 比较：==, !=, >, <, >=, <=, in, not in, is, is not
    - 布尔：and, or, not
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise UnsafeExpressionError(f"语法错误: {e}") from e

    _validate_ast(tree.body)
    return _eval_node(tree.body, context)


def _validate_ast(node: ast.AST) -> None:
    """递归验证 AST 节点安全性。"""
    if isinstance(node, ast.Expression):
        _validate_ast(node.body)
    elif isinstance(node, ast.BoolOp):
        if not isinstance(node.op, _ALLOWED_BOOL_OPS):
            raise UnsafeExpressionError(f"不允许的布尔运算: {type(node.op).__name__}")
        for value in node.values:
            _validate_ast(value)
    elif isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, _ALLOWED_UNARY_OPS):
            raise UnsafeExpressionError(f"不允许的一元运算: {type(node.op).__name__}")
        _validate_ast(node.operand)
    elif isinstance(node, ast.Compare):
        _validate_ast(node.left)
        for op in node.ops:
            if not isinstance(op, _ALLOWED_COMPARE_OPS):
                raise UnsafeExpressionError(f"不允许的比较运算: {type(op).__name__}")
        for comp in node.comparators:
            _validate_ast(comp)
    elif isinstance(node, ast.Constant):
        pass
    elif isinstance(node, ast.Name):
        pass
    elif isinstance(node, ast.Attribute):
        _validate_ast(node.value)
    elif isinstance(node, (ast.List, ast.Tuple)):
        for elt in node.elts:
            _validate_ast(elt)
    else:
        raise UnsafeExpressionError(
            f"不允许的表达式类型: {type(node).__name__}"
        )


def _eval_node(node: ast.AST, context: dict[str, Any]) -> Any:
    """递归求值 AST 节点。"""
    if isinstance(node, ast.Constant):
        return node.value

    elif isinstance(node, ast.Name):
        return context.get(node.id)

    elif isinstance(node, ast.Attribute):
        # dot-separated path: a.b → context["a"]["b"]
        value = _eval_node(node.value, context)
        if isinstance(value, dict):
            return value.get(node.attr)
        return None

    elif isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            result: Any = True
            for value in node.values:
                result = _eval_node(value, context)
                if not result:
                    return result
            return result
        else:  # Or
            result = False
            for value in node.values:
                result = _eval_node(value, context)
                if result:
                    return result
            return result

    elif isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, context)
        if isinstance(node.op, ast.Not):
            return not operand
        elif isinstance(node.op, ast.USub):
            return -operand
        return operand

    elif isinstance(node, ast.Compare):
        left = _eval_node(node.left, context)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, context)
            if isinstance(op, ast.Eq):
                result = left == right
            elif isinstance(op, ast.NotEq):
                result = left != right
            elif isinstance(op, ast.Lt):
                result = left < right
            elif isinstance(op, ast.LtE):
                result = left <= right
            elif isinstance(op, ast.Gt):
                result = left > right
            elif isinstance(op, ast.GtE):
                result = left >= right
            elif isinstance(op, ast.Is):
                result = left is right
            elif isinstance(op, ast.IsNot):
                result = left is not right
            elif isinstance(op, ast.In):
                result = left in right
            elif isinstance(op, ast.NotIn):
                result = left not in right
            else:
                raise UnsafeExpressionError(f"不支持的比较运算: {type(op).__name__}")
            if not result:
                return False
            left = right
        return True

    elif isinstance(node, (ast.List, ast.Tuple)):
        return [_eval_node(elt, context) for elt in node.elts]

    raise UnsafeExpressionError(f"无法求值: {type(node).__name__}")
