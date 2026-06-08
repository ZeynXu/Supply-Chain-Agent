"""
九维轨迹评分器

消费Harness Trace数据，计算九个维度的归一化评分。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..config import EvalConfig, TrajectoryWeights
from .base import (
    DimensionScore,
    TrajectoryScore,
    EvalContext,
    GoldResult,
)

logger = logging.getLogger(__name__)


# 维度名称常量
DIM_TOOL_SELECTION = "tool_selection"
DIM_PARAMS_COMPLETE = "params_complete"
DIM_PARAMS_VALID = "params_valid"
DIM_EXECUTION_ORDER = "execution_order"
DIM_AUDIT_COMPLIANCE = "audit_compliance"
DIM_ANSWER_REACHABILITY = "answer_reachability"
DIM_ERROR_RECOVERY = "error_recovery"
DIM_CLARIFICATION_EFFICIENCY = "clarification_efficiency"
DIM_LATENCY = "latency"

# 所有维度列表
ALL_DIMENSIONS = [
    DIM_TOOL_SELECTION,
    DIM_PARAMS_COMPLETE,
    DIM_PARAMS_VALID,
    DIM_EXECUTION_ORDER,
    DIM_AUDIT_COMPLIANCE,
    DIM_ANSWER_REACHABILITY,
    DIM_ERROR_RECOVERY,
    DIM_CLARIFICATION_EFFICIENCY,
    DIM_LATENCY,
]


class TrajectoryScorer:
    """
    九维轨迹评分器

    输入：Harness Trace数据
    输出：九个维度的归一化评分 + 综合得分
    """

    # 默认延迟阈值（毫秒）
    DEFAULT_LATENCY_THRESHOLD_MS = 5000

    # 澄清循环最大轮次
    MAX_CLARIFICATION_ROUNDS = 3

    def __init__(
        self,
        config: Optional[EvalConfig] = None,
        trace_dir: Optional[str] = None,
        use_harness_rules: bool = True
    ):
        """
        初始化

        Args:
            config: 评估配置
            trace_dir: Trace文件目录
            use_harness_rules: 是否使用Harness Rules进行审计合规评估
        """
        self.config = config or EvalConfig.get_default()
        self.weights = self.config.trajectory_weights
        self.trace_dir = Path(trace_dir or "/root/autodl-tmp/harness-traces")
        self.use_harness_rules = use_harness_rules

        # 初始化Harness Rules集成
        self._rules_integration = None
        if use_harness_rules:
            try:
                from ..harness_integration import get_rules_integration
                self._rules_integration = get_rules_integration()
            except ImportError:
                logger.warning("Harness Rules集成不可用")
                self._rules_integration = None

    async def score(
        self,
        thread_id: str,
        gold: Optional[GoldResult] = None,
        context: Optional[EvalContext] = None
    ) -> TrajectoryScore:
        """
        评分主入口

        Args:
            thread_id: 会话ID
            gold: 黄金标准（可选）
            context: 评估上下文（可选，若提供则直接使用）

        Returns:
            TrajectoryScore: 九维评分结果
        """
        # 获取评估上下文
        if context is None:
            context = await self._build_context(thread_id)

        # 计算各维度评分
        dimension_scores = [
            self._score_tool_selection(context, gold),
            self._score_params_completeness(context),
            self._score_params_validity(context),
            self._score_execution_order(context),
            self._score_audit_compliance(context),
            self._score_answer_reachability(context, gold),
            self._score_error_recovery(context),
            self._score_clarification_efficiency(context),
            self._score_latency(context),
        ]

        # 计算加权综合得分
        overall_score = self._calculate_overall_score(dimension_scores)

        return TrajectoryScore(
            trace_id=thread_id,
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            metadata={
                "weights": self.weights.to_dict(),
                "context_status": context.status,
                "tool_call_count": len(context.tool_calls)
            }
        )

    async def _build_context(self, thread_id: str) -> EvalContext:
        """
        构建评估上下文

        Args:
            thread_id: 会话ID

        Returns:
            EvalContext: 评估上下文
        """
        # 尝试从Trace文件加载
        trace_data = await self._load_trace(thread_id)

        if trace_data is None:
            return EvalContext(
                thread_id=thread_id,
                user_query="",
                status="no_trace"
            )

        # 解析Trace数据
        return self._parse_trace_to_context(thread_id, trace_data)

    async def _load_trace(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """加载Trace数据"""
        # 按日期查找Trace文件
        for trace_file in self.trace_dir.glob("*.jsonl"):
            try:
                with open(trace_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            trace = json.loads(line)
                            if trace.get("trace_id") == thread_id:
                                return trace
            except Exception as e:
                logger.debug(f"Error reading trace file {trace_file}: {e}")

        return None

    def _parse_trace_to_context(
        self,
        thread_id: str,
        trace_data: Dict[str, Any]
    ) -> EvalContext:
        """解析Trace数据为评估上下文"""
        attributes = trace_data.get("attributes", {})
        events = trace_data.get("events", [])

        # 提取工具调用
        tool_calls = []
        for event in events:
            if event.get("name", "").startswith("tool_call"):
                tool_calls.append({
                    "tool_name": event.get("attributes", {}).get("tool_name", ""),
                    "params": event.get("attributes", {}).get("params", {}),
                    "success": event.get("attributes", {}).get("success", True),
                    "timestamp": event.get("timestamp", "")
                })

        return EvalContext(
            thread_id=thread_id,
            user_query=attributes.get("user_query", ""),
            intent=attributes.get("intent", {}),
            trace=trace_data,
            tool_calls=tool_calls,
            audit_results=attributes.get("audit_results", {}),
            final_response=attributes.get("final_response", ""),
            latency_ms=trace_data.get("duration_ms", 0),
            status=trace_data.get("status", "ok")
        )

    def _calculate_overall_score(
        self,
        dimension_scores: List[DimensionScore]
    ) -> float:
        """计算加权综合得分"""
        total = 0.0
        for ds in dimension_scores:
            total += ds.score * ds.weight
        return round(total, 4)

    # ============================================
    # 各维度评分方法
    # ============================================

    def _score_tool_selection(
        self,
        context: EvalContext,
        gold: Optional[GoldResult]
    ) -> DimensionScore:
        """
        工具选择正确性评分

        评分逻辑：
        - 有黄金标准：正确工具数 / 期望工具数
        - 无黄金标准：成功工具调用数 / 总工具调用数
        """
        tool_calls = context.tool_calls

        if not tool_calls:
            # 无工具调用
            if gold and gold.expected_tools:
                # 期望有工具调用但实际没有
                return DimensionScore(
                    dimension=DIM_TOOL_SELECTION,
                    score=0.0,
                    weight=self.weights.tool_selection,
                    passed=False,
                    message="期望调用工具但实际未调用"
                )
            else:
                # 无需工具调用
                return DimensionScore(
                    dimension=DIM_TOOL_SELECTION,
                    score=1.0,
                    weight=self.weights.tool_selection,
                    passed=True,
                    message="无工具调用需求"
                )

        if gold and gold.expected_tools:
            # 有黄金标准：计算匹配率
            actual_tools = {tc.get("tool_name", "") for tc in tool_calls}
            expected_tools = set(gold.expected_tools)

            if not expected_tools:
                score = 1.0
            else:
                intersection = actual_tools & expected_tools
                score = len(intersection) / len(expected_tools)

            return DimensionScore(
                dimension=DIM_TOOL_SELECTION,
                score=score,
                weight=self.weights.tool_selection,
                passed=score >= 0.8,
                details={
                    "actual_tools": list(actual_tools),
                    "expected_tools": list(expected_tools),
                    "matched": list(intersection)
                },
                message=f"工具匹配率: {score:.2%}"
            )
        else:
            # 无黄金标准：计算成功率
            successful = sum(1 for tc in tool_calls if tc.get("success", True))
            score = successful / len(tool_calls)

            return DimensionScore(
                dimension=DIM_TOOL_SELECTION,
                score=score,
                weight=self.weights.tool_selection,
                passed=score >= 0.8,
                details={
                    "total_calls": len(tool_calls),
                    "successful_calls": successful
                },
                message=f"工具调用成功率: {score:.2%}"
            )

    def _score_params_completeness(
        self,
        context: EvalContext
    ) -> DimensionScore:
        """
        参数完整性评分

        评分逻辑：完整参数调用数 / 总调用数
        """
        tool_calls = context.tool_calls

        if not tool_calls:
            return DimensionScore(
                dimension=DIM_PARAMS_COMPLETE,
                score=1.0,
                weight=self.weights.params_complete,
                passed=True,
                message="无工具调用"
            )

        # 检查参数完整性
        complete_count = 0
        incomplete_details = []

        for tc in tool_calls:
            params = tc.get("params", {})
            tool_name = tc.get("tool_name", "")

            # 简单判断：参数不为空且不是占位符
            is_complete = bool(params) and not any(
                str(v).startswith("$") or v is None
                for v in params.values()
            )

            if is_complete:
                complete_count += 1
            else:
                incomplete_details.append({
                    "tool": tool_name,
                    "params": params
                })

        score = complete_count / len(tool_calls)

        return DimensionScore(
            dimension=DIM_PARAMS_COMPLETE,
            score=score,
            weight=self.weights.params_complete,
            passed=score >= 0.9,
            details={
                "total_calls": len(tool_calls),
                "complete_calls": complete_count,
                "incomplete": incomplete_details[:3]  # 最多记录3个
            },
            message=f"参数完整率: {score:.2%}"
        )

    def _score_params_validity(
        self,
        context: EvalContext
    ) -> DimensionScore:
        """
        参数有效性评分

        评分逻辑：通过验证的参数数 / 总参数数
        """
        tool_calls = context.tool_calls

        if not tool_calls:
            return DimensionScore(
                dimension=DIM_PARAMS_VALID,
                score=1.0,
                weight=self.weights.params_valid,
                passed=True,
                message="无工具调用"
            )

        # 检查参数有效性
        valid_count = 0
        invalid_details = []

        for tc in tool_calls:
            params = tc.get("params", {})
            tool_name = tc.get("tool_name", "")

            # 简单验证：参数值类型正确且符合基本约束
            is_valid = self._validate_params(tool_name, params)

            if is_valid:
                valid_count += 1
            else:
                invalid_details.append({
                    "tool": tool_name,
                    "params": params
                })

        score = valid_count / len(tool_calls)

        return DimensionScore(
            dimension=DIM_PARAMS_VALID,
            score=score,
            weight=self.weights.params_valid,
            passed=score >= 0.9,
            details={
                "total_calls": len(tool_calls),
                "valid_calls": valid_count,
                "invalid": invalid_details[:3]
            },
            message=f"参数有效率: {score:.2%}"
        )

    def _validate_params(self, tool_name: str, params: Dict[str, Any]) -> bool:
        """验证参数有效性"""
        # 基本验证：参数值不为空字符串或None
        for key, value in params.items():
            if value is None:
                return False
            if isinstance(value, str) and not value.strip():
                return False
        return True

    def _score_execution_order(
        self,
        context: EvalContext
    ) -> DimensionScore:
        """
        执行顺序合理性评分

        评分逻辑：检查工具调用顺序是否符合预期
        """
        tool_calls = context.tool_calls

        if len(tool_calls) <= 1:
            return DimensionScore(
                dimension=DIM_EXECUTION_ORDER,
                score=1.0,
                weight=self.weights.execution_order,
                passed=True,
                message="调用数<=1，顺序合理"
            )

        # 检查基本顺序规则
        # 规则1：查询类工具应在修改类工具之前
        # 规则2：审计应在执行之后
        order_violations = []

        query_tools = {"query_customer", "query_order", "query_shipment"}
        modify_tools = {"create_work_order", "approve_work_order", "update_status"}

        last_query_idx = -1
        first_modify_idx = len(tool_calls)

        for i, tc in enumerate(tool_calls):
            tool_name = tc.get("tool_name", "")
            if tool_name in query_tools:
                last_query_idx = i
            if tool_name in modify_tools and first_modify_idx == len(tool_calls):
                first_modify_idx = i

        # 查询应在修改之前
        if last_query_idx > first_modify_idx:
            order_violations.append("query_after_modify")

        score = 1.0 if not order_violations else 0.5

        return DimensionScore(
            dimension=DIM_EXECUTION_ORDER,
            score=score,
            weight=self.weights.execution_order,
            passed=score >= 0.8,
            details={
                "violations": order_violations,
                "call_sequence": [tc.get("tool_name", "") for tc in tool_calls]
            },
            message="顺序合理" if score == 1.0 else "存在顺序问题"
        )

    def _score_audit_compliance(
        self,
        context: EvalContext
    ) -> DimensionScore:
        """
        审计规则遵循评分

        评分逻辑：
        1. 如果启用了Harness Rules集成，直接调用规则引擎评估
        2. 否则使用context中的audit_results
        """
        # 尝试使用Harness Rules引擎
        if self._rules_integration and self._rules_integration.is_available():
            return self._score_audit_with_harness_rules(context)

        # 回退到使用context中的audit_results
        return self._score_audit_from_context(context)

    def _score_audit_with_harness_rules(
        self,
        context: EvalContext
    ) -> DimensionScore:
        """使用Harness Rules引擎进行审计评分"""
        # 构建规则评估上下文
        rule_context = {
            "work_order": context.metadata.get("work_order", {}) if hasattr(context, 'metadata') else {},
            "order": context.metadata.get("order", {}) if hasattr(context, 'metadata') else {},
            "customer": context.metadata.get("customer", {}) if hasattr(context, 'metadata') else {},
            "action": context.intent.get("intent_level_2", ""),
            "status": context.status,
        }

        # 从tool_calls中提取更多信息
        if context.tool_calls:
            for tc in context.tool_calls:
                tool_name = tc.get("tool_name", "")
                if "order" in tool_name:
                    rule_context["order"] = tc.get("params", {})
                elif "customer" in tool_name:
                    rule_context["customer"] = tc.get("params", {})
                elif "work_order" in tool_name or "work" in tool_name:
                    rule_context["work_order"] = tc.get("params", {})

        try:
            # 调用Harness Rules评估
            issues, warnings, notifications = self._rules_integration.evaluate_rules(rule_context)

            total_violations = len(issues) + len(warnings)

            # 计算评分
            if total_violations == 0:
                score = 1.0
            elif len(issues) == 0:
                score = 0.8
            else:
                score = max(0.5, 1.0 - len(issues) * 0.1)

            return DimensionScore(
                dimension=DIM_AUDIT_COMPLIANCE,
                score=score,
                weight=self.weights.audit_compliance,
                passed=len(issues) == 0,
                details={
                    "source": "harness_rules",
                    "issues_count": len(issues),
                    "warnings_count": len(warnings),
                    "notifications_count": len(notifications),
                    "issues": [str(i) for i in issues[:3]],
                    "warnings": [str(w) for w in warnings[:3]]
                },
                message=f"违规数: {total_violations} (Harness Rules)"
            )
        except Exception as e:
            logger.error(f"Harness Rules评估失败: {e}")
            return self._score_audit_from_context(context)

    def _score_audit_from_context(
        self,
        context: EvalContext
    ) -> DimensionScore:
        """从context中的audit_results计算审计评分"""
        audit_results = context.audit_results

        if not audit_results:
            return DimensionScore(
                dimension=DIM_AUDIT_COMPLIANCE,
                score=1.0,
                weight=self.weights.audit_compliance,
                passed=True,
                message="无审计结果"
            )

        # 统计违规情况
        issues = audit_results.get("issues", [])
        warnings = audit_results.get("warnings", [])

        total_violations = len(issues) + len(warnings)

        # 简化计算：无违规=1.0，有warning=0.8，有issue=0.5
        if total_violations == 0:
            score = 1.0
        elif len(issues) == 0:
            score = 0.8
        else:
            score = max(0.5, 1.0 - len(issues) * 0.1)

        return DimensionScore(
            dimension=DIM_AUDIT_COMPLIANCE,
            score=score,
            weight=self.weights.audit_compliance,
            passed=len(issues) == 0,
            details={
                "source": "context",
                "issues_count": len(issues),
                "warnings_count": len(warnings),
                "issues": issues[:3],
                "warnings": warnings[:3]
            },
            message=f"违规数: {total_violations}"
        )

    def _score_answer_reachability(
        self,
        context: EvalContext,
        gold: Optional[GoldResult]
    ) -> DimensionScore:
        """
        最终答案可达性评分

        评分逻辑：
        - 有黄金标准：检查响应关键词覆盖率
        - 无黄金标准：检查是否成功返回结果
        """
        if context.status == "error":
            return DimensionScore(
                dimension=DIM_ANSWER_REACHABILITY,
                score=0.0,
                weight=self.weights.answer_reachability,
                passed=False,
                message="执行失败"
            )

        final_response = context.final_response

        if gold and gold.expected_response_keywords:
            # 检查关键词覆盖
            keywords = gold.expected_response_keywords
            matched = sum(1 for kw in keywords if kw.lower() in final_response.lower())
            score = matched / len(keywords)

            return DimensionScore(
                dimension=DIM_ANSWER_REACHABILITY,
                score=score,
                weight=self.weights.answer_reachability,
                passed=score >= 0.7,
                details={
                    "expected_keywords": keywords,
                    "matched_count": matched
                },
                message=f"关键词覆盖率: {score:.2%}"
            )
        else:
            # 检查是否有有效响应
            has_response = bool(final_response and len(final_response) > 10)
            score = 1.0 if has_response else 0.0

            return DimensionScore(
                dimension=DIM_ANSWER_REACHABILITY,
                score=score,
                weight=self.weights.answer_reachability,
                passed=has_response,
                message="有有效响应" if has_response else "无有效响应"
            )

    def _score_error_recovery(
        self,
        context: EvalContext
    ) -> DimensionScore:
        """
        错误恢复能力评分

        评分逻辑：成功恢复的错误数 / 总错误数
        """
        tool_calls = context.tool_calls

        # 统计错误和恢复情况
        errors = []
        recoveries = []

        for i, tc in enumerate(tool_calls):
            if not tc.get("success", True):
                errors.append(i)
                # 检查后续是否有重试或降级
                if i + 1 < len(tool_calls):
                    next_call = tool_calls[i + 1]
                    if next_call.get("success", True):
                        recoveries.append(i)

        if not errors:
            return DimensionScore(
                dimension=DIM_ERROR_RECOVERY,
                score=1.0,
                weight=self.weights.error_recovery,
                passed=True,
                message="无错误发生"
            )

        # 计算恢复率
        recovery_rate = len(recoveries) / len(errors)

        # 如果最终状态是成功的，说明恢复成功
        if context.status == "ok":
            score = max(recovery_rate, 0.8)
        else:
            score = recovery_rate

        return DimensionScore(
            dimension=DIM_ERROR_RECOVERY,
            score=score,
            weight=self.weights.error_recovery,
            passed=context.status == "ok",
            details={
                "errors_count": len(errors),
                "recoveries_count": len(recoveries),
                "error_indices": errors
            },
            message=f"错误恢复率: {recovery_rate:.2%}"
        )

    def _score_clarification_efficiency(
        self,
        context: EvalContext
    ) -> DimensionScore:
        """
        澄清循环效率评分

        评分逻辑：澄清轮次是否在阈值内
        """
        # 从Trace中提取澄清轮次
        events = []
        if context.trace and isinstance(context.trace, dict):
            events = context.trace.get("events", [])

        # 统计澄清相关事件
        clarification_rounds = 0
        for event in events:
            event_name = event.get("name", "")
            if "clarification" in event_name.lower() or "ask_user" in event_name.lower():
                clarification_rounds += 1

        # 评分：3轮内满分，超过扣分
        if clarification_rounds == 0:
            score = 1.0
            message = "无需澄清"
        elif clarification_rounds <= self.MAX_CLARIFICATION_ROUNDS:
            score = 1.0 - (clarification_rounds - 1) * 0.1
            message = f"澄清轮次: {clarification_rounds}"
        else:
            score = max(0.5, 1.0 - (clarification_rounds - self.MAX_CLARIFICATION_ROUNDS) * 0.15)
            message = f"澄清轮次过多: {clarification_rounds}"

        return DimensionScore(
            dimension=DIM_CLARIFICATION_EFFICIENCY,
            score=score,
            weight=self.weights.clarification_efficiency,
            passed=clarification_rounds <= self.MAX_CLARIFICATION_ROUNDS,
            details={
                "clarification_rounds": clarification_rounds,
                "max_rounds": self.MAX_CLARIFICATION_ROUNDS
            },
            message=message
        )

    def _score_latency(
        self,
        context: EvalContext
    ) -> DimensionScore:
        """
        响应时间合规性评分

        评分逻辑：min(1, threshold_ms / actual_ms)
        """
        latency_ms = context.latency_ms
        threshold_ms = self.config.thresholds.latency_p99_ms

        if latency_ms == 0:
            # 无延迟数据，假设正常
            return DimensionScore(
                dimension=DIM_LATENCY,
                score=1.0,
                weight=self.weights.latency,
                passed=True,
                message="无延迟数据"
            )

        # 计算得分：延迟越低分数越高
        if latency_ms <= threshold_ms:
            score = 1.0
        else:
            # 超出阈值，按比例扣分
            score = max(0, threshold_ms / latency_ms)

        passed = latency_ms <= threshold_ms

        return DimensionScore(
            dimension=DIM_LATENCY,
            score=score,
            weight=self.weights.latency,
            passed=passed,
            details={
                "latency_ms": latency_ms,
                "threshold_ms": threshold_ms
            },
            message=f"延迟: {latency_ms}ms (阈值: {threshold_ms}ms)"
        )
