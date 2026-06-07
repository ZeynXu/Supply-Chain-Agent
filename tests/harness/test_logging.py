"""结构化日志测试"""

import pytest
import json
import logging
import io

from supply_chain_agent.harness.observability.logging_config import (
    StructuredFormatter,
    StructuredLogger,
    configure_logging,
    get_logger,
)


class TestStructuredFormatter:
    """结构化日志格式化器测试"""

    def test_format_produces_valid_json(self):
        """测试格式化输出有效 JSON"""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )

        output = formatter.format(record)

        # 验证是有效 JSON
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["logger"] == "test.logger"
        assert "timestamp" in data

    def test_format_includes_extra_fields(self):
        """测试包含额外字段"""
        formatter = StructuredFormatter(include_extra=True)
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.extra_fields = {"user_id": "123", "action": "query"}

        output = formatter.format(record)
        data = json.loads(output)

        assert data["user_id"] == "123"
        assert data["action"] == "query"


class TestStructuredLogger:
    """结构化日志记录器测试"""

    def test_info_logs_with_extra_fields(self, caplog):
        """测试 info 方法记录额外字段"""
        logger = StructuredLogger("test.module")

        with caplog.at_level(logging.INFO):
            logger.info("Test message", user_id="123", action="query")

        # 验证日志被记录
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert hasattr(record, 'extra_fields')
        assert record.extra_fields["user_id"] == "123"

    def test_get_logger_caches_instances(self):
        """测试 get_logger 缓存实例"""
        logger1 = get_logger("test.module")
        logger2 = get_logger("test.module")

        assert logger1 is logger2

        # 不同名称返回不同实例
        logger3 = get_logger("test.other")
        assert logger1 is not logger3


class TestConfigureLogging:
    """配置全局日志测试"""

    def test_configure_logging_adds_structured_handler(self):
        """测试配置添加结构化 handler"""
        root_logger = logging.getLogger()

        # 清除现有 handlers
        root_logger.handlers.clear()

        configure_logging()

        # 验证添加了结构化 handler
        assert len(root_logger.handlers) == 1
        assert isinstance(root_logger.handlers[0].formatter, StructuredFormatter)
