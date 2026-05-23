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
