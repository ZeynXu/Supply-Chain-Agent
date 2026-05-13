"""
MCP Server for Supply Chain Agent tools.

This module implements the MCP server with mock enterprise APIs.
"""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from contextlib import asynccontextmanager

from fastmcp import FastMCP

# Import mock data
from .mock_data.sample_data import (
    ORDER_DATA,
    LOGISTICS_DATA,
    CONTRACT_TEMPLATES,
    WORK_ORDERS,
    WORK_ORDER_TYPES,
    ISSUE_CATEGORIES,
    PRIORITY_LEVELS,
    SAMPLE_ISSUES
)


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
                order_id: Purchase order ID

            Returns:
                Order information including status, amount, supplier, etc.
            """
            self._check_health("query_order_status")

            # Simulate API delay
            time.sleep(0.1)

            if order_id in ORDER_DATA:
                return ORDER_DATA[order_id]
            else:
                self._record_failure("query_order_status")
                raise ValueError(f"Order {order_id} not found")

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
            time.sleep(0.2)

            if tracking_no in LOGISTICS_DATA:
                return LOGISTICS_DATA[tracking_no]
            else:
                self._record_failure("get_logistics_trace")
                raise ValueError(f"Tracking number {tracking_no} not found")

        # Search Contract Template Tool
        @self.mcp.tool()
        def search_contract_template(query: str, top_k: int = 2) -> Dict[str, Any]:
            """
            Search for contract templates by keyword.

            Args:
                query: Search keyword
                top_k: Number of results to return

            Returns:
                Matching contract templates with titles and content.
            """
            self._check_health("search_contract_template")

            # Simulate search delay
            time.sleep(0.15)

            # Simple keyword matching
            query_lower = query.lower()
            results = []

            for template in CONTRACT_TEMPLATES:
                title_lower = template["title"].lower()
                if query_lower in title_lower:
                    results.append(template)
                    if len(results) >= top_k:
                        break

            return {"templates": results}

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

            # Check if order exists
            if order_id not in WORK_ORDERS:
                raise ValueError(f"Work order {order_id} not found")

            # Return pre-filled form for confirmation
            return {
                "order_id": order_id,
                "work_order": WORK_ORDERS[order_id],
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
        def create_work_order(work_type: str, description: str, priority: str = "中",
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
            import random
            new_id = f"WO-2026-{random.randint(100, 999):03d}"

            # Create work order
            work_order = {
                "work_order_id": new_id,
                "order_id": order_id,
                "type": work_type,
                "status": "待处理",
                "created_by": "Agent System",
                "created_date": time.strftime("%Y-%m-%d"),
                "description": description,
                "priority": priority,
                "assigned_to": assigned_to,
                "estimated_time": "待评估",
                "required_approvals": ["部门主管"],
                "attachments": []
            }

            # Add to WORK_ORDERS (in-memory for demo)
            WORK_ORDERS[new_id] = work_order

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
            import random
            new_id = f"ISSUE-2026-{random.randint(100, 999):03d}"

            # Create issue report
            issue_report = {
                "issue_id": new_id,
                "title": f"{issue_type}: {affected_order if affected_order else description[:30]}...",
                "category": issue_type,
                "priority": urgency,
                "description": description,
                "affected_order": affected_order,
                "reported_by": reported_by or "Agent System",
                "report_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "待处理",
                "assigned_to": "异常处理组",
                "estimated_resolution": "待评估",
                "attachments": [],
                "updates": [
                    {
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "user": "Agent System",
                        "action": "创建问题报告",
                        "details": f"自动创建{issue_type}问题报告"
                    }
                ]
            }

            # Add to SAMPLE_ISSUES (in-memory for demo)
            SAMPLE_ISSUES[new_id] = issue_report

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

    def run_server(self, port: int = 8001):
        """Run the MCP server (synchronous)."""
        print(f"Starting MCP server on port {port}...")
        print("Available tools:")
        print("- query_order_status")
        print("- get_logistics_trace")
        print("- search_contract_template")
        print("- approve_work_order (requires confirmation)")
        print("- create_work_order (新增)")
        print("- report_issue (新增)")
        print("- check_tool_health")

        # FastMCP.run() is synchronous
        self.mcp.run(transport="http", port=port)


def run_mcp_server(port: int = 8001):
    """Run the MCP server (synchronous wrapper for compatibility)."""
    server = MCPServer()
    server.run_server(port)


async def run_mcp_server_async(port: int = 8001):
    """Async wrapper for running MCP server in async context."""
    import asyncio
    server = MCPServer()
    # Run in thread pool since mcp.run() is synchronous
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: server.run_server(port))