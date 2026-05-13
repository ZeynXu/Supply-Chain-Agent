"""
稳定性监控系统

监控系统性能指标、收集统计信息、生成稳定性报告。
"""

import time
import json
import asyncio
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import statistics
from enum import Enum


class MetricType(Enum):
    """指标类型"""
    RESPONSE_TIME = "response_time"          # 响应时间（毫秒）
    SUCCESS_RATE = "success_rate"            # 成功率（百分比）
    ERROR_RATE = "error_rate"                # 错误率（百分比）
    RETRY_COUNT = "retry_count"              # 重试次数
    CIRCUIT_BREAKER_STATE = "circuit_breaker_state"  # 熔断器状态
    MEMORY_USAGE = "memory_usage"            # 内存使用
    CPU_USAGE = "cpu_usage"                  # CPU使用
    ACTIVE_CONNECTIONS = "active_connections"  # 活动连接数
    QUEUE_SIZE = "queue_size"                # 队列大小


class AlertLevel(Enum):
    """警报级别"""
    INFO = "info"        # 信息级别
    WARNING = "warning"  # 警告级别
    ERROR = "error"      # 错误级别
    CRITICAL = "critical"  # 致命级别


@dataclass
class MetricPoint:
    """指标数据点"""
    metric_type: str
    value: float
    timestamp: float
    tags: Dict[str, str] = None
    metadata: Dict[str, Any] = None

    def to_dict(self):
        """转换为字典"""
        return {
            "metric_type": self.metric_type,
            "value": self.value,
            "timestamp": self.timestamp,
            "timestamp_human": datetime.fromtimestamp(self.timestamp).isoformat(),
            "tags": self.tags or {},
            "metadata": self.metadata or {}
        }


@dataclass
class Alert:
    """警报"""
    level: str
    title: str
    message: str
    metric_type: str
    metric_value: float
    threshold: float
    timestamp: float
    resolved: bool = False
    resolved_at: float = None
    resolved_by: str = None

    def to_dict(self):
        """转换为字典"""
        return {
            "level": self.level,
            "title": self.title,
            "message": self.message,
            "metric_type": self.metric_type,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "timestamp": self.timestamp,
            "timestamp_human": datetime.fromtimestamp(self.timestamp).isoformat(),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
            "resolved_human": datetime.fromtimestamp(self.resolved_at).isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by
        }


@dataclass
class ThresholdConfig:
    """阈值配置"""
    metric_type: str
    warning_threshold: float
    error_threshold: float
    critical_threshold: float
    window_minutes: int = 5  # 时间窗口（分钟）
    sample_size: int = 10    # 样本大小


@dataclass
class PerformanceSummary:
    """性能摘要"""
    time_period: str                         # 时间周期
    total_requests: int                      # 总请求数
    successful_requests: int                 # 成功请求数
    failed_requests: int                     # 失败请求数
    avg_response_time_ms: float              # 平均响应时间
    p95_response_time_ms: float              # 95%响应时间
    p99_response_time_ms: float              # 99%响应时间
    success_rate: float                      # 成功率
    error_rate: float                        # 错误率
    avg_retries_per_request: float           # 平均重试次数
    circuit_breaker_stats: Dict[str, Any]    # 熔断器统计
    top_errors: List[Dict[str, Any]]         # 主要错误类型
    suggestions: List[str]                   # 改进建议


