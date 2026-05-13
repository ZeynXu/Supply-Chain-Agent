"""
MCP Tool Client for Supply Chain Agent.

This module provides a client for calling MCP tools with circuit breaker and fallback mechanisms.
Enhanced with LLM-based fallback responses.
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
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


@dataclass
class CircuitBreaker:
    """Circuit breaker for tool calls."""
    failure_count: int = 0
    last_failure_time: float = 0
    is_open: bool = False
    open_until: float = 0


class ToolClient:
    """Client for calling MCP tools using FastMCP client."""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or f"http://{settings.mcp_server_host}:{settings.mcp_server_port}/mcp"
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        # Use local MCPServer instance for direct calls
        self._server: Optional[Any] = None

        # LLM和知识库（用于降级响应）
        self._llm_client: Optional[LLMClient] = None
        self._knowledge_retriever: Optional[KnowledgeRetriever] = None

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

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def _check_circuit_breaker(self, tool_name: str) -> bool:
        """Check if circuit breaker is open for a tool."""
        if tool_name not in self.circuit_breakers:
            self.circuit_breakers[tool_name] = CircuitBreaker()

        breaker = self.circuit_breakers[tool_name]

        # Reset breaker if it's been open long enough
        if breaker.is_open and time.time() > breaker.open_until:
            breaker.is_open = False
            breaker.failure_count = 0
            return True

        # Check if breaker should be opened
        if breaker.failure_count >= settings.circuit_breaker_failures:
            if not breaker.is_open:
                breaker.is_open = True
                breaker.open_until = time.time() + settings.circuit_breaker_reset_timeout
                print(f"⚠️  Circuit breaker opened for {tool_name} (will reset in {settings.circuit_breaker_reset_timeout}s)")
            return False

        return not breaker.is_open

    def _record_failure(self, tool_name: str):
        """Record a failure for circuit breaker."""
        if tool_name not in self.circuit_breakers:
            self.circuit_breakers[tool_name] = CircuitBreaker()

        breaker = self.circuit_breakers[tool_name]
        breaker.failure_count += 1
        breaker.last_failure_time = time.time()

        # Check if we should open the breaker
        if breaker.failure_count >= settings.circuit_breaker_failures:
            breaker.is_open = True
            breaker.open_until = time.time() + settings.circuit_breaker_reset_timeout

    def _record_success(self, tool_name: str):
        """Record a success for circuit breaker."""
        if tool_name in self.circuit_breakers:
            self.circuit_breakers[tool_name].failure_count = 0
            self.circuit_breakers[tool_name].is_open = False

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

    async def query_order_status(self, order_id: str) -> Dict[str, Any]:
        """Query order status with LLM-based fallback mechanism."""
        try:
            return await self.call_tool("query_order_status", order_id=order_id)
        except Exception as e:
            # 使用LLM降级响应
            return await self._fallback_response(
                user_input=f"查询订单{order_id}",
                intent_info={
                    "intent_level_1": "状态查询",
                    "intent_level_2": "订单状态查询"
                },
                error=str(e)
            )

    async def get_logistics_trace(self, tracking_no: str) -> Dict[str, Any]:
        """Get logistics trace with LLM-based fallback."""
        try:
            return await self.call_tool("get_logistics_trace", tracking_no=tracking_no)
        except Exception as e:
            return await self._fallback_response(
                user_input=f"查询物流{tracking_no}",
                intent_info={
                    "intent_level_1": "状态查询",
                    "intent_level_2": "物流查询"
                },
                error=str(e)
            )

    async def search_contract_template(self, query: str, top_k: int = 2) -> Dict[str, Any]:
        """Search contract templates."""
        try:
            return await self.call_tool("search_contract_template", query=query, top_k=top_k)
        except Exception as e:
            print(f"Contract search failed: {e}")
            return {"templates": []}

    async def approve_work_order(self, order_id: str, comment: str) -> Dict[str, Any]:
        """Approve work order (requires confirmation)."""
        try:
            return await self.call_tool("approve_work_order", order_id=order_id, comment=comment)
        except Exception as e:
            raise RuntimeError(f"Work order approval failed: {e}")

    async def check_health(self) -> Dict[str, Any]:
        """Check health of all tools."""
        try:
            return await self.call_tool("check_tool_health")
        except Exception as e:
            return {"error": f"Health check failed: {e}", "tools": {}}

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
            except Exception:
                pass

        # 如果LLM失败，使用默认提示
        if not llm_message:
            llm_message = f"抱歉，{intent_info.get('intent_level_2', '相关服务')}暂时不可用。请稍后重试或联系客服。"

        return {
            "fallback": True,
            "message": llm_message,
            "knowledge_references": knowledge_result if knowledge_result != "无相关指引" else None,
            "suggestion": "请稍后重试或联系客服",
            "original_error": error,
            # 明确标记：不包含真实数据
            "data_available": False
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
