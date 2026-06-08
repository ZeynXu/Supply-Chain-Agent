"""
工具调用评估器

评估工具调用的决策边界和参数合法性。
"""

from typing import Dict, Any, Optional

from ..config import EvalConfig
from .base import (
    ToolCallActual,
    ToolCallGold,
    ToolCallEvaluation,
)


class ToolCallValidator:
    """
    工具调用评估器

    评估维度（权重配置匹配供应链场景优先级）：
    - 决策正确性（30%）：是否应该调用工具
    - 工具选择（25%）：选择的工具是否匹配意图
    - 参数完整性（25%）：必填参数是否完整
    - 参数有效性（20%）：参数是否符合业务约束
    """

    def __init__(self, config: Optional[EvalConfig] = None):
        """
        初始化

        Args:
            config: 评估配置
        """
        self.config = config or EvalConfig.get_default()

    def evaluate(
        self,
        actual: ToolCallActual,
        gold: ToolCallGold
    ) -> ToolCallEvaluation:
        """
        评估工具调用

        Args:
            actual: 实际工具调用
            gold: 黄金标准

        Returns:
            ToolCallEvaluation: 评估结果
        """
        breakdown = {}

        # 1. 决策正确性（30%）：是否该调用工具
        decision_score = self._eval_decision(actual, gold)
        breakdown["decision"] = decision_score

        # 2. 工具选择（25%）：选择的工具是否正确
        tool_score = self._eval_tool_selection(actual, gold)
        breakdown["tool_selection"] = tool_score

        # 3. 参数完整性（25%）：必填参数是否完整
        completeness_score = self._eval_param_completeness(actual, gold)
        breakdown["param_completeness"] = completeness_score

        # 4. 参数有效性（20%）：参数是否符合约束
        validity_score = self._eval_param_validity(actual, gold)
        breakdown["param_validity"] = validity_score

        # 计算综合得分
        overall = (
            decision_score * 0.30 +
            tool_score * 0.25 +
            completeness_score * 0.25 +
            validity_score * 0.20
        )

        return ToolCallEvaluation(
            decision_correct=decision_score == 1.0,
            tool_correct=tool_score == 1.0,
            params_complete=completeness_score == 1.0,
            params_valid=validity_score == 1.0,
            overall_score=round(overall, 4),
            details={
                "actual_tool": actual.tool_name,
                "expected_tool": gold.expected_tool,
                "actual_params": actual.params,
                "expected_params": gold.expected_params
            },
            breakdown=breakdown
        )

    def evaluate_batch(
        self,
        actuals: list[ToolCallActual],
        golds: list[ToolCallGold]
    ) -> list[ToolCallEvaluation]:
        """
        批量评估

        Args:
            actuals: 实际工具调用列表
            golds: 黄金标准列表

        Returns:
            评估结果列表
        """
        results = []
        for actual, gold in zip(actuals, golds):
            results.append(self.evaluate(actual, gold))
        return results

    def _eval_decision(
        self,
        actual: ToolCallActual,
        gold: ToolCallGold
    ) -> float:
        """
        评估决策正确性

        判断是否应该调用工具
        """
        # 如果期望不调用工具，但实际调用了
        if not gold.should_call_tool:
            if actual.tool_name:
                return 0.0  # 不应该调用但调用了
            else:
                return 1.0  # 正确地没有调用

        # 如果期望调用工具，但实际没调用
        if gold.should_call_tool:
            if not actual.tool_name:
                return 0.0  # 应该调用但没调用
            else:
                return 1.0  # 正确地调用了

        return 1.0

    def _eval_tool_selection(
        self,
        actual: ToolCallActual,
        gold: ToolCallGold
    ) -> float:
        """
        评估工具选择正确性
        """
        if not gold.should_call_tool:
            # 不期望调用工具，此项不适用
            return 1.0

        if not gold.expected_tool:
            # 没有期望工具，此项不适用
            return 1.0

        if actual.tool_name == gold.expected_tool:
            return 1.0
        else:
            return 0.0

    def _eval_param_completeness(
        self,
        actual: ToolCallActual,
        gold: ToolCallGold
    ) -> float:
        """
        评估参数完整性

        检查必填参数是否完整
        """
        if not gold.should_call_tool:
            return 1.0

        expected_params = gold.expected_params
        if not expected_params:
            return 1.0

        actual_params = actual.params

        # 检查期望参数是否都在实际参数中
        missing = []
        for key, expected_value in expected_params.items():
            if key not in actual_params:
                missing.append(key)
            elif actual_params[key] is None:
                missing.append(key)

        if not missing:
            return 1.0

        # 按缺失比例扣分
        completeness = 1.0 - len(missing) / len(expected_params)
        return max(0.0, completeness)

    def _eval_param_validity(
        self,
        actual: ToolCallActual,
        gold: ToolCallGold
    ) -> float:
        """
        评估参数有效性

        检查参数是否符合业务约束
        """
        if not gold.should_call_tool:
            return 1.0

        constraints = gold.param_constraints
        if not constraints:
            # 无约束，检查基本有效性
            return self._check_basic_validity(actual.params)

        actual_params = actual.params
        violations = []

        for key, constraint in constraints.items():
            if key not in actual_params:
                continue

            value = actual_params[key]

            # 检查类型约束
            if "type" in constraint:
                expected_type = constraint["type"]
                if not self._check_type(value, expected_type):
                    violations.append(f"{key}: type mismatch")

            # 检查范围约束
            if "min" in constraint and value < constraint["min"]:
                violations.append(f"{key}: below min")
            if "max" in constraint and value > constraint["max"]:
                violations.append(f"{key}: above max")

            # 检查枚举约束
            if "enum" in constraint:
                if value not in constraint["enum"]:
                    violations.append(f"{key}: not in enum")

        if not violations:
            return 1.0

        # 按违规比例扣分
        validity = 1.0 - len(violations) / len(constraints)
        return max(0.0, validity)

    def _check_basic_validity(self, params: Dict[str, Any]) -> float:
        """检查基本参数有效性"""
        if not params:
            return 0.5  # 空参数给一半分

        valid_count = 0
        for key, value in params.items():
            if value is not None and value != "":
                valid_count += 1

        return valid_count / len(params)

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查类型"""
        type_map = {
            "str": str,
            "string": str,
            "int": int,
            "integer": int,
            "float": float,
            "bool": bool,
            "boolean": bool,
            "list": list,
            "dict": dict,
        }

        expected = type_map.get(expected_type.lower())
        if expected is None:
            return True

        return isinstance(value, expected)
