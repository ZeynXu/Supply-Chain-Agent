"""
智能异常重试机制模块

实现多种重试策略、熔断器模式和智能错误处理，提升系统稳定性。
"""

import time
import asyncio
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import random


class RetryStrategyType(Enum):
    """重试策略类型枚举"""
    FIXED_DELAY = "fixed_delay"      # 固定延迟重试
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # 指数退避重试
    RANDOM_JITTER = "random_jitter"  # 随机抖动重试
    ADAPTIVE = "adaptive"            # 自适应重试


class CircuitBreakerState(Enum):
    """熔断器状态枚举"""
    CLOSED = "closed"      # 闭合状态：正常服务
    OPEN = "open"          # 打开状态：拒绝请求
    HALF_OPEN = "half_open"  # 半开状态：尝试恢复


class ErrorSeverity(Enum):
    """错误严重性等级"""
    LOW = "low"        # 低严重性：可自动恢复的临时错误
    MEDIUM = "medium"  # 中等严重性：需要人工干预的错误
    HIGH = "high"      # 高严重性：系统级错误
    CRITICAL = "critical"  # 致命错误：服务不可用


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3                     # 最大重试次数
    base_delay_ms: int = 1000                # 基础延迟（毫秒）
    max_delay_ms: int = 10000                # 最大延迟（毫秒）
    strategy: RetryStrategyType = RetryStrategyType.EXPONENTIAL_BACKOFF  # 重试策略
    jitter_factor: float = 0.1               # 抖动因子（0-1）
    retry_on_exceptions: List[str] = field(default_factory=list)  # 触发重试的异常类型


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5               # 失败阈值
    failure_window_seconds: int = 60         # 失败窗口时间（秒）
    recovery_timeout_seconds: int = 30       # 恢复超时时间（秒）
    success_threshold: int = 3               # 成功阈值（半开状态下）
    half_open_timeout_seconds: int = 10      # 半开超时时间（秒）


@dataclass
class ErrorPattern:
    """错误模式"""
    error_type: str                         # 错误类型
    pattern: str                            # 错误模式（正则表达式）
    severity: ErrorSeverity                 # 严重性等级
    suggested_action: str                   # 建议操作
    auto_recoverable: bool = True           # 是否可自动恢复


class RetryStrategy:
    """重试策略基类"""

    def __init__(self, config: RetryConfig):
        self.config = config

    def calculate_delay(self, attempt: int) -> int:
        """
        计算重试延迟

        Args:
            attempt: 当前重试次数（0为第一次尝试）

        Returns:
            延迟时间（毫秒）
        """
        raise NotImplementedError


class FixedDelayStrategy(RetryStrategy):
    """固定延迟重试策略"""

    def calculate_delay(self, attempt: int) -> int:
        """固定延迟"""
        return self.config.base_delay_ms


class ExponentialBackoffStrategy(RetryStrategy):
    """指数退避重试策略"""

    def calculate_delay(self, attempt: int) -> int:
        """指数退避延迟"""
        delay = self.config.base_delay_ms * (2 ** attempt)
        return min(delay, self.config.max_delay_ms)


class RandomJitterStrategy(RetryStrategy):
    """随机抖动重试策略"""

    def calculate_delay(self, attempt: int) -> int:
        """指数退避+随机抖动"""
        base_delay = self.config.base_delay_ms * (2 ** attempt)
        jitter = base_delay * self.config.jitter_factor
        delay = base_delay + random.uniform(-jitter, jitter)
        return min(max(delay, self.config.base_delay_ms), self.config.max_delay_ms)


class AdaptiveStrategy(RetryStrategy):
    """自适应重试策略"""

    def __init__(self, config: RetryConfig, system_load: float = 0.0):
        super().__init__(config)
        self.system_load = system_load  # 系统负载（0.0-1.0）

    def calculate_delay(self, attempt: int) -> int:
        """根据系统负载调整延迟"""
        # 基础指数退避
        base_delay = self.config.base_delay_ms * (2 ** attempt)

        # 根据系统负载调整延迟（负载高时增加延迟）
        load_factor = 1.0 + self.system_load
        adjusted_delay = base_delay * load_factor

        # 添加随机抖动
        jitter = adjusted_delay * self.config.jitter_factor
        final_delay = adjusted_delay + random.uniform(-jitter, jitter)

        return min(max(final_delay, self.config.base_delay_ms), self.config.max_delay_ms)


