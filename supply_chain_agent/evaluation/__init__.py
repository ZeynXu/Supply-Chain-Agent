"""
Agent评估系统

基于Harness Engineering基础设施的扩展评估层，提供：
- 轨迹驱动评估（九维评分）
- LLM Judge主观质量评分
- 评估报告生成
- 生产监控接口
- Harness集成（Rules、Evals、错误聚类）
"""

from .config import EvalConfig, LLMJudgeConfig, get_eval_config
from .core.base import (
    DimensionScore,
    TrajectoryScore,
    QualityScore,
    EvalContext,
    GoldenSample,
    GoldResult,
    QualityAnnotations,
    FullEvaluation,
    ToolCallActual,
    ToolCallGold,
    ToolCallEvaluation,
)
from .core.trajectory_scorer import TrajectoryScorer, ALL_DIMENSIONS
from .core.tool_call_validator import ToolCallValidator
from .judges.llm_judge import LLMJudge
from .judges.calibrator import Calibrator, CalibrationResult
from .runners.eval_runner import EvalRunner, EvalRunnerConfig, quick_evaluate
from .reports.generator import EvaluationReporter, ReportConfig
from .monitoring.dashboard import EvalDashboard, DashboardData
from .harness_integration import (
    HarnessRulesIntegration,
    HarnessEvalsIntegration,
    HarnessErrorClusterIntegration,
    HarnessWeeklyReportIntegration,
    get_rules_integration,
    get_evals_integration,
    get_error_cluster_integration,
)

__all__ = [
    # 配置
    "EvalConfig",
    "LLMJudgeConfig",
    "get_eval_config",
    # 基础数据结构
    "DimensionScore",
    "TrajectoryScore",
    "QualityScore",
    "EvalContext",
    "GoldenSample",
    "GoldResult",
    "QualityAnnotations",
    "FullEvaluation",
    "ToolCallActual",
    "ToolCallGold",
    "ToolCallEvaluation",
    # 核心组件
    "TrajectoryScorer",
    "ToolCallValidator",
    "ALL_DIMENSIONS",
    # LLM Judge
    "LLMJudge",
    "Calibrator",
    "CalibrationResult",
    # 运行器
    "EvalRunner",
    "EvalRunnerConfig",
    "quick_evaluate",
    # 报告
    "EvaluationReporter",
    "ReportConfig",
    # 监控
    "EvalDashboard",
    "DashboardData",
    # Harness集成
    "HarnessRulesIntegration",
    "HarnessEvalsIntegration",
    "HarnessErrorClusterIntegration",
    "HarnessWeeklyReportIntegration",
    "get_rules_integration",
    "get_evals_integration",
    "get_error_cluster_integration",
]
