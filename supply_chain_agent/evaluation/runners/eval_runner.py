"""
评估运行器

编排各类评估器，提供统一的评估入口。
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..config import EvalConfig
from ..core.base import (
    FullEvaluation,
    TrajectoryScore,
    QualityScore,
    EvalContext,
    GoldenSample,
    GoldResult,
    ToolCallActual,
    ToolCallGold,
    ToolCallEvaluation,
)
from ..core.trajectory_scorer import TrajectoryScorer
from ..core.tool_call_validator import ToolCallValidator
from ..judges.llm_judge import LLMJudge

logger = logging.getLogger(__name__)


@dataclass
class EvalRunnerConfig:
    """评估运行器配置"""
    include_trajectory: bool = True       # 是否进行轨迹评分
    include_quality: bool = True          # 是否进行质量评分
    include_tool_validation: bool = True # 是否进行工具调用验证
    include_harness_evals: bool = True    # 是否集成Harness Evals
    quality_sample_rate: float = 1.0      # 质量评分采样率（生产环境可降低）
    max_concurrent: int = 10              # 最大并发评估数

    def to_dict(self) -> Dict[str, Any]:
        return {
            "include_trajectory": self.include_trajectory,
            "include_quality": self.include_quality,
            "include_tool_validation": self.include_tool_validation,
            "include_harness_evals": self.include_harness_evals,
            "quality_sample_rate": self.quality_sample_rate,
            "max_concurrent": self.max_concurrent
        }


class EvalRunner:
    """
    评估运行编排器

    编排轨迹评分、LLM Judge等评估器，提供统一的评估入口。
    集成Harness Evals框架。
    """

    def __init__(
        self,
        config: Optional[EvalConfig] = None,
        runner_config: Optional[EvalRunnerConfig] = None,
        trace_dir: Optional[str] = None,
        agents: Optional[Dict[str, Any]] = None
    ):
        """
        初始化

        Args:
            config: 评估系统配置
            runner_config: 运行器配置
            trace_dir: Trace文件目录
            agents: Agent实例字典，用于Harness Evals集成
                   {"parser": ParserAgent, "executor": ExecutorAgent, ...}
        """
        self.config = config or EvalConfig.get_default()
        self.runner_config = runner_config or EvalRunnerConfig()
        self.trace_dir = trace_dir
        self.agents = agents or {}

        # 初始化各评估器
        self.trajectory_scorer = TrajectoryScorer(self.config, trace_dir)
        self.llm_judge = LLMJudge(self.config.llm_judge)
        self.tool_validator = ToolCallValidator(self.config)

        # 初始化Harness Evals集成
        self._harness_evals = None
        if self.runner_config.include_harness_evals:
            try:
                from ..harness_integration import get_evals_integration
                self._harness_evals = get_evals_integration()
            except ImportError:
                logger.warning("Harness Evals集成不可用")

        # 统计信息
        self._stats = {
            "total_evaluated": 0,
            "total_passed": 0,
            "total_failed": 0,
            "errors": 0
        }

    async def evaluate_thread(
        self,
        thread_id: str,
        gold: Optional[GoldResult] = None,
        context: Optional[EvalContext] = None
    ) -> FullEvaluation:
        """
        评估单个会话

        Args:
            thread_id: 会话ID
            gold: 黄金标准（可选）
            context: 评估上下文（可选，若提供则直接使用）

        Returns:
            FullEvaluation: 完整评估结果
        """
        # 构建评估上下文
        if context is None:
            context = await self._build_context(thread_id, gold)

        # 轨迹评分
        trajectory_score = None
        if self.runner_config.include_trajectory:
            trajectory_score = await self.trajectory_scorer.score(thread_id, gold, context)

        # 质量评分
        quality_score = None
        if self.runner_config.include_quality and context.final_response:
            # 采样判断
            import random
            if random.random() <= self.runner_config.quality_sample_rate:
                quality_score = await self.llm_judge.score(
                    context.user_query,
                    context.final_response,
                    context
                )

        # 工具调用验证
        tool_evaluations = []
        if self.runner_config.include_tool_validation and gold and context.tool_calls:
            tool_evaluations = self._evaluate_tool_calls(context, gold)

        # 综合判断
        overall_passed = self._determine_pass(trajectory_score, quality_score, tool_evaluations)

        # 更新统计
        self._stats["total_evaluated"] += 1
        if overall_passed:
            self._stats["total_passed"] += 1
        else:
            self._stats["total_failed"] += 1

        return FullEvaluation(
            thread_id=thread_id,
            trajectory_score=trajectory_score or self._get_default_trajectory_score(thread_id),
            quality_score=quality_score,
            tool_evaluations=tool_evaluations,
            overall_passed=overall_passed,
            metadata={
                "config": self.runner_config.to_dict(),
                "evaluated_at": datetime.now().isoformat()
            }
        )

    async def evaluate_batch(
        self,
        samples: List[GoldenSample]
    ) -> Dict[str, FullEvaluation]:
        """
        批量评估

        Args:
            samples: 黄金样本列表

        Returns:
            评估结果字典，key为sample_id
        """
        results = {}

        # 简单串行处理（可优化为并发）
        for sample in samples:
            try:
                result = await self.evaluate_thread(
                    sample.sample_id,
                    sample.gold_result
                )
                results[sample.sample_id] = result
            except Exception as e:
                logger.error(f"Evaluation failed for {sample.sample_id}: {e}")
                self._stats["errors"] += 1

        return results

    async def evaluate_from_traces(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[FullEvaluation]:
        """
        从Trace文件评估

        Args:
            start_time: 开始时间
            end_time: 结束时间
            limit: 最大评估数量

        Returns:
            评估结果列表
        """
        results = []
        trace_dir = Path(self.trace_dir or "/root/autodl-tmp/harness-traces")

        if not trace_dir.exists():
            logger.warning(f"Trace directory not found: {trace_dir}")
            return results

        # 查找Trace文件
        trace_files = sorted(trace_dir.glob("*.jsonl"), reverse=True)

        for trace_file in trace_files[:7]:  # 最多查看7天
            if len(results) >= limit:
                break

            try:
                with open(trace_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if len(results) >= limit:
                            break

                        if line.strip():
                            trace = json.loads(line)
                            thread_id = trace.get("trace_id", "")

                            if thread_id:
                                result = await self.evaluate_thread(thread_id)
                                results.append(result)
            except Exception as e:
                logger.error(f"Error reading trace file {trace_file}: {e}")

        return results

    async def _build_context(
        self,
        thread_id: str,
        gold: Optional[GoldResult]
    ) -> EvalContext:
        """构建评估上下文"""
        # 使用TrajectoryScorer的上下文构建逻辑
        return await self.trajectory_scorer._build_context(thread_id)

    def _evaluate_tool_calls(
        self,
        context: EvalContext,
        gold: GoldResult
    ) -> List[ToolCallEvaluation]:
        """评估工具调用"""
        evaluations = []

        for tc in context.tool_calls:
            actual = ToolCallActual(
                tool_name=tc.get("tool_name", ""),
                params=tc.get("params", {}),
                success=tc.get("success", True)
            )

            # 构建黄金标准
            gold_tc = ToolCallGold(
                should_call_tool=bool(gold.expected_tools),
                expected_tool=gold.expected_tools[0] if gold.expected_tools else None,
                expected_params={}
            )

            evaluation = self.tool_validator.evaluate(actual, gold_tc)
            evaluations.append(evaluation)

        return evaluations

    def _determine_pass(
        self,
        trajectory_score: Optional[TrajectoryScore],
        quality_score: Optional[QualityScore],
        tool_evaluations: List[ToolCallEvaluation]
    ) -> bool:
        """判断是否通过"""
        # 轨迹评分判断
        if trajectory_score:
            if trajectory_score.overall_score < self.config.thresholds.trajectory_pass:
                return False

        # 质量评分判断
        if quality_score:
            avg_quality = quality_score.average_score()
            if avg_quality < self.config.thresholds.quality_pass:
                return False

        # 工具调用判断
        if tool_evaluations:
            for te in tool_evaluations:
                if not te.tool_correct and te.overall_score < 0.5:
                    return False

        return True

    def _get_default_trajectory_score(self, thread_id: str) -> TrajectoryScore:
        """获取默认轨迹评分"""
        from ..core.base import DimensionScore
        from ..core.trajectory_scorer import ALL_DIMENSIONS

        return TrajectoryScore(
            trace_id=thread_id,
            overall_score=0.0,
            dimension_scores=[
                DimensionScore(dimension=d, score=0.0, weight=0.0, passed=False)
                for d in ALL_DIMENSIONS
            ],
            metadata={"error": "Trajectory scoring disabled or failed"}
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.copy()
        if stats["total_evaluated"] > 0:
            stats["pass_rate"] = stats["total_passed"] / stats["total_evaluated"]
        else:
            stats["pass_rate"] = 0.0
        return stats

    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            "total_evaluated": 0,
            "total_passed": 0,
            "total_failed": 0,
            "errors": 0
        }

    # ============================================
    # Harness Evals集成方法
    # ============================================

    async def run_harness_intent_eval(
        self,
        test_cases: Optional[List[Dict[str, Any]]] = None
    ) -> List[Any]:
        """
        运行Harness意图识别评估

        Args:
            test_cases: 测试用例列表，格式：
                [{"input": {"user_input": "..."}, "expected": {"intent_level_1": "...", ...}}, ...]

        Returns:
            评估结果列表
        """
        if self._harness_evals is None:
            logger.warning("Harness Evals集成未启用")
            return []

        parser = self.agents.get("parser")
        if parser is None:
            logger.warning("未提供Parser Agent，无法运行意图评估")
            return []

        return await self._harness_evals.run_intent_eval(parser, test_cases or [])

    async def run_harness_tool_eval(
        self,
        test_cases: Optional[List[Dict[str, Any]]] = None
    ) -> List[Any]:
        """
        运行Harness工具调用评估

        Args:
            test_cases: 测试用例列表

        Returns:
            评估结果列表
        """
        if self._harness_evals is None:
            logger.warning("Harness Evals集成未启用")
            return []

        executor = self.agents.get("executor")
        if executor is None:
            logger.warning("未提供Executor Agent，无法运行工具评估")
            return []

        return await self._harness_evals.run_tool_eval(executor, test_cases or [])

    async def run_harness_e2e_eval(
        self,
        test_cases: Optional[List[Dict[str, Any]]] = None
    ) -> List[Any]:
        """
        运行Harness端到端评估

        Args:
            test_cases: 测试用例列表

        Returns:
            评估结果列表
        """
        if self._harness_evals is None:
            logger.warning("Harness Evals集成未启用")
            return []

        orchestrator = self.agents.get("orchestrator")
        if orchestrator is None:
            logger.warning("未提供Orchestrator Agent，无法运行端到端评估")
            return []

        return await self._harness_evals.run_e2e_eval(orchestrator, test_cases or [])

    async def run_harness_audit_eval(
        self,
        test_cases: Optional[List[Dict[str, Any]]] = None
    ) -> List[Any]:
        """
        运行Harness审计规则评估

        Args:
            test_cases: 测试用例列表

        Returns:
            评估结果列表
        """
        if self._harness_evals is None:
            logger.warning("Harness Evals集成未启用")
            return []

        auditor = self.agents.get("auditor")
        if auditor is None:
            logger.warning("未提供Auditor Agent，无法运行审计评估")
            return []

        return await self._harness_evals.run_audit_eval(auditor, test_cases or [])

    async def run_all_harness_evals(
        self,
        test_cases: Optional[Dict[str, List[Dict[str, Any]]]] = None
    ) -> Dict[str, List[Any]]:
        """
        运行所有Harness评估

        Args:
            test_cases: 按类型分组的测试用例
                {"intent": [...], "tool": [...], "e2e": [...], "audit": [...]}

        Returns:
            各类评估结果
        """
        test_cases = test_cases or {}
        results = {}

        # 意图评估
        if "intent" in test_cases or self.agents.get("parser"):
            results["intent"] = await self.run_harness_intent_eval(test_cases.get("intent"))

        # 工具评估
        if "tool" in test_cases or self.agents.get("executor"):
            results["tool"] = await self.run_harness_tool_eval(test_cases.get("tool"))

        # 端到端评估
        if "e2e" in test_cases or self.agents.get("orchestrator"):
            results["e2e"] = await self.run_harness_e2e_eval(test_cases.get("e2e"))

        # 审计评估
        if "audit" in test_cases or self.agents.get("auditor"):
            results["audit"] = await self.run_harness_audit_eval(test_cases.get("audit"))

        return results

    def set_agents(self, agents: Dict[str, Any]):
        """
        设置Agent实例

        Args:
            agents: Agent实例字典
        """
        self.agents.update(agents)


# 便捷函数
async def quick_evaluate(
    thread_id: str,
    include_quality: bool = False
) -> FullEvaluation:
    """
    快速评估单个会话

    Args:
        thread_id: 会话ID
        include_quality: 是否进行质量评分

    Returns:
        FullEvaluation
    """
    runner_config = EvalRunnerConfig(
        include_quality=include_quality,
        quality_sample_rate=1.0
    )
    runner = EvalRunner(runner_config=runner_config)
    return await runner.evaluate_thread(thread_id)
