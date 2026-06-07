"""
工具调用评估器

评估 Executor Agent 的工具调用正确率。
"""

from .base import BaseEvaluator, EvalResult, EvalLevel
from typing import Dict, Any, List


class ToolCallAccuracyEvaluator(BaseEvaluator):
    """工具调用准确率评估器"""

    eval_id = "tool_call_accuracy"
    eval_name = "Tool Call Accuracy"
    eval_level = EvalLevel.LEVEL_1_GATE

    def __init__(self, executor_agent, threshold: float = 0.9):
        """
        初始化

        Args:
            executor_agent: Executor Agent 实例
            threshold: 通过阈值
        """
        self.executor = executor_agent
        self.threshold = threshold

    async def evaluate(self, input_data: Dict[str, Any], expected_output: Dict[str, Any]) -> EvalResult:
        """
        评估工具调用

        Args:
            input_data: 包含 intent 的输入数据
            expected_output: 包含 expected_tools 的期望输出

        Returns:
            EvalResult
        """
        intent = input_data.get("intent", {})
        expected_tools = expected_output.get("expected_tools", [])

        try:
            # 生成执行计划
            actual_plan = await self.executor.create_execution_plan(intent)
            actual_tools = [t if isinstance(t, str) else t.get("name", t) for t in actual_plan]

            # 计算匹配度
            expected_set = set(expected_tools)
            actual_set = set(actual_tools)

            if not expected_set:
                score = 1.0 if not actual_set else 0.5
            else:
                intersection = expected_set & actual_set
                score = len(intersection) / len(expected_set)

            passed = score >= self.threshold

            details = {
                "expected_tools": expected_tools,
                "actual_tools": actual_tools,
                "matched": list(expected_set & actual_set),
                "missing": list(expected_set - actual_set),
                "extra": list(actual_set - expected_set)
            }

            return self._create_result(passed, score, details)

        except Exception as e:
            return self._create_result(False, 0.0, {}, str(e))


class ToolParamValidationEvaluator(BaseEvaluator):
    """工具参数验证评估器"""

    eval_id = "tool_param_validation"
    eval_name = "Tool Parameter Validation"
    eval_level = EvalLevel.LEVEL_1_GATE

    def __init__(self, executor_agent):
        """
        初始化

        Args:
            executor_agent: Executor Agent 实例
        """
        self.executor = executor_agent

    async def evaluate(self, input_data: Dict[str, Any], expected_output: Dict[str, Any]) -> EvalResult:
        """
        评估工具参数

        Args:
            input_data: 包含 tool_name 和 params 的输入数据
            expected_output: 包含 is_valid 的期望输出

        Returns:
            EvalResult
        """
        tool_name = input_data.get("tool_name", "")
        params = input_data.get("params", {})
        expected_valid = expected_output.get("is_valid", True)

        try:
            # 验证参数
            validation_result = self.executor._validate_tool_params(tool_name, params)
            actual_valid = validation_result.get("valid", False)

            passed = actual_valid == expected_valid
            score = 1.0 if passed else 0.0

            details = {
                "tool_name": tool_name,
                "params": params,
                "validation_result": validation_result,
                "expected_valid": expected_valid,
                "actual_valid": actual_valid
            }

            return self._create_result(passed, score, details)

        except Exception as e:
            return self._create_result(False, 0.0, {}, str(e))


class ToolExecutionSuccessEvaluator(BaseEvaluator):
    """工具执行成功率评估器"""

    eval_id = "tool_execution_success"
    eval_name = "Tool Execution Success Rate"
    eval_level = EvalLevel.LEVEL_2_ALERT

    def __init__(self, executor_agent, threshold: float = 0.95):
        """
        初始化

        Args:
            executor_agent: Executor Agent 实例
            threshold: 通过阈值
        """
        self.executor = executor_agent
        self.threshold = threshold

    async def evaluate(self, input_data: Dict[str, Any], expected_output: Dict[str, Any]) -> EvalResult:
        """
        评估工具执行

        Args:
            input_data: 包含 tool_name 和 params 的输入数据
            expected_output: 期望输出（此处不使用）

        Returns:
            EvalResult
        """
        tool_name = input_data.get("tool_name", "")
        params = input_data.get("params", {})

        try:
            result = await self.executor.execute_task(tool_name, params)

            success = result.get("success", False) and "error" not in result
            score = 1.0 if success else 0.0

            details = {
                "tool_name": tool_name,
                "success": success,
                "result_keys": list(result.keys())
            }

            if not success:
                details["error"] = result.get("error", "Unknown error")

            passed = success

            return self._create_result(passed, score, details)

        except Exception as e:
            return self._create_result(False, 0.0, {}, str(e))
