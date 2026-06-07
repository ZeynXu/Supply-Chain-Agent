"""
结构化日志配置

输出 JSON 格式日志，便于采集到 ELK/Loki。
"""

import json
import logging
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from functools import lru_cache


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""

    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        """格式化为 JSON"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 添加额外字段
        if self.include_extra and hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }

        return json.dumps(log_data, ensure_ascii=False)


class StructuredLogger:
    """结构化日志记录器"""

    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # 避免重复添加 handler
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(StructuredFormatter())
            self.logger.addHandler(handler)

    def _log(self, level: int, message: str, **kwargs):
        """内部日志方法"""
        record = self.logger.makeRecord(
            self.logger.name, level, "", 0, message, (), None
        )
        record.extra_fields = kwargs
        self.logger.handle(record)

    def info(self, message: str, **kwargs):
        """记录 INFO 级别日志"""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """记录 WARNING 级别日志"""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """记录 ERROR 级别日志"""
        self._log(logging.ERROR, message, **kwargs)

    def debug(self, message: str, **kwargs):
        """记录 DEBUG 级别日志"""
        self._log(logging.DEBUG, message, **kwargs)

    def with_context(self, **context) -> 'ContextLogger':
        """返回带上下文的日志记录器"""
        return ContextLogger(self, context)


class ContextLogger:
    """带上下文的日志记录器"""

    def __init__(self, logger: StructuredLogger, context: Dict[str, Any]):
        self.logger = logger
        self.context = context

    def info(self, message: str, **kwargs):
        self.logger.info(message, **{**self.context, **kwargs})

    def warning(self, message: str, **kwargs):
        self.logger.warning(message, **{**self.context, **kwargs})

    def error(self, message: str, **kwargs):
        self.logger.error(message, **{**self.context, **kwargs})

    def debug(self, message: str, **kwargs):
        self.logger.debug(message, **{**self.context, **kwargs})


@lru_cache(maxsize=32)
def get_logger(name: str) -> StructuredLogger:
    """获取结构化日志记录器（带缓存）"""
    return StructuredLogger(name)


def configure_logging(level: int = logging.INFO):
    """配置全局日志"""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 移除现有 handlers
    root_logger.handlers.clear()

    # 添加结构化 handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(handler)
