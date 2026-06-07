"""
端到端评估器

评估完整工作流的执行效果。
"""

from .base import BaseEvaluator, EvalResult, EvalLevel
from typing import Dict, Any
import time


class E2EWorkflowEvaluator(BaseEvaluator):
    """端到端工作流评估器"""

    eval_id = "e2e_workflow"
    eval_name = "End-to-End Workflow Success"
    eval_level = EvalLevel.LEVEL_1_GATE

    def __init__(self, orchestrator_agent, threshold: float = 0.85):
        """
        初始化

        Args:
            orchestrator_agent: Orchestrator Agent 实例
            threshold: 通过阈值
        """
        self.orchestrator = orchestrator_agent
        self.threshold = threshold

    async def evaluate(self, input_data: Dict[str, Any], expected_output: Dict[str, Any]) -> EvalResult:
        """
        评估端到端工作流

        Args:
            input_data: 包含 user_query 的输入数据
            expected_output: 包含 response_keywords 和 tools_used 的期望输出

        Returns:
            EvalResult
        """
        user_query = input_data.get("user_query", "")
        expected_response_keywords = expected_output.get("response_keywords", [])
        expected_tools_used = expected_output.get("tools_used", [])

        try:
            # 执行完整工作流
            result = await self.orchestrator.process(user_query)

            # 评估响应内容
            response = result.get("response", "")
            keyword_score = self._calculate_keyword_score(response, expected_response_keywords)

            # 评估工具使用
            actual_tools = result.get("tools_used", [])
            tool_score = self._calculate_tool_score(actual_tools, expected_tools_used)

            # 综合评分
            score = keyword_score * 0.4 + tool_score * 0.4 + (1.0 if result.get("success", False) else 0.0) * 0.2

            passed = score >= self.threshold

            details = {
                "response_preview": response[:200] if response else "",
                "keyword_score": keyword_score,
                "actual_tools": actual_tools,
                "expected_tools": expected_tools_used,
                "tool_score": tool_score,
                "workflow_success": result.get("success", False)
            }

            return self._create_result(passed, score, details)

        except Exception as e:
            return self._create_result(False, 0.0, {}, str(e))

    def _calculate_keyword_score(self, response: str, keywords: list) -> float:
        """计算关键词匹配分数"""
        if not keywords:
            return 1.0

        response_lower = response.lower()
        matched = sum(1 for kw in keywords if kw.lower() in response_lower)
        return matched / len(keywords)

    def _calculate_tool_score(self, actual: list, expected: list) -> float:
        """计算工具匹配分数"""
        if not expected:
            return 1.0

        actual_set = set(actual)
        expected_set = set(expected)

        intersection = actual_set & expected_set
        return len(intersection) / len(expected_set)


class E2ELatencyEvaluator(BaseEvaluator):
    """端到端延迟评估器"""

    eval_id = "e2e_latency"
    eval_name = "End-to-End Latency"
    eval_level = EvalLevel.LEVEL_2_ALERT

    def __init__(self, orchestrator_agent, max_latency_ms: float = 5000):
        """
        初始化

        Args:
            orchestrator_agent: Orchestrator Agent 实例
            max_latency_ms: 最大允许延迟（毫秒）
        """
        self.orchestrator = orchestrator_agent
        self.max_latency_ms = max_latency_ms

    async def evaluate(self, input_data: Dict[str, Any], expected_output: Dict[str, Any]) -> EvalResult:
        """
        评估端到端延迟

        Args:
            input_data: 包含 user_query 的输入数据
            expected_output: 期望输出（此处不使用）

        Returns:
            EvalResult
        """
        user_query = input_data.get("user_query", "")

        try:
            start_time = time.time()
            result = await self.orchestrator.process(user_query)
            end_time = time.time()

            latency_ms = (end_time - start_time) * 1000

            # 计算分数（延迟越低分数越高）
            if latency_ms <= self.max_latency_ms:
                score = 1.0
            else:
                # 超出部分按比例扣分
                score = max(0, 1 - (latency_ms - self.max_latency_ms) / self.max_latency_ms)

            passed = latency_ms <= self.max_latency_ms

            details = {
                "latency_ms": latency_ms,
                "max_latency_ms": self.max_latency_ms,
                "workflow_success": result.get("success", False)
            }

            return self._create_result(passed, score, details)

        except Exception as e:
            return self._create_result(False, 0.0, {}, str(e))