class MetricCollector:
    """指标收集器"""

    def __init__(self, retention_days: int = 7):
        self.retention_days = retention_days
        self.metrics: List[MetricPoint] = []
        self.alerts: List[Alert] = []

        # 默认阈值配置
        self.thresholds = [
            ThresholdConfig(
                metric_type=MetricType.RESPONSE_TIME.value,
                warning_threshold=3000,   # 3秒
                error_threshold=5000,     # 5秒
                critical_threshold=10000, # 10秒
                window_minutes=5
            ),
            ThresholdConfig(
                metric_type=MetricType.SUCCESS_RATE.value,
                warning_threshold=90.0,   # 90%
                error_threshold=80.0,     # 80%
                critical_threshold=70.0,  # 70%
                window_minutes=5
            ),
            ThresholdConfig(
                metric_type=MetricType.ERROR_RATE.value,
                warning_threshold=10.0,   # 10%
                error_threshold=20.0,     # 20%
                critical_threshold=30.0,  # 30%
                window_minutes=5
            ),
            ThresholdConfig(
                metric_type=MetricType.CIRCUIT_BREAKER_STATE.value,
                warning_threshold=0.5,    # 50%的熔断器半开或打开
                error_threshold=0.7,      # 70%的熔断器半开或打开
                critical_threshold=0.9,   # 90%的熔断器半开或打开
                window_minutes=5
            )
        ]

    def record_metric(self, metric_type: str, value: float, tags: Dict[str, str] = None,
                     metadata: Dict[str, Any] = None):
        """
        记录指标

        Args:
            metric_type: 指标类型
            value: 指标值
            tags: 标签
            metadata: 元数据
        """
        metric_point = MetricPoint(
            metric_type=metric_type,
            value=value,
            timestamp=time.time(),
            tags=tags or {},
            metadata=metadata or {}
        )

        self.metrics.append(metric_point)

        # 检查阈值并生成警报
        self._check_thresholds(metric_point)

        # 清理旧数据
        self._cleanup_old_metrics()

    def _check_thresholds(self, metric_point: MetricPoint):
        """检查阈值并生成警报"""
        for threshold_config in self.thresholds:
            if threshold_config.metric_type != metric_point.metric_type:
                continue

            # 检查是否超过阈值
            level = None
            threshold_value = None

            if metric_point.value >= threshold_config.critical_threshold:
                level = AlertLevel.CRITICAL
                threshold_value = threshold_config.critical_threshold
            elif metric_point.value >= threshold_config.error_threshold:
                level = AlertLevel.ERROR
                threshold_value = threshold_config.error_threshold
            elif metric_point.value >= threshold_config.warning_threshold:
                level = AlertLevel.WARNING
                threshold_value = threshold_config.warning_threshold

            if level:
                # 创建警报
                alert = Alert(
                    level=level.value,
                    title=f"{metric_point.metric_type} 超过阈值",
                    message=f"{metric_point.metric_type} 当前值 {metric_point.value:.2f} "
                           f"超过 {level.value} 阈值 {threshold_value:.2f}",
                    metric_type=metric_point.metric_type,
                    metric_value=metric_point.value,
                    threshold=threshold_value,
                    timestamp=time.time()
                )

                self.alerts.append(alert)
                print(f"⚠️ 警报: {alert.title} - {alert.message}")

    def _cleanup_old_metrics(self):
        """清理旧指标数据"""
        cutoff_time = time.time() - (self.retention_days * 24 * 3600)
        self.metrics = [m for m in self.metrics if m.timestamp >= cutoff_time]

        # 只保留最近1000个指标点（防止内存泄漏）
        if len(self.metrics) > 1000:
            self.metrics = self.metrics[-1000:]

    def get_metrics(self, metric_type: str = None, start_time: float = None,
                   end_time: float = None, tags: Dict[str, str] = None) -> List[MetricPoint]:
        """
        获取指标数据

        Args:
            metric_type: 指标类型过滤器
            start_time: 开始时间戳
            end_time: 结束时间戳
            tags: 标签过滤器

        Returns:
            指标数据点列表
        """
        filtered_metrics = self.metrics

        # 应用过滤器
        if metric_type:
            filtered_metrics = [m for m in filtered_metrics if m.metric_type == metric_type]

        if start_time:
            filtered_metrics = [m for m in filtered_metrics if m.timestamp >= start_time]

        if end_time:
            filtered_metrics = [m for m in filtered_metrics if m.timestamp <= end_time]

        if tags:
            filtered_metrics = [
                m for m in filtered_metrics
                if all(m.tags.get(k) == v for k, v in tags.items())
            ]

        return filtered_metrics

    def get_alerts(self, level: str = None, resolved: bool = None,
                  start_time: float = None) -> List[Alert]:
        """
        获取警报

        Args:
            level: 警报级别过滤器
            resolved: 是否已解决过滤器
            start_time: 开始时间戳

        Returns:
            警报列表
        """
        filtered_alerts = self.alerts

        if level:
            filtered_alerts = [a for a in filtered_alerts if a.level == level]

        if resolved is not None:
            filtered_alerts = [a for a in filtered_alerts if a.resolved == resolved]

        if start_time:
            filtered_alerts = [a for a in filtered_alerts if a.timestamp >= start_time]

        return filtered_alerts

    def resolve_alert(self, alert_index: int, resolved_by: str = "system"):
        """
        解决警报

        Args:
            alert_index: 警报索引
            resolved_by: 解决者
        """
        if 0 <= alert_index < len(self.alerts):
            self.alerts[alert_index].resolved = True
            self.alerts[alert_index].resolved_at = time.time()
            self.alerts[alert_index].resolved_by = resolved_by


