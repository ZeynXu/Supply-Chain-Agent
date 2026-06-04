"""
MCP Tool Client for Supply Chain Agent.

This module provides a client for calling MCP tools with circuit breaker and fallback mechanisms.
Enhanced with LLM-based fallback responses.

Following MCP Server Design.md specification for tool interfaces.
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, Callable
from functools import wraps

from supply_chain_agent.config import settings

# LLM和知识库导入
try:
    from supply_chain_agent.agents.llm_client import LLMClient, get_llm_client
    from supply_chain_agent.memory.knowledge_retriever import KnowledgeRetriever, get_knowledge_retriever
    from supply_chain_agent.prompts.fallback import FALLBACK_RESPONSE_PROMPT
    FALLBACK_LLM_AVAILABLE = True
except ImportError:
    FALLBACK_LLM_AVAILABLE = False

# 使用统一的熔断器实现（来自retry_manager）
from supply_chain_agent.agents.retry_manager import CircuitBreaker, CircuitBreakerConfig


class ToolClient:
    """Client for calling MCP tools using FastMCP client."""

    # 工具名称常量（避免硬编码）
    TOOLS = [
        "query_customer",
        "query_customer_orders",
        "query_order",
        "query_order_items",
        "query_product",
        "query_shipment",
        "query_customer_statistics",
        "create_work_order",
        "approve_work_order",
        "report_issue",
    ]

    def __init__(self, base_url: str = None):
        self.base_url = base_url or f"http://{settings.mcp_server_host}:{settings.mcp_server_port}/mcp"
        # 使用统一的熔断器配置
        self._cb_config = CircuitBreakerConfig(
            failure_threshold=settings.circuit_breaker_failures,
            recovery_timeout_seconds=settings.circuit_breaker_reset_timeout
        )
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        # Use local MCPServer instance for direct calls
        self._server: Optional[Any] = None

        # LLM和知识库（用于降级响应）
        self._llm_client: Optional[LLMClient] = None
        self._knowledge_retriever: Optional[KnowledgeRetriever] = None

        # 工具定义缓存（动态获取）
        self._tool_definitions: Optional[Dict[str, Dict]] = None

    def _get_server(self):
        """Get or create local MCP server instance."""
        if self._server is None:
            from supply_chain_agent.tools.server import MCPServer
            self._server = MCPServer()
        return self._server

    @property
    def llm_client(self) -> Optional['LLMClient']:
        """Lazy load LLM client for fallback."""
        if self._llm_client is None and FALLBACK_LLM_AVAILABLE:
            try:
                self._llm_client = get_llm_client()
            except ValueError:
                pass
        return self._llm_client

    @property
    def knowledge_retriever(self) -> Optional['KnowledgeRetriever']:
        """Lazy load knowledge retriever for fallback."""
        if self._knowledge_retriever is None and FALLBACK_LLM_AVAILABLE:
            self._knowledge_retriever = get_knowledge_retriever()
        return self._knowledge_retriever

    def get_tool_definitions(self) -> Dict[str, Dict]:
        """
        动态获取工具定义（从MCPServer获取，避免重复定义）。

        Returns:
            工具定义字典，key为工具名，value为定义信息
        """
        if self._tool_definitions is None:
            server = self._get_server()
            self._tool_definitions = {}

            # 从MCP server获取工具列表
            if hasattr(server.mcp, '_tools'):
                for name, tool in server.mcp._tools.items():
                    self._tool_definitions[name] = {
                        "name": name,
                        "description": tool.description if hasattr(tool, 'description') else "",
                        "parameters": {}
                    }

        return self._tool_definitions

    def list_tools(self) -> list[str]:
        """获取可用工具列表"""
        return self.TOOLS

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def _get_circuit_breaker(self, tool_name: str) -> CircuitBreaker:
        """获取或创建熔断器（使用统一实现）"""
        if tool_name not in self.circuit_breakers:
            self.circuit_breakers[tool_name] = CircuitBreaker(tool_name, self._cb_config)
        return self.circuit_breakers[tool_name]

    def _check_circuit_breaker(self, tool_name: str) -> bool:
        """Check if circuit breaker allows call for a tool."""
        breaker = self._get_circuit_breaker(tool_name)
        return breaker.is_call_allowed()

    def _record_failure(self, tool_name: str):
        """Record a failure for circuit breaker."""
        breaker = self._get_circuit_breaker(tool_name)
        breaker.record_failure()

    def _record_success(self, tool_name: str):
        """Record a success for circuit breaker."""
        breaker = self._get_circuit_breaker(tool_name)
        breaker.record_success()

    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Call an MCP tool with circuit breaker protection.

        Args:
            tool_name: Name of the tool to call
            **kwargs: Arguments to pass to the tool

        Returns:
            Tool execution result

        Raises:
            RuntimeError: If circuit breaker is open or tool call fails
        """
        # Check circuit breaker
        if not self._check_circuit_breaker(tool_name):
            raise RuntimeError(f"Circuit breaker is open for {tool_name}")

        try:
            # Use local MCP server instance for direct calls
            server = self._get_server()
            result = await server.mcp.call_tool(tool_name, kwargs)

            # Record success
            self._record_success(tool_name)

            # FastMCP returns a CallToolResult object with structured_content
            if hasattr(result, 'structured_content') and result.structured_content:
                return result.structured_content
            elif hasattr(result, 'content'):
                # Extract content from the result
                content = result.content
                if isinstance(content, list) and len(content) > 0:
                    first_content = content[0]
                    if hasattr(first_content, 'text'):
                        try:
                            return json.loads(first_content.text)
                        except json.JSONDecodeError:
                            return {"result": first_content.text}
                return {"result": content}
            return result if isinstance(result, dict) else {"result": str(result)}

        except Exception as e:
            self._record_failure(tool_name)
            raise RuntimeError(f"Tool call failed for {tool_name}: {e}")

    async def invoke(
        self,
        tool_name: str,
        params: Dict[str, Any],
        intent_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        通用工具调用方法（带降级响应）。

        Args:
            tool_name: 工具名称
            params: 工具参数
            intent_info: 意图信息（用于降级响应）

        Returns:
            工具执行结果或降级响应
        """
        try:
            return await self.call_tool(tool_name, **params)
        except Exception as e:
            # 构建降级响应
            user_input = f"{tool_name}({params})"
            fallback_intent = intent_info or {
                "intent_level_1": "信息查询",
                "intent_level_2": tool_name
            }
            return await self._fallback_response(
                user_input=user_input,
                intent_info=fallback_intent,
                error=str(e)
            )

    # ==========================================
    # Design Document Tool Wrappers (Section 4)
    # ==========================================

    async def query_customer(self, customer_id: int) -> Dict[str, Any]:
        """
        根据客户ID查询客户基本信息。

        Args:
            customer_id: 客户唯一标识

        Returns:
            客户基本信息，包括姓名、邮箱、地区等
        """
        try:
            return await self.call_tool("query_customer", customer_id=customer_id)
        except Exception as e:
            return await self._fallback_response(
                user_input=f"查询客户{customer_id}",
                intent_info={
                    "intent_level_1": "信息查询",
                    "intent_level_2": "客户信息查询"
                },
                error=str(e)
            )

    async def query_customer_orders(
        self,
        customer_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        查询某客户的订单列表（分页）。

        Args:
            customer_id: 客户唯一标识
            limit: 返回数量限制 (1-100)
            offset: 分页偏移量

        Returns:
            订���列表概要
        """
        try:
            return await self.call_tool(
                "query_customer_orders",
                customer_id=customer_id,
                limit=limit,
                offset=offset
            )
        except Exception as e:
            return await self._fallback_response(
                user_input=f"查询客户{customer_id}的订单",
                intent_info={
                    "intent_level_1": "信息查询",
                    "intent_level_2": "订单列表查询"
                },
                error=str(e)
            )

    async def query_order(self, order_id: int) -> Dict[str, Any]:
        """
        根据订单ID查询订单头详细信息。

        Args:
            order_id: 订单唯一标识

        Returns:
            订单详细信息
        """
        try:
            return await self.call_tool("query_order", order_id=order_id)
        except Exception as e:
            return await self._fallback_response(
                user_input=f"查询订单{order_id}",
                intent_info={
                    "intent_level_1": "信息查询",
                    "intent_level_2": "订单详情查询"
                },
                error=str(e)
            )

    async def query_order_items(self, order_id: int) -> Dict[str, Any]:
        """
        根据订单ID查询订单行项目明细。

        Args:
            order_id: 订单唯一标识

        Returns:
            订单明细行列表
        """
        try:
            return await self.call_tool("query_order_items", order_id=order_id)
        except Exception as e:
            return await self._fallback_response(
                user_input=f"查询订单{order_id}的明细",
                intent_info={
                    "intent_level_1": "信息查询",
                    "intent_level_2": "订单明细查询"
                },
                error=str(e)
            )

    async def query_product(self, product_card_id: int) -> Dict[str, Any]:
        """
        根据产品卡片ID查询产品信息。

        Args:
            product_card_id: 产品卡片唯一标识

        Returns:
            产品详情
        """
        try:
            return await self.call_tool("query_product", product_card_id=product_card_id)
        except Exception as e:
            return await self._fallback_response(
                user_input=f"查询产品{product_card_id}",
                intent_info={
                    "intent_level_1": "信息查询",
                    "intent_level_2": "产品信息查询"
                },
                error=str(e)
            )

    async def query_shipment(self, order_id: int) -> Dict[str, Any]:
        """
        根据订单ID查询物流基本信息及状态描述。

        Args:
            order_id: 订单唯一标识

        Returns:
            物流信息及状态描述
        """
        try:
            return await self.call_tool("query_shipment", order_id=order_id)
        except Exception as e:
            return await self._fallback_response(
                user_input=f"查询订单{order_id}的物流状态",
                intent_info={
                    "intent_level_1": "状态查询",
                    "intent_level_2": "物流状态查询"
                },
                error=str(e)
            )

    async def query_customer_statistics(self, customer_id: int) -> Dict[str, Any]:
        """
        获取客户的风险评估统计指标及当前履约占用。

        Args:
            customer_id: 客户唯一标识

        Returns:
            统计指标，包括交易行为、履约占用等
        """
        try:
            return await self.call_tool("query_customer_statistics", customer_id=customer_id)
        except Exception as e:
            return await self._fallback_response(
                user_input=f"查询客户{customer_id}的统计数据",
                intent_info={
                    "intent_level_1": "风险评估",
                    "intent_level_2": "客户统计查询"
                },
                error=str(e)
            )

    # ==========================================
    # Legacy compatibility methods
    # ==========================================

    async def query_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Legacy method: Query order status (converted to use query_order).

        Args:
            order_id: Purchase order ID (numeric or PO-XXXXX format)

        Returns:
            Order information including status, amount, customer, etc.
        """
        # Extract numeric ID from format like "PO-2026-001" or use directly
        try:
            if order_id.startswith("PO-"):
                numeric_id = int(order_id.split("-")[-1])
            else:
                numeric_id = int(order_id)
        except (ValueError, IndexError):
            return {"error": {"code": 422, "message": f"Invalid order ID format: {order_id}"}}

        # Use new query_order tool
        result = await self.query_order(numeric_id)

        # If error, return error
        if "error" in result:
            return result

        # Get order items for additional context
        items_result = await self.query_order_items(numeric_id)
        shipment_result = await self.query_shipment(numeric_id)

        # Transform to legacy format for backward compatibility
        items = items_result.get("items", [])

        return {
            "order_id": f"PO-{result.get('order_id')}",
            "customer_id": result.get("customer_id"),
            "status": result.get("order_status"),
            "delivery_status": result.get("delivery_status"),
            "amount": sum(item.get("order_item_total", 0) for item in items),
            "currency": "USD",
            "order_date": result.get("order_date"),
            "market": result.get("market"),
            "items": [
                {
                    "sku": f"SKU-{item.get('product_card_id')}",
                    "quantity": item.get("quantity"),
                    "unit_price": item.get("product_price"),
                    "category": None  # Not included in order_items response
                }
                for item in items[:5]
            ],
            "shipping_mode": shipment_result.get("shipping_mode"),
            "late_delivery_risk": shipment_result.get("late_delivery_risk"),
            "tracking_no": f"SF{result.get('order_id'):010d}",
            "warehouse": result.get("order_region")
        }

    async def check_health(self) -> Dict[str, Any]:
        """Check health of all tools."""
        return {
            "tools": {
                "query_customer": {"healthy": True},
                "query_customer_orders": {"healthy": True},
                "query_order": {"healthy": True},
                "query_order_items": {"healthy": True},
                "query_product": {"healthy": True},
                "query_shipment": {"healthy": True},
                "query_customer_statistics": {"healthy": True}
            }
        }

    async def _fallback_response(
        self,
        user_input: str,
        intent_info: Dict[str, Any],
        error: str
    ) -> Dict[str, Any]:
        """
        降级响应：知识库优先 + LLM生成合理提示

        Args:
            user_input: 用户原始输入
            intent_info: 意图信息
            error: 原始错误信息

        Returns:
            降级响应结果（不包含假数据）
        """
        knowledge_result = "无相关指引"

        # 第一步：知识库检索
        if self.knowledge_retriever:
            try:
                results = await self.knowledge_retriever.search(
                    query=user_input,
                    top_k=3
                )
                if results:
                    knowledge_result = "\n".join([
                        f"- {r['content'][:200]}" for r in results[:2]
                    ])
            except Exception:
                pass

        # 第二步：LLM生成合理提示
        llm_message = None
        if self.llm_client:
            try:
                prompt = FALLBACK_RESPONSE_PROMPT.format(
                    user_input=user_input,
                    intent_info=json.dumps(intent_info, ensure_ascii=False),
                    knowledge_result=knowledge_result
                )
                llm_message = await self.llm_client.generate(prompt)
                # L11修复：确保LLM消息明确说明无数据
                if llm_message and "数据" in llm_message and "不可用" not in llm_message:
                    llm_message = f"⚠️ 服务暂时不可用：{llm_message}（当前无法获取真实数据）"
            except Exception:
                pass

        # 如果LLM失败，使用默认提示
        if not llm_message:
            intent_name = intent_info.get('intent_level_2', '相关服务')
            llm_message = f"抱歉，{intent_name}服务暂时不可用，无法获取真实数据。请稍后重试或联系客服获取帮助。"

        return {
            "fallback": True,
            "message": llm_message,
            "knowledge_references": knowledge_result if knowledge_result != "无相关指引" else None,
            "suggestion": "请稍后重试或联系客服",
            "original_error": error,
            # L11修复：明确标记不包含真实数据，并添加提示
            "data_available": False,
            "data_notice": "⚠️ 当前响应为降级提示，不包含真实业务数据"
        }


# Singleton instance
_tool_client: Optional[ToolClient] = None


async def get_tool_client() -> ToolClient:
    """Get singleton tool client instance."""
    global _tool_client
    if _tool_client is None:
        _tool_client = ToolClient()
    return _tool_client


async def close_tool_client():
    """Close the tool client."""
    global _tool_client
    _tool_client = None


def reset_tool_client():
    """
    H4修复：重置工具客户端单例（用于测试）

    同步版本，供ServiceContainer调用。
    """
    global _tool_client
    _tool_client = None