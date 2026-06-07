"""Trace 收集器测试"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from datetime import date

from supply_chain_agent.harness.observability.trace import (
    TraceCollector,
    TraceSpan,
    get_trace_collector,
    reset_trace_collector,
    trace_context,
)


class TestTraceCollector:
    """Trace 收集器测试"""

    @pytest.fixture
    def temp_trace_dir(self, tmp_path):
        """创建临时 Trace 目录"""
        trace_dir = tmp_path / "traces"
        trace_dir.mkdir()
        return str(trace_dir)

    def test_init_creates_directory(self, tmp_path):
        """测试初始化创建目录"""
        trace_dir = tmp_path / "new_traces"
        collector = TraceCollector(trace_dir=str(trace_dir), enabled=False)

        assert trace_dir.exists()

    def test_start_and_end_trace(self, temp_trace_dir):
        """测试开始和结束 Trace"""
        collector = TraceCollector(trace_dir=temp_trace_dir, enabled=True, sample_rate=1.0)

        span_id = collector.start_trace("test-trace-123", "parse_input")
        assert span_id != ""

        # 验证 span 被存储
        assert span_id in collector._current_trace

        collector.end_trace(span_id, status="ok")

        # 验证 span 被移除
        assert span_id not in collector._current_trace

    def test_trace_written_to_file_on_sample(self, temp_trace_dir):
        """测试采样时写入文件"""
        collector = TraceCollector(trace_dir=temp_trace_dir, enabled=True, sample_rate=1.0)

        span_id = collector.start_trace("test-trace-456", "execute_task")
        collector.end_trace(span_id, status="ok")

        # 检查文件是否创建
        today = date.today().isoformat()
        trace_file = Path(temp_trace_dir) / f"{today}.jsonl"

        assert trace_file.exists()

        # 验证内容
        with open(trace_file, 'r') as f:
            line = f.readline()
            data = json.loads(line)
            assert data["trace_id"] == "test-trace-456"
            assert data["operation"] == "execute_task"
            assert data["status"] == "ok"

    def test_error_trace_always_recorded(self, temp_trace_dir):
        """测试错误 Trace 总是被记录"""
        # 采样率为 0，不采样正常 Trace
        collector = TraceCollector(trace_dir=temp_trace_dir, enabled=True, sample_rate=0.0)

        span_id = collector.start_trace("test-trace-789", "audit")
        collector.end_trace(span_id, status="error", force_record=True)

        # 验证文件被创建
        today = date.today().isoformat()
        trace_file = Path(temp_trace_dir) / f"{today}.jsonl"

        assert trace_file.exists()

        with open(trace_file, 'r') as f:
            line = f.readline()
            data = json.loads(line)
            assert data["status"] == "error"

    def test_add_event_to_trace(self, temp_trace_dir):
        """测试添加事件到 Trace"""
        collector = TraceCollector(trace_dir=temp_trace_dir, enabled=True, sample_rate=1.0)

        span_id = collector.start_trace("test-trace-abc", "plan_task")
        collector.add_event(span_id, "sub_step", {"detail": "generating plan"})
        collector.end_trace(span_id, status="ok")

        # 验证事件
        today = date.today().isoformat()
        trace_file = Path(temp_trace_dir) / f"{today}.jsonl"

        with open(trace_file, 'r') as f:
            data = json.loads(f.readline())
            assert len(data["events"]) == 1
            assert data["events"][0]["name"] == "sub_step"

    def test_disabled_collector_does_nothing(self, temp_trace_dir):
        """测试禁用的收集器不工作"""
        collector = TraceCollector(trace_dir=temp_trace_dir, enabled=False)

        span_id = collector.start_trace("test-trace", "operation")
        assert span_id == ""  # 禁用时应返回空

        collector.end_trace(span_id, status="ok")  # 不应抛出异常

    def test_trace_context_manager(self, temp_trace_dir):
        """测试 trace_context 上下文管理器"""
        reset_trace_collector()
        collector = TraceCollector(trace_dir=temp_trace_dir, enabled=True, sample_rate=1.0)

        # 替换全局收集器
        import supply_chain_agent.harness.observability.trace as trace_module
        trace_module._trace_collector = collector

        with trace_context("test_operation", "ctx-trace-123") as span_id:
            assert span_id != ""

        # 验证 Trace 被记录
        today = date.today().isoformat()
        trace_file = Path(temp_trace_dir) / f"{today}.jsonl"

        assert trace_file.exists()

        with open(trace_file, 'r') as f:
            data = json.loads(f.readline())
            assert data["operation"] == "test_operation"
            assert data["status"] == "ok"

        reset_trace_collector()

    def test_trace_context_on_exception(self, temp_trace_dir):
        """测试异常时 Trace 记录错误状态"""
        reset_trace_collector()
        collector = TraceCollector(trace_dir=temp_trace_dir, enabled=True, sample_rate=1.0)

        import supply_chain_agent.harness.observability.trace as trace_module
        trace_module._trace_collector = collector

        with pytest.raises(ValueError):
            with trace_context("failing_operation", "ctx-trace-456") as span_id:
                raise ValueError("Test error")

        # 验证错误被记录
        today = date.today().isoformat()
        trace_file = Path(temp_trace_dir) / f"{today}.jsonl"

        with open(trace_file, 'r') as f:
            data = json.loads(f.readline())
            assert data["status"] == "error"
            assert len(data["events"]) == 1
            assert data["events"][0]["name"] == "exception"

        reset_trace_collector()
