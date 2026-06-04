"""
统一日志工具（L1修复：替代print语句）

提供带日志级别、时间戳的日志功能，生产环境可关闭调试日志。
"""

import logging
import sys
from datetime import datetime
from typing import Any, Optional, Dict
from supply_chain_agent.config import settings


# 创建logger
logger = logging.getLogger("supply_chain_agent")
logger.setLevel(logging.DEBUG if settings.debug_mode else logging.INFO)

# 控制台handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG if settings.debug_mode else logging.INFO)

# 格式化器
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def log_debug(message: str, **kwargs: Any) -> None:
    """调试日志（仅开发环境输出）"""
    logger.debug(message, **kwargs)


def log_info(message: str, **kwargs: Any) -> None:
    """信息日志"""
    logger.info(message, **kwargs)


def log_warning(message: str, **kwargs: Any) -> None:
    """警告日志"""
    logger.warning(message, **kwargs)


def log_error(message: str, **kwargs: Any) -> None:
    """错误日志"""
    logger.error(message, **kwargs)


def log_agent(agent_name: str, action: str, details: Optional[Dict] = None) -> None:
    """
    Agent操作日志（带结构化信息）

    Args:
        agent_name: Agent名称
        action: 执行动作
        details: 详细信息
    """
    detail_str = f" | {details}" if details else ""
    log_info(f"[{agent_name}] {action}{detail_str}")


# 兼容性函数：替代print语句
def print_info(message: str) -> None:
    """替代print的信息输出（带时间戳）"""
    if settings.debug_mode:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    else:
        log_info(message)


def print_debug(message: str) -> None:
    """替代print的调试输出（仅开发环境）"""
    if settings.debug_mode:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] DEBUG: {message}")


def print_warning(message: str) -> None:
    """替代print的警告输出"""
    log_warning(message)


def print_error(message: str) -> None:
    """替代print的错误输出"""
    log_error(message)


# 导出
__all__ = [
    "logger",
    "log_debug",
    "log_info",
    "log_warning",
    "log_error",
    "log_agent",
    "print_info",
    "print_debug",
    "print_warning",
    "print_error"
]
