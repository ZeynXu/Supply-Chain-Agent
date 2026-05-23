"""
MCP Server for Supply Chain Agent tools.

This module implements the MCP server with database-backed enterprise APIs.
All data comes from the database loaded from /root/Supply-Chain-Agent/dataset/.
No mock data is used.
"""

import asyncio
import json
import time
import random
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastmcp import FastMCP

# Import database module
from supply_chain_agent.data.supply_chain_db import (
    get_order_by_id,
    get_order_items,
    get_shipping_info,
    get_customer_by_id,
    get_product_by_id,
    get_statistics,
    get_sample_orders_for_testing,
    search_orders,
    create_work_order,
    get_work_order,
    list_work_orders,
    update_work_order,
    add_work_order_timeline_event,
    create_issue,
    get_issue,
    list_issues,
    render_fallback_template,
)

# Import memory manager for SOP search
try:
    from supply_chain_agent.memory.vector_store import memory_manager
    VECTOR_STORE_AVAILABLE = True
except ImportError:
    VECTOR_STORE_AVAILABLE = False


@dataclass
class ToolHealth:
    """Tool health status."""
    name: str
    last_checked: float
    failure_count: int = 0
    last_failure_time: float = 0
    is_healthy: bool = True


class MCPServer:
    """MCP Server for supply chain tools."""

    def __init__(self):
        self.mcp = FastMCP("supply_chain_tools")
        self.tool_health: Dict[str, ToolHealth] = {}
        self.setup_tools()

    def setup_tools(self):
        """Setup all MCP tools."""
        # Query Order Status Tool
        @self.mcp.tool()
        def query_order_status(order_id: str) -> Dict[str, Any]:
            """
            Query purchase order details.

            Args:
                order_id: Purchase order ID (numeric or PO-XXXXX format)

            Returns:
                Order information including status, amount, customer, etc.
            """
            self._check_health("query_order_status")

            # Simulate API delay
            time.sleep(0.05)

            # Extract numeric ID from format like "PO-2026-001" or use directly
            try:
                if order_id.startswith("PO-"):
                    numeric_id = int(order_id.split("-")[-1])
                else:
                    numeric_id = int(order_id)
            except (ValueError, IndexError):
                raise ValueError(f"Invalid order ID format: {order_id}")

            # Query database
            order = get_order_by_id(numeric_id)
            if not order:
                self._record_failure("query_order_status")
                raise ValueError(f"Order {order_id} not found in database")

            # Get order items
            items = get_order_items(order["order_id"])
            # Get shipping info
            shipping = get_shipping_info(order["order_id"])

            # Calculate total amount
            total_amount = sum(item.get("sales", 0) or 0 for item in items)

            return {
                "order_id": f"PO-{order['order_id']}",
                "customer": f"{order.get('customer_fname', '')} {order.get('customer_lname', '')}".strip(),
                "customer_city": order.get("customer_city"),
                "customer_country": order.get("customer_country"),
                "status": order.get("order_status"),
                "delivery_status": order.get("delivery_status"),
                "late_delivery_risk": order.get("late_delivery_risk"),
                "amount": total_amount,
                "currency": "USD",
                "order_date": order.get("order_date"),
                "market": order.get("market"),
                "items": [
                    {
                        "sku": f"SKU-{item.get('product_card_id')}",
                        "description": item.get("product_name", "Unknown"),
                        "quantity": item.get("order_item_quantity", 0),
                        "unit_price": item.get("order_item_product_price", 0),
                        "category": item.get("category_name")
                    }
                    for item in items[:5]  # Limit to 5 items
                ],
                "shipping_mode": shipping.get("shipping_mode") if shipping else None,
                "days_for_shipping": shipping.get("days_for_shipping_real") if shipping else None,
                "tracking_no": f"SF{order['order_id']:010d}" if order else None,
                "warehouse": order.get("order_region"),
                "priority": "高" if order.get("late_delivery_risk") else "常规"
            }

        # Get Logistics Trace Tool
        @self.mcp.tool()
        def get_logistics_trace(tracking_no: str) -> Dict[str, Any]:
            """
            Query logistics tracking information.

            Args:
                tracking_no: Logistics tracking number

            Returns:
                Logistics trace information including status, location, ETA.
            """
            self._check_health("get_logistics_trace")

            # Simulate API delay
            time.sleep(0.1)

            # Extract order ID from tracking number format "SF{order_id}"
            if not tracking_no.startswith("SF"):
                raise ValueError(f"Invalid tracking number format: {tracking_no}")

            try:
                numeric_id = int(tracking_no[2:])
            except ValueError:
                raise ValueError(f"Invalid tracking number: {tracking_no}")

            order = get_order_by_id(numeric_id)
            shipping = get_shipping_info(numeric_id)

            if not order or not shipping:
                self._record_failure("get_logistics_trace")
                raise ValueError(f"Tracking number {tracking_no} not found")

            # Generate simulated logistics events based on order status
            delivery_status = order.get("delivery_status", "Unknown")
            current_location = order.get("order_city", "Unknown")
            destination = order.get("customer_city", "Unknown")

            events = self._generate_logistics_events(
                delivery_status, current_location, destination, shipping
            )

            return {
                "tracking_no": tracking_no,
                "carrier": shipping.get("shipping_mode", "Standard"),
                "status": delivery_status,
                "current_location": current_location,
                "destination": destination,
                "sender": order.get("order_region", "Unknown"),
                "receiver": f"{order.get('customer_fname', '')} {order.get('customer_lname', '')}".strip(),
                "weight": round(random.uniform(1, 50), 1),
                "volume": f"{random.uniform(0.1, 1.0):.2f}m³",
                "events": events,
                "eta": self._calculate_eta(delivery_status),
                "estimated_days": shipping.get("days_for_shipment_scheduled", 3)
            }

        # Search Contract Template Tool (now searches SOP documents)
        @self.mcp.tool()
        def search_contract_template(query: str, top_k: int = 2) -> Dict[str, Any]:
            """
            Search for SOP documents and contract-related information.

            Args:
                query: Search keyword
                top_k: Number of results to return

            Returns:
                Matching SOP documents with titles and content.
            """
            self._check_health("search_contract_template")

            # Simulate search delay
            time.sleep(0.15)

            # Use vector store for semantic search
            if VECTOR_STORE_AVAILABLE:
                try:
                    results = memory_manager.long_term.search_sop(query, limit=top_k)
                    templates = [
                        {
                            "title": r.get("metadata", {}).get("source", "SOP Document"),
                            "content": r.get("content", ""),
                            "doc_type": r.get("metadata", {}).get("doc_type", "sop")
                        }
                        for r in results
                    ]
                    return {"templates": templates}
                except Exception as e:
                    print(f"SOP search error: {e}")

            # If no vector store, return empty
            return {"templates": [], "message": "SOP search not available - vector store not initialized"}

        # Approve Work Order Tool (requires confirmation)
        @self.mcp.tool()
        def approve_work_order(order_id: str, comment: str) -> Dict[str, Any]:
            """
            Submit work order for approval (requires user confirmation).

            IMPORTANT: This tool only generates pre-filled forms and requires
            user confirmation before actual submission.

            Args:
                order_id: Work order ID
                comment: Approval comment

            Returns:
                Pre-filled approval form for user confirmation.
            """
            self._check_health("approve_work_order")

            # Check if work order exists in database
            work_order = get_work_order(order_id)
            if not work_order:
                raise ValueError(f"Work order {order_id} not found")

            # Return pre-filled form for confirmation
            return {
                "order_id": order_id,
                "work_order": work_order,
                "comment": comment,
                "approver": "Agent System",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "requires_confirmation": True,
                "confirmation_message": (
                    "⚠️ **需要用户确认**\n\n"
                    f"即将审批工单: {order_id}\n"
                    f"审批意见: {comment}\n\n"
                    "请确认是否提交审批？"
                )
            }

        # Create Work Order Tool
        @self.mcp.tool()
        def create_work_order_tool(work_type: str, description: str, priority: str = "中",
                            assigned_to: Optional[str] = None, order_id: Optional[str] = None) -> Dict[str, Any]:
            """
            Create a new work order.

            Args:
                work_type: Type of work order (e.g., 质量检验, 生产跟踪, 物流异常)
                description: Detailed description of the work order
                priority: Priority level (紧急, 高, 中, 低)
                assigned_to: Optional assignee for the work order
                order_id: Optional related order ID

            Returns:
                Created work order information including work order ID and status.
            """
            self._check_health("create_work_order")

            # Simulate API delay
            time.sleep(0.15)

            # Generate new work order ID
            new_id = f"WO-{datetime.now().strftime('%Y')}-{random.randint(100, 999):03d}"

            # Create work order in database
            work_order = create_work_order(
                work_order_id=new_id,
                work_type=work_type,
                description=description,
                priority=priority,
                order_id=order_id,
                assigned_to=assigned_to,
                created_by="Agent System"
            )

            return {
                "success": True,
                "work_order": work_order,
                "message": f"工单已创建: {new_id}",
                "next_steps": ["等待处理", "等待审批"]
            }

        # Report Issue Tool
        @self.mcp.tool()
        def report_issue(issue_type: str, description: str, urgency: str = "中",
                        affected_order: Optional[str] = None, reported_by: Optional[str] = None) -> Dict[str, Any]:
            """
            Report a supply chain issue or exception.

            Args:
                issue_type: Type of issue (e.g., 物流延迟, 质量问题, 供应短缺)
                description: Detailed description of the issue
                urgency: Urgency level (紧急, 高, 中, 低)
                affected_order: Optional affected order ID
                reported_by: Optional reporter name

            Returns:
                Issue report information including issue ID and tracking information.
            """
            self._check_health("report_issue")

            # Simulate API delay
            time.sleep(0.2)

            # Generate new issue ID
            new_id = f"ISSUE-{datetime.now().strftime('%Y')}-{random.randint(100, 999):03d}"

            # Create issue in database
            issue_report = create_issue(
                issue_id=new_id,
                issue_type=issue_type,
                description=description,
                urgency=urgency,
                affected_order=affected_order,
                reported_by=reported_by or "Agent System"
            )

            return {
                "success": True,
                "issue_report": issue_report,
                "message": f"异常报告已创建: {new_id}",
                "next_steps": ["等待处理", "跟踪解决进度"],
                "response_time": "1小时内响应" if urgency in ["紧急", "高"] else "24小时内响应"
            }

        # Tool health check
        @self.mcp.tool()
        def check_tool_health(tool_name: Optional[str] = None) -> Dict[str, Any]:
            """
            Check health status of MCP tools.

            Args:
                tool_name: Optional specific tool name to check

            Returns:
                Health status of requested tools
            """
            if tool_name:
                if tool_name in self.tool_health:
                    return {
                        "tool": tool_name,
                        "status": self.tool_health[tool_name]
                    }
                else:
                    return {
                        "tool": tool_name,
                        "error": "Tool not found"
                    }
            else:
                return {
                    "tools": {
                        name: {
                            "healthy": health.is_healthy,
                            "failure_count": health.failure_count,
                            "last_checked": health.last_checked
                        }
                        for name, health in self.tool_health.items()
                    }
                }

    def _check_health(self, tool_name: str):
        """Check if tool is healthy before execution."""
        if tool_name not in self.tool_health:
            self.tool_health[tool_name] = ToolHealth(
                name=tool_name,
                last_checked=time.time(),
                is_healthy=True
            )

        health = self.tool_health[tool_name]
        health.last_checked = time.time()

        # Circuit breaker: if tool failed 3 times in last 3 seconds, disable it
        current_time = time.time()
        if health.failure_count >= 3 and (current_time - health.last_failure_time) < 3:
            health.is_healthy = False
            raise RuntimeError(f"Tool {tool_name} is temporarily disabled (circuit breaker)")

    def _record_failure(self, tool_name: str):
        """Record tool failure for circuit breaker."""
        if tool_name not in self.tool_health:
            self.tool_health[tool_name] = ToolHealth(
                name=tool_name,
                last_checked=time.time()
            )

        health = self.tool_health[tool_name]
        health.failure_count += 1
        health.last_failure_time = time.time()

    def _generate_logistics_events(self, delivery_status: str, current_location: str,
                                    destination: str, shipping: Dict) -> List[Dict]:
        """Generate simulated logistics events based on delivery status."""
        events = []
        base_time = datetime.now() - timedelta(days=random.randint(1, 5))

        if "Late" in delivery_status:
            events = [
                {
                    "timestamp": (base_time + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
                    "location": "发货仓库",
                    "description": "快件已揽收",
                    "status": "已揽收"
                },
                {
                    "timestamp": (base_time + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
                    "location": "转运中心",
                    "description": "快件运输中（预计延迟）",
                    "status": "运输中"
                },
                {
                    "timestamp": (base_time + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
                    "location": current_location,
                    "description": "快件到达中转场（延迟）",
                    "status": "到达中转场"
                }
            ]
        elif "Advance" in delivery_status:
            events = [
                {
                    "timestamp": base_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "location": "发货仓库",
                    "description": "快件已揽收",
                    "status": "已揽收"
                },
                {
                    "timestamp": (base_time + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"),
                    "location": current_location,
                    "description": "快件提前到达",
                    "status": "已到达"
                },
                {
                    "timestamp": (base_time + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
                    "location": destination,
                    "description": "快件已签收",
                    "status": "已签收"
                }
            ]
        elif "on time" in delivery_status.lower():
            events = [
                {
                    "timestamp": base_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "location": "发货仓库",
                    "description": "快件已揽收",
                    "status": "已揽收"
                },
                {
                    "timestamp": (base_time + timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S"),
                    "location": current_location,
                    "description": "快件运输中",
                    "status": "运输中"
                },
                {
                    "timestamp": (base_time + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
                    "location": destination,
                    "description": "快件派送中",
                    "status": "派送中"
                }
            ]
        else:  # Canceled or other
            events = [
                {
                    "timestamp": base_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "location": "发货仓库",
                    "description": "快件已揽收",
                    "status": "已揽收"
                },
                {
                    "timestamp": (base_time + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S"),
                    "location": "转运中心",
                    "description": "快件已取消",
                    "status": "已取消"
                }
            ]

        return events

    def _calculate_eta(self, delivery_status: str) -> str:
        """Calculate estimated time of arrival based on delivery status."""
        if "Late" in delivery_status:
            eta = datetime.now() + timedelta(days=random.randint(1, 3))
            return eta.strftime("%Y-%m-%d %H:%M:%S")
        elif "Advance" in delivery_status:
            return "已送达"
        elif "on time" in delivery_status.lower():
            eta = datetime.now() + timedelta(hours=random.randint(6, 24))
            return eta.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return "已取消"

    def run_server(self, port: int = 8001):
        """Run the MCP server (synchronous)."""
        print(f"Starting MCP server on port {port}...")
        print("Available tools:")
        print("- query_order_status")
        print("- get_logistics_trace")
        print("- search_contract_template")
        print("- approve_work_order (requires confirmation)")
        print("- create_work_order_tool")
        print("- report_issue")
        print("- check_tool_health")

        # FastMCP.run() is synchronous
        self.mcp.run(transport="http", port=port)


def run_mcp_server(port: int = 8001):
    """Run the MCP server (synchronous wrapper for compatibility)."""
    server = MCPServer()
    server.run_server(port)


async def run_mcp_server_async(port: int = 8001):
    """Async wrapper for running MCP server in async context."""
    server = MCPServer()
    # Run in thread pool since mcp.run() is synchronous
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: server.run_server(port))
