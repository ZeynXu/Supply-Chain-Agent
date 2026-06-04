"""
Orchestrator Agent (总控Agent)

M1修复：职责边界明确化
======================
Orchestrator作为纯协调者，职责边界如下：

**核心职责**:
1. 依赖注入：管理子Agent（Parser/Executor/Auditor/ReportGenerator）的创建和注入
2. 高层API封装：提供简洁的process()接口给上层调用
3. 响应处理：提取和格式化最终响应
4. 错误协调：协调工作流错误，生成降级响应

**已移至Workflow类**:
- 工作流控制逻辑（process_with_events, resume_with_events）
- 节点元数据定义（NODE_METADATA）
- 事件发送逻辑

**非职责（由其他组件负责）**:
- 意图识别 → ParserAgent
- 工具执行 → ExecutorAgent
- 结果审计 → AuditorAgent
- 报告生成 → ReportGenerator
- 状态持久化 → LangGraph checkpoint
- 工作流控制 → SupplyChainWorkflow
"""

from typing import Dict, Any, List, Optional, Callable
import asyncio
import time

from supply_chain_agent.config import settings
from supply_chain_agent.agents.parser import ParserAgent
from supply_chain_agent.agents.executor import ExecutorAgent
from supply_chain_agent.agents.auditor import AuditorAgent
from supply_chain_agent.agents.report_generator import ReportGenerator
from supply_chain_agent.graph.state import AgentState, state_manager
# H4修复：移除直接导入memory_manager，改用ServiceContainer

# H6修复：导入具体异常类型
from supply_chain_agent.common.exceptions import (
    SupplyChainError,
    RecoverableError,
    UnrecoverableError,
    is_recoverable,
    wrap_exception,
)
# H4修复：导入ServiceContainer
from supply_chain_agent.common.service_container import ServiceContainer


