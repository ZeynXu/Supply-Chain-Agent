"""
Prometheus 指标定义和收集

在 FastAPI 中暴露 /metrics 端点。
"""

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
from prometheus_client.exposition import generate_latest
from fastapi import Response
from typing import Dict, Any, Optional


# 创建独立的 Registry，避免全局污染
registry = CollectorRegistry()

# ============================================
# 核心指标定义
# ============================================

# 请求计数器
REQUEST_COUNT = Counter(
    'agent_requests_total',
    'Total agent requests',
    ['intent', 'intent_level_2', 'status'],
    registry=registry
)

# 请求延迟直方图
REQUEST_DURATION = Histogram(
    'agent_request_duration_seconds',
    'Request duration in seconds',
    ['intent'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
    registry=registry
)

# 工具调用计数器
TOOL_CALL_COUNT = Counter(
    'agent_tool_calls_total',
    'Total tool calls',
    ['tool_name', 'status'],
    registry=registry
)

# 工具调用延迟
TOOL_CALL_DURATION = Histogram(
    'agent_tool_call_duration_seconds',
    'Tool call duration in seconds',
    ['tool_name'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=registry
)

# 熔断器状态
CIRCUIT_BREAKER_STATE = Gauge(
    'agent_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['tool_name'],
    registry=registry
)

# 活跃会话数
ACTIVE_SESSIONS = Gauge(
    'agent_active_sessions',
    'Number of active sessions',
    registry=registry
)

# 审计结果计数
AUDIT_RESULT_COUNT = Counter(
    'agent_audit_results_total',
    'Total audit results',
    ['severity', 'action'],
    registry=registry
)

# 规则触发计数
RULE_TRIGGER_COUNT = Counter(
    'agent_rule_trigger_total',
    'Total rule triggers',
    ['rule_id', 'severity'],
    registry=registry
)

# Trace 采样计数
TRACE_SAMPLE_COUNT = Counter(
    'agent_trace_samples_total',
    'Total trace samples',
    ['status'],
    registry=registry
)


# ============================================
# 指标收集函数
# ============================================

def record_request(intent: str, intent_level_2: str, status: str, duration: float):
    """记录请求指标"""
    REQUEST_COUNT.labels(intent=intent, intent_level_2=intent_level_2, status=status).inc()
    REQUEST_DURATION.labels(intent=intent).observe(duration)


def record_tool_call(tool_name: str, status: str, duration: float):
    """记录工具调用指标"""
    TOOL_CALL_COUNT.labels(tool_name=tool_name, status=status).inc()
    TOOL_CALL_DURATION.labels(tool_name=tool_name).observe(duration)


def set_circuit_breaker_state(tool_name: str, state: int):
    """设置熔断器状态"""
    CIRCUIT_BREAKER_STATE.labels(tool_name=tool_name).set(state)


def set_active_sessions(count: int):
    """设置活跃会话数"""
    ACTIVE_SESSIONS.set(count)


def record_audit_result(severity: str, action: str):
    """记录审计结果"""
    AUDIT_RESULT_COUNT.labels(severity=severity, action=action).inc()


def record_rule_trigger(rule_id: str, severity: str):
    """记录规则触发"""
    RULE_TRIGGER_COUNT.labels(rule_id=rule_id, severity=severity).inc()


def record_trace_sample(status: str):
    """记录 Trace 采样"""
    TRACE_SAMPLE_COUNT.labels(status=status).inc()


def get_metrics_response() -> Response:
    """生成 Prometheus metrics 响应"""
    return Response(
        content=generate_latest(registry),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


# ============================================
# FastAPI 集成
# ============================================

def setup_metrics_endpoint(app):
    """为 FastAPI 应用添加 /metrics 端点"""

    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint"""
        return get_metrics_response()

    return app
