"""
规则评估引擎

使用安全的表达式评估，只允许访问预定义变量。
"""

import ast
import operator
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
import logging

from .loader import BusinessRule

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """规则评估结果"""
    rule_id: str
    rule_name: str
    triggered: bool
    severity: str
    action: str
    message: str


class SafeExpressionEvaluator:
    """
    安全表达式评估器

    只允许访问预定义变量，防止代码注入。
    使用 AST 解析而非 eval() 确保安全性。
    """

    ALLOWED_OPERATORS = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }

    ALLOWED_BOOL_OPS = {
        ast.And: lambda values: all(values),
        ast.Or: lambda values: any(values),
    }

    def __init__(self, allowed_variables: List[str] = None):
        self.allowed_variables = allowed_variables or [
            'work_order', 'order', 'customer', 'shipment',
            'action', 'comment', 'amount', 'status', 'type'
        ]

    def evaluate(self, expression: str, context: Dict[str, Any]) -> bool:
        """
        安全评估表达式

        Args:
            expression: 条件表达式字符串
            context: 变量上下文字典

        Returns:
            表达式评估结果 (True/False)
        """
        try:
            tree = ast.parse(expression, mode='eval')
            return self._eval_node(tree.body, context)
        except Exception as e:
            logger.warning(f"Expression evaluation error: {e}")
            return False

    def _eval_node(self, node, context: Dict[str, Any]) -> Any:
        """递归评估 AST 节点"""
        # 常量
        if isinstance(node, ast.Constant):
            return node.value

        # 名称引用
        elif isinstance(node, ast.Name):
            if node.id in self.allowed_variables:
                return context.get(node.id)
            raise ValueError(f"Variable '{node.id}' not allowed")

        # 属性访问 (obj.attr)
        elif isinstance(node, ast.Attribute):
            obj = self._eval_node(node.value, context)
            if node.attr == 'get' and isinstance(obj, dict):
                # 返回一个可调用的 get 方法
                return lambda *args: obj.get(*args)
            raise ValueError(f"Attribute access '{node.attr}' not allowed")

        # 方法调用
        elif isinstance(node, ast.Call):
            # 只允许 .get() 方法调用
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'get':
                obj = self._eval_node(node.func.value, context)
                args = [self._eval_node(arg, context) for arg in node.args]
                if isinstance(obj, dict):
                    return obj.get(*args)
                elif callable(obj):
                    return obj(*args)
            raise ValueError(f"Function call not allowed")

        # 比较操作
        elif isinstance(node, ast.Compare):
            left = self._eval_node(node.left, context)
            for op, right in zip(node.ops, node.comparators):
                right_val = self._eval_node(right, context)

                # 处理 in/not in 操作
                if isinstance(op, ast.In):
                    if left not in right_val:
                        return False
                elif isinstance(op, ast.NotIn):
                    if left in right_val:
                        return False
                else:
                    op_func = self.ALLOWED_OPERATORS.get(type(op))
                    if not op_func:
                        raise ValueError(f"Operator {type(op).__name__} not allowed")
                    if not op_func(left, right_val):
                        return False
                left = right_val
            return True

        # 布尔操作
        elif isinstance(node, ast.BoolOp):
            values = [self._eval_node(v, context) for v in node.values]
            bool_op = self.ALLOWED_BOOL_OPS.get(type(node.op))
            if bool_op:
                return bool_op(values)
            raise ValueError(f"Boolean operator {type(node.op).__name__} not allowed")

        # 一元操作
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, context)
            if isinstance(node.op, ast.Not):
                return not operand
            raise ValueError(f"Unary operator {type(node.op).__name__} not allowed")

        # 列表
        elif isinstance(node, ast.List):
            return [self._eval_node(elt, context) for elt in node.elts]

        raise ValueError(f"Node type {type(node).__name__} not supported")


class RuleEvaluator:
    """规则评估引擎"""

    def __init__(self, rule_loader: 'RuleLoader'):
        self.loader = rule_loader
        self.evaluator = SafeExpressionEvaluator()

    def evaluate_all(
        self,
        context: Dict[str, Any]
    ) -> Tuple[List[EvaluationResult], List[EvaluationResult], List[EvaluationResult]]:
        """
        评估所有启用的规则

        Args:
            context: 评估上下文，包含 work_order, order, customer 等

        Returns:
            (issues, warnings, notifications) 三元组
        """
        issues = []
        warnings = []
        notifications = []

        for rule in self.loader.get_all_rules():
            try:
                triggered = self.evaluator.evaluate(rule.condition, context)

                if triggered:
                    result = EvaluationResult(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        triggered=True,
                        severity=rule.severity,
                        action=rule.action,
                        message=rule.message
                    )

                    if rule.severity == 'block':
                        issues.append(result)
                    elif rule.severity == 'warn':
                        warnings.append(result)
                    else:
                        notifications.append(result)

            except Exception as e:
                logger.error(f"Rule '{rule.id}' evaluation failed: {e}")

        return issues, warnings, notifications

    def evaluate_rule(self, rule_id: str, context: Dict[str, Any]) -> Optional[EvaluationResult]:
        """评估单个规则"""
        rule = self.loader.get_rule(rule_id)
        if not rule or not rule.enabled:
            return None

        try:
            triggered = self.evaluator.evaluate(rule.condition, context)
            return EvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                triggered=triggered,
                severity=rule.severity,
                action=rule.action,
                message=rule.message
            )
        except Exception as e:
            logger.error(f"Rule '{rule_id}' evaluation failed: {e}")
            return None
