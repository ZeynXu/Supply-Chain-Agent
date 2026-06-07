"""
Trace 命令行查询工具

支持按 thread_id、时间、错误类型过滤。

Usage:
    python -m supply_chain_agent.harness.observability.trace_cli --status error
    python -m supply_chain_agent.harness.observability.trace_cli --trace-id xxx
    python -m supply_chain_agent.harness.observability.trace_cli --date 2026-06-07
"""

import json
import argparse
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional


DEFAULT_TRACE_DIR = "/root/autodl-tmp/harness-traces"


def load_traces(trace_dir: str, date_str: str = None) -> List[Dict[str, Any]]:
    """
    加载 Trace 文件

    Args:
        trace_dir: Trace 目录
        date_str: 指定日期 (YYYY-MM-DD)，为空则加载最近 7 天

    Returns:
        Trace 列表
    """
    trace_path = Path(trace_dir)
    traces = []

    if date_str:
        # 加载指定日期
        trace_file = trace_path / f"{date_str}.jsonl"
        if trace_file.exists():
            with open(trace_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        traces.append(json.loads(line))
    else:
        # 加载最近 7 天
        for i in range(7):
            d = date.today() - timedelta(days=i)
            trace_file = trace_path / f"{d.isoformat()}.jsonl"
            if trace_file.exists():
                with open(trace_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            traces.append(json.loads(line))

    return traces


def filter_traces(
    traces: List[Dict[str, Any]],
    trace_id: str = None,
    status: str = None,
    operation: str = None,
    min_duration: int = None
) -> List[Dict[str, Any]]:
    """
    过滤 Trace

    Args:
        traces: Trace 列表
        trace_id: Trace ID 过滤
        status: 状态过滤 (ok/error)
        operation: 操作名称过滤
        min_duration: 最小持续时间 (ms)

    Returns:
        过滤后的 Trace 列表
    """
    filtered = traces

    if trace_id:
        filtered = [t for t in filtered if t.get('trace_id') == trace_id]

    if status:
        filtered = [t for t in filtered if t.get('status') == status]

    if operation:
        filtered = [t for t in filtered if operation in t.get('operation', '')]

    if min_duration:
        filtered = [t for t in filtered if t.get('duration_ms', 0) >= min_duration]

    return filtered


def print_traces(traces: List[Dict[str, Any]], verbose: bool = False):
    """
    打印 Trace

    Args:
        traces: Trace 列表
        verbose: 是否详细输出
    """
    for trace in traces:
        print(f"\n{'='*60}")
        print(f"Trace ID: {trace.get('trace_id')}")
        print(f"Span ID: {trace.get('span_id')}")
        print(f"Operation: {trace.get('operation')}")
        print(f"Status: {trace.get('status')}")
        print(f"Duration: {trace.get('duration_ms')} ms")
        print(f"Time: {trace.get('start_time')}")

        if verbose:
            print(f"\nAttributes: {json.dumps(trace.get('attributes', {}), indent=2, ensure_ascii=False)}")
            if trace.get('events'):
                print(f"\nEvents:")
                for event in trace.get('events', []):
                    print(f"  - {event.get('name')}: {event.get('timestamp')}")
                    if event.get('attributes'):
                        print(f"    Attributes: {event.get('attributes')}")


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='Trace query tool')
    parser.add_argument('--date', '-d', help='Date (YYYY-MM-DD)')
    parser.add_argument('--trace-id', '-t', help='Filter by trace ID')
    parser.add_argument('--status', '-s', help='Filter by status (ok/error)')
    parser.add_argument('--operation', '-o', help='Filter by operation')
    parser.add_argument('--min-duration', '-m', type=int, help='Minimum duration (ms)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--trace-dir', default=DEFAULT_TRACE_DIR, help='Trace directory')

    args = parser.parse_args()

    traces = load_traces(args.trace_dir, args.date)
    traces = filter_traces(
        traces,
        trace_id=args.trace_id,
        status=args.status,
        operation=args.operation,
        min_duration=args.min_duration
    )

    print(f"Found {len(traces)} traces")
    print_traces(traces, verbose=args.verbose)


if __name__ == '__main__':
    main()
