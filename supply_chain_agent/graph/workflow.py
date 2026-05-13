"""
LangGraph Workflow definition for Supply Chain Agent.

Defines the graph structure and nodes for multi-agent collaboration.
"""

from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from supply_chain_agent.graph.state import AgentState, state_manager


class SupplyChainWorkflow:
    """Main workflow graph for Supply Chain Agent."""

    def __init__(self, orchestrator: Optional['OrchestratorAgent'] = None):
        """
        Initialize workflow with optional orchestrator for dependency injection.

        Args:
            orchestrator: OrchestratorAgent instance for shared agent access
        """
        self.orchestrator = orchestrator
        self.checkpointer = MemorySaver()
        self.workflow = StateGraph(AgentState)
        self.setup_nodes()
        self.setup_edges()
        self.graph = self.workflow.compile(checkpointer=self.checkpointer)

    def setup_nodes(self):
        """Setup all nodes in the graph."""

        # Node 1: Parser Agent (解析师)
        async def parse_input_node(state: AgentState) -> Dict[str, Any]:
            """Parse user intent and extract information."""
            print("[进入节点: parse_input - 解析师节点]")
            # Use shared parser instance from orchestrator
            parser = self.orchestrator.parser if self.orchestrator else None
            if parser is None:
                from supply_chain_agent.agents.parser import ParserAgent
                parser = ParserAgent()

            user_input = state["messages"][-1]["content"]

            try:
                intent = await parser.parse_intent(user_input)

                # Extract entities into slots
                extracted_slots = {}
                if "entities" in intent:
                    for entity in intent["entities"]:
                        if isinstance(entity, dict) and "type" in entity and "value" in entity:
                            extracted_slots[entity["type"]] = entity["value"]

                # Check for missing slots
                missing_slots = []
                if "required_slots" in intent:
                    for slot in intent["required_slots"]:
                        if slot not in extracted_slots:
                            missing_slots.append(slot)

                return {
                    "user_intent": intent,
                    "extracted_slots": extracted_slots,
                    "missing_slots": missing_slots,
                    "context_window": state.get("context_window", []) + [
                        {"agent": "parse_input", "action": "parsed_intent", "intent": intent}
                    ]
                }

            except Exception as e:
                return {
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Parser error: {e}",
                    "validation_errors": state.get("validation_errors", []) + [f"Parser error: {e}"],
                }

        # Node 2: Clarification Handler
        async def clarify_node(state: AgentState) -> Dict[str, Any]:
            """Handle missing information by asking for clarification."""
            print("[进入节点: clarify - 澄清节点]")

            # 获取当前循环计数
            current_loop_count = state.get("clarification_loop_count", 0)

            # 检查澄清循环计数，达到3次直接跳转到handle_error
            if current_loop_count >= 3:
                print(f"[澄清节点] 已达到最大循环次数 (3次)，跳转到handle_error")
                return {
                    "missing_slots": [],
                    "clarification_loop_count": current_loop_count,
                    "max_clarification_reached": True,
                    "messages": state.get("messages", []) + [{
                        "role": "assistant",
                        "content": "抱歉，已多次尝试获取信息但未能成功。请稍后重试或联系客服人员。"
                    }],
                    "context_window": state.get("context_window", []) + [
                        {"agent": "clarify", "action": "max_loops_reached", "count": current_loop_count}
                    ]
                }

            # Increment loop count
            new_loop_count = current_loop_count + 1
            print(f"[澄清节点] 当前循环次数: {new_loop_count}/3")

            # Use shared parser instance from orchestrator
            parser = self.orchestrator.parser if self.orchestrator else None
            if parser is None:
                from supply_chain_agent.agents.parser import ParserAgent
                parser = ParserAgent()

            # Request clarification from user (使用 interrupt 等待用户输入)
            if state.get("missing_slots"):
                response = await parser.request_clarification(state["missing_slots"])

                # Use interrupt to pause execution and wait for user input
                interrupt_data = {
                    "type": "clarification_required",
                    "prompt": response,
                    "missing_slots": state["missing_slots"],
                    "loop_count": new_loop_count
                }
                user_input = interrupt(interrupt_data)

                # 正常返回，跳转 parse_input 重新解析
                return {
                    "messages": state.get("messages", []) + [
                        {"role": "assistant", "content": response},
                        {"role": "user", "content": user_input}
                    ],
                    "clarification_loop_count": new_loop_count,
                    "waiting_for_input": False,
                    "context_window": state.get("context_window", []) + [
                        {"agent": "clarify", "action": "requested_clarification", "user_input": user_input, "loop_count": new_loop_count}
                    ]
                }

            # No missing slots, should not reach here normally
            return {
                "waiting_for_input": False,
                "clarification_loop_count": new_loop_count
            }

        # Node 3: Task Planner
        async def plan_task_node(state: AgentState) -> Dict[str, Any]:
            """Plan execution tasks based on intent."""
            print("[进入节点: plan_task - 任务规划节点]")

            try:
                # Use shared executor instance from orchestrator
                if self.orchestrator:
                    tasks = await self.orchestrator.executor.create_execution_plan(state.get("user_intent", {}))
                else:
                    from supply_chain_agent.agents.executor import ExecutorAgent
                    executor = ExecutorAgent()
                    tasks = await executor.create_execution_plan(state.get("user_intent", {}))

                return {
                    "task_queue": tasks,
                    "current_task": tasks[0] if tasks else None,
                    "context_window": state.get("context_window", []) + [
                        {"agent": "plan_task", "action": "created_plan", "tasks": tasks}
                    ]
                }

            except Exception as e:
                return {
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Task planning error: {e}",
                    "validation_errors": state.get("validation_errors", []) + [f"Task planning error: {e}"],
                }

        # Node 4: Executor Agent (调度员)
        async def execute_task_node(state: AgentState) -> Dict[str, Any]:
            """Execute tasks using tools."""
            print("[进入节点: execute_task - 执行器节点]")

            # Use shared executor instance from orchestrator
            executor = self.orchestrator.executor if self.orchestrator else None
            if executor is None:
                from supply_chain_agent.agents.executor import ExecutorAgent
                executor = ExecutorAgent()

            if not state.get("task_queue"):
                return {"execution_complete": True}

            try:
                task = state["task_queue"][0]
                result = await executor.execute_task(task, state.get("extracted_slots", {}))

                # Build updated state fields
                new_tool_results = {**state.get("tool_results", {}), task: result}
                new_task_queue = state["task_queue"][1:]

                updates = {
                    "tool_results": new_tool_results,
                    "task_queue": new_task_queue,
                }

                if new_task_queue:
                    updates["current_task"] = new_task_queue[0]
                else:
                    updates["current_task"] = None
                    updates["execution_complete"] = True

                # Add to context
                context_item = {"agent": "execute_task", "action": "executed_task", "task": task, "result": result}
                updates["context_window"] = state.get("context_window", []) + [context_item]

                return updates

            except Exception as e:
                # Add error
                updates = {
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Execution error: {e}",
                    "validation_errors": state.get("validation_errors", []) + [f"Execution error: {e}"],
                }

                # Check if we should retry
                if state.get("error_count", 0) < 3:
                    return updates  # Will go to retry handler
                else:
                    updates["execution_failed"] = True
                    return updates

        # Node 5: Retry Handler
        async def retry_node(state: AgentState) -> Dict[str, Any]:
            """Handle retry logic for failed tasks."""
            print("[进入节点: retry - 重试处理节点]")
            if state.get("error_count", 0) < 3:
                return {
                    "error_count": 0,
                    "last_error": None,
                    "validation_errors": [],
                    "should_retry": True
                }
            else:
                return {
                    "should_retry": False,
                    "execution_failed": True
                }

        # Node 6: Auditor Agent (审计员)
        async def audit_node(state: AgentState) -> Dict[str, Any]:
            """Audit tool execution results."""
            print("[进入节点: audit - 审计员节点]")

            # Use shared auditor instance from orchestrator
            auditor = self.orchestrator.auditor if self.orchestrator else None
            if auditor is None:
                from supply_chain_agent.agents.auditor import AuditorAgent
                auditor = AuditorAgent()

            try:
                audit = await auditor.audit_results(state.get("tool_results", {}))
                return {
                    "audit_results": audit,
                    "context_window": state.get("context_window", []) + [
                        {"agent": "audit", "action": "audited_results", "audit": audit}
                    ]
                }

            except Exception as e:
                return {
                    "audit_results": {"passed": False, "issues": [str(e)]},
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Audit error: {e}",
                }

        # Node 7: Report Generator
        async def generate_report_node(state: AgentState) -> Dict[str, Any]:
            """Generate final report and response card."""
            print("[进入节点: generate_report - 报告生成节点]")

            # Use shared report_generator instance from orchestrator
            report_generator = self.orchestrator.report_generator if self.orchestrator else None
            if report_generator is None:
                from supply_chain_agent.agents.report_generator import ReportGenerator
                report_generator = ReportGenerator()

            try:
                # Check if there were any tool errors
                tool_results = state.get("tool_results", {})
                error_messages = []
                for tool_name, result in tool_results.items():
                    if isinstance(result, dict):
                        if result.get("error") or result.get("success") == False:
                            # Extract user-friendly error message
                            error_detail = result.get("error", "未知错误")
                            # Clean up error message
                            if "Order" in error_detail and "not found" in error_detail:
                                # Extract order ID from error
                                import re
                                match = re.search(r'Order (\S+) not found', error_detail)
                                if match:
                                    order_id = match.group(1)
                                    error_messages.append(f"订单 **{order_id}** 不存在，请检查订单号是否正确")
                                else:
                                    error_messages.append("查询的订单不存在，请检查订单号是否正确")
                            elif "Tracking" in error_detail or "tracking" in error_detail.lower():
                                error_messages.append("查询的运单不存在，请检查运单号是否正确")
                            else:
                                error_messages.append(f"**{tool_name}**: {error_detail}")

                # If there were errors, generate error response
                if error_messages:
                    error_response = "⚠️ **查询结果**\n\n"
                    error_response += "\n".join(f"- {msg}" for msg in error_messages)
                    error_response += "\n\n**建议**：\n"
                    error_response += "1. 检查输入的订单号/运单号是否正确\n"
                    error_response += "2. 确认订单是否已创建\n"
                    error_response += "3. 如有疑问，请联系客服人员"

                    return {
                        "final_report": {"summary": error_response, "errors": error_messages},
                        "response_card": {"summary": error_response},
                        "messages": state.get("messages", []) + [{
                            "role": "assistant",
                            "content": error_response
                        }],
                        "context_window": state.get("context_window", []) + [
                            {"agent": "generate_report", "action": "generated_error_report", "errors": error_messages}
                        ]
                    }

                report = await report_generator.generate_report(
                    state.get("user_intent", {}),
                    state.get("tool_results", {}),
                    state.get("audit_results", {})
                )

                card = await report_generator.generate_response_card(report)

                return {
                    "final_report": report,
                    "response_card": card,
                    "messages": state.get("messages", []) + [{
                        "role": "assistant",
                        "content": card.get("summary", "处理完成")
                    }],
                    "context_window": state.get("context_window", []) + [
                        {"agent": "generate_report", "action": "generated_report", "report": report}
                    ]
                }

            except Exception as e:
                return {
                    "messages": state.get("messages", []) + [{
                        "role": "assistant",
                        "content": f"抱歉，系统在处理您的请求时遇到问题：{str(e)}\n\n建议联系客服进行人工处理。"
                    }],
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Report generation error: {e}",
                }

        # Node 8: Error Handler
        async def handle_error_node(state: AgentState) -> Dict[str, Any]:
            """Handle errors and generate appropriate responses."""
            print("[进入节点: handle_error - 错误处理节点]")
            last_error = state.get("last_error")
            error_count = state.get("error_count", 0)

            # Generate error response based on error type
            if error_count >= 3:
                response = "⚠️ **系统遇到多次错误**\n\n"
            else:
                response = "🔄 **系统暂时遇到问题**\n\n"

            if last_error:
                response += f"**错误详情**: {last_error}\n\n"
            else:
                response += "**错误详情**: 未知错误\n\n"

            response += "如果问题持续，请稍后重试或联系技术支持。"

            return {
                "messages": state.get("messages", []) + [{
                    "role": "assistant",
                    "content": response
                }],
                "context_window": state.get("context_window", []) + [
                    {"agent": "handle_error", "action": "handled_error", "error": last_error}
                ]
            }

        # Add all nodes to the graph
        self.workflow.add_node("parse_input", parse_input_node)
        self.workflow.add_node("clarify", clarify_node)
        self.workflow.add_node("plan_task", plan_task_node)
        self.workflow.add_node("execute_task", execute_task_node)
        self.workflow.add_node("retry", retry_node)
        self.workflow.add_node("audit", audit_node)
        self.workflow.add_node("generate_report", generate_report_node)
        self.workflow.add_node("handle_error", handle_error_node)

    def setup_edges(self):
        """Setup edges between nodes."""

        # Start with parse_input
        self.workflow.set_entry_point("parse_input")

        # From parse_input, check if clarification is needed
        self.workflow.add_conditional_edges(
            "parse_input",
            self._check_clarification_needed,
            {
                "needs_clarification": "clarify",
                "no_clarification": "plan_task"
            }
        )

        # From clarify, check if max loops reached or continue to parse_input
        self.workflow.add_conditional_edges(
            "clarify",
            self._check_clarification_result,
            {
                "continue": "parse_input",
                "max_loops_reached": "handle_error"
            }
        )

        # From task planner, check if ready for execution
        self.workflow.add_conditional_edges(
            "plan_task",
            self._check_ready_for_execution,
            {
                "ready": "execute_task",
                "not_ready": "handle_error",
                "skip_to_report": "generate_report"
            }
        )

        # From execute_task, check next step
        self.workflow.add_conditional_edges(
            "execute_task",
            self._check_execution_status,
            {
                "continue_execution": "execute_task",  # Loop back for next task
                "execution_complete": "audit",
                "execution_failed": "retry"
            }
        )

        # From retry handler, decide next step
        self.workflow.add_conditional_edges(
            "retry",
            self._check_retry_status,
            {
                "retry": "execute_task",
                "abort": "handle_error"
            }
        )

        # From audit, check audit result
        self.workflow.add_conditional_edges(
            "audit",
            self._check_audit_result,
            {
                "audit_passed": "generate_report",
                "audit_failed": "handle_error"
            }
        )

        # From report generator, end
        self.workflow.add_edge("generate_report", END)

        # From error handler, end
        self.workflow.add_edge("handle_error", END)

    def _check_clarification_needed(self, state: AgentState) -> str:
        """Check if clarification is needed."""
        # If missing slots exist, need clarification
        if len(state.get("missing_slots", [])) > 0:
            return "needs_clarification"
        else:
            return "no_clarification"

    def _check_clarification_result(self, state: AgentState) -> str:
        """Check clarification result to determine next step."""
        # If max clarification loops reached, go to error handler
        if state.get("max_clarification_reached", False):
            return "max_loops_reached"
        # Otherwise, continue to parse_input for re-parsing
        return "continue"

    def _check_ready_for_execution(self, state: AgentState) -> str:
        """Check if ready for execution."""
        # If still have missing slots, go to error handler
        if state.get("missing_slots"):
            return "not_ready"
        # If no task queue or empty task queue, skip to report
        task_queue = state.get("task_queue", [])
        if not task_queue or len(task_queue) == 0:
            return "skip_to_report"
        # If we have intent and tasks, we're ready
        if state.get("user_intent"):
            return "ready"
        return "skip_to_report"

    def _check_execution_status(self, state: AgentState) -> str:
        """Check execution status."""
        # Check if execution failed
        if state.get("execution_failed", False):
            return "execution_failed"

        # Check if execution is complete (no more tasks in queue)
        task_queue = state.get("task_queue", [])
        if not task_queue or state.get("execution_complete", False):
            return "execution_complete"

        # Still have tasks to execute
        return "continue_execution"

    def _check_retry_status(self, state: AgentState) -> str:
        """Check retry status."""
        if state.get("should_retry", False):
            return "retry"
        else:
            return "abort"

    def _check_audit_result(self, state: AgentState) -> str:
        """Check audit result."""
        audit_results = state.get("audit_results", {})
        if audit_results.get("passed", False):
            return "audit_passed"
        else:
            return "audit_failed"

    async def process(self, user_input: str, config: Optional[Dict[str, Any]] = None,
                      thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process user input through the workflow.

        Args:
            user_input: User's query
            config: Optional configuration for the graph
            thread_id: Optional thread ID for conversation continuity

        Returns:
            Final state after processing, may contain __interrupt__ for clarification
        """
        actual_thread_id = thread_id or "default"
        actual_config = config or {"configurable": {"thread_id": actual_thread_id}}

        initial_state = state_manager.create_initial_state(user_input)

        # Run the graph
        final_state = await self.graph.ainvoke(
            initial_state,
            config=actual_config
        )

        return final_state

    async def resume(self, user_input: str, thread_id: str = "default") -> Dict[str, Any]:
        """
        Resume workflow execution after user provides clarification input.

        Args:
            user_input: User's clarification input
            thread_id: Thread ID for the conversation to resume

        Returns:
            Final state after processing
        """
        config = {"configurable": {"thread_id": thread_id}}

        # Resume the graph with the user's input as Command to update state
        from langgraph.types import Command
        final_state = await self.graph.ainvoke(
            Command(resume=user_input),
            config=config
        )

        return final_state

    def get_state(self, thread_id: str = "default") -> Optional[Dict[str, Any]]:
        """
        Get current state for a thread.

        Args:
            thread_id: Thread ID to get state for

        Returns:
            Current state or None if not found
        """
        config = {"configurable": {"thread_id": thread_id}}
        state_snapshot = self.graph.get_state(config)
        if state_snapshot:
            return state_snapshot.values
        return None

    def is_waiting_for_input(self, thread_id: str = "default") -> bool:
        """
        Check if workflow is waiting for user input (interrupted).

        Args:
            thread_id: Thread ID to check

        Returns:
            True if waiting for input, False otherwise
        """
        config = {"configurable": {"thread_id": thread_id}}
        state_snapshot = self.graph.get_state(config)
        if state_snapshot and state_snapshot.next:
            # If there are pending nodes, check if it's due to interrupt
            return True
        return False

    def get_interrupt_info(self, thread_id: str = "default") -> Optional[Dict[str, Any]]:
        """
        Get interrupt information if workflow is paused.

        Args:
            thread_id: Thread ID to check

        Returns:
            Interrupt info dict or None
        """
        config = {"configurable": {"thread_id": thread_id}}
        state_snapshot = self.graph.get_state(config)
        if state_snapshot and hasattr(state_snapshot, 'values'):
            # Check for __interrupt__ in state values
            interrupts = state_snapshot.values.get('__interrupt__')
            if interrupts:
                # Return the first interrupt info
                for interrupt in interrupts:
                    # Handle different interrupt formats
                    if hasattr(interrupt, 'value'):
                        return interrupt.value
                    elif isinstance(interrupt, dict):
                        return interrupt
                    elif isinstance(interrupt, tuple) and len(interrupt) >= 2:
                        return interrupt[1] if isinstance(interrupt[1], dict) else {"prompt": str(interrupt[1])}
                    else:
                        try:
                            return dict(interrupt) if interrupt else None
                        except (TypeError, ValueError):
                            return {"prompt": str(interrupt)} if interrupt else None
        return None

    def check_interrupt_in_result(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check if result contains interrupt information.

        Args:
            result: The workflow result from ainvoke

        Returns:
            Interrupt info dict or None
        """
        interrupts = result.get('__interrupt__')
        if interrupts:
            # Return the first interrupt info
            for interrupt in interrupts:
                # Handle different interrupt formats
                # LangGraph Interrupt object has a 'value' attribute
                if hasattr(interrupt, 'value'):
                    return interrupt.value
                # Handle tuple format: (Interrupt(...),) - the interrupt itself is the tuple element
                elif isinstance(interrupt, tuple):
                    # If tuple contains Interrupt objects
                    for item in interrupt:
                        if hasattr(item, 'value'):
                            return item.value
                        elif isinstance(item, dict):
                            return item
                    # Fallback: return the tuple as dict if possible
                    if len(interrupt) >= 2:
                        return interrupt[1] if isinstance(interrupt[1], dict) else {"prompt": str(interrupt[1])}
                    return {"prompt": str(interrupt[0]) if interrupt else "请提供更多信息"}
                elif isinstance(interrupt, dict):
                    return interrupt
                else:
                    # Fallback: try to convert to dict or return as string
                    try:
                        return dict(interrupt) if interrupt else None
                    except (TypeError, ValueError):
                        return {"prompt": str(interrupt)} if interrupt else None
        return None

    def get_graph_info(self) -> Dict[str, Any]:
        """Get information about the graph structure."""
        # For now, return a simplified representation
        # LangGraph's CompiledStateGraph doesn't expose entry_point directly
        return {
            "nodes": list(self.graph.nodes),
            "edges": self._get_edge_info(),
            "entry_point": "START"  # Hardcode entry point for now
        }

    def _get_edge_info(self) -> Dict[str, Any]:
        """Get information about edges."""
        # This is a simplified representation
        edges = {}
        for node in self.graph.nodes:
            edges[node] = []
            # In LangGraph, we'd need to inspect the graph structure
            # For now, return placeholder
        return edges


# Global workflow instance (lazy initialization)
_workflow_instance: Optional[SupplyChainWorkflow] = None


def get_workflow(orchestrator: Optional['OrchestratorAgent'] = None) -> SupplyChainWorkflow:
    """
    Get or create workflow instance.

    Args:
        orchestrator: OrchestratorAgent instance for shared agent access

    Returns:
        SupplyChainWorkflow instance
    """
    global _workflow_instance
    if _workflow_instance is None or orchestrator is not None:
        _workflow_instance = SupplyChainWorkflow(orchestrator)
    return _workflow_instance


# Backward compatibility: global workflow property
class _WorkflowProxy:
    """Proxy for backward compatibility with global workflow access."""
    def __getattr__(self, name):
        return getattr(get_workflow(), name)


workflow = _WorkflowProxy()
