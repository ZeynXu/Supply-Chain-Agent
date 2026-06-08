"""
评估报告生成器

生成评估报告，与Harness周度报告协同。
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..config import EvalConfig
from ..core.base import FullEvaluation, TrajectoryScore, QualityScore

logger = logging.getLogger(__name__)


@dataclass
class ReportConfig:
    """报告配置"""
    output_dir: str = "./reports"
    include_details: bool = True     # 是否包含详细内容
    top_issues_count: int = 10       # Top问题数量
    dimension_chart: bool = False    # 是否生成维度图表（需要matplotlib）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output_dir": self.output_dir,
            "include_details": self.include_details,
            "top_issues_count": self.top_issues_count,
            "dimension_chart": self.dimension_chart
        }


class EvaluationReporter:
    """
    评估报告生成器

    生成评估报告，支持Markdown和JSON格式。
    与Harness周度报告协同输出。
    """

    def __init__(
        self,
        config: Optional[EvalConfig] = None,
        report_config: Optional[ReportConfig] = None
    ):
        """
        初始化

        Args:
            config: 评估系统配置
            report_config: 报告配置
        """
        self.config = config or EvalConfig.get_default()
        self.report_config = report_config or ReportConfig()
        self.output_dir = Path(self.report_config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        evaluations: List[FullEvaluation],
        period: str,
        title: str = "Agent评估报告"
    ) -> str:
        """
        生成评估报告

        Args:
            evaluations: 评估结果列表
            period: 报告周期
            title: 报告标题

        Returns:
            str: Markdown格式报告
        """
        if not evaluations:
            return self._generate_empty_report(period, title)

        # 计算统计数据
        stats = self._calculate_statistics(evaluations)

        # 生成Markdown报告
        report = self._format_markdown(stats, period, title, evaluations)

        return report

    def generate_and_save(
        self,
        evaluations: List[FullEvaluation],
        period: str,
        filename: Optional[str] = None
    ) -> Path:
        """
        生成并保存报告

        Args:
            evaluations: 评估结果列表
            period: 报告周期
            filename: 文件名（可选）

        Returns:
            Path: 报告文件路径
        """
        report = self.generate_report(evaluations, period)

        if filename is None:
            filename = f"eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        report_path = self.output_dir / filename

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)

        logger.info(f"Report saved to {report_path}")
        return report_path

    def generate_json_report(
        self,
        evaluations: List[FullEvaluation],
        period: str
    ) -> Dict[str, Any]:
        """
        生成JSON格式报告

        Args:
            evaluations: 评估结果列表
            period: 报告周期

        Returns:
            Dict: JSON格式报告数据
        """
        stats = self._calculate_statistics(evaluations)

        return {
            "period": period,
            "generated_at": datetime.now().isoformat(),
            "statistics": stats,
            "evaluations": [e.to_dict() for e in evaluations]
        }

    def _calculate_statistics(
        self,
        evaluations: List[FullEvaluation]
    ) -> Dict[str, Any]:
        """计算统计数据"""
        total = len(evaluations)
        passed = sum(1 for e in evaluations if e.overall_passed)

        # 轨迹评分统计
        trajectory_scores = [e.trajectory_score for e in evaluations if e.trajectory_score]
        avg_trajectory = sum(t.overall_score for t in trajectory_scores) / len(trajectory_scores) if trajectory_scores else 0

        # 维度评分统计
        dimension_averages = self._calculate_dimension_averages(trajectory_scores)

        # 质量评分统计
        quality_scores = [e.quality_score for e in evaluations if e.quality_score]
        quality_averages = self._calculate_quality_averages(quality_scores)

        # Top问题
        top_issues = self._extract_top_issues(evaluations)

        # 按状态分布
        status_distribution = defaultdict(int)
        for e in evaluations:
            if e.overall_passed:
                status_distribution["passed"] += 1
            else:
                status_distribution["failed"] += 1

        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 0,
            "avg_trajectory_score": round(avg_trajectory, 4),
            "dimension_averages": dimension_averages,
            "quality_averages": quality_averages,
            "top_issues": top_issues,
            "status_distribution": dict(status_distribution)
        }

    def _calculate_dimension_averages(
        self,
        trajectory_scores: List[TrajectoryScore]
    ) -> Dict[str, float]:
        """计算各维度平均分"""
        dimension_totals = defaultdict(list)

        for ts in trajectory_scores:
            for ds in ts.dimension_scores:
                dimension_totals[ds.dimension].append(ds.score)

        return {
            dim: round(sum(scores) / len(scores), 4)
            for dim, scores in dimension_totals.items()
            if scores
        }

    def _calculate_quality_averages(
        self,
        quality_scores: List[QualityScore]
    ) -> Dict[str, float]:
        """计算质量评分平均分"""
        if not quality_scores:
            return {}

        return {
            "helpfulness": round(sum(q.helpfulness for q in quality_scores) / len(quality_scores), 2),
            "clarity": round(sum(q.clarity for q in quality_scores) / len(quality_scores), 2),
            "faithfulness": round(sum(q.faithfulness for q in quality_scores) / len(quality_scores), 2)
        }

    def _extract_top_issues(
        self,
        evaluations: List[FullEvaluation]
    ) -> List[Dict[str, Any]]:
        """提取Top问题"""
        issues = []

        for e in evaluations:
            if not e.overall_passed:
                issue = {
                    "thread_id": e.thread_id,
                    "trajectory_score": e.trajectory_score.overall_score if e.trajectory_score else 0,
                    "failed_dimensions": [],
                    "quality_score": None
                }

                # 收集失败维度
                if e.trajectory_score:
                    for ds in e.trajectory_score.dimension_scores:
                        if not ds.passed:
                            issue["failed_dimensions"].append({
                                "dimension": ds.dimension,
                                "score": ds.score,
                                "message": ds.message
                            })

                # 质量评分
                if e.quality_score:
                    issue["quality_score"] = round(e.quality_score.average_score(), 2)

                issues.append(issue)

        # 按轨迹评分排序
        issues.sort(key=lambda x: x["trajectory_score"])

        return issues[:self.report_config.top_issues_count]

    def _format_markdown(
        self,
        stats: Dict[str, Any],
        period: str,
        title: str,
        evaluations: List[FullEvaluation]
    ) -> str:
        """格式化Markdown报告"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        report = f"""# {title}

