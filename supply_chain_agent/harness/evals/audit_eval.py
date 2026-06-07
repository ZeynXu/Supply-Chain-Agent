"""
审计规则评估器

评估 Auditor Agent 的规则覆盖率。
"""

from .base import BaseEvaluator, EvalResult, EvalLevel
from typing import Dict, Any, List


class AuditRuleCoverageEvaluator(BaseEvaluator):
    """审计规则覆盖率评估器"""

    eval_id = "audit_rule_coverage"
    eval_name = "Audit Rule Coverage"
    eval_level = EvalLevel.LEVEL_2_ALERT

    def __init__(self, auditor_agent, rule_evaluator=None, threshold: float = 0.9):
        """
        初始化

        Args:
            auditor_agent: Auditor Agent 实例
            rule_evaluator: 规则评估器（可选）
            threshold: 通过阈值
        """
        self.auditor = auditor_agent
        self.rule_evaluator = rule_evaluator
        self.threshold = threshold

    async def evaluate(self, input_data: Dict[str, Any], expected_output: Dict[str, Any]) -> EvalResult:
        """
        评估审计规则覆盖

        Args:
            input_data: 包含 tool_results 的输入数据
            expected_output: 包含 expected_violations 的期望输出

        Returns:
            EvalResult
        """
        tool_results = input_data.get("tool_results", {})
        expected_violations = expected_output.get("expected_violations", [])

        try:
            # 执行审计
            audit_result = await self.auditor.audit_results(tool_results)

            # 获取触发的规则
            actual_issues = audit_result.get("issues", [])
            actual_warnings = audit_result.get("warnings", [])

            # 计算覆盖率
            triggered_rules = set()
            for issue in actual_issues:
                triggered_rules.add(str(issue))

            expected_set = set(expected_violations)

            # 计算召回率
            if expected_set:
                intersection = expected_set & triggered_rules
                recall = len(intersection) / len(expected_set)
            else:
                recall = 1.0 if not triggered_rules else 0.5

            passed = recall >= self.threshold

            details = {
                "expected_violations": expected_violations,
                "actual_issues": actual_issues,
                "actual_warnings": actual_warnings,
                "recall": recall
            }

            return self._create_result(passed, recall, details)

        except Exception as e:
            return self._create_result(False, 0.0, {}, str(e))


class RiskScoreEvaluator(BaseEvaluator):
    """风险评分评估器"""

    eval_id = "risk_score"
    eval_name = "Risk Score Accuracy"
    eval_level = EvalLevel.LEVEL_2_ALERT

    def __init__(self, auditor_agent, tolerance: float = 0.2):
        """
        初始化

        Args:
            auditor_agent: Auditor Agent 实例
            tolerance: 允许的误差范围
        """
        self.auditor = auditor_agent
        self.tolerance = tolerance

    async def evaluate(self, input_data: Dict[str, Any], expected_output: Dict[str, Any]) -> EvalResult:
        """
        评估风险评分

        Args:
            input_data: 包含 tool_results 的输入数据
            expected_output: 包含 expected_risk_score 的期望输出

        Returns:
            EvalResult
        """
        tool_results = input_data.get("tool_results", {})
        expected_risk = expected_output.get("expected_risk_score", 0.0)

        try:
            actual_risk = await self.auditor.get_risk_score(tool_results)

            # 计算误差
            error = abs(actual_risk - expected_risk)
            score = max(0, 1 - error / self.tolerance)

            passed = error <= self.tolerance

            details = {
                "expected_risk_score": expected_risk,
                "actual_risk_score": actual_risk,
                "error": error,
                "tolerance": self.tolerance
            }

            return self._create_result(passed, score, details)

        except Exception as e:
            return self._create_result(False, 0.0, {}, str(e))
