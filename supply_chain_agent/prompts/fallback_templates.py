"""
Fallback Response Templates - Loaded from database.

This module provides fallback response templates loaded from
/root/Supply-Chain-Agent/dataset/OtherData/FallbackResponseTemplate.csv
"""

from typing import Dict, Any, Optional
from supply_chain_agent.data.supply_chain_db import (
    get_fallback_template,
    render_fallback_template
)


# Error code constants for easy reference
class ErrorCodes:
    """Error code constants for fallback templates."""
    QUERY_ORDER_TIMEOUT = "QUERY_ORDER_TIMEOUT"
    QUERY_ORDER_NOT_FOUND = "QUERY_ORDER_NOT_FOUND"
    QUERY_ORDER_ITEMS_TIMEOUT = "QUERY_ORDER_ITEMS_TIMEOUT"
    QUERY_CUSTOMER_TIMEOUT = "QUERY_CUSTOMER_TIMEOUT"
    QUERY_CUSTOMER_NOT_FOUND = "QUERY_CUSTOMER_NOT_FOUND"
    QUERY_PRODUCT_TIMEOUT = "QUERY_PRODUCT_TIMEOUT"
    QUERY_PRODUCT_NOT_FOUND = "QUERY_PRODUCT_NOT_FOUND"
    QUERY_SHIPMENT_TIMEOUT = "QUERY_SHIPMENT_TIMEOUT"
    QUERY_SHIPMENT_NOT_FOUND = "QUERY_SHIPMENT_NOT_FOUND"
    LOGISTICS_TRACE_FAILED = "LOGISTICS_TRACE_FAILED"
    MCP_SERVER_UNREACHABLE = "MCP_SERVER_UNREACHABLE"
    DATABASE_CONNECTION_FAILED = "DATABASE_CONNECTION_FAILED"
    RAG_KNOWLEDGE_RETRIEVAL_FAILED = "RAG_KNOWLEDGE_RETRIEVAL_FAILED"
    INTENT_CLASSIFICATION_LOW_CONFIDENCE = "INTENT_CLASSIFICATION_LOW_CONFIDENCE"
    ENTITY_EXTRACTION_INCOMPLETE = "ENTITY_EXTRACTION_INCOMPLETE"
    SLOT_FILLING_FAILED = "SLOT_FILLING_FAILED"
    WORKFLOW_EXECUTION_FAILED = "WORKFLOW_EXECUTION_FAILED"
    APPROVAL_RISK_EXCEEDS_LIMIT = "APPROVAL_RISK_EXCEEDS_LIMIT"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"
    TOOL_CALL_MAX_RETRIES_EXCEEDED = "TOOL_CALL_MAX_RETRIES_EXCEEDED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    CONTEXT_LENGTH_EXCEEDED = "CONTEXT_LENGTH_EXCEEDED"
    GENERAL_FALLBACK = "GENERAL_FALLBACK"


