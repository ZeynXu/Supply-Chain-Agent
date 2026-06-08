"""
评估系统基础数据结构

定义评分结果、评估上下文、黄金样本等核心数据类型。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional


class EvalLevel(Enum):
    """评估等级"""
    LEVEL_1_GATE = 1      # 门禁级：必须通过才能部署
    LEVEL_2_ALERT = 2     # 告警级：失败只告警
    LEVEL_3_MANUAL = 3    # 手动级：可选执行


@dataclass
class DimensionScore:
    """单维度评分"""
    dimension: str                           # 维度名称
    score: float                             # 分数 0.0-1.0
    weight: float                            # 权重
    details: Dict[str, Any] = field(default_factory=dict)  # 详细信息
    passed: bool = True                      # 是否达标
    message: str = ""                        # 评分说明

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "dimension": self.dimension,
            "score": self.score,
            "weight": self.weight,
            "details": self.details,
            "passed": self.passed,
            "message": self.message
        }


@dataclass
class TrajectoryScore:
    """轨迹评分结果"""
    trace_id: str
    overall_score: float                    # 综合得分 0.0-1.0
    dimension_scores: List[DimensionScore]  # 九维评分
    evaluated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "overall_score": self.overall_score,
            "dimension_scores": [d.to_dict() for d in self.dimension_scores],
            "evaluated_at": self.evaluated_at.isoformat(),
            "metadata": self.metadata
        }

    def get_dimension_score(self, dimension: str) -> Optional[DimensionScore]:
        """获取指定维度的评分"""
        for ds in self.dimension_scores:
            if ds.dimension == dimension:
                return ds
        return None


@dataclass
class QualityAnnotations:
    """质量标注（人工标注）"""
    helpfulness: float      # 帮助性 1-5
    clarity: float          # 清晰度 1-5
    faithfulness: float     # 忠实度 1-5
    annotator: str = ""     # 标注人
    notes: str = ""         # 备注

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "helpfulness": self.helpfulness,
            "clarity": self.clarity,
            "faithfulness": self.faithfulness,
            "annotator": self.annotator,
            "notes": self.notes
        }

    def to_labels(self) -> Dict[str, str]:
        """转换为分类标签"""
        def to_label(score: float) -> str:
            if score >= 4.5:
                return "excellent"
            elif score >= 3.5:
                return "good"
            elif score >= 2.5:
                return "acceptable"
            else:
                return "poor"

        return {
            "helpfulness": to_label(self.helpfulness),
            "clarity": to_label(self.clarity),
            "faithfulness": to_label(self.faithfulness)
        }


@dataclass
class QualityScore:
    """LLM Judge质量评分"""
    helpfulness: float      # 帮助性 1-5
    clarity: float          # 清晰度 1-5
    faithfulness: float     # 忠实度 1-5
    reasoning: str          # 评分理由
    confidence: float       # 置信度 0-1

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "helpfulness": self.helpfulness,
            "clarity": self.clarity,
            "faithfulness": self.faithfulness,
            "reasoning": self.reasoning,
            "confidence": self.confidence
        }

    def average_score(self) -> float:
        """计算平均分"""
        return (self.helpfulness + self.clarity + self.faithfulness) / 3

    def to_labels(self) -> Dict[str, str]:
        """转换为分类标签"""
        def to_label(score: float) -> str:
            if score >= 4.5:
                return "excellent"
            elif score >= 3.5:
                return "good"
            elif score >= 2.5:
                return "acceptable"
            else:
                return "poor"

        return {
            "helpfulness": to_label(self.helpfulness),
            "clarity": to_label(self.clarity),
            "faithfulness": to_label(self.faithfulness)
        }


@dataclass
class GoldResult:
    """黄金标准结果"""
    expected_intent: Dict[str, str] = field(default_factory=dict)           # 期望意图
    expected_tools: List[str] = field(default_factory=list)                 # 期望工具
    expected_response_keywords: List[str] = field(default_factory=list)     # 期望响应关键词
    expected_violations: List[str] = field(default_factory=list)            # 期望违规项
    quality_annotations: Optional[QualityAnnotations] = None                # 质量标注
    expected_response: str = ""                                             # 期望响应（用于LLM Judge）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "expected_intent": self.expected_intent,
            "expected_tools": self.expected_tools,
            "expected_response_keywords": self.expected_response_keywords,
            "expected_violations": self.expected_violations,
            "quality_annotations": self.quality_annotations.to_dict() if self.quality_annotations else None,
            "expected_response": self.expected_response
        }


@dataclass
class GoldenSample:
    """黄金样本"""
    sample_id: str
    user_query: str
    gold_result: GoldResult
    category: str = "general"           # 分类：intent/tool/quality/general
    difficulty: str = "medium"          # 难度：easy/medium/hard
    created_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "sample_id": self.sample_id,
            "user_query": self.user_query,
            "gold_result": self.gold_result.to_dict(),
            "category": self.category,
            "difficulty": self.difficulty,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags
        }


@dataclass
class EvalContext:
    """评估上下文"""
    thread_id: str                              # 会话ID
    user_query: str                             # 用户查询
    intent: Dict[str, Any] = field(default_factory=dict)            # 解析后的意图
    trace: Optional[Any] = None                 # Trace数据（TraceSpan）
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)  # 工具调用记录
    audit_results: Dict[str, Any] = field(default_factory=dict)     # 审计结果
    final_response: str = ""                    # 最终响应
    gold_result: Optional[GoldResult] = None    # 黄金标准（可选）
    latency_ms: int = 0                         # 延迟（毫秒）
    status: str = "ok"                          # 状态：ok/error

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "thread_id": self.thread_id,
            "user_query": self.user_query,
            "intent": self.intent,
            "trace": str(self.trace) if self.trace else None,
            "tool_calls": self.tool_calls,
            "audit_results": self.audit_results,
            "final_response": self.final_response,
            "gold_result": self.gold_result.to_dict() if self.gold_result else None,
            "latency_ms": self.latency_ms,
            "status": self.status
        }


@dataclass
class ToolCallActual:
    """实际工具调用"""
    tool_name: str
    params: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    success: bool = True
    error_message: str = ""
    latency_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "tool_name": self.tool_name,
            "params": self.params,
            "result": self.result,
            "success": self.success,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms
        }


@dataclass
class ToolCallGold:
    """黄金标准工具调用"""
    should_call_tool: bool                  # 是否应该调用工具
    expected_tool: Optional[str] = None     # 期望调用的工具
    expected_params: Dict[str, Any] = field(default_factory=dict)  # 期望参数
    param_constraints: Dict[str, Any] = field(default_factory=dict)  # 参数约束

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "should_call_tool": self.should_call_tool,
            "expected_tool": self.expected_tool,
            "expected_params": self.expected_params,
            "param_constraints": self.param_constraints
        }


@dataclass
class ToolCallEvaluation:
    """工具调用评估结果"""
    decision_correct: bool              # 是否应该调用工具
    tool_correct: bool                  # 工具选择是否正确
    params_complete: bool               # 参数是否完整
    params_valid: bool                  # 参数是否有效
    overall_score: float                # 综合得分
    details: Dict[str, Any] = field(default_factory=dict)
    breakdown: Dict[str, float] = field(default_factory=dict)  # 各项得分明细

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "decision_correct": self.decision_correct,
            "tool_correct": self.tool_correct,
            "params_complete": self.params_complete,
            "params_valid": self.params_valid,
            "overall_score": self.overall_score,
            "details": self.details,
            "breakdown": self.breakdown
        }


@dataclass
class FullEvaluation:
    """完整评估结果"""
    thread_id: str
    trajectory_score: TrajectoryScore
    quality_score: Optional[QualityScore] = None
    tool_evaluations: List[ToolCallEvaluation] = field(default_factory=list)
    eval_results: List[Any] = field(default_factory=list)  # 来自Harness Evals
    overall_passed: bool = True
    evaluated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "thread_id": self.thread_id,
            "trajectory_score": self.trajectory_score.to_dict(),
            "quality_score": self.quality_score.to_dict() if self.quality_score else None,
            "tool_evaluations": [t.to_dict() for t in self.tool_evaluations],
            "eval_results": [str(e) for e in self.eval_results],
            "overall_passed": self.overall_passed,
            "evaluated_at": self.evaluated_at.isoformat(),
            "metadata": self.metadata
        }
