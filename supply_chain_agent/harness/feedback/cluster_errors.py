"""
错误聚类分析脚本

分析日志和 Trace，按错误类型分组，生成报告。

Usage:
    python -m supply_chain_agent.harness.feedback.cluster_errors --days 7
    python -m supply_chain_agent.harness.feedback.cluster_errors --output report.json
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict, List, Any, Tuple
import argparse


DEFAULT_LOG_DIR = "/root/Supply-Chain-Agent/logs"
DEFAULT_TRACE_DIR = "/root/autodl-tmp/harness-traces"


class ErrorCluster:
    """错误聚类器"""

    # 错误模式定义
    ERROR_PATTERNS = {
        "MissingParameterError": r"缺少必要参数|missing.*param|MissingParameter",
        "ToolTimeoutError": r"timeout|超时|TimeoutError",
        "ToolExecutionError": r"tool.*error|执行失败|ToolExecution",
        "IntentParseError": r"intent.*parse|意图解析|IntentParse",
        "ValidationError": r"validation|验证失败|ValidationError",
        "CircuitBreakerOpenError": r"circuit.*breaker|熔断器|CircuitBreaker",
        "ConnectionError": r"connection|连接|ConnectionError",
        "RateLimitError": r"rate.*limit|限流|RateLimit",
    }

    def __init__(self, log_dir: str = DEFAULT_LOG_DIR, trace_dir: str = DEFAULT_TRACE_DIR):
        """
        初始化

        Args:
            log_dir: 日志目录
            trace_dir: Trace 目录
        """
        self.log_dir = Path(log_dir)
        self.trace_dir = Path(trace_dir)

    def analyze(self, days: int = 7) -> Dict[str, Any]:
        """
        分析指定天数内的错误

        Args:
            days: 分析天数

        Returns:
            错误聚类报告
        """
        errors = self._collect_errors(days)
        clustered = self._cluster_errors(errors)
        report = self._generate_report(clustered, days)

        return report

    def _collect_errors(self, days: int) -> List[Dict[str, Any]]:
        """收集错误"""
        errors = []

        # 从 Trace 收集
        errors.extend(self._collect_from_traces(days))

        # 从日志收集（如果存在）
        errors.extend(self._collect_from_logs(days))

        return errors

    def _collect_from_traces(self, days: int) -> List[Dict[str, Any]]:
        """从 Trace 文件收集错误"""
        errors = []

        for i in range(days):
            d = date.today() - timedelta(days=i)
            trace_file = self.trace_dir / f"{d.isoformat()}.jsonl"

            if trace_file.exists():
                with open(trace_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                trace = json.loads(line)
                                if trace.get("status") == "error":
                                    errors.append({
                                        "source": "trace",
                                        "timestamp": trace.get("start_time"),
                                        "operation": trace.get("operation"),
                                        "error": trace.get("attributes", {}).get("error", "Unknown"),
                                        "trace_id": trace.get("trace_id")
                                    })
                            except json.JSONDecodeError:
                                continue

        return errors

    def _collect_from_logs(self, days: int) -> List[Dict[str, Any]]:
        """从日志文件收集错误"""
        errors = []

        # 检查日志目录是否存在
        if not self.log_dir.exists():
            return errors

        for log_file in self.log_dir.glob("*.log"):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if "error" in line.lower() or "ERROR" in line:
                            errors.append({
                                "source": "log",
                                "file": log_file.name,
                                "line": line.strip()[:500]
                            })
            except Exception:
                pass

        return errors

    def _cluster_errors(self, errors: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """聚类错误"""
        clustered = defaultdict(list)

        for error in errors:
            error_type = self._classify_error(error)
            clustered[error_type].append(error)

        return dict(clustered)

    def _classify_error(self, error: Dict[str, Any]) -> str:
        """分类错误"""
        error_text = error.get("error", "") or error.get("line", "")

        for error_type, pattern in self.ERROR_PATTERNS.items():
            if re.search(pattern, error_text, re.IGNORECASE):
                return error_type

        return "UnknownError"

    def _generate_report(self, clustered: Dict[str, List], days: int) -> Dict[str, Any]:
        """生成报告"""
        # 统计
        stats = []
        for error_type, errors in clustered.items():
            stats.append({
                "error_type": error_type,
                "count": len(errors),
                "examples": errors[:3]
            })

        # 按数量排序
        stats.sort(key=lambda x: x["count"], reverse=True)

        return {
            "report_date": datetime.now().isoformat(),
            "analysis_period": f"最近 {days} 天",
            "total_errors": sum(s["count"] for s in stats),
            "error_types": len(stats),
            "top_errors": stats[:10],
            "suggestions": self._generate_suggestions(stats)
        }

    def _generate_suggestions(self, stats: List[Dict]) -> List[str]:
        """生成改进建议"""
        suggestions = []

        for stat in stats[:3]:
            error_type = stat["error_type"]
            count = stat["count"]

            if error_type == "MissingParameterError":
                suggestions.append(f"参数缺失错误 ({count}次): 建议优化参数提取逻辑或增加必填项验证")
            elif error_type == "ToolTimeoutError":
                suggestions.append(f"工具超时错误 ({count}次): 建议增加超时时间或优化慢查询")
            elif error_type == "IntentParseError":
                suggestions.append(f"意图解析错误 ({count}次): 建议优化意图识别 Prompt 或增加训练样本")
            elif error_type == "CircuitBreakerOpenError":
                suggestions.append(f"熔断器打开 ({count}次): 建议检查下游服务稳定性")
            elif error_type == "ValidationError":
                suggestions.append(f"验证失败 ({count}次): 建议检查输入数据格式")

        return suggestions


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='Error clustering analysis')
    parser.add_argument('--days', '-d', type=int, default=7, help='Days to analyze')
    parser.add_argument('--output', '-o', help='Output file path')
    parser.add_argument('--log-dir', default=DEFAULT_LOG_DIR, help='Log directory')
    parser.add_argument('--trace-dir', default=DEFAULT_TRACE_DIR, help='Trace directory')

    args = parser.parse_args()

    cluster = ErrorCluster(args.log_dir, args.trace_dir)
    report = cluster.analyze(args.days)

    # 输出
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Report saved to {args.output}")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
