"""
Orchestrator Agent (总控Agent)

Responsible for maintaining global state, managing context windows, and deciding which sub-agent to activate.
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
from supply_chain_agent.memory.vector_store import memory_manager


class OrchestratorAgent:
    """Main orchestrator agent for the supply chain system."""

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
        # Lazy import to avoid circular dependency
        self._workflow = None
        # Thread ID for conversation continuity
        self.current_thread_id = "default"

    @property
    def workflow(self):
        """Lazy load workflow to avoid circular import."""
        if self._workflow is None:
            from supply_chain_agent.graph.workflow import get_workflow
            self._workflow = get_workflow(self)
        return self._workflow

    async def process(self, user_input: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process user input through the complete agent workflow.

        Args:
            user_input: User's query
            thread_id: Optional thread ID for conversation continuity

        Returns:
            Dict with 'response', 'waiting_for_input', and 'clarification_prompt' if applicable
        """
        if thread_id:
            self.current_thread_id = thread_id

        print("-" * 50)
        print(f"🔍 处理用户请求: {user_input}")

        # Record user input in memory
        memory_manager.record_agent_action(
            agent_name="user",
            action="input",
            details={"text": user_input},
            importance=0.7
        )

        try:
            # Check if we're resuming from a clarification
            if self.workflow.is_waiting_for_input(self.current_thread_id):
                print("📌 检测到等待用户输入，恢复工作流...")
                # Resume workflow with user's clarification input
                final_state = await self.workflow.resume(user_input, self.current_thread_id)
            else:
                # Start new workflow
                final_state = await self.workflow.process(user_input, thread_id=self.current_thread_id)

            # Check if result contains interrupt information
            interrupt_info = self.workflow.check_interrupt_in_result(final_state)
            if interrupt_info:
                # Handle different interrupt_info formats
                if isinstance(interrupt_info, dict):
                    clarification_prompt = interrupt_info.get("prompt", "请提供更多信息")
                    missing_slots = interrupt_info.get("missing_slots", [])
                elif isinstance(interrupt_info, tuple):
                    # Tuple format: could be (key, value) or nested structure
                    if len(interrupt_info) >= 2:
                        second_item = interrupt_info[1]
                        if isinstance(second_item, dict):
                            clarification_prompt = second_item.get("prompt", "请提供更多信息")
                            missing_slots = second_item.get("missing_slots", [])
                        else:
                            clarification_prompt = str(second_item)
                            missing_slots = []
                    else:
                        clarification_prompt = str(interrupt_info[0]) if interrupt_info else "请提供更多信息"
                        missing_slots = []
                else:
                    clarification_prompt = str(interrupt_info) if interrupt_info else "请提供更多信息"
                    missing_slots = []
                print(f"⏸️ 工作流暂停，等待用户输入: {clarification_prompt}")

                # Record clarification request in memory
                memory_manager.record_agent_action(
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

            # Record response in memory
            memory_manager.record_agent_action(
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

        except Exception as e:
            print(f"❌ 工作流执行错误: {e}")

            # Record error in memory
            memory_manager.record_agent_action(
                agent_name="workflow",
                action="execution_error",
                details={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "fallback_used": True
                },
                importance=0.9
            )

            error_response = await self._handle_workflow_error(e, user_input)
            return {
                "response": error_response,
                "waiting_for_input": False,
                "error": str(e)
            }

    def _extract_response(self, final_state: Dict[str, Any]) -> str:
        """Extract response from final state."""
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

        Args:
            user_input: User's query
            thread_id: Optional thread ID for conversation continuity
            callback: Async callback function(event_type, data) for events

        Returns:
            Dict with 'response', 'waiting_for_input', and 'clarification_prompt' if applicable
        """
        if thread_id:
            self.current_thread_id = thread_id

        async def emit_event(event_type: str, data: Dict[str, Any]):
            """Helper to emit events via callback."""
            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, data)
                else:
                    callback(event_type, data)

        print(f"🔍 处理用户请求: {user_input}")
        print("-" * 50)

        # Record user input in memory
        memory_manager.record_agent_action(
            agent_name="user",
            action="input",
            details={"text": user_input},
            importance=0.7
        )

        try:
            # Check if we're resuming from a clarification
            if self.workflow.is_waiting_for_input(self.current_thread_id):
                print("📌 检测到等待用户输入，恢复工作流...")
                await emit_event("step_start", {
                    "stepId": f"clarify-{thread_id}",
                    "agentType": "clarify",
                    "title": "继续澄清",
                    "description": "处理用户的澄清输入..."
                })
                # Use _resume_with_events to continue emitting events
                final_state = await self._resume_with_events(user_input, self.current_thread_id, emit_event)
                await emit_event("step_end", {
                    "stepId": f"clarify-{thread_id}"
                })
            else:
                # Start new workflow with event emission
                final_state = await self._process_workflow_with_events(user_input, emit_event)

            # Check if result contains interrupt information
            interrupt_info = self.workflow.check_interrupt_in_result(final_state)
            if interrupt_info:
                # Handle different interrupt_info formats
                if isinstance(interrupt_info, dict):
                    clarification_prompt = interrupt_info.get("prompt", "请提供更多信息")
                    missing_slots = interrupt_info.get("missing_slots", [])
                elif isinstance(interrupt_info, tuple):
                    # Tuple format: could be (key, value) or nested structure
                    if len(interrupt_info) >= 2:
                        second_item = interrupt_info[1]
                        if isinstance(second_item, dict):
                            clarification_prompt = second_item.get("prompt", "请提供更多信息")
                            missing_slots = second_item.get("missing_slots", [])
                        else:
                            clarification_prompt = str(second_item)
                            missing_slots = []
                    else:
                        clarification_prompt = str(interrupt_info[0]) if interrupt_info else "请提供更多信息"
                        missing_slots = []
                else:
                    clarification_prompt = str(interrupt_info) if interrupt_info else "请提供更多信息"
                    missing_slots = []
                print(f"⏸️ 工作流暂停，等待用户输入: {clarification_prompt}")

                memory_manager.record_agent_action(
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

            memory_manager.record_agent_action(
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

        except Exception as e:
            print(f"❌ 工作流执行错误: {e}")

            memory_manager.record_agent_action(
                agent_name="workflow",
                action="execution_error",
                details={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "fallback_used": True
                },
                importance=0.9
            )

            error_response = await self._handle_workflow_error(e, user_input)
            return {
                "response": error_response,
                "waiting_for_input": False,
                "error": str(e)
            }

    async def _process_workflow_with_events(
        self,
        user_input: str,
        emit_event: Callable[[str, Dict[str, Any]], None]
    ) -> Dict[str, Any]:
        """
        Process workflow with step-by-step event emission.

        Args:
            user_input: User's query
            emit_event: Callback to emit events

        Returns:
            Final state dict
        """
        from supply_chain_agent.graph.state import state_manager
        import time

        initial_state = state_manager.create_initial_state(user_input)
        actual_thread_id = self.current_thread_id
        config = {"configurable": {"thread_id": actual_thread_id}}

        # Define node execution order and metadata
        node_metadata = {
            "parse_input": {
                "agentType": "parse_input",
                "title": "解析用户意图",
                "description": "正在分析您的请求，提取关键信息..."
            },
            "clarify": {
                "agentType": "clarify",
                "title": "请求澄清",
                "description": "需要更多信息来处理您的请求..."
            },
            "plan_task": {
                "agentType": "plan_task",
                "title": "任务规划",
                "description": "正在制定执行计划..."
            },
            "execute_task": {
                "agentType": "execute_task",
                "title": "执行任务",
                "description": "正在调用工具执行任务..."
            },
            "retry": {
                "agentType": "retry",
                "title": "重试处理",
                "description": "正在重试失败的任务..."
            },
            "audit": {
                "agentType": "audit",
                "title": "审计结果",
                "description": "正在验证执行结果..."
            },
            "generate_report": {
                "agentType": "generate_report",
                "title": "生成报告",
                "description": "正在生成最终响应..."
            },
            "handle_error": {
                "agentType": "handle_error",
                "title": "错误处理",
                "description": "正在处理错误..."
            }
        }

        # Run the graph and track node transitions
        current_state = initial_state
        step_counter = 0

        # Stream the workflow execution
        async for event in self.workflow.graph.astream(initial_state, config=config):
            for node_name, node_output in event.items():
                if node_name == "__interrupt__":
                    # Handle interrupt for clarification
                    # Return properly formatted state with __interrupt__
                    if isinstance(node_output, tuple):
                        return {"__interrupt__": [node_output]}
                    elif isinstance(node_output, list):
                        return {"__interrupt__": node_output}
                    elif isinstance(node_output, dict):
                        return {"__interrupt__": [node_output]}
                    else:
                        return {"__interrupt__": [(node_output,)]}

                if node_name in node_metadata:
                    step_counter += 1
                    step_id = f"{node_name}-{step_counter}"
                    metadata = node_metadata[node_name]

                    # Emit step start
                    await emit_event("step_start", {
                        "stepId": step_id,
                        "agentType": metadata["agentType"],
                        "title": metadata["title"],
                        "description": metadata["description"]
                    })

                    # Check for tool results to report
                    if node_name == "execute_task" and isinstance(node_output, dict):
                        tool_results = node_output.get("tool_results", {})
                        for tool_name, tool_result in tool_results.items():
                            await emit_event("tool_call", {
                                "stepId": step_id,
                                "toolCall": {
                                    "id": f"tool-{tool_name}-{step_counter}",
                                    "name": tool_name,
                                    "parameters": {},
                                    "response": tool_result if isinstance(tool_result, dict) else {"result": str(tool_result)},
                                    "status": "success" if not (isinstance(tool_result, dict) and tool_result.get("error")) else "error",
                                    "startTime": int(time.time() * 1000),
                                    "endTime": int(time.time() * 1000)
                                }
                            })

                    # Emit step end
                    await emit_event("step_end", {
                        "stepId": step_id
                    })

                current_state = {**current_state, **node_output} if isinstance(node_output, dict) else current_state

        return current_state

    async def _resume_with_events(
        self,
        user_input: str,
        thread_id: str,
        emit_event: Callable[[str, Dict[str, Any]], None]
    ) -> Dict[str, Any]:
        """
        Resume workflow with step-by-step event emission.

        Args:
            user_input: User's clarification input
            thread_id: Thread ID to resume
            emit_event: Callback to emit events

        Returns:
            Final state dict
        """
        import time
        from langgraph.types import Command

        config = {"configurable": {"thread_id": thread_id}}

        # Define node execution order and metadata (same as _process_workflow_with_events)
        node_metadata = {
            "parse_input": {
                "agentType": "parse_input",
                "title": "解析用户意图",
                "description": "正在分析您的请求，提取关键信息..."
            },
            "clarify": {
                "agentType": "clarify",
                "title": "请求澄清",
                "description": "需要更多信息来处理您的请求..."
            },
            "plan_task": {
                "agentType": "plan_task",
                "title": "任务规划",
                "description": "正在制定执行计划..."
            },
            "execute_task": {
                "agentType": "execute_task",
                "title": "执行任务",
                "description": "正在调用工具执行任务..."
            },
            "retry": {
                "agentType": "retry",
                "title": "重试处理",
                "description": "正在重试失败的任务..."
            },
            "audit": {
                "agentType": "audit",
                "title": "审计结果",
                "description": "正在验证执行结果..."
            },
            "generate_report": {
                "agentType": "generate_report",
                "title": "生成报告",
                "description": "正在生成最终响应..."
            },
            "handle_error": {
                "agentType": "handle_error",
                "title": "错误处理",
                "description": "正在处理错误..."
            }
        }

        # Resume with Command
        step_counter = 0
        current_state = {}

        async for event in self.workflow.graph.astream(Command(resume=user_input), config=config):
            for node_name, node_output in event.items():
                if node_name == "__interrupt__":
                    # Handle interrupt for clarification
                    if isinstance(node_output, tuple):
                        return {"__interrupt__": [node_output]}
                    elif isinstance(node_output, list):
                        return {"__interrupt__": node_output}
                    elif isinstance(node_output, dict):
                        return {"__interrupt__": [node_output]}
                    else:
                        return {"__interrupt__": [(node_output,)]}

                if node_name in node_metadata:
                    step_counter += 1
                    step_id = f"{node_name}-{step_counter}"
                    metadata = node_metadata[node_name]

                    # Emit step start
                    await emit_event("step_start", {
                        "stepId": step_id,
                        "agentType": metadata["agentType"],
                        "title": metadata["title"],
                        "description": metadata["description"]
                    })

                    # Check for tool results to report
                    if node_name == "execute_task" and isinstance(node_output, dict):
                        tool_results = node_output.get("tool_results", {})
                        for tool_name, tool_result in tool_results.items():
                            await emit_event("tool_call", {
                                "stepId": step_id,
                                "toolCall": {
                                    "id": f"tool-{tool_name}-{step_counter}",
                                    "name": tool_name,
                                    "parameters": {},
                                    "response": tool_result if isinstance(tool_result, dict) else {"result": str(tool_result)},
                                    "status": "success" if not (isinstance(tool_result, dict) and tool_result.get("error")) else "error",
                                    "startTime": int(time.time() * 1000),
                                    "endTime": int(time.time() * 1000)
                                }
                            })

                    # Emit step end
                    await emit_event("step_end", {
                        "stepId": step_id
                    })

                current_state = {**current_state, **node_output} if isinstance(node_output, dict) else current_state

        return current_state

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
        """Handle workflow execution error."""
        print(f"工作流错误处理: {error}")

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
                        except Exception as e:
                            results[task] = {"error": str(e)}

                    # Generate simple response
                    if "query_order_status" in results:
                        order_data = results["query_order_status"]
                        if "error" not in order_data:
                            return (
                                f"✅ 简易查询完成\n\n"
                                f"订单号: {order_data.get('order_id', 'N/A')}\n"
                                f"状态: {order_data.get('status', 'N/A')}\n"
                                f"备注: 使用简化模式处理"
                            )

            return "🔄 系统正在维护中，请稍后重试。"

        except Exception as fallback_error:
            return f"❌ 系统暂时无法处理您的请求。错误: {str(fallback_error)[:100]}"
