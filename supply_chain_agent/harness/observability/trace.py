"""
按需 Trace 收集器

采样率控制 + 错误全量记录 + 本地文件存储。
"""

import json
import os
import random
import threading
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict, field
from contextlib import contextmanager
import uuid


@dataclass
class TraceSpan:
    """Trace Span 定义"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation: str
    start_time: str
    end_time: Optional[str] = None
    duration_ms: Optional[int] = None
    status: str = "ok"
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)


class TraceCollector:
    """
    Trace 收集器

    特性：
    - 采样率控制（默认 1%）
    - 错误全量记录
    - JSON Lines 格式存储
    - 按天轮转
    - 线程安全
    """

    DEFAULT_TRACE_DIR = "/root/autodl-tmp/harness-traces"
    DEFAULT_SAMPLE_RATE = 0.01  # 1%
    DEFAULT_RETENTION_DAYS = 7

    def __init__(
        self,
        trace_dir: str = None,
        sample_rate: float = None,
        retention_days: int = None,
        enabled: bool = None
    ):
        self.trace_dir = Path(trace_dir or os.getenv("HARNESS_TRACE_DIR", self.DEFAULT_TRACE_DIR))
        self.sample_rate = float(os.getenv("HARNESS_TRACE_SAMPLE_RATE", sample_rate or self.DEFAULT_SAMPLE_RATE))
        self.retention_days = retention_days or self.DEFAULT_RETENTION_DAYS
        self.enabled = enabled if enabled is not None else os.getenv("HARNESS_TRACE_ENABLED", "true").lower() == "true"

        self._current_trace: Dict[str, TraceSpan] = {}
        self._lock = threading.RLock()

        # 确保目录存在
        self.trace_dir.mkdir(parents=True, exist_ok=True)

    def should_sample(self) -> bool:
        """判断是否应该采样"""
        if not self.enabled:
            return False
        return random.random() < self.sample_rate

    def start_trace(self, trace_id: str, operation: str, attributes: Dict[str, Any] = None) -> str:
        """
        开始一个 Trace

        Args:
            trace_id: Trace ID
            operation: 操作名称
            attributes: 附加属性

        Returns:
            span_id: Span ID
        """
        if not self.enabled:
            return ""

        with self._lock:
            span_id = self._generate_span_id()
            span = TraceSpan(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=None,
                operation=operation,
                start_time=datetime.utcnow().isoformat() + "Z",
                attributes=attributes or {},
                events=[]
            )

            self._current_trace[span_id] = span
            return span_id

    def end_trace(self, span_id: str, status: str = "ok", force_record: bool = False):
        """
        结束一个 Trace

        Args:
            span_id: Span ID
            status: 状态 (ok/error)
            force_record: 强制记录（忽略采样率）
        """
        if not self.enabled or span_id not in self._current_trace:
            return

        with self._lock:
            span = self._current_trace[span_id]
            span.end_time = datetime.utcnow().isoformat() + "Z"
            span.status = status

            # 计算持续时间
            start = datetime.fromisoformat(span.start_time.replace("Z", ""))
            end = datetime.fromisoformat(span.end_time.replace("Z", ""))
            span.duration_ms = int((end - start).total_seconds() * 1000)

            # 判断是否记录
            should_record = force_record or status == "error" or self.should_sample()

            if should_record:
                self._write_span(span)

            del self._current_trace[span_id]

    def add_event(self, span_id: str, name: str, attributes: Dict[str, Any] = None):
        """
        添加事件到 Span

        Args:
            span_id: Span ID
            name: 事件名称
            attributes: 事件属性
        """
        if not self.enabled or span_id not in self._current_trace:
            return

        with self._lock:
            span = self._current_trace[span_id]
            event = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "name": name,
                "attributes": attributes or {}
            }
            span.events.append(event)

    def _write_span(self, span: TraceSpan):
        """写入 Span 到文件"""
        today = date.today().isoformat()
        trace_file = self.trace_dir / f"{today}.jsonl"

        try:
            with open(trace_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(asdict(span), ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[Harness] Failed to write trace: {e}")

    def _generate_span_id(self) -> str:
        """生成 Span ID"""
        return uuid.uuid4().hex[:16]

    def cleanup_old_traces(self):
        """清理过期的 Trace 文件"""
        cutoff_date = date.today() - timedelta(days=self.retention_days)

        for trace_file in self.trace_dir.glob("*.jsonl"):
            try:
                file_date_str = trace_file.stem
                file_date = date.fromisoformat(file_date_str)
                if file_date < cutoff_date:
                    trace_file.unlink()
                    print(f"[Harness] Cleaned up old trace file: {trace_file}")
            except ValueError:
                pass


# 全局 Trace 收集器实例
_trace_collector: Optional[TraceCollector] = None


def get_trace_collector() -> TraceCollector:
    """获取全局 Trace 收集器"""
    global _trace_collector
    if _trace_collector is None:
        _trace_collector = TraceCollector()
    return _trace_collector


def reset_trace_collector():
    """重置全局 Trace 收集器（用于测试）"""
    global _trace_collector
    _trace_collector = None


@contextmanager
def trace_context(operation: str, trace_id: str = None, attributes: Dict[str, Any] = None):
    """
    Trace 上下文管理器

    Usage:
        with trace_context("parse_input", "thread-123") as span_id:
            # do work
            pass

    Args:
        operation: 操作名称
        trace_id: Trace ID（可选，自动生成）
        attributes: 附加属性

    Yields:
        span_id: Span ID
    """
    collector = get_trace_collector()
    trace_id = trace_id or uuid.uuid4().hex
    span_id = collector.start_trace(trace_id, operation, attributes)

    try:
        yield span_id
        collector.end_trace(span_id, status="ok")
    except Exception as e:
        collector.add_event(span_id, "exception", {"error": str(e), "type": type(e).__name__})
        collector.end_trace(span_id, status="error", force_record=True)
        raise
