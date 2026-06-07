"""Evals 评估框架测试"""

import pytest
from dataclasses import asdict

from supply_chain_agent.harness.evals.base import (
    BaseEvaluator,
    EvalResult,
    EvalLevel,
    EvalSuite,
)


class MockEvaluator(BaseEvaluator):
    """测试用评估器"""

    eval_id = "mock_eval"
    eval_name = "Mock Evaluator"
    eval_level = EvalLevel.LEVEL_1_GATE

    async def evaluate(self, input_data, expected_output):
        score = 1.0 if input_data.get("value") == expected_output.get("expected") else 0.0
        passed = score == 1.0
        return self._create_result(passed, score, {"input": input_data, "expected": expected_output})


class TestEvalResult:
    """EvalResult 测试"""

    def test_to_dict(self):
        """测试转换为字典"""
        result = EvalResult(
            eval_id="test",
            eval_name="Test",
            level=EvalLevel.LEVEL_1_GATE,
            passed=True,
            score=1.0,
            details={"key": "value"}
        )

        d = result.to_dict()

        assert d["eval_id"] == "test"
        assert d["level"] == 1
        assert d["passed"] is True
        assert d["details"]["key"] == "value"


class TestBaseEvaluator:
    """BaseEvaluator 测试"""

    @pytest.mark.asyncio
    async def test_evaluate_returns_result(self):
        """测试评估返回结果"""
        evaluator = MockEvaluator()

        result = await evaluator.evaluate({"value": "a"}, {"expected": "a"})

        assert result.passed is True
        assert result.score == 1.0
        assert result.eval_id == "mock_eval"
        assert result.level == EvalLevel.LEVEL_1_GATE

    @pytest.mark.asyncio
    async def test_evaluate_failure(self):
        """测试评估失败"""
        evaluator = MockEvaluator()

        result = await evaluator.evaluate({"value": "a"}, {"expected": "b"})

        assert result.passed is False
        assert result.score == 0.0


class TestEvalSuite:
    """EvalSuite 测试"""

    @pytest.mark.asyncio
    async def test_run_all(self):
        """测试运行所有评估"""
        suite = EvalSuite("test_suite")
        suite.add_evaluator(MockEvaluator())
        suite.add_evaluator(MockEvaluator())

        test_cases = [
            {"input": {"value": "a"}, "expected": {"expected": "a"}},
            {"input": {"value": "b"}, "expected": {"expected": "b"}},
        ]

        results = await suite.run_all(test_cases)

        assert len(results) == 4  # 2 evaluators * 2 cases

    def test_get_summary(self):
        """测试获取摘要"""
        suite = EvalSuite("test_suite")

        results = [
            EvalResult("a", "A", EvalLevel.LEVEL_1_GATE, True, 1.0, {}),
            EvalResult("b", "B", EvalLevel.LEVEL_1_GATE, False, 0.5, {}),
            EvalResult("c", "C", EvalLevel.LEVEL_2_ALERT, True, 0.8, {}),
        ]

        summary = suite.get_summary(results)

        assert summary["total"] == 3
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["pass_rate"] == 2/3
        assert "level_1" in summary["by_level"]
        assert "level_2" in summary["by_level"]
