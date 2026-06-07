"""
周度分析报告生成器

生成周度 Harness 改进报告。

Usage:
    python -m supply_chain_agent.harness.feedback.weekly_report
    python -m supply_chain_agent.harness.feedback.weekly_report --year 2026 --week 23
"""

import json
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse


DEFAULT_REPORT_DIR = "/root/Supply-Chain-Agent/harness/improvements"
DEFAULT_TRACE_DIR = "/root/autodl-tmp/harness-traces"


class WeeklyReportGenerator:
    """周度报告生成器"""

    def __init__(
        self,
        report_dir: str = DEFAULT_REPORT_DIR,
        trace_dir: str = DEFAULT_TRACE_DIR
    ):
        """
        初始化

        Args:
            report_dir: 报告目录
            trace_dir: Trace 目录
        """
        self.report_dir = Path(report_dir)
        self.trace_dir = Path(trace_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, year: int = None, week: int = None) -> str:
        """
        生成周度报告

        Args:
            year: 年份（默认当前年）
            week: 周数（默认当前周）

        Returns:
            报告文件路径
        """
        year = year or datetime.now().year
        week = week or datetime.now().isocalendar()[1]

        # 收集数据
        metrics = self._collect_metrics()
        errors = self._collect_errors()
        evals = self._collect_eval_results()

        # 生成报告
        report_content = self._format_report(year, week, metrics, errors, evals)

        # 保存报告
        report_file = self.report_dir / f"{year}-W{week:02d}.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

        return str(report_file)

    def _collect_metrics(self) -> Dict[str, Any]:
        """收集指标数据"""
        # 这里应该从 Prometheus 或其他数据源收集
        # 简化实现
        return {
            "total_requests": 0,
            "success_rate": 0.0,
            "avg_latency_ms": 0.0,
            "tool_calls": {}
        }

    def _collect_errors(self) -> List[Dict[str, Any]]:
        """收集错误数据"""
        from .cluster_errors import ErrorCluster

        cluster = ErrorCluster(trace_dir=str(self.trace_dir))
        report = cluster.analyze(days=7)

        return report.get("top_errors", [])

    def _collect_eval_results(self) -> Dict[str, Any]:
        """收集 Evals 结果"""
        # 简化实现
        return {
            "total_evals": 0,
            "passed": 0,
            "failed": 0
        }

    def _format_report(
        self,
        year: int,
        week: int,
        metrics: Dict[str, Any],
        errors: List[Dict[str, Any]],
        evals: Dict[str, Any]
    ) -> str:
        """格式化报告"""
        report_date = datetime.now().strftime("%Y-%m-%d")

        content = f"""# Harness 周度分析报告

**报告周期**: {year} 年第 {week} 周
**生成时间**: {report_date}

---

## 1. 性能指标概览

| 指标 | 数值 |
|------|------|
| 总请求数 | {metrics.get('total_requests', 0)} |
| 成功率 | {metrics.get('success_rate', 0):.2%} |
| 平均延迟 | {metrics.get('avg_latency_ms', 0):.0f} ms |

---

## 2. Top 3 错误类型

"""

        for i, error in enumerate(errors[:3], 1):
            content += f"""### {i}. {error.get('error_type', 'Unknown')}

- **出现次数**: {error.get('count', 0)} 次
- **建议**: 分析根因并优化

"""

        content += f"""---

## 3. Evals 执行情况

| 指标 | 数值 |
|------|------|
| 总评估数 | {evals.get('total_evals', 0)} |
| 通过数 | {evals.get('passed', 0)} |
| 失败数 | {evals.get('failed', 0)} |

---

## 4. 本周改进项

- [ ] 待填写

---

## 5. 下周计划

- [ ] 待填写

---

*报告由 Harness 自动生成*
"""

        return content


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='Generate weekly report')
    parser.add_argument('--year', '-y', type=int, help='Year')
    parser.add_argument('--week', '-w', type=int, help='Week number')
    parser.add_argument('--report-dir', default=DEFAULT_REPORT_DIR, help='Report directory')
    parser.add_argument('--trace-dir', default=DEFAULT_TRACE_DIR, help='Trace directory')

    args = parser.parse_args()

    generator = WeeklyReportGenerator(args.report_dir, args.trace_dir)
    report_file = generator.generate(args.year, args.week)

    print(f"Report generated: {report_file}")


if __name__ == '__main__':
    main()