class CircuitBreaker:
    """熔断器类"""

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change_time = time.time()
        self.half_open_attempts = 0

    def is_call_allowed(self) -> bool:
        """
        检查是否允许调用

        Returns:
            True if call is allowed, False if circuit is open
        """
        current_time = time.time()

        # 检查是否需要重置失败计数
        if (self.last_failure_time and
            current_time - self.last_failure_time > self.config.failure_window_seconds):
            self.failure_count = 0

        # 状态机逻辑
        if self.state == CircuitBreakerState.OPEN:
            # 检查是否应该进入半开状态
            if current_time - self.last_state_change_time > self.config.recovery_timeout_seconds:
                self.state = CircuitBreakerState.HALF_OPEN
                self.last_state_change_time = current_time
                self.half_open_attempts = 0
                return True
            return False

        elif self.state == CircuitBreakerState.HALF_OPEN:
            # 限制半开状态下的尝试次数
            if self.half_open_attempts >= self.config.success_threshold * 2:
                return False
            self.half_open_attempts += 1
            return True

        else:  # CLOSED
            return True

    def record_success(self):
        """记录成功调用"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            # 如果达到成功阈值，恢复到闭合状态
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.half_open_attempts = 0
                self.last_state_change_time = time.time()
        elif self.state == CircuitBreakerState.CLOSED:
            # 成功调用后重置失败计数
            if self.failure_count > 0:
                self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        """记录失败调用"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitBreakerState.HALF_OPEN:
            # 半开状态下失败，立即打开
            self.state = CircuitBreakerState.OPEN
            self.last_state_change_time = time.time()
            self.half_open_attempts = 0
        elif self.state == CircuitBreakerState.CLOSED:
            # 闭合状态下达到失败阈值，打开熔断器
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                self.last_state_change_time = time.time()

    def get_status(self) -> Dict[str, Any]:
        """获取熔断器状态"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_state_change_time": self.last_state_change_time,
            "is_allowed": self.is_call_allowed()
        }


class ErrorClassifier:
    """错误分类器"""

    def __init__(self):
        # 定义常见错误模式
        self.error_patterns = [
            ErrorPattern(
                error_type="connection_error",
                pattern=r"(connection|connect|timeout|timed out)",
                severity=ErrorSeverity.LOW,
                suggested_action="检查网络连接或稍后重试",
                auto_recoverable=True
            ),
            ErrorPattern(
                error_type="rate_limit",
                pattern=r"(rate limit|too many requests|quota exceeded)",
                severity=ErrorSeverity.MEDIUM,
                suggested_action="等待限制解除或减少请求频率",
                auto_recoverable=True
            ),
            ErrorPattern(
                error_type="authentication_error",
                pattern=r"(auth|authentication|unauthorized|forbidden)",
                severity=ErrorSeverity.HIGH,
                suggested_action="检查凭据或重新认证",
                auto_recoverable=False
            ),
            ErrorPattern(
                error_type="resource_not_found",
                pattern=r"(not found|404|does not exist)",
                severity=ErrorSeverity.MEDIUM,
                suggested_action="检查资源ID或路径是否正确",
                auto_recoverable=False
            ),
            ErrorPattern(
                error_type="server_error",
                pattern=r"(server error|500|internal error)",
                severity=ErrorSeverity.HIGH,
                suggested_action="联系系统管理员或稍后重试",
                auto_recoverable=True
            ),
            ErrorPattern(
                error_type="validation_error",
                pattern=r"(validation|invalid|bad request|400)",
                severity=ErrorSeverity.MEDIUM,
                suggested_action="检查输入参数是否符合要求",
                auto_recoverable=False
            ),
            ErrorPattern(
                error_type="service_unavailable",
                pattern=r"(service unavailable|503|maintenance)",
                severity=ErrorSeverity.CRITICAL,
                suggested_action="等待服务恢复或使用备用服务",
                auto_recoverable=True
            )
        ]

    def classify_error(self, error: Exception) -> Dict[str, Any]:
        """
        分类错误

        Args:
            error: 异常对象

        Returns:
            错误分类信息
        """
        error_message = str(error).lower()
        error_type = type(error).__name__

        for pattern in self.error_patterns:
            if pattern.pattern.lower() in error_message:
                return {
                    "type": pattern.error_type,
                    "severity": pattern.severity.value,
                    "suggested_action": pattern.suggested_action,
                    "auto_recoverable": pattern.auto_recoverable,
                    "original_error": error_type,
                    "message": str(error)
                }

        # 默认分类
        return {
            "type": "unknown_error",
            "severity": ErrorSeverity.MEDIUM.value,
            "suggested_action": "检查错误日志或联系技术支持",
            "auto_recoverable": False,
            "original_error": error_type,
            "message": str(error)
        }


class RetryManager:
    """重试管理器"""

    def __init__(self, config: RetryConfig = None, circuit_breaker_config: CircuitBreakerConfig = None):
        self.config = config or RetryConfig()
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self.error_classifier = ErrorClassifier()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.execution_stats: Dict[str, Dict[str, Any]] = {}

        # 创建策略实例
        self.strategies = {
            RetryStrategyType.FIXED_DELAY: FixedDelayStrategy(self.config),
            RetryStrategyType.EXPONENTIAL_BACKOFF: ExponentialBackoffStrategy(self.config),
            RetryStrategyType.RANDOM_JITTER: RandomJitterStrategy(self.config),
            RetryStrategyType.ADAPTIVE: AdaptiveStrategy(self.config)
        }

    def get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name, self.circuit_breaker_config)
        return self.circuit_breakers[name]

    async def execute_with_retry(
        self,
        func: Callable,
        func_name: str,
        circuit_breaker_name: str = None,
        *args,
        **kwargs
    ) -> Any:
        """
        执行带重试和熔断器的函数

        Args:
            func: 要执行的函数
            func_name: 函数名称（用于统计）
            circuit_breaker_name: 熔断器名称
            *args, **kwargs: 函数参数

        Returns:
            函数执行结果

        Raises:
            Exception: 如果所有重试都失败
        """
        start_time = time.time()
        last_error = None
        retry_count = 0

        # 获取熔断器
        circuit_breaker = None
        if circuit_breaker_name:
            circuit_breaker = self.get_circuit_breaker(circuit_breaker_name)

            # 检查是否允许调用
            if not circuit_breaker.is_call_allowed():
                raise Exception(f"Circuit breaker '{circuit_breaker_name}' is OPEN")

        # 选择策略
        strategy = self.strategies.get(self.config.strategy, self.strategies[RetryStrategyType.EXPONENTIAL_BACKOFF])

        for attempt in range(self.config.max_retries + 1):
            try:
                if attempt > 0:
                    # 计算延迟
                    delay_ms = strategy.calculate_delay(attempt - 1)
                    await asyncio.sleep(delay_ms / 1000.0)

                # 执行函数
                result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

                # 记录成功
                if circuit_breaker:
                    circuit_breaker.record_success()

                # 更新统计
                execution_time = (time.time() - start_time) * 1000  # 毫秒
                self._record_success(func_name, execution_time, retry_count)

                return result

            except Exception as e:
                last_error = e
                retry_count = attempt

                # 分类错误
                error_info = self.error_classifier.classify_error(e)

                # 检查是否应该重试
                if not self._should_retry(error_info, attempt):
                    break

                # 记录失败
                if circuit_breaker:
                    circuit_breaker.record_failure()

                # 记录错误统计
                self._record_error(func_name, error_info)

        # 所有重试都失败
        execution_time = (time.time() - start_time) * 1000
        self._record_failure(func_name, execution_time, retry_count, last_error)

        # 根据错误类型决定是否抛出原始异常
        error_info = self.error_classifier.classify_error(last_error)
        if not error_info["auto_recoverable"]:
            raise last_error
        else:
            raise Exception(f"Operation failed after {retry_count} retries: {str(last_error)}")

    def _should_retry(self, error_info: Dict[str, Any], attempt: int) -> bool:
        """
        判断是否应该重试

        Args:
            error_info: 错误信息
            attempt: 当前尝试次数

        Returns:
            是否应该重试
        """
        # 检查最大重试次数
        if attempt >= self.config.max_retries:
            return False

        # 检查是否可自动恢复
        if not error_info.get("auto_recoverable", False):
            return False

        # 检查错误类型是否在重试列表
        if (self.config.retry_on_exceptions and
            error_info["type"] not in self.config.retry_on_exceptions):
            return False

        return True

    def _record_success(self, func_name: str, execution_time_ms: float, retry_count: int):
        """记录成功执行"""
        if func_name not in self.execution_stats:
            self.execution_stats[func_name] = {
                "success_count": 0,
                "failure_count": 0,
                "total_execution_time_ms": 0,
                "total_retries": 0,
                "last_success": time.time()
            }

        stats = self.execution_stats[func_name]
        stats["success_count"] += 1
        stats["total_execution_time_ms"] += execution_time_ms
        stats["total_retries"] += retry_count
        stats["last_success"] = time.time()

    def _record_error(self, func_name: str, error_info: Dict[str, Any]):
        """记录错误"""
        if func_name not in self.execution_stats:
            self.execution_stats[func_name] = {
                "success_count": 0,
                "failure_count": 0,
                "total_execution_time_ms": 0,
                "total_retries": 0,
                "errors": {}
            }

        stats = self.execution_stats[func_name]

        # 记录错误类型
        error_type = error_info["type"]
        if "errors" not in stats:
            stats["errors"] = {}

        if error_type not in stats["errors"]:
            stats["errors"][error_type] = {
                "count": 0,
                "severity": error_info["severity"],
                "last_occurred": None
            }

        stats["errors"][error_type]["count"] += 1
        stats["errors"][error_type]["last_occurred"] = time.time()

    def _record_failure(self, func_name: str, execution_time_ms: float, retry_count: int, error: Exception):
        """记录失败执行"""
        if func_name not in self.execution_stats:
            self.execution_stats[func_name] = {
                "success_count": 0,
                "failure_count": 0,
                "total_execution_time_ms": 0,
                "total_retries": 0
            }

        stats = self.execution_stats[func_name]
        stats["failure_count"] += 1
        stats["total_execution_time_ms"] += execution_time_ms
        stats["total_retries"] += retry_count

    def get_statistics(self, func_name: str = None) -> Dict[str, Any]:
        """
        获取执行统计

        Args:
            func_name: 可选的函数名称

        Returns:
            统计信息
        """
        if func_name:
            return self.execution_stats.get(func_name, {})

        # 汇总所有统计
        total_stats = {
            "total_functions": len(self.execution_stats),
            "total_successes": 0,
            "total_failures": 0,
            "avg_success_rate": 0.0,
            "circuit_breaker_status": {}
        }

        success_count = 0
        failure_count = 0

        for func_name, stats in self.execution_stats.items():
            total_stats["total_successes"] += stats.get("success_count", 0)
            total_stats["total_failures"] += stats.get("failure_count", 0)
            success_count += stats.get("success_count", 0)
            failure_count += stats.get("failure_count", 0)

        total_operations = success_count + failure_count
        if total_operations > 0:
            total_stats["avg_success_rate"] = success_count / total_operations

        # 添加熔断器状态
        for name, cb in self.circuit_breakers.items():
            total_stats["circuit_breaker_status"][name] = cb.get_status()

        return total_stats


# 全局重试管理器实例
retry_manager = RetryManager()


# 导出主要类
__all__ = [
    "RetryStrategyType",
    "CircuitBreakerState",
    "ErrorSeverity",
    "RetryConfig",
    "CircuitBreakerConfig",
    "ErrorPattern",
    "RetryStrategy",
    "CircuitBreaker",
    "ErrorClassifier",
    "RetryManager",
    "retry_manager"
]