**报告周期**: {period}
**生成时间**: {now}

---

## 1. 总体概览

| 指标 | 数值 |
|------|------|
| 评估总数 | {stats['total']} |
| 通过数 | {stats['passed']} |
| 失败数 | {stats['failed']} |
| 通过率 | {stats['pass_rate']:.2%} |
| 平均轨迹评分 | {stats['avg_trajectory_score']:.3f} |

---

## 2. 维度评分分布

{self._format_dimension_table(stats['dimension_averages'])}

---

## 3. 质量评分分布

{self._format_quality_table(stats['quality_averages'])}

---

## 4. Top问题分析

{self._format_issues(stats['top_issues'])}

"""

        if self.report_config.include_details:
            report += f"""---

## 5. 详细评估结果

{self._format_details(evaluations)}

"""

        report += """---

*报告由评估系统自动生成*
"""
        return report

    def _format_dimension_table(self, dimension_averages: Dict[str, float]) -> str:
        """格式化维度评分表格"""
        if not dimension_averages:
            return "无轨迹评分数据"

        # 维度中文名称
        dimension_names = {
            "tool_selection": "工具选择",
            "params_complete": "参数完整性",
            "params_valid": "参数有效性",
            "execution_order": "执行顺序",
            "audit_compliance": "审计合规",
            "answer_reachability": "答案可达性",
            "error_recovery": "错误恢复",
            "clarification_efficiency": "澄清效率",
            "latency": "响应时间"
        }

        lines = ["| 维度 | 平均分 | 状态 |", "|------|--------|------|"]

        for dim, score in sorted(dimension_averages.items(), key=lambda x: x[1]):
            name = dimension_names.get(dim, dim)
            status = "✅" if score >= 0.75 else "⚠️" if score >= 0.5 else "❌"
            lines.append(f"| {name} | {score:.3f} | {status} |")

        return "\n".join(lines)

    def _format_quality_table(self, quality_averages: Dict[str, float]) -> str:
        """格式化质量评分表格"""
        if not quality_averages:
            return "无质量评分数据"

        names = {
            "helpfulness": "帮助性",
            "clarity": "清晰度",
            "faithfulness": "忠实度"
        }

        lines = ["| 维度 | 平均分 | 状态 |", "|------|--------|------|"]

        for dim, score in quality_averages.items():
            name = names.get(dim, dim)
            status = "✅" if score >= 4.0 else "⚠️" if score >= 3.0 else "❌"
            lines.append(f"| {name} | {score:.2f} | {status} |")

        return "\n".join(lines)

    def _format_issues(self, top_issues: List[Dict[str, Any]]) -> str:
        """格式化Top问题"""
        if not top_issues:
            return "✅ 无失败案例"

        lines = []
        for i, issue in enumerate(top_issues, 1):
            lines.append(f"### {i}. Thread: `{issue['thread_id']}`")
            lines.append(f"- **轨迹评分**: {issue['trajectory_score']:.3f}")

            if issue.get("quality_score"):
                lines.append(f"- **质量评分**: {issue['quality_score']}")

            if issue.get("failed_dimensions"):
                lines.append("- **失败维度**:")
                for fd in issue["failed_dimensions"]:
                    lines.append(f"  - {fd['dimension']}: {fd['score']:.3f} - {fd['message']}")

            lines.append("")

        return "\n".join(lines)

    def _format_details(self, evaluations: List[FullEvaluation]) -> str:
        """格式化详细结果"""
        if not evaluations:
            return "无评估结果"

        # 只显示前10个
        lines = []
        for e in evaluations[:10]:
            status = "✅ 通过" if e.overall_passed else "❌ 失败"
            lines.append(f"- **{e.thread_id}**: {status} (轨迹: {e.trajectory_score.overall_score:.3f})")

        if len(evaluations) > 10:
            lines.append(f"\n... 共 {len(evaluations)} 个评估结果")

        return "\n".join(lines)

    def _generate_empty_report(self, period: str, title: str) -> str:
        """生成空报告"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return f"""# {title}

**报告周期**: {period}
**生成时间**: {now}

---

## 说明

本次评估周期内无评估数据。

---

*报告由评估系统自动生成*
"""
