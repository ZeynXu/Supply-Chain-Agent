"""
参数预检装饰器

为 Executor Agent 提供可选的参数预检功能。
"""

import os
import logging
from functools import wraps
from typing import Callable, List, Dict, Any

logger = logging.getLogger(__name__)


def with_pre_check(checks: List[Callable] = None):
    """
    参数预检装饰器

    在执行工具前执行额外校验。

    Args:
        checks: 校验函数列表，每个函数接受 (tool_name, params) 参数

    Usage:
        @with_pre_check([check_order_exists])
        async def execute_tool(self, tool_name, params):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, tool_name, params):
            # 检查是否启用预检
            if os.getenv("HARNESS_PRE_CHECK", "false").lower() != "true":
                return await func(self, tool_name, params)

            # 执行预检
            if checks:
                for check in checks:
                    try:
                        check(tool_name, params)
                    except ValueError as e:
                        logger.warning(f"Pre-check failed for {tool_name}: {e}")
                        raise

            return await func(self, tool_name, params)
        return wrapper
    return decorator


def check_required_params(required_params: Dict[str, type]):
    """
    创建必填参数校验器

    Args:
        required_params: 参数名到类型的映射

    Returns:
        校验函数
    """
    def check(tool_name: str, params: Dict[str, Any]):
        for param_name, param_type in required_params.items():
            if param_name not in params:
                raise ValueError(f"Missing required parameter: {param_name}")

            if not isinstance(params[param_name], param_type):
                raise ValueError(
                    f"Parameter '{param_name}' must be of type {param_type.__name__}, "
                    f"got {type(params[param_name]).__name__}"
                )

    return check


def check_param_range(param_name: str, min_val: Any = None, max_val: Any = None):
    """
    创建参数范围校验器

    Args:
        param_name: 参数名
        min_val: 最小值
        max_val: 最大值

    Returns:
        校验函数
    """
    def check(tool_name: str, params: Dict[str, Any]):
        if param_name not in params:
            return  # 参数不存在，跳过

        value = params[param_name]

        if min_val is not None and value < min_val:
            raise ValueError(
                f"Parameter '{param_name}' must be >= {min_val}, got {value}"
            )

        if max_val is not None and value > max_val:
            raise ValueError(
                f"Parameter '{param_name}' must be <= {max_val}, got {value}"
            )

    return check


def check_param_choices(param_name: str, choices: List[Any]):
    """
    创建参数选项校验器

    Args:
        param_name: 参数名
        choices: 允许的值列表

    Returns:
        校验函数
    """
    def check(tool_name: str, params: Dict[str, Any]):
        if param_name not in params:
            return  # 参数不存在，跳过

        value = params[param_name]

        if value not in choices:
            raise ValueError(
                f"Parameter '{param_name}' must be one of {choices}, got {value}"
            )

    return check
