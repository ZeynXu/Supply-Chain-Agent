"""
意图识别评估器

评估 Parser Agent 的意图解析准确率。
"""

from .base import BaseEvaluator, EvalResult, EvalLevel
from typing import Dict, Any, List


class IntentAccuracyEvaluator(BaseEvaluator):
    """意图识别准确率评估器"""

    eval_id = "intent_accuracy"
    eval_name = "Intent Recognition Accuracy"
    eval_level = EvalLevel.LEVEL_1_GATE

    def __init__(self, parser_agent, threshold: float = 0.85):
        """
        初始化

        Args:
            parser_agent: Parser Agent 实例
            threshold: 通过阈值
        """
        self.parser = parser_agent
        self.threshold = threshold

    async def evaluate(self, input_data: Dict[str, Any], expected_output: Dict[str, Any]) -> EvalResult:
        """
        评估意图识别

        Args:
            input_data: 包含 user_input 的输入数据
            expected_output: 期望的意图输出

        Returns:
            EvalResult
        """
        user_input = input_data.get("user_input", "")

        try:
            # 执行意图解析
            actual_output = await self.parser.parse_intent(user_input)

            # 计算准确率
            expected_intent_1 = expected_output.get("intent_level_1", "")
            expected_intent_2 = expected_output.get("intent_level_2", "")

            actual_intent_1 = actual_output.get("intent_level_1", "")
            actual_intent_2 = actual_output.get("intent_level_2", "")

            # 计分逻辑
            score = 0.0
            details = {}

            # 一级意图匹配 (40%)
            if actual_intent_1 == expected_intent_1:
                score += 0.4
                details["intent_level_1_match"] = True
            else:
                details["intent_level_1_match"] = False
                details["expected_intent_1"] = expected_intent_1
                details["actual_intent_1"] = actual_intent_1

            # 二级意图匹配 (40%)
            if actual_intent_2 == expected_intent_2:
                score += 0.4
                details["intent_level_2_match"] = True
            else:
                details["intent_level_2_match"] = False
                details["expected_intent_2"] = expected_intent_2
                details["actual_intent_2"] = actual_intent_2

            # 实体匹配 (20%)
            expected_entities = expected_output.get("entities", [])
            actual_entities = actual_output.get("entities", [])

            entity_score = self._calculate_entity_score(expected_entities, actual_entities)
            score += entity_score * 0.2
            details["entity_score"] = entity_score

            passed = score >= self.threshold

            return self._create_result(passed, score, details)

        except Exception as e:
            return self._create_result(False, 0.0, {}, str(e))

    def _calculate_entity_score(self, expected: list, actual: list) -> float:
        """计算实体匹配分数"""
        if not expected:
            return 1.0 if not actual else 0.5

        expected_set = {(e.get("type"), str(e.get("value"))) for e in expected if isinstance(e, dict)}
        actual_set = {(e.get("type"), str(e.get("value"))) for e in actual if isinstance(e, dict)}

        if not expected_set:
            return 1.0

        intersection = expected_set & actual_set
        return len(intersection) / len(expected_set)


class IntentConfidenceEvaluator(BaseEvaluator):
    """意图置信度评估器"""

    eval_id = "intent_confidence"
    eval_name = "Intent Confidence Score"
    eval_level = EvalLevel.LEVEL_2_ALERT

    def __init__(self, parser_agent, min_confidence: float = 0.7):
        """
        初始化

        Args:
            parser_agent: Parser Agent 实例
            min_confidence: 最小置信度阈值
        """
        self.parser = parser_agent
        self.min_confidence = min_confidence

    async def evaluate(self, input_data: Dict[str, Any], expected_output: Dict[str, Any]) -> EvalResult:
        """
        评估意图置信度

        Args:
            input_data: 包含 user_input 的输入数据
            expected_output: 期望输出（此处不使用）

        Returns:
            EvalResult
        """
        user_input = input_data.get("user_input", "")

        try:
            actual_output = await self.parser.parse_intent(user_input)
            confidence = actual_output.get("confidence", 0.0)

            passed = confidence >= self.min_confidence

            return self._create_result(
                passed,
                confidence,
                {
                    "confidence": confidence,
                    "min_confidence": self.min_confidence
                }
            )

        except Exception as e:
            return self._create_result(False, 0.0, {}, str(e))
