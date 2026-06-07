"""
Evals 基础评估器框架

支持自建评估 + TruLens + OpenAI evals 通用功能。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum
import json


class EvalLevel(Enum):
    """评估等级"""
    LEVEL_1_GATE = 1      # 门禁级：必须通过才能部署
    LEVEL_2_ALERT = 2     # 告警级：失败只告警
    LEVEL_3_MANUAL = 3    # 手动级：可选执行


@dataclass
class EvalResult:
    """评估结果"""
    eval_id: str
    eval_name: str
    level: EvalLevel
    passed: bool
    score: float  # 0.0 - 1.0
    details: Dict[str, Any]
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "eval_id": self.eval_id,
            "eval_name": self.eval_name,
            "level": self.level.value,
            "passed": self.passed,
            "score": self.score,
            "details": self.details,
            "error_message": self.error_message
        }


class BaseEvaluator(ABC):
    """评估器基类"""

    eval_id: str = ""
    eval_name: str = ""
    eval_level: EvalLevel = EvalLevel.LEVEL_2_ALERT

    @abstractmethod
    async def evaluate(self, input_data: Dict[str, Any], expected_output: Dict[str, Any]) -> EvalResult:
        """
        执行评估

        Args:
            input_data: 输入数据
            expected_output: 期望输出

        Returns:
            EvalResult
        """
        pass

    def _create_result(
        self,
        passed: bool,
        score: float,
        details: Dict[str, Any],
        error: str = None
    ) -> EvalResult:
        """创建评估结果"""
        return EvalResult(
            eval_id=self.eval_id,
            eval_name=self.eval_name,
            level=self.eval_level,
            passed=passed,
            score=score,
            details=details,
            error_message=error
        )


class EvalSuite:
    """评估套件"""

    def __init__(self, name: str):
        self.name = name
        self.evaluators: List[BaseEvaluator] = []

    def add_evaluator(self, evaluator: BaseEvaluator):
        """添加评估器"""
        self.evaluators.append(evaluator)

    async def run_all(self, test_cases: List[Dict[str, Any]]) -> List[EvalResult]:
        """
        运行所有评估

        Args:
            test_cases: 测试用例列表，每个用例包含 input 和 expected

        Returns:
            所有评估结果
        """
        results = []
        for case in test_cases:
            for evaluator in self.evaluators:
                result = await evaluator.evaluate(
                    case.get("input", {}),
                    case.get("expected", {})
                )
                results.append(result)
        return results

    def get_summary(self, results: List[EvalResult]) -> Dict[str, Any]:
        """获取评估摘要"""
        total = len(results)
        passed = sum(1 for r in results if r.passed)

        by_level = {}
        for level in EvalLevel:
            level_results = [r for r in results if r.level == level]
            by_level[f"level_{level.value}"] = {
                "total": len(level_results),
                "passed": sum(1 for r in level_results if r.passed),
                "avg_score": sum(r.score for r in level_results) / len(level_results) if level_results else 0
            }

        return {
            "suite_name": self.name,
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 0,
            "by_level": by_level
        }

    def save_results(self, results: List[EvalResult], filepath: str):
        """保存评估结果到文件"""
        data = {
            "suite_name": self.name,
            "results": [r.to_dict() for r in results],
            "summary": self.get_summary(results)
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