def determine_error_code(
    error_detail: str,
    tool_name: str = None,
    error_count: int = 0,
    validation_errors: list = None,
    max_clarification_reached: bool = False
) -> str:
    """
    统一的错误代码确定函数（解决M19重复定义问题）。

    Args:
        error_detail: 错误详情字符串
        tool_name: 工具名称（可选）
        error_count: 错误计数
        validation_errors: 验证错误列表
        max_clarification_reached: 是否达到最大澄清循环次数

    Returns:
        错误编码
    """
    error_detail_lower = error_detail.lower() if error_detail else ""
    validation_errors = validation_errors or []

    # 1. 检查是否达到最大澄清循环次数
    if max_clarification_reached:
        return ErrorCodes.ENTITY_EXTRACTION_INCOMPLETE

    # 2. 检查是否有验证错误
    if validation_errors:
        validation_error_str = " ".join(validation_errors).lower()
        if "parser" in validation_error_str:
            return ErrorCodes.INTENT_CLASSIFICATION_LOW_CONFIDENCE
        if "entity" in validation_error_str or "实体" in validation_error_str:
            return ErrorCodes.ENTITY_EXTRACTION_INCOMPLETE
        if "slot" in validation_error_str or "槽位" in validation_error_str:
            return ErrorCodes.SLOT_FILLING_FAILED
        if "planning" in validation_error_str or "task" in validation_error_str:
            return ErrorCodes.WORKFLOW_EXECUTION_FAILED

    # 3. 检查错误计数
    if error_count >= 3:
        return ErrorCodes.TOOL_CALL_MAX_RETRIES_EXCEEDED

    # 4. 根据错误详情判断
    if error_detail:
        # 数据库连接错误
        if "database" in error_detail_lower or "数据库" in error_detail:
            return ErrorCodes.DATABASE_CONNECTION_FAILED
        # MCP 服务不可达
        if "mcp" in error_detail_lower or "service" in error_detail_lower or "服务" in error_detail:
            return ErrorCodes.MCP_SERVER_UNREACHABLE
        # 熔断
        if "circuit" in error_detail_lower or "熔断" in error_detail:
            return ErrorCodes.CIRCUIT_BREAKER_OPEN
        # 会话过期
        if "session" in error_detail_lower or "会话" in error_detail:
            return ErrorCodes.SESSION_EXPIRED
        # 上下文超限
        if "context" in error_detail_lower or "上下文" in error_detail:
            return ErrorCodes.CONTEXT_LENGTH_EXCEEDED

    # 5. 工具特定错误判断
    if tool_name:
        # 订单相关错误
        if tool_name in ["query_order", "query_order_items"]:
            if "not found" in error_detail_lower or "不存在" in error_detail:
                return ErrorCodes.QUERY_ORDER_NOT_FOUND
            if "timeout" in error_detail_lower or "超时" in error_detail:
                return ErrorCodes.QUERY_ORDER_TIMEOUT

        # 客户相关错误
        elif tool_name == "query_customer":
            if "not found" in error_detail_lower or "不存在" in error_detail:
                return ErrorCodes.QUERY_CUSTOMER_NOT_FOUND
            if "timeout" in error_detail_lower or "超时" in error_detail:
                return ErrorCodes.QUERY_CUSTOMER_TIMEOUT

        # 产品相关错误
        elif tool_name == "query_product":
            if "not found" in error_detail_lower or "不存在" in error_detail:
                return ErrorCodes.QUERY_PRODUCT_NOT_FOUND
            if "timeout" in error_detail_lower or "超时" in error_detail:
                return ErrorCodes.QUERY_PRODUCT_TIMEOUT

        # 物流/运输相关错误
        elif tool_name in ["query_shipment", "query_logistics"]:
            if "not found" in error_detail_lower or "不存在" in error_detail:
                return ErrorCodes.QUERY_SHIPMENT_NOT_FOUND
            if "timeout" in error_detail_lower or "超时" in error_detail:
                return ErrorCodes.QUERY_SHIPMENT_TIMEOUT
            if "trace" in error_detail_lower or "轨迹" in error_detail:
                return ErrorCodes.LOGISTICS_TRACE_FAILED

    # 默认返回工作流执行失败
    return ErrorCodes.WORKFLOW_EXECUTION_FAILED


def get_fallback_response(error_code: str, **kwargs) -> Dict[str, Any]:
    """
    Get fallback response for an error code.

    Args:
        error_code: Error code from ErrorCodes
        **kwargs: Variables to substitute in the template

    Returns:
        Dict with template info and rendered message
    """
    template = get_fallback_template(error_code)

    if template:
        message = render_fallback_template(error_code, **kwargs)
        return {
            "error_code": error_code,
            "message": message,
            "severity": template.get("severity", "info"),
            "scenario": template.get("scenario", ""),
            "from_database": True
        }

    # Default fallback if template not found
    return {
        "error_code": error_code,
        "message": f"系统暂时无法处理您的请求（错误代码: {error_code}）。请稍后重试或联系技术支持。",
        "severity": "warning",
        "scenario": "未知错误",
        "from_database": False
    }


def get_order_not_found_response(order_id: str) -> str:
    """Get response for order not found."""
    result = get_fallback_response(ErrorCodes.QUERY_ORDER_NOT_FOUND, order_id=order_id)
    return result["message"]


def get_logistics_timeout_response(tracking_no: str) -> str:
    """Get response for logistics query timeout."""
    result = get_fallback_response(ErrorCodes.LOGISTICS_TRACE_FAILED, tracking_no=tracking_no)
    return result["message"]


def get_database_unavailable_response() -> str:
    """Get response when database is unavailable."""
    result = get_fallback_response(ErrorCodes.DATABASE_CONNECTION_FAILED)
    return result["message"]


def get_intent_clarification_response() -> str:
    """Get response when intent classification has low confidence."""
    result = get_fallback_response(ErrorCodes.INTENT_CLASSIFICATION_LOW_CONFIDENCE)
    return result["message"]


def get_entity_incomplete_response(missing_entities: list) -> str:
    """Get response when entity extraction is incomplete."""
    missing_str = "、".join(missing_entities)
    result = get_fallback_response(
        ErrorCodes.ENTITY_EXTRACTION_INCOMPLETE,
        missing_slots=missing_str
    )
    return result["message"]


def get_circuit_breaker_response(service_name: str, recovery_time: int) -> str:
    """Get response when circuit breaker is open."""
    result = get_fallback_response(
        ErrorCodes.CIRCUIT_BREAKER_OPEN,
        service_name=service_name,
        recovery_time=str(recovery_time)
    )
    return result["message"]


def get_max_retries_exceeded_response(query_target: str, max_retries: int) -> str:
    """Get response when max retries exceeded."""
    result = get_fallback_response(
        ErrorCodes.TOOL_CALL_MAX_RETRIES_EXCEEDED,
        query_target=query_target,
        max_retries=str(max_retries)
    )
    return result["message"]