class OrchestratorAgent:
    """
    Main orchestrator agent for the supply chain system.

    M1修复：作为纯协调者，负责子Agent依赖注入和高层API封装。
    工作流控制逻辑已移至SupplyChainWorkflow类。
    """

    def __init__(self,
                 parser: Optional[ParserAgent] = None,
                 executor: Optional[ExecutorAgent] = None,
                 auditor: Optional[AuditorAgent] = None,
                 report_generator: Optional[ReportGenerator] = None):
        """
        Initialize orchestrator with optional dependency injection.

        Args:
            parser: ParserAgent instance (created if not provided)
            executor: ExecutorAgent instance (created if not provided)
            auditor: AuditorAgent instance (created if not provided)
            report_generator: ReportGenerator instance (created if not provided)
        """
        self.parser = parser or ParserAgent()
        self.executor = executor or ExecutorAgent()
        self.auditor = auditor or AuditorAgent()
        self.report_generator = report_generator or ReportGenerator()
        self._workflow = None
        self.current_thread_id = "default"

    @property
    def workflow(self) -> 'SupplyChainWorkflow':
        """
        Lazy load workflow, injecting agent dependencies (no circular dependency).

        M30修复：添加返回类型注解，确保不返回None。
        """
        if self._workflow is None:
            from supply_chain_agent.graph.workflow import SupplyChainWorkflow, get_workflow
            # 直接注入各个 agents，而不是传入 orchestrator 自身
            self._workflow = get_workflow(
                parser=self.parser,
                executor=self.executor,
                auditor=self.auditor,
                report_generator=self.report_generator
            )
        return self._workflow

    async def process(self, user_input: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process user input through the complete agent workflow.

        重构：直接调用process_with_callback，避免代码重复（M15）。

        Args:
            user_input: User's query
            thread_id: Optional thread ID for conversation continuity

        Returns:
            Dict with 'response', 'waiting_for_input', and 'clarification_prompt' if applicable
        """
        # 直接调用process_with_callback，使用空回调函数
        return await self.process_with_callback(user_input, thread_id, callback=None)

    def _extract_response(self, final_state: Dict[str, Any]) -> str:
        """
        Extract response from final state.

        L2修复：补充文档字符串。
        从最终状态中提取响应文本，按以下优先级：
        1. 最后一条assistant消息
        2. response_card格式化结果
        3. 默认响应

        Args:
            final_state: 工作流最终状态，包含messages和response_card

        Returns:
            响应文本字符串
        """
        # Try to get response from messages
        messages = final_state.get("messages", [])
        if messages:
            # Find the last assistant message
            assistant_messages = []
            for msg in messages:
                # Handle both dict and tuple message formats
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    assistant_messages.append(msg)
                elif isinstance(msg, tuple) and len(msg) >= 2:
                    # Tuple format might be (role, content) or similar
                    if msg[0] == "assistant":
                        assistant_messages.append({"role": "assistant", "content": msg[1] if len(msg) > 1 else ""})
            if assistant_messages:
                last_msg = assistant_messages[-1]
                if isinstance(last_msg, dict):
                    return last_msg.get("content", "处理完成")
                else:
                    return str(last_msg)

        # Fallback to response card
        response_card = final_state.get("response_card")
        if response_card:
            return self.report_generator._format_response_card(response_card)

        # Ultimate fallback
        return "✅ 处理完成，但未能生成详细响应。"

    async def process_with_callback(
        self,
        user_input: str,
        thread_id: Optional[str] = None,
        callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Process user input with event callbacks for real-time tracking.

        M1修复：简化为委托给Workflow的事件处理方法。

        Args:
            user_input: User's query
            thread_id: Optional thread ID for conversation continuity
            callback: Async callback function(event_type, data) for events

        Returns:
            Dict with 'response', 'waiting_for_input', and 'clarification_prompt' if applicable
        """
        if thread_id:
            self.current_thread_id = thread_id

        print(f"🔍 处理用户请求: {user_input}")
        print("-" * 50)

        # Record user input in memory
        ServiceContainer.get_memory_manager().record_agent_action(
            agent_name="user",
            action="input",
            details={"text": user_input},
            importance=0.7
        )

        try:
            # M1修复：委托给Workflow的事件处理方法
            if self.workflow.is_waiting_for_input(self.current_thread_id):
                print("📌 检测到等待用户输入，恢复工作流...")
                final_state = await self.workflow.resume_with_events(
                    user_input, self.current_thread_id, callback
                )
            else:
                final_state = await self.workflow.process_with_events(
                    user_input, self.current_thread_id, callback
                )

            # Check if result contains interrupt information
            interrupt_info = self.workflow.check_interrupt_in_result(final_state)
            if interrupt_info:
                clarification_prompt, missing_slots = self._extract_interrupt_info(interrupt_info)
                print(f"⏸️ 工作流暂停，等待用户输入: {clarification_prompt}")

                ServiceContainer.get_memory_manager().record_agent_action(
                    agent_name="workflow",
                    action="interrupt_for_clarification",
                    details={
                        "prompt": clarification_prompt,
                        "missing_slots": missing_slots,
                        "source": "clarify_node"
                    },
                    importance=0.6
                )

                return {
                    "response": clarification_prompt,
                    "waiting_for_input": True,
                    "clarification_prompt": clarification_prompt,
                    "missing_slots": missing_slots,
                    "thread_id": self.current_thread_id
                }

            # Extract response from final state
            response = self._extract_response(final_state)

            ServiceContainer.get_memory_manager().record_agent_action(
                agent_name="workflow",
                action="completed",
                details={
                    "response_preview": response[:100] + "..." if len(response) > 100 else response,
                    "has_response_card": final_state.get("response_card") is not None,
                    "tool_results_keys": list(final_state.get("tool_results", {}).keys())
                },
                importance=0.8
            )

            return {
                "response": response,
                "waiting_for_input": False,
                "thread_id": self.current_thread_id
            }

        except RecoverableError as e:
            print(f"⚠️ 可恢复错误: {type(e).__name__}: {e}")

            ServiceContainer.get_memory_manager().record_agent_action(
                agent_name="workflow",
                action="recoverable_error",
                details={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "fallback_used": True,
                    "is_recoverable": True
                },
                importance=0.7
            )

            error_response = await self._handle_workflow_error(e, user_input)
            return {
                "response": error_response,
                "waiting_for_input": False,
                "error": str(e),
                "is_recoverable": True
            }
        except UnrecoverableError as e:
            print(f"❌ 不可恢复错误: {type(e).__name__}: {e}")

            ServiceContainer.get_memory_manager().record_agent_action(
                agent_name="workflow",
                action="unrecoverable_error",
                details={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "fallback_used": False,
                    "is_recoverable": False
                },
                importance=0.9
            )

            return {
                "response": f"抱歉，系统无法处理您的请求。错误信息：{e}",
                "waiting_for_input": False,
                "error": str(e),
                "is_recoverable": False
            }
        except SupplyChainError as e:
            print(f"❌ 业务错误: {type(e).__name__}: {e}")

            ServiceContainer.get_memory_manager().record_agent_action(
                agent_name="workflow",
                action="business_error",
                details={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "original_error": str(e.original_error) if e.original_error else None,
                    "context": e.context,
                    "fallback_used": True
                },
                importance=0.8
            )

            error_response = await self._handle_workflow_error(e, user_input)
            return {
                "response": error_response,
                "waiting_for_input": False,
                "error": str(e)
            }
        except Exception as e:
            wrapped = wrap_exception(e, {"method": "process_with_callback", "user_input": user_input[:100]})
            print(f"❌ 工作流执行错误: {type(wrapped).__name__}: {e}")

            ServiceContainer.get_memory_manager().record_agent_action(
                agent_name="workflow",
                action="execution_error",
                details={
                    "error_type": type(wrapped).__name__,
                    "error_message": str(e),
                    "fallback_used": True,
                    "is_recoverable": is_recoverable(wrapped)
                },
                importance=0.9
            )

            error_response = await self._handle_workflow_error(e, user_input)
            return {
                "response": error_response,
                "waiting_for_input": False,
                "error": str(e)
            }

    def _extract_interrupt_info(self, interrupt_info: Any) -> tuple:
        """Extract clarification prompt and missing slots from interrupt info."""
        if isinstance(interrupt_info, dict):
            return interrupt_info.get("prompt", "请提供更多信息"), interrupt_info.get("missing_slots", [])
        elif isinstance(interrupt_info, tuple) and len(interrupt_info) >= 2:
            second_item = interrupt_info[1]
            if isinstance(second_item, dict):
                return second_item.get("prompt", "请提供更多信息"), second_item.get("missing_slots", [])
            return str(second_item), []
        return str(interrupt_info) if interrupt_info else "请提供更多信息", []

                ServiceContainer.get_memory_manager().record_agent_action(
                    agent_name="workflow",
                    action="interrupt_for_clarification",
                    details={
                        "prompt": clarification_prompt,
                        "missing_slots": missing_slots,
                        "source": "clarify_node"
                    },
                    importance=0.6
                )

                return {
                    "response": clarification_prompt,
                    "waiting_for_input": True,
                    "clarification_prompt": clarification_prompt,
                    "missing_slots": missing_slots,
                    "thread_id": self.current_thread_id
                }

            # Extract response from final state
            response = self._extract_response(final_state)

            ServiceContainer.get_memory_manager().record_agent_action(
                agent_name="workflow",
                action="completed",
                details={
                    "response_preview": response[:100] + "..." if len(response) > 100 else response,
                    "has_response_card": final_state.get("response_card") is not None,
                    "tool_results_keys": list(final_state.get("tool_results", {}).keys())
                },
                importance=0.8
            )

            return {
                "response": response,
                "waiting_for_input": False,
                "thread_id": self.current_thread_id
            }

        # H6修复：区分异常类型
        except RecoverableError as e:
            # 可恢复错误 - 记录并尝试恢复
            print(f"⚠️ 可恢复错误: {type(e).__name__}: {e}")

            ServiceContainer.get_memory_manager().record_agent_action(
                agent_name="workflow",
                action="recoverable_error",
                details={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "fallback_used": True,
                    "is_recoverable": True
                },
                importance=0.7
            )

            error_response = await self._handle_workflow_error(e, user_input)
            return {
                "response": error_response,
                "waiting_for_input": False,
                "error": str(e),
                "is_recoverable": True
            }
        except UnrecoverableError as e:
            # 不可恢复错误 - 直接返回错误信息
            print(f"❌ 不可恢复错误: {type(e).__name__}: {e}")

            ServiceContainer.get_memory_manager().record_agent_action(
                agent_name="workflow",
                action="unrecoverable_error",
                details={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "fallback_used": False,
                    "is_recoverable": False
                },
                importance=0.9
            )

            return {
                "response": f"抱歉，系统无法处理您的请求。错误信息：{e}",
                "waiting_for_input": False,
                "error": str(e),
                "is_recoverable": False
            }
        except SupplyChainError as e:
            # 其他业务异常 - 记录完整上下文
            print(f"❌ 业务错误: {type(e).__name__}: {e}")

            ServiceContainer.get_memory_manager().record_agent_action(
                agent_name="workflow",
                action="business_error",
                details={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "original_error": str(e.original_error) if e.original_error else None,
                    "context": e.context,
                    "fallback_used": True
                },
                importance=0.8
            )

            error_response = await self._handle_workflow_error(e, user_input)
            return {
                "response": error_response,
                "waiting_for_input": False,
                "error": str(e)
            }
        except Exception as e:
            # 未知异常 - 包装后处理
            wrapped = wrap_exception(e, {"method": "process_with_callback", "user_input": user_input[:100]})
            print(f"❌ 工作流执行错误: {type(wrapped).__name__}: {e}")

            ServiceContainer.get_memory_manager().record_agent_action(
                agent_name="workflow",
                action="execution_error",
                details={
                    "error_type": type(wrapped).__name__,
                    "error_message": str(e),
                    "fallback_used": True,
                    "is_recoverable": is_recoverable(wrapped)
                },
                importance=0.9
            )

            error_response = await self._handle_workflow_error(e, user_input)
            return {
                "response": error_response,
                "waiting_for_input": False,
                "error": str(e)
            }

    async def process_simple(self, user_input: str) -> str:
        """
        Simple process method that returns just the response string.
        Maintains backward compatibility with existing code.

        Args:
            user_input: User's query

        Returns:
            Agent response string
        """
        result = await self.process(user_input)
        return result.get("response", "处理完成")

    async def _handle_workflow_error(self, error: Exception, user_input: str) -> str:
        """Handle workflow execution error with proper error context preservation."""
        import traceback
        import uuid

        # 生成错误追踪ID
        error_id = str(uuid.uuid4())[:8]
        error_type = type(error).__name__
        error_trace = traceback.format_exc()

        # 打印详细错误信息（开发调试用）
        print(f"工作流错误处理 [{error_id}]: {error_type}: {error}")
        print(f"错误堆栈:\n{error_trace}")

        # 记录完整错误上下文到memory
        ServiceContainer.get_memory_manager().record_agent_action(
            agent_name="orchestrator",
            action="workflow_error",
            details={
                "error_id": error_id,
                "error_type": error_type,
                "error_message": str(error),
                "error_trace": error_trace,
                "user_input": user_input[:100] if user_input else None
            },
            importance=0.9
        )

        # Try simple processing as fallback
        try:
            # Parse intent directly
            intent = await self.parser.parse_intent(user_input)
            validation = await self.parser.validate_intent(intent)

            if validation["valid"]:
                # Create simple plan
                tasks = await self.executor.create_execution_plan(intent)

                if tasks:
                    # Execute tasks
                    results = {}
                    for task in tasks:
                        try:
                            result = await self.executor.execute_task(task, {})
                            results[task] = result
                        except SupplyChainError as e:
                            # H6修复：区分异常类型
                            results[task] = {"error": str(e), "error_type": type(e).__name__}
                        except Exception as e:
                            wrapped = wrap_exception(e, {"task": str(task)})
                            results[task] = {"error": str(e), "error_type": type(wrapped).__name__}

                    # Generate simple response
                    if "query_order" in results:
                        order_data = results["query_order"]
                        if "error" not in order_data:
                            return (
                                f"✅ 简易查询完成\n\n"
                                f"订单号: {order_data.get('order_id', 'N/A')}\n"
                                f"状态: {order_data.get('status', 'N/A')}\n"
                                f"备注: 使用简化模式处理"
                            )

            return f"🔄 系统正在维护中，请稍后重试。（错误码：{error_id}）"

        # H6修复：区分异常类型
        except SupplyChainError as fallback_error:
            fallback_error_type = type(fallback_error).__name__
            print(f"降级处理也失败 [{error_id}]: {fallback_error_type}: {fallback_error}")
            return f"❌ 系统暂时无法处理您的请求。（错误码：{error_id}，类型：{fallback_error_type}）"
        except Exception as fallback_error:
            wrapped = wrap_exception(fallback_error, {"context": "fallback_handler"})
            fallback_error_type = type(wrapped).__name__
            print(f"降级处理也失败 [{error_id}]: {fallback_error_type}: {fallback_error}")
            return f"❌ 系统暂时无法处理您的请求。（错误码：{error_id}）"
