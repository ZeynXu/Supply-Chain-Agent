"""Prometheus Metrics 测试"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from supply_chain_agent.harness.observability.metrics import (
    setup_metrics_endpoint,
    record_request,
    record_tool_call,
    record_audit_result,
    record_rule_trigger,
    registry,
)


class TestPrometheusMetrics:
    """Prometheus 指标测试"""

    def test_setup_metrics_endpoint(self):
        """测试创建 /metrics 端点"""
        app = FastAPI()
        setup_metrics_endpoint(app)

        client = TestClient(app)
        response = client.get("/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_record_request(self):
        """测试记录请求指标"""
        # 记录一些请求
        record_request("信息查询", "订单查询", "success", 0.5)
        record_request("信息查询", "订单查询", "success", 0.3)
        record_request("工单管理", "审批工单", "error", 1.0)

        # 导出指标
        from prometheus_client.exposition import generate_latest
        output = generate_latest(registry).decode('utf-8')

        # 验证指标存在
        assert "agent_requests_total" in output
        assert 'intent="信息查询"' in output
        assert 'status="success"' in output
        assert "agent_request_duration_seconds" in output

    def test_record_tool_call(self):
        """测试记录工具调用指标"""
        record_tool_call("query_order", "success", 0.1)
        record_tool_call("query_order", "error", 0.2)

        from prometheus_client.exposition import generate_latest
        output = generate_latest(registry).decode('utf-8')

        assert "agent_tool_calls_total" in output
        assert 'tool_name="query_order"' in output

    def test_record_audit_result(self):
        """测试记录审计结果指标"""
        record_audit_result("block", "reject")
        record_audit_result("warn", "escalate")

        from prometheus_client.exposition import generate_latest
        output = generate_latest(registry).decode('utf-8')

        assert "agent_audit_results_total" in output

    def test_record_rule_trigger(self):
        """测试记录规则触发指标"""
        record_rule_trigger("high_value_approval", "block")
        record_rule_trigger("customer_risk_check", "warn")

        from prometheus_client.exposition import generate_latest
        output = generate_latest(registry).decode('utf-8')

        assert "agent_rule_trigger_total" in output
        assert 'rule_id="high_value_approval"' in output
