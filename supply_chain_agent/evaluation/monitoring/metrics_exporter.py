"""
评估指标导出模块

导出评估相关指标到Prometheus，复用Harness Metrics框架。
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

# 复用Harness Metrics的registry
try:
    from supply_chain_agent.harness.observability.metrics import registry
except ImportError:
    registry = CollectorRegistry()

logger = logging.getLogger(__name__)


# ============================================
# 评估相关指标定义
# ============================================

# 评估运行计数
EVAL_RUN_COUNT = Counter(
    'evaluation_runs_total',
    'Total evaluation runs',
    ['type', 'status'],
    registry=registry
)

# 轨迹评分分布
TRAJECTORY_SCORE = Histogram(
    'evaluation_trajectory_score',
    'Trajectory score distribution',
    ['dimension'],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    registry=registry
)

# 轨迹综合评分
TRAJECTORY_OVERALL_SCORE = Histogram(
    'evaluation_trajectory_overall_score',
    'Overall trajectory score distribution',
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    registry=registry
)

# 质量评分分布
QUALITY_SCORE = Histogram(
    'evaluation_quality_score',
    'Quality score distribution by dimension',
    ['dimension'],
    buckets=[1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
    registry=registry
)

# 工具调用评估计数
TOOL_EVAL_COUNT = Counter(
    'evaluation_tool_calls_total',
    'Tool call evaluation counts',
    ['tool_name', 'correct'],
    registry=registry
)

# 黄金集校准结果
CALIBRATION_KAPPA = Gauge(
    'evaluation_calibration_kappa',
    'Latest calibration Cohen\'s Kappa',
    ['dimension'],
    registry=registry
)

# 评估通过率
EVAL_PASS_RATE = Gauge(
    'evaluation_pass_rate',
    'Current evaluation pass rate',
    registry=registry
)

# 评估延迟
EVAL_DURATION = Histogram(
    'evaluation_duration_seconds',
    'Evaluation duration in seconds',
    ['type'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
    registry=registry
)

# LLM Judge调用计数
LLM_JUDGE_CALL_COUNT = Counter(
    'evaluation_llm_judge_calls_total',
    'LLM Judge call counts',
    ['provider', 'status'],
    registry=registry
)

# LLM Judge延迟
LLM_JUDGE_DURATION = Histogram(
    'evaluation_llm_judge_duration_seconds',
    'LLM Judge call duration in seconds',
    ['provider'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry
)


# ============================================
# 指标记录函数
# ============================================

def record_eval_run(eval_type: str, status: str):
    """
    记录评估运行

    Args:
        eval_type: 评估类型 (trajectory, quality, full)
        status: 状态 (passed, failed, error)
    """
    EVAL_RUN_COUNT.labels(type=eval_type, status=status).inc()


def record_trajectory_score(dimension: str, score: float):
    """
    记录轨迹维度评分

    Args:
        dimension: 维度名称
        score: 评分 0.0-1.0
    """
    TRAJECTORY_SCORE.labels(dimension=dimension).observe(score)


def record_trajectory_overall(score: float):
    """
    记录轨迹综合评分

    Args:
        score: 综合评分 0.0-1.0
    """
    TRAJECTORY_OVERALL_SCORE.observe(score)


def record_quality_score(dimension: str, score: float):
    """
    记录质量评分

    Args:
        dimension: 维度名称 (helpfulness, clarity, faithfulness)
        score: 评分 1-5
    """
    QUALITY_SCORE.labels(dimension=dimension).observe(score)


def record_tool_eval(tool_name: str, correct: bool):
    """
    记录工具调用评估

    Args:
        tool_name: 工具名称
        correct: 是否正确
    """
    TOOL_EVAL_COUNT.labels(
        tool_name=tool_name,
        correct='true' if correct else 'false'
    ).inc()


def set_calibration_kappa(dimension: str, kappa: float):
    """
    设置校准Kappa值

    Args:
        dimension: 维度名称
        kappa: Cohen's Kappa值
    """
    CALIBRATION_KAPPA.labels(dimension=dimension).set(kappa)


def set_eval_pass_rate(rate: float):
    """
    设置评估通过率

    Args:
        rate: 通过率 0.0-1.0
    """
    EVAL_PASS_RATE.set(rate)


def record_eval_duration(eval_type: str, duration_seconds: float):
    """
    记录评估延迟

    Args:
        eval_type: 评估类型
        duration_seconds: 持续时间（秒）
    """
    EVAL_DURATION.labels(type=eval_type).observe(duration_seconds)


def record_llm_judge_call(provider: str, status: str, duration_seconds: float = 0):
    """
    记录LLM Judge调用

    Args:
        provider: 提供商 (zhipu, openai, anthropic)
        status: 状态 (success, error, timeout)
        duration_seconds: 持续时间（秒）
    """
    LLM_JUDGE_CALL_COUNT.labels(provider=provider, status=status).inc()
    if duration_seconds > 0:
        LLM_JUDGE_DURATION.labels(provider=provider).observe(duration_seconds)


# ============================================
# 批量记录函数
# ============================================

def record_full_evaluation(eval_result: Dict[str, Any]):
    """
    记录完整评估结果

    Args:
        eval_result: 评估结果字典
    """
    # 记录运行
    status = 'passed' if eval_result.get('overall_passed', False) else 'failed'
    record_eval_run('full', status)

    # 记录轨迹评分
    trajectory = eval_result.get('trajectory_score', {})
    if trajectory:
        overall = trajectory.get('overall_score', 0)
        record_trajectory_overall(overall)

        for ds in trajectory.get('dimension_scores', []):
            record_trajectory_score(ds['dimension'], ds['score'])

    # 记录质量评分
    quality = eval_result.get('quality_score', {})
    if quality:
        for dim in ['helpfulness', 'clarity', 'faithfulness']:
            if dim in quality:
                record_quality_score(dim, quality[dim])


def record_batch_evaluations(eval_results: list):
    """
    批量记录评估结果

    Args:
        eval_results: 评估结果列表
    """
    if not eval_results:
        return

    passed = sum(1 for e in eval_results if e.get('overall_passed', False))
    rate = passed / len(eval_results)
    set_eval_pass_rate(rate)

    for result in eval_results:
        record_full_evaluation(result)


# ============================================
# FastAPI集成
# ============================================

def setup_eval_metrics_endpoint(app):
    """
    为FastAPI应用添加评估指标端点

    注意：主要的/metrics端点已在Harness中配置，
    这里只是添加额外的评估相关路由。
    """
    from fastapi import Response

    @app.get("/eval/metrics/prometheus")
    async def eval_metrics():
        """评估指标端点（复用Harness registry）"""
        from prometheus_client.exposition import generate_latest
        return Response(
            content=generate_latest(registry),
            media_type="text/plain; version=0.0.4; charset=utf-8"
        )

    return app
