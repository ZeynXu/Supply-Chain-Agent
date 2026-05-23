"""
MCP Tools module for Supply Chain Agent.

This module provides MCP server and client implementations following the
MCP Server Design specification.

Read-Only Query Tools:
- query_customer: 根据客户ID查询客户基本信息
- query_customer_orders: 查询某客户的订单列表（分页）
- query_order: 根据订单ID查询订单头详细信息
- query_order_items: 根据订单ID查询订单行项目明细
- query_product: 根据产品卡片ID查询产品信息
- query_shipment: 根据订单ID查询物流基本信息及状态描述
- query_customer_statistics: 获取客户的风险评估统计指标及当前履约占用

Write Operation Tools:
- create_work_order: 创建新工单（写入操作）
- approve_work_order: 审批工单（写入操作）
- report_issue: 上报问题/异常（写入操作）
"""

from supply_chain_agent.tools.server import MCPServer, run_mcp_server
from supply_chain_agent.tools.client import ToolClient, get_tool_client, close_tool_client

__all__ = [
    "MCPServer",
    "run_mcp_server",
    "ToolClient",
    "get_tool_client",
    "close_tool_client",
]
