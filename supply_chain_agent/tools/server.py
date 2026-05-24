"""
MCP Server for Supply Chain Agent tools.

This module implements the MCP server with database-backed enterprise APIs.
All tools are read-only and follow the design specification in:
/root/Supply-Chain-Agent/docs/MCP Server Design.md

Core Principles:
- 数据真实: All data from MySQL database, no mock/simulated data
- 边界清晰: Single responsibility per tool, no overlap
- 输出标准化: Structured JSON output, consistent field naming
- 计算透明: Deterministic business rules, explainable logic
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from fastmcp import FastMCP

# Import database module
from supply_chain_agent.data.supply_chain_db import (
    get_order_by_id,
    get_order_items,
    get_shipping_info,
    get_customer_by_id,
    get_product_by_id,
    get_orders_by_customer,
    get_customer_order_count,
    get_customer_statistics,
    create_work_order as _create_work_order_db,
    approve_work_order as _approve_work_order_db,
    get_work_order,
    report_issue as _report_issue_db,
    VALID_WORK_TYPES,
    VALID_PRIORITIES,
    VALID_ISSUE_TYPES,
    VALID_URGENCIES,
)


@dataclass
class MCPError:
    """Standard MCP error response."""
    code: int
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message
            }
        }


# MCP Error Codes
ERROR_NOT_FOUND = 404
ERROR_BAD_GATEWAY = 502
ERROR_UNPROCESSABLE_ENTITY = 422
ERROR_INTERNAL = 500
ERROR_CONFLICT = 409
ERROR_FORBIDDEN = 403


class MCPServer:
    """MCP Server for supply chain tools following design specification."""

    def __init__(self):
        self.mcp = FastMCP("supply_chain_tools")
        self._setup_tools()

    def _setup_tools(self):
        """Setup all MCP tools according to design specification."""

        # ==========================================
        # 4.1 query_customer
        # ==========================================
        @self.mcp.tool()
        def query_customer(customer_id: int) -> Dict[str, Any]:
            """
            根据客户ID查询客户基本信息。

            Args:
                customer_id: 客户唯一标识 (整数)

            Returns:
                客户基本信息，包括姓名、邮箱、地区等
            """
            try:
                customer = get_customer_by_id(customer_id)
                if not customer:
                    return MCPError(
                        code=ERROR_NOT_FOUND,
                        message=f"客户 {customer_id} 不存在"
                    ).to_dict()

                # Mask email for privacy
                email = customer.get("Customer_Email", "")
                if email and "@" in email:
                    parts = email.split("@")
                    masked_email = f"{parts[0][0]}***@{parts[1]}"
                else:
                    masked_email = "***@example.com"

                return {
                    "customer_id": customer.get("Customer_Id"),
                    "first_name": customer.get("Customer_Fname"),
                    "last_name": customer.get("Customer_Lname"),
                    "email": masked_email,
                    "segment": customer.get("Customer_Segment"),
                    "city": customer.get("Customer_City"),
                    "state": customer.get("Customer_State"),
                    "zipcode": customer.get("Customer_Zipcode"),
                    "country": customer.get("Customer_Country"),
                    "latitude": customer.get("Latitude"),
                    "longitude": customer.get("Longitude")
                }
            except Exception as e:
                return MCPError(
                    code=ERROR_INTERNAL,
                    message=f"查询客户失败: {str(e)}"
                ).to_dict()

        # ==========================================
        # 4.2 query_customer_orders
        # ==========================================
        @self.mcp.tool()
        def query_customer_orders(
            customer_id: int,
            limit: int = 20,
            offset: int = 0
        ) -> Dict[str, Any]:
            """
            查询某客户的所有订单概要，支持分页。

            Args:
                customer_id: 客户唯一标识
                limit: 返回数量限制 (1-100, 默认20)
                offset: 分页偏移量 (默认0)

            Returns:
                订单列表概要，按order_date降序排列
            """
            try:
                # Validate parameters
                if limit < 1 or limit > 100:
                    return MCPError(
                        code=ERROR_UNPROCESSABLE_ENTITY,
                        message="limit必须在1-100之间"
                    ).to_dict()
                if offset < 0:
                    return MCPError(
                        code=ERROR_UNPROCESSABLE_ENTITY,
                        message="offset不能为负数"
                    ).to_dict()

                # Check customer exists
                customer = get_customer_by_id(customer_id)
                if not customer:
                    return MCPError(
                        code=ERROR_NOT_FOUND,
                        message=f"客户 {customer_id} 不存在"
                    ).to_dict()

                # Get orders
                orders = get_orders_by_customer(customer_id, limit=limit, offset=offset)
                total_count = get_customer_order_count(customer_id)

                return {
                    "customer_id": customer_id,
                    "total_orders": total_count,
                    "orders": [
                        {
                            "order_id": order.get("order_id"),
                            "order_date": order.get("order_date"),
                            "order_status": order.get("order_status"),
                            "delivery_status": order.get("delivery_status"),
                            "benefit_per_order": order.get("benefit_per_order"),
                            "market": order.get("market")
                        }
                        for order in orders
                    ]
                }
            except Exception as e:
                return MCPError(
                    code=ERROR_INTERNAL,
                    message=f"查询客户订单失败: {str(e)}"
                ).to_dict()

        # ==========================================
        # 4.3 query_order
        # ==========================================
        @self.mcp.tool()
        def query_order(order_id: int) -> Dict[str, Any]:
            """
            根据订单ID查询订单头详细信息。

            Args:
                order_id: 订单唯一标识 (整数)

            Returns:
                订单详细信息，包括状态、金额、地区等
            """
            try:
                order = get_order_by_id(order_id)
                if not order:
                    return MCPError(
                        code=ERROR_NOT_FOUND,
                        message=f"订单 {order_id} 不存在"
                    ).to_dict()

                return {
                    "order_id": order.get("order_id"),
                    "customer_id": order.get("customer_id"),
                    "order_date": order.get("order_date"),
                    "order_status": order.get("order_status"),
                    "delivery_status": order.get("delivery_status"),
                    "market": order.get("market"),
                    "order_region": order.get("order_region"),
                    "order_city": order.get("order_city"),
                    "order_state": order.get("order_state"),
                    "order_country": order.get("order_country"),
                    "type": order.get("type"),
                    "sales_per_customer": order.get("sales_per_customer"),
                    "benefit_per_order": order.get("benefit_per_order"),
                    "order_profit_per_order": order.get("order_profit_per_order")
                }
            except Exception as e:
                return MCPError(
                    code=ERROR_INTERNAL,
                    message=f"查询订单失败: {str(e)}"
                ).to_dict()

        # ==========================================
        # 4.4 query_order_items
        # ==========================================
        @self.mcp.tool()
        def query_order_items(order_id: int) -> Dict[str, Any]:
            """
            查询指定订单的所有明细行。

            Args:
                order_id: 订单唯一标识 (整数)

            Returns:
                订单明细行列表，包含产品、数量、价格等
            """
            try:
                # Check order exists
                order = get_order_by_id(order_id)
                if not order:
                    return MCPError(
                        code=ERROR_NOT_FOUND,
                        message=f"订单 {order_id} 不存在"
                    ).to_dict()

                items = get_order_items(order_id)

                return {
                    "order_id": order_id,
                    "items": [
                        {
                            "order_item_id": item.get("order_item_id"),
                            "product_card_id": item.get("product_card_id"),
                            "quantity": item.get("order_item_quantity"),
                            "product_price": item.get("order_item_product_price"),
                            "discount": item.get("order_item_discount"),
                            "discount_rate": item.get("order_item_discount_rate"),
                            "order_item_total": item.get("order_item_total"),
                            "profit_ratio": item.get("order_item_profit_ratio"),
                            "sales": item.get("sales")
                        }
                        for item in items
                    ]
                }
            except Exception as e:
                return MCPError(
                    code=ERROR_INTERNAL,
                    message=f"查询订单明细失败: {str(e)}"
                ).to_dict()

        # ==========================================
        # 4.5 query_product
        # ==========================================
        @self.mcp.tool()
        def query_product(product_card_id: int) -> Dict[str, Any]:
            """
            根据产品卡片ID查询产品详情。

            Args:
                product_card_id: 产品卡片唯一标识 (整数)

            Returns:
                产品详情，包括名称、分类、价格等
            """
            try:
                product = get_product_by_id(product_card_id)
                if not product:
                    return MCPError(
                        code=ERROR_NOT_FOUND,
                        message=f"产品 {product_card_id} 不存在"
                    ).to_dict()

                return {
                    "product_card_id": int(product.get("Product_Card_Id", 0)),
                    "product_category_id": int(product.get("Product_Category_Id", 0)) if product.get("Product_Category_Id") else None,
                    "category_name": product.get("Category_Name"),
                    "product_name": product.get("Product_Name"),
                    "product_description": product.get("Product_Description", ""),
                    "price": float(product.get("Product_Price", 0)) if product.get("Product_Price") else None,
                    "product_status": int(product.get("Product_Status", 0)) if product.get("Product_Status") else None,
                    "department_id": None,  # Not directly available
                    "department_name": product.get("Department_Name")
                }
            except Exception as e:
                return MCPError(
                    code=ERROR_INTERNAL,
                    message=f"查询产品失败: {str(e)}"
                ).to_dict()

        # ==========================================
        # 4.6 query_shipment
        # ==========================================
        @self.mcp.tool()
        def query_shipment(order_id: int) -> Dict[str, Any]:
            """
            查询订单的物流基本信息，并根据已有字段生成确定性的状态描述。

            Args:
                order_id: 订单唯一标识 (整数)

            Returns:
                物流信息及状态描述
            """
            try:
                # Check order exists
                order = get_order_by_id(order_id)
                if not order:
                    return MCPError(
                        code=ERROR_NOT_FOUND,
                        message=f"订单 {order_id} 不存在"
                    ).to_dict()

                shipping = get_shipping_info(order_id)

                if not shipping:
                    return {
                        "order_id": order_id,
                        "shipping_mode": None,
                        "shipping_date": None,
                        "days_for_shipping_real": None,
                        "days_for_shipment_scheduled": None,
                        "late_delivery_risk": None,
                        "status_description": "无物流信息。"
                    }

                # Generate status description based on deterministic rules
                status_description = self._generate_shipment_status(
                    shipping, order
                )

                return {
                    "order_id": order_id,
                    "shipping_mode": shipping.get("shipping_mode"),
                    "shipping_date": shipping.get("shipping_date"),
                    "days_for_shipping_real": shipping.get("days_for_shipping_real"),
                    "days_for_shipment_scheduled": shipping.get("days_for_shipment_scheduled"),
                    "late_delivery_risk": order.get("late_delivery_risk"),
                    "status_description": status_description
                }
            except Exception as e:
                return MCPError(
                    code=ERROR_INTERNAL,
                    message=f"查询物流失败: {str(e)}"
                ).to_dict()

        # ==========================================
        # 4.7 query_customer_statistics
        # ==========================================
        @self.mcp.tool()
        def query_customer_statistics(customer_id: int) -> Dict[str, Any]:
            """
            为客户风险评估和审批决策提供聚合统计指标。

            Args:
                customer_id: 客户唯一标识 (整数)

            Returns:
                统计指标，包括交易行为、履约占用等
            """
            try:
                # Check customer exists
                customer = get_customer_by_id(customer_id)
                if not customer:
                    return MCPError(
                        code=ERROR_NOT_FOUND,
                        message=f"客户 {customer_id} 不存在"
                    ).to_dict()

                # Get statistics from database
                stats = get_customer_statistics(customer_id)

                return {
                    "customer_id": customer_id,
                    "total_sales": stats.get("total_sales", 0),
                    "total_orders": stats.get("total_orders", 0),
                    "delayed_orders": stats.get("delayed_orders", 0),
                    "cancelled_orders": stats.get("cancelled_orders", 0),
                    "avg_order_profit": stats.get("avg_order_profit", 0),
                    "late_delivery_rate": stats.get("late_delivery_rate", 0),
                    "current_occupied_amount": stats.get("current_occupied_amount", 0),
                    "current_pending_orders": stats.get("current_pending_orders", 0)
                }
            except Exception as e:
                return MCPError(
                    code=ERROR_INTERNAL,
                    message=f"查询客户统计失败: {str(e)}"
                ).to_dict()

        # ==========================================
        # 4.8 create_work_order
        # ==========================================
        @self.mcp.tool()
        def create_work_order(
            work_type: str,
            description: str,
            priority: str = "中",
            order_id: str = None,
            assigned_to: str = None
        ) -> Dict[str, Any]:
            """
            创建新工单，用于记录需要人工介入或系统处理的业务事项。

            Args:
                work_type: 工单类型 (审批/异常处理/退款/调拨/质检/其他)
                description: 工单描述，详细说明需要处理的事项
                priority: 优先级 (高/中/低)，默认中
                order_id: 关联订单ID（可选）
                assigned_to: 分配给谁处理（可选，不指定则由系统自动分配）

            Returns:
                创建的工单信息，包括工单ID、状态、时间线等
            """
            try:
                # Validate work_type
                if work_type not in VALID_WORK_TYPES:
                    return MCPError(
                        code=ERROR_UNPROCESSABLE_ENTITY,
                        message=f"无效的工单类型: {work_type}，有效类型: {VALID_WORK_TYPES}"
                    ).to_dict()

                # Validate priority
                if priority not in VALID_PRIORITIES:
                    return MCPError(
                        code=ERROR_UNPROCESSABLE_ENTITY,
                        message=f"无效的优先级: {priority}，有效优先级: {VALID_PRIORITIES}"
                    ).to_dict()

                # Validate order_id if provided
                if order_id:
                    try:
                        order = get_order_by_id(int(order_id))
                        if not order:
                            return MCPError(
                                code=ERROR_NOT_FOUND,
                                message=f"关联订单 {order_id} 不存在"
                            ).to_dict()
                    except ValueError:
                        return MCPError(
                            code=ERROR_UNPROCESSABLE_ENTITY,
                            message=f"无效的订单ID格式: {order_id}"
                        ).to_dict()

                # Create work order
                work_order = _create_work_order_db(
                    work_type=work_type,
                    description=description,
                    priority=priority,
                    order_id=order_id,
                    assigned_to=assigned_to
                )

                return {
                    "success": True,
                    "work_order": work_order
                }

            except Exception as e:
                return MCPError(
                    code=ERROR_INTERNAL,
                    message=f"创建工单失败: {str(e)}"
                ).to_dict()

        # ==========================================
        # 4.9 approve_work_order
        # ==========================================
        @self.mcp.tool()
        def approve_work_order(
            work_order_id: str,
            action: str,
            comment: str = "",
            approver: str = "Agent System"
        ) -> Dict[str, Any]:
            """
            审批工单，更新工单状态并记录审批意见。

            Args:
                work_order_id: 工单唯一标识
                action: 审批动作 (approve/reject/escalate)
                comment: 审批意见/备注
                approver: 审批人标识（可选，默认为Agent System）

            Returns:
                更新后的工单信息，包括新状态和时间线
            """
            try:
                # Validate action
                valid_actions = ["approve", "reject", "escalate"]
                if action not in valid_actions:
                    return MCPError(
                        code=ERROR_UNPROCESSABLE_ENTITY,
                        message=f"无效的审批动作: {action}，有效动作: {valid_actions}"
                    ).to_dict()

                # Check work order exists
                work_order = get_work_order(work_order_id)
                if not work_order:
                    return MCPError(
                        code=ERROR_NOT_FOUND,
                        message=f"工单 {work_order_id} 不存在"
                    ).to_dict()

                # Check if status allows approval
                current_status = work_order.get("status")
                if current_status not in ["待处理", "待审批"]:
                    return MCPError(
                        code=ERROR_CONFLICT,
                        message=f"工单状态 '{current_status}' 不允许审批操作，仅 '待处理' 或 '待审批' 状态可审批"
                    ).to_dict()

                # Execute approval
                updated_work_order = _approve_work_order_db(
                    work_order_id=work_order_id,
                    action=action,
                    comment=comment,
                    approver=approver
                )

                return {
                    "success": True,
                    "work_order": updated_work_order
                }

            except ValueError as e:
                return MCPError(
                    code=ERROR_UNPROCESSABLE_ENTITY,
                    message=str(e)
                ).to_dict()
            except Exception as e:
                return MCPError(
                    code=ERROR_INTERNAL,
                    message=f"审批工单失败: {str(e)}"
                ).to_dict()

        # ==========================================
        # 4.10 report_issue
        # ==========================================
        @self.mcp.tool()
        def report_issue(
            issue_type: str,
            description: str,
            urgency: str = "中",
            affected_order: str = None,
            reported_by: str = "Agent System"
        ) -> Dict[str, Any]:
            """
            上报问题/异常，用于记录供应链过程中发现的各类问题。

            Args:
                issue_type: 问题类型 (物流延迟/库存异常/质量缺陷/数据错误/客户投诉/其他)
                description: 问题描述，详细说明问题详情
                urgency: 紧急程度 (高/中/低)，默认中
                affected_order: 受影响订单ID（可选）
                reported_by: 报告人标识（可选，默认为Agent System）

            Returns:
                创建的问题报告信息，包括问题ID、状态、分配等
            """
            try:
                # Validate issue_type
                if issue_type not in VALID_ISSUE_TYPES:
                    return MCPError(
                        code=ERROR_UNPROCESSABLE_ENTITY,
                        message=f"无效的问题类型: {issue_type}，有效类型: {VALID_ISSUE_TYPES}"
                    ).to_dict()

                # Validate urgency
                if urgency not in VALID_URGENCIES:
                    return MCPError(
                        code=ERROR_UNPROCESSABLE_ENTITY,
                        message=f"无效的紧急程度: {urgency}，有效紧急程度: {VALID_URGENCIES}"
                    ).to_dict()

                # Validate affected_order if provided
                if affected_order:
                    try:
                        order = get_order_by_id(int(affected_order))
                        if not order:
                            return MCPError(
                                code=ERROR_NOT_FOUND,
                                message=f"受影响订单 {affected_order} 不存在"
                            ).to_dict()
                    except ValueError:
                        return MCPError(
                            code=ERROR_UNPROCESSABLE_ENTITY,
                            message=f"无效的订单ID格式: {affected_order}"
                        ).to_dict()

                # Create issue report
                issue = _report_issue_db(
                    issue_type=issue_type,
                    description=description,
                    urgency=urgency,
                    affected_order=affected_order,
                    reported_by=reported_by
                )

                return {
                    "success": True,
                    "issue": issue
                }

            except Exception as e:
                return MCPError(
                    code=ERROR_INTERNAL,
                    message=f"上报问题失败: {str(e)}"
                ).to_dict()

    def _generate_shipment_status(
        self,
        shipping: Dict[str, Any],
        order: Dict[str, Any]
    ) -> str:
        """
        Generate shipment status description based on deterministic rules.

        Rules from design document:
        - If shipping_date is NULL: "尚未发货。"
        - If late_delivery_risk=1 or delivery_status='Late delivery':
          "已于{shipping_date}发货，实际运输{real}天（计划{scheduled}天），存在延迟。"
        - Otherwise: "已于{shipping_date}发货，实际运输{real}天，无延迟风险。"
        - If delivery_status='Shipping canceled': append " 该订单物流已取消。"
        """
        shipping_date = shipping.get("shipping_date")
        delivery_status = order.get("delivery_status", "")
        late_delivery_risk = order.get("late_delivery_risk", 0)

        # Not shipped yet
        if not shipping_date:
            return "尚未发货。"

        days_real = shipping.get("days_for_shipping_real", 0)
        days_scheduled = shipping.get("days_for_shipment_scheduled", 0)

        # Generate description
        if late_delivery_risk == 1 or delivery_status == "Late delivery":
            description = f"已于{shipping_date}发货，实际运输{days_real}天（计划{days_scheduled}天），存在延迟。"
        else:
            description = f"已于{shipping_date}发货，实际运输{days_real}天，无延迟风险。"

        # Check for cancellation
        if delivery_status == "Shipping canceled":
            description += " 该订单物流已取消。"

        return description

    def run_server(self, port: int = 8001):
        """Run the MCP server (synchronous)."""
        print(f"Starting MCP server on port {port}...")
        print("Available tools:")
        print("--- Read-Only Query Tools ---")
        print("- query_customer: 根据客户ID查询客户基本信息")
        print("- query_customer_orders: 查询某客户的订单列表（分页）")
        print("- query_order: 根据订单ID查询订单头详细信息")
        print("- query_order_items: 根据订单ID查询订单行项目明细")
        print("- query_product: 根据产品卡片ID查询产品信息")
        print("- query_shipment: 根据订单ID查询物流基本信息及状态描述")
        print("- query_customer_statistics: 获取客户的风险评估统计指标及当前履约占用")
        print("--- Write Operation Tools ---")
        print("- create_work_order: 创建新工单")
        print("- approve_work_order: 审批工单")
        print("- report_issue: 上报问题/异常")

        # FastMCP.run() is synchronous
        self.mcp.run(transport="http", port=port)


def run_mcp_server(port: int = 8001):
    """Run the MCP server (synchronous wrapper for compatibility)."""
    server = MCPServer()
    server.run_server(port)


# For backward compatibility, keep async wrapper
async def run_mcp_server_async(port: int = 8001):
    """Async wrapper for running MCP server in async context."""
    import asyncio
    server = MCPServer()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: server.run_server(port))