class PerformanceAnalyzer:
    """性能分析器"""

    def __init__(self, metric_collector: MetricCollector):
        self.collector = metric_collector

    def analyze_performance(self, time_period_minutes: int = 60) -> PerformanceSummary:
        """
        分析性能

        Args:
            time_period_minutes: 分析时间周期（分钟）

        Returns:
            性能摘要
        """
        # 计算时间范围
        end_time = time.time()
        start_time = end_time - (time_period_minutes * 60)

        # 获取相关指标
        response_times = self.collector.get_metrics(
            metric_type=MetricType.RESPONSE_TIME.value,
            start_time=start_time,
            end_time=end_time
        )

        success_rates = self.collector.get_metrics(
            metric_type=MetricType.SUCCESS_RATE.value,
            start_time=start_time,
            end_time=end_time
        )

        error_rates = self.collector.get_metrics(
            metric_type=MetricType.ERROR_RATE.value,
            start_time=start_time,
            end_time=end_time
        )

        retry_counts = self.collector.get_metrics(
            metric_type=MetricType.RETRY_COUNT.value,
            start_time=start_time,
            end_time=end_time
        )

        # 计算统计信息
        if response_times:
            response_time_values = [m.value for m in response_times]
            avg_response_time = statistics.mean(response_time_values)
            if len(response_time_values) > 1:
                p95_response_time = statistics.quantiles(response_time_values, n=20)[18]  # 95%
                p99_response_time = statistics.quantiles(response_time_values, n=100)[98]  # 99%
            else:
                p95_response_time = p99_response_time = avg_response_time
        else:
            avg_response_time = p95_response_time = p99_response_time = 0.0

        # 计算成功率
        avg_success_rate = statistics.mean([m.value for m in success_rates]) if success_rates else 0.0
        avg_error_rate = statistics.mean([m.value for m in error_rates]) if error_rates else 0.0

        # 计算平均重试次数
        avg_retries = statistics.mean([m.value for m in retry_counts]) if retry_counts else 0.0

        # 估算请求数量
        total_requests = len(response_times) * 10  # 简化估算
        successful_requests = int(total_requests * (avg_success_rate / 100))
        failed_requests = total_requests - successful_requests

        # 获取错误分布
        recent_alerts = self.collector.get_alerts(start_time=start_time)
        error_types = {}
        for alert in recent_alerts:
            error_type = alert.metric_type
            error_types[error_type] = error_types.get(error_type, 0) + 1

        top_errors = [
            {"error_type": error_type, "count": count}
            for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        # 生成改进建议
        suggestions = self._generate_suggestions(avg_response_time, avg_success_rate, avg_error_rate)

        return PerformanceSummary(
            time_period=f"最近{time_period_minutes}分钟",
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time_ms=round(avg_response_time, 2),
            p95_response_time_ms=round(p95_response_time, 2),
            p99_response_time_ms=round(p99_response_time, 2),
            success_rate=round(avg_success_rate, 2),
            error_rate=round(avg_error_rate, 2),
            avg_retries_per_request=round(avg_retries, 2),
            circuit_breaker_stats={},  # 可以从retry_manager获取
            top_errors=top_errors,
            suggestions=suggestions
        )

    def _generate_suggestions(self, avg_response_time: float, success_rate: float,
                            error_rate: float) -> List[str]:
        """生成改进建议"""
        suggestions = []

        # 响应时间建议
        if avg_response_time > 5000:  # 5秒
            suggestions.append("响应时间过长，建议优化慢查询或增加缓存")
        elif avg_response_time > 3000:  # 3秒
            suggestions.append("响应时间偏高，建议检查网络延迟或数据库性能")

        # 成功率建议
        if success_rate < 70:  # 70%
            suggestions.append("成功率过低，建议检查系统稳定性和错误处理机制")
        elif success_rate < 85:  # 85%
            suggestions.append("成功率有待提高，建议优化重试机制和熔断器配置")

        # 错误率建议
        if error_rate > 30:  # 30%
            suggestions.append("错误率过高，建议加强系统监控和故障排查")
        elif error_rate > 15:  # 15%
            suggestions.append("错误率偏高，建议分析主要错误类型并针对性优化")

        # 通用建议
        if not suggestions:
            suggestions.append("系统性能良好，继续保持当前配置")

        if success_rate > 95 and avg_response_time < 2000:
            suggestions.append("系统性能优秀，可考虑降低监控频率以节省资源")

        return suggestions


class StabilityReportGenerator:
    """稳定性报告生成器"""

    def __init__(self, metric_collector: MetricCollector, performance_analyzer: PerformanceAnalyzer):
        self.collector = metric_collector
        self.analyzer = performance_analyzer

    def generate_report(self, time_period_minutes: int = 60) -> Dict[str, Any]:
        """
        生成稳定性报告

        Args:
            time_period_minutes: 报告时间周期（分钟）

        Returns:
            稳定性报告
        """
        # 获取性能摘要
        performance_summary = self.analyzer.analyze_performance(time_period_minutes)

        # 获取活跃警报
        active_alerts = self.collector.get_alerts(resolved=False)
        recent_alerts = self.collector.get_alerts(start_time=time.time() - (time_period_minutes * 60))

        # 获取系统指标趋势
        response_time_trend = self._get_metric_trend(MetricType.RESPONSE_TIME.value, time_period_minutes)
        success_rate_trend = self._get_metric_trend(MetricType.SUCCESS_RATE.value, time_period_minutes)

        # 构建报告
        report = {
            "report_id": f"stability_{int(time.time())}",
            "generated_at": datetime.now().isoformat(),
            "time_period": f"{time_period_minutes}分钟",
            "summary": {
                "status": self._determine_overall_status(performance_summary, active_alerts),
                "availability": round(performance_summary.success_rate, 2),
                "performance": round(100 - (performance_summary.avg_response_time_ms / 100), 2),  # 性能评分
                "stability": round(100 - (len(active_alerts) * 5), 2)  # 稳定性评分
            },
            "performance_metrics": asdict(performance_summary),
            "alerts": {
                "active": [a.to_dict() for a in active_alerts[:10]],  # 只显示前10个活跃警报
                "recent": len(recent_alerts),
                "resolved": len([a for a in recent_alerts if a.resolved])
            },
            "trends": {
                "response_time": response_time_trend,
                "success_rate": success_rate_trend
            },
            "recommendations": performance_summary.suggestions,
            "next_steps": self._generate_next_steps(performance_summary, active_alerts)
        }

        return report

    def _get_metric_trend(self, metric_type: str, time_period_minutes: int) -> Dict[str, Any]:
        """获取指标趋势"""
        end_time = time.time()
        start_time = end_time - (time_period_minutes * 60)

        metrics = self.collector.get_metrics(
            metric_type=metric_type,
            start_time=start_time,
            end_time=end_time
        )

        if not metrics:
            return {"data_points": 0, "trend": "stable", "values": []}

        # 计算趋势（简单线性回归）
        values = [m.value for m in metrics]
        timestamps = [m.timestamp for m in metrics]

        if len(values) < 2:
            return {"data_points": len(values), "trend": "insufficient_data", "values": values}

        # 简单趋势判断
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]

        avg_first = statistics.mean(first_half) if first_half else 0
        avg_second = statistics.mean(second_half) if second_half else 0

        if avg_second > avg_first * 1.1:
            trend = "increasing"
        elif avg_second < avg_first * 0.9:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "data_points": len(values),
            "trend": trend,
            "avg_value": round(statistics.mean(values), 2),
            "min_value": round(min(values), 2),
            "max_value": round(max(values), 2),
            "values": values[-10:]  # 最近10个值
        }

    def _determine_overall_status(self, performance_summary: PerformanceSummary,
                                 active_alerts: List[Alert]) -> str:
        """确定总体状态"""
        # 检查关键指标
        if performance_summary.success_rate < 70:
            return "critical"
        elif performance_summary.success_rate < 85:
            return "warning"

        # 检查响应时间
        if performance_summary.avg_response_time_ms > 5000:
            return "warning"
        elif performance_summary.avg_response_time_ms > 3000:
            return "degraded"

        # 检查警报
        critical_alerts = [a for a in active_alerts if a.level == AlertLevel.CRITICAL.value]
        if critical_alerts:
            return "critical"

        error_alerts = [a for a in active_alerts if a.level == AlertLevel.ERROR.value]
        if error_alerts:
            return "error"

        warning_alerts = [a for a in active_alerts if a.level == AlertLevel.WARNING.value]
        if warning_alerts:
            return "warning"

        return "healthy"

    def _generate_next_steps(self, performance_summary: PerformanceSummary,
                            active_alerts: List[Alert]) -> List[str]:
        """生成下一步行动建议"""
        next_steps = []

        # 基于性能问题
        if performance_summary.success_rate < 85:
            next_steps.append("优先处理成功率问题，检查主要错误类型")

        if performance_summary.avg_response_time_ms > 3000:
            next_steps.append("优化慢查询，检查数据库索引和缓存策略")

        # 基于警报
        critical_alerts = [a for a in active_alerts if a.level == AlertLevel.CRITICAL.value]
        if critical_alerts:
            next_steps.append(f"立即处理 {len(critical_alerts)} 个关键警报")

        error_alerts = [a for a in active_alerts if a.level == AlertLevel.ERROR.value]
        if error_alerts:
            next_steps.append(f"处理 {len(error_alerts)} 个错误级别警报")

        # 一般维护建议
        if len(active_alerts) > 10:
            next_steps.append("清理积压警报，优化监控阈值")

        if performance_summary.avg_retries_per_request > 1.5:
            next_steps.append("优化重试策略，减少不必要的重试")

        # 默认建议
        if not next_steps:
            next_steps.append("定期检查系统日志，保持监控配置更新")
            next_steps.append("进行性能压力测试，验证系统容量")

        return next_steps


# 全局稳定性监控实例
stability_monitor = MetricCollector()
performance_analyzer = PerformanceAnalyzer(stability_monitor)
report_generator = StabilityReportGenerator(stability_monitor, performance_analyzer)


# 导出主要类
__all__ = [
    "MetricType",
    "AlertLevel",
    "MetricCollector",
    "PerformanceAnalyzer",
    "StabilityReportGenerator",
    "stability_monitor",
    "performance_analyzer",
    "report_generator"
]