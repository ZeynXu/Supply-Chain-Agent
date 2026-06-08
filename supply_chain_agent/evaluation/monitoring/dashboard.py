"""
评估监控仪表盘

消费Harness Metrics和Trace，提供实时监控数据接口。
集成Harness错误聚类结果。
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..config import EvalConfig
from ..core.base import FullEvaluation
from ..runners.eval_runner import EvalRunner

logger = logging.getLogger(__name__)


@dataclass
class DashboardData:
    """仪表盘数据"""
    # 概览指标
    total_requests: int = 0
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    # 评估指标
    avg_trajectory_score: float = 0.0
    avg_quality_score: float = 0.0
    pass_rate: float = 0.0

    # 维度评分
    dimension_scores: Dict[str, float] = field(default_factory=dict)

    # 时间序列数据
    time_series: List[Dict[str, Any]] = field(default_factory=list)

    # 意图分布
    intent_distribution: Dict[str, int] = field(default_factory=dict)

    # 错误分布
    error_distribution: Dict[str, int] = field(default_factory=dict)

    # 错误聚类结果（来自Harness）
    error_clusters: List[Dict[str, Any]] = field(default_factory=list)

    # 改进建议（来自Harness错误聚类）
    improvement_suggestions: List[str] = field(default_factory=list)

    # 最近评估
    recent_evaluations: List[Dict[str, Any]] = field(default_factory=list)

    # 告警
    alerts: List[Dict[str, Any]] = field(default_factory=list)

    # 错误聚类结果（来自Harness）
    error_clusters: List[Dict[str, Any]] = field(default_factory=list)

    # 改进建议（来自Harness错误聚类）
    improvement_suggestions: List[str] = field(default_factory=list)

    # 元数据
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_requests": self.total_requests,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "avg_trajectory_score": self.avg_trajectory_score,
            "avg_quality_score": self.avg_quality_score,
            "pass_rate": self.pass_rate,
            "dimension_scores": self.dimension_scores,
            "time_series": self.time_series,
            "intent_distribution": self.intent_distribution,
            "error_distribution": self.error_distribution,
            "error_clusters": self.error_clusters,
            "improvement_suggestions": self.improvement_suggestions,
            "recent_evaluations": self.recent_evaluations,
            "alerts": self.alerts,
            "updated_at": self.updated_at.isoformat()
        }


class EvalDashboard:
    """
    评估监控仪表盘

    消费Harness Metrics和Trace数据，提供实时监控数据接口。
    集成Harness错误聚类结果。
    """

    def __init__(
        self,
        config: Optional[EvalConfig] = None,
        trace_dir: Optional[str] = None,
        log_dir: Optional[str] = None,
        enable_error_cluster: bool = True
    ):
        """
        初始化

        Args:
            config: 评估系统配置
            trace_dir: Trace文件目录
            log_dir: 日志文件目录
            enable_error_cluster: 是否启用错误聚类集成
        """
        self.config = config or EvalConfig.get_default()
        self.trace_dir = Path(trace_dir or "/root/autodl-tmp/harness-traces")
        self.log_dir = log_dir or "/root/Supply-Chain-Agent/logs"
        self.enable_error_cluster = enable_error_cluster
        self.eval_runner = EvalRunner(self.config, trace_dir=str(self.trace_dir))

        # 初始化错误聚类集成
        self._error_cluster_integration = None
        if enable_error_cluster:
            try:
                from ..harness_integration import get_error_cluster_integration
                self._error_cluster_integration = get_error_cluster_integration(
                    self.log_dir, str(self.trace_dir)
                )
            except ImportError:
                logger.warning("错误聚类集成不可用")

        # 缓存
        self._cache: Dict[str, Any] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=5)

    async def get_dashboard_data(
        self,
        time_range: str = "24h"
    ) -> DashboardData:
        """
        获取仪表盘数据

        Args:
            time_range: 时间范围 (1h, 24h, 7d, 30d)

        Returns:
            DashboardData: 仪表盘数据
        """
        # 检查缓存
        if self._is_cache_valid():
            return self._cache.get("dashboard", DashboardData())

        # 计算时间范围
        end_time = datetime.now()
        start_time = self._parse_time_range(time_range)

        # 收集数据
        data = await self._collect_dashboard_data(start_time, end_time)

        # 更新缓存
        self._cache["dashboard"] = data
        self._cache_time = datetime.now()

        return data

    async def get_overview_metrics(self) -> Dict[str, Any]:
        """
        获取概览指标

        Returns:
            概览指标字典
        """
        data = await self.get_dashboard_data()

        return {
            "total_requests": data.total_requests,
            "success_rate": data.success_rate,
            "avg_latency_ms": data.avg_latency_ms,
            "p99_latency_ms": data.p99_latency_ms,
            "avg_trajectory_score": data.avg_trajectory_score,
            "pass_rate": data.pass_rate
        }

    async def get_dimension_scores(self) -> Dict[str, float]:
        """
        获取各维度评分

        Returns:
            维度评分字典
        """
        data = await self.get_dashboard_data()
        return data.dimension_scores

    async def get_time_series(
        self,
        metric: str = "success_rate",
        granularity: str = "hour"
    ) -> List[Dict[str, Any]]:
        """
        获取时间序列数据

        Args:
            metric: 指标名称
            granularity: 粒度 (hour, day)

        Returns:
            时间序列数据
        """
        data = await self.get_dashboard_data()
        return data.time_series

    async def get_intent_distribution(self) -> Dict[str, int]:
        """
        获取意图分布

        Returns:
            意图分布字典
        """
        data = await self.get_dashboard_data()
        return data.intent_distribution

    async def get_error_distribution(self) -> Dict[str, int]:
        """
        获取错误分布

        Returns:
            错误分布字典
        """
        data = await self.get_dashboard_data()
        return data.error_distribution

    async def get_alerts(self) -> List[Dict[str, Any]]:
        """
        获取告警列表

        Returns:
            告警列表
        """
        data = await self.get_dashboard_data()
        return data.alerts

    async def refresh(self):
        """刷新缓存"""
        self._cache_time = None
        await self.get_dashboard_data()

    async def _collect_dashboard_data(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> DashboardData:
        """收集仪表盘数据"""
        data = DashboardData()

        # 从Trace文件收集数据
        trace_data = await self._load_traces(start_time, end_time)

        if not trace_data:
            return data

        # 计算基础指标
        data.total_requests = len(trace_data)

        # 计算成功率
        success_count = sum(1 for t in trace_data if t.get("status") == "ok")
        data.success_rate = success_count / data.total_requests if data.total_requests > 0 else 0

        # 计算延迟
        latencies = [t.get("duration_ms", 0) for t in trace_data if t.get("duration_ms")]
        if latencies:
            data.avg_latency_ms = sum(latencies) / len(latencies)
            data.p99_latency_ms = sorted(latencies)[int(len(latencies) * 0.99)] if len(latencies) > 10 else max(latencies)

        # 计算意图分布
        for t in trace_data:
            intent = t.get("attributes", {}).get("intent", {})
            intent_level_1 = intent.get("intent_level_1", "unknown")
            data.intent_distribution[intent_level_1] = data.intent_distribution.get(intent_level_1, 0) + 1

        # 计算错误分布
        for t in trace_data:
            if t.get("status") == "error":
                error = t.get("attributes", {}).get("error", "UnknownError")
                data.error_distribution[error] = data.error_distribution.get(error, 0) + 1

        # 生成时间序列
        data.time_series = self._generate_time_series(trace_data, start_time, end_time)

        # 集成错误聚类结果
        if self._error_cluster_integration:
            try:
                # 计算天数
                days = (end_time - start_time).days or 1
                cluster_report = self._error_cluster_integration.analyze_errors(days)

                # 提取错误聚类
                data.error_clusters = cluster_report.get("top_errors", [])[:5]

                # 提取改进建议
                data.improvement_suggestions = cluster_report.get("suggestions", [])

                # 合并错误分布
                for cluster in data.error_clusters:
                    error_type = cluster.get("error_type", "")
                    count = cluster.get("count", 0)
                    if error_type and error_type not in data.error_distribution:
                        data.error_distribution[error_type] = count
            except Exception as e:
                logger.error(f"错误聚类集成失败: {e}")

        # 检查告警
        data.alerts = self._check_alerts(data)

        # 更新时间
        data.updated_at = datetime.now()

        return data

    async def _load_traces(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """加载Trace数据"""
        traces = []

        # 确定要读取的日期范围
        current_date = start_time.date()
        end_date = end_time.date()

        while current_date <= end_date:
            trace_file = self.trace_dir / f"{current_date.isoformat()}.jsonl"

            if trace_file.exists():
                try:
                    with open(trace_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                trace = json.loads(line)
                                traces.append(trace)
                except Exception as e:
                    logger.error(f"Error reading trace file {trace_file}: {e}")

            current_date += timedelta(days=1)

        return traces

    def _generate_time_series(
        self,
        traces: List[Dict[str, Any]],
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """生成时间序列数据"""
        # 按小时分组
        hourly_data = defaultdict(lambda: {"total": 0, "success": 0, "latency": []})

        for t in traces:
            try:
                ts_str = t.get("start_time", "")
                if ts_str:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    hour_key = ts.strftime("%Y-%m-%d %H:00")

                    hourly_data[hour_key]["total"] += 1
                    if t.get("status") == "ok":
                        hourly_data[hour_key]["success"] += 1
                    if t.get("duration_ms"):
                        hourly_data[hour_key]["latency"].append(t.get("duration_ms"))
            except Exception:
                continue

        # 转换为列表
        series = []
        for hour, stats in sorted(hourly_data.items()):
            series.append({
                "time": hour,
                "total": stats["total"],
                "success_rate": stats["success"] / stats["total"] if stats["total"] > 0 else 0,
                "avg_latency_ms": sum(stats["latency"]) / len(stats["latency"]) if stats["latency"] else 0
            })

        return series[-24:]  # 最多返回24个数据点

    def _check_alerts(self, data: DashboardData) -> List[Dict[str, Any]]:
        """检查告警条件"""
        alerts = []
        thresholds = self.config.thresholds

        # 成功率告警
        if data.success_rate < thresholds.success_rate:
            alerts.append({
                "level": "warning" if data.success_rate >= thresholds.success_rate * 0.9 else "critical",
                "type": "success_rate",
                "message": f"成功率 {data.success_rate:.2%} 低于阈值 {thresholds.success_rate:.2%}",
                "value": data.success_rate,
                "threshold": thresholds.success_rate
            })

        # P99延迟告警
        if data.p99_latency_ms > thresholds.latency_p99_ms:
            alerts.append({
                "level": "warning",
                "type": "latency",
                "message": f"P99延迟 {data.p99_latency_ms:.0f}ms 超过阈值 {thresholds.latency_p99_ms}ms",
                "value": data.p99_latency_ms,
                "threshold": thresholds.latency_p99_ms
            })

        # 轨迹评分告警
        if data.avg_trajectory_score < thresholds.trajectory_pass:
            alerts.append({
                "level": "warning",
                "type": "trajectory_score",
                "message": f"平均轨迹评分 {data.avg_trajectory_score:.3f} 低于阈值 {thresholds.trajectory_pass}",
                "value": data.avg_trajectory_score,
                "threshold": thresholds.trajectory_pass
            })

        return alerts

    def _parse_time_range(self, time_range: str) -> datetime:
        """解析时间范围"""
        now = datetime.now()

        if time_range == "1h":
            return now - timedelta(hours=1)
        elif time_range == "24h":
            return now - timedelta(hours=24)
        elif time_range == "7d":
            return now - timedelta(days=7)
        elif time_range == "30d":
            return now - timedelta(days=30)
        else:
            return now - timedelta(hours=24)

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if self._cache_time is None:
            return False

        return datetime.now() - self._cache_time < self._cache_ttl

    def invalidate_cache(self):
        """使缓存失效"""
        self._cache_time = None
        self._cache.clear()


# FastAPI集成
def setup_dashboard_routes(app, dashboard: EvalDashboard):
    """
    为FastAPI应用添加仪表盘路由

    Args:
        app: FastAPI应用实例
        dashboard: EvalDashboard实例
    """
    from fastapi import Response
    import json

    @app.get("/eval/dashboard")
    async def get_dashboard():
        """获取仪表盘数据"""
        data = await dashboard.get_dashboard_data()
        return Response(
            content=json.dumps(data.to_dict(), ensure_ascii=False),
            media_type="application/json"
        )

    @app.get("/eval/metrics")
    async def get_metrics():
        """获取评估指标"""
        data = await dashboard.get_overview_metrics()
        return data

    @app.get("/eval/dimensions")
    async def get_dimensions():
        """获取维度评分"""
        data = await dashboard.get_dimension_scores()
        return data

    @app.get("/eval/alerts")
    async def get_alerts():
        """获取告警列表"""
        data = await dashboard.get_alerts()
        return data

    @app.post("/eval/refresh")
    async def refresh_dashboard():
        """刷新仪表盘"""
        await dashboard.refresh()
        return {"status": "ok"}

    return app
