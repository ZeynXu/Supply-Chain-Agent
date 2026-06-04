"""
H6修复：定义具体异常类型层次结构

解决异常处理过于宽泛的问题，区分可恢复和不可恢复错误。
"""

from typing import Optional, Dict, Any


# ============== 基础异常类 ==============

class SupplyChainError(Exception):
    """供应链Agent基础异常"""

    def __init__(self, message: str, original_error: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
        self.original_error = original_error
        self.context = context or {}
        super().__init__(message)


# ============== 可恢复异常（可重试） ==============

class RecoverableError(SupplyChainError):
    """可恢复异常基类 - 可以通过重试或其他策略恢复"""
    pass


class ConnectionError(RecoverableError):
    """连接错误 - 可重试"""
    pass


class TimeoutError(RecoverableError):
    """超时错误 - 可重试"""
    pass


class RateLimitError(RecoverableError):
    """速率限制错误 - 等待后可重试"""
    pass


class ServiceUnavailableError(RecoverableError):
    """服务不可用错误 - 可重试"""
    pass


# ============== 不可恢复异常（需用户干预） ==============

class UnrecoverableError(SupplyChainError):
    """不可恢复异常基类 - 需要用户干预或系统管理员处理"""
    pass


class ValidationError(UnrecoverableError):
    """验证错误 - 需要用户提供正确输入"""
    pass


class NotFoundError(UnrecoverableError):
    """资源未找到错误"""
    pass


class PermissionDeniedError(UnrecoverableError):
    """权限拒绝错误"""
    pass


class ConfigurationError(UnrecoverableError):
    """配置错误 - 需要管理员修复配置"""
    pass


# ============== 业务异常 ==============

class IntentParseError(SupplyChainError):
    """意图解析错误"""
    pass


class EntityExtractionError(SupplyChainError):
    """实体提取错误"""
    pass


class ToolExecutionError(SupplyChainError):
    """工具执行错误"""

    def __init__(self, tool_name: str, message: str, original_error: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' failed: {message}", original_error, context)


class CircuitBreakerOpenError(SupplyChainError):
    """熔断器打开错误"""

    def __init__(self, circuit_name: str, recovery_time: Optional[float] = None):
        self.circuit_name = circuit_name
        self.recovery_time = recovery_time
        message = f"Circuit breaker '{circuit_name}' is open"
        if recovery_time:
            message += f", will recover in {recovery_time:.1f}s"
        super().__init__(message)


class ClarificationMaxAttemptsError(UnrecoverableError):
    """澄清最大尝试次数错误"""
    pass


class ExecutionPlanError(UnrecoverableError):
    """执行计划生成错误"""
    pass


# ============== 辅助函数 ==============

def is_recoverable(error: Exception) -> bool:
    """判断异常是否可恢复"""
    return isinstance(error, RecoverableError)


def is_connection_error(error: Exception) -> bool:
    """判断是否为连接类错误"""
    return isinstance(error, (ConnectionError, TimeoutError, ServiceUnavailableError))


def get_error_category(error: Exception) -> str:
    """获取错误类别"""
    if isinstance(error, RecoverableError):
        return "recoverable"
    elif isinstance(error, UnrecoverableError):
        return "unrecoverable"
    elif isinstance(error, SupplyChainError):
        return "business"
    else:
        return "unknown"


def wrap_exception(error: Exception, context: Optional[Dict[str, Any]] = None) -> SupplyChainError:
    """
    将标准异常包装为SupplyChainError

    Args:
        error: 原始异常
        context: 错误上下文

    Returns:
        包装后的异常
    """
    if isinstance(error, SupplyChainError):
        if context:
            error.context.update(context)
        return error

    # 根据标准异常类型映射
    error_type = type(error).__name__

    if error_type in ('ConnectionError', 'ConnectionRefusedError', 'ConnectionResetError'):
        return ConnectionError(str(error), error, context)
    elif error_type == 'TimeoutError':
        return TimeoutError(str(error), error, context)
    elif error_type in ('HTTPStatusError', 'HTTPError'):
        return ServiceUnavailableError(str(error), error, context)
    elif error_type == 'ValueError':
        return ValidationError(str(error), error, context)
    elif error_type == 'KeyError':
        return NotFoundError(str(error), error, context)
    elif error_type == 'PermissionError':
        return PermissionDeniedError(str(error), error, context)
    else:
        return SupplyChainError(str(error), error, context)


__all__ = [
    # 基础类
    'SupplyChainError',
    # 可恢复异常
    'RecoverableError',
    'ConnectionError',
    'TimeoutError',
    'RateLimitError',
    'ServiceUnavailableError',
    # 不可恢复异常
    'UnrecoverableError',
    'ValidationError',
    'NotFoundError',
    'PermissionDeniedError',
    'ConfigurationError',
    # 业务异常
    'IntentParseError',
    'EntityExtractionError',
    'ToolExecutionError',
    'CircuitBreakerOpenError',
    'ClarificationMaxAttemptsError',
    'ExecutionPlanError',
    # 辅助函数
    'is_recoverable',
    'is_connection_error',
    'get_error_category',
    'wrap_exception',
]
