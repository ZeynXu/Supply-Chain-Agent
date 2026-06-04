"""
LangGraph Workflow definition for Supply Chain Agent.

Defines the graph structure and nodes for multi-agent collaboration.
"""

from typing import Dict, Any, Optional, List, Callable
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
import traceback
import asyncio
import time

from supply_chain_agent.graph.state import AgentState, state_manager

# H6修复：导入具体异常类型
from supply_chain_agent.common.exceptions import (
    SupplyChainError,
    RecoverableError,
    UnrecoverableError,
    ValidationError,
    IntentParseError,
    ToolExecutionError,
    CircuitBreakerOpenError,
    ExecutionPlanError,
    ClarificationMaxAttemptsError,
    is_recoverable,
    wrap_exception,
)


class SupplyChainWorkflow:
    """Main workflow graph for Supply Chain Agent."""

    def __init__(
        self,
        parser=None,
        executor=None,
        auditor=None,
        report_generator=None
    ):
        """
        Initialize workflow with agent dependencies (dependency injection).

        Args:
            parser: ParserAgent instance for intent parsing
            executor: ExecutorAgent instance for task execution
            auditor: AuditorAgent instance for result auditing
            report_generator: ReportGenerator instance for report generation
        """
        # 直接注入需要的 agents，而不是依赖 Orchestrator
        self.parser = parser
        self.executor = executor
        self.auditor = auditor
        self.report_generator = report_generator

        self.checkpointer = MemorySaver()
        self.workflow = StateGraph(AgentState)
        self.setup_nodes()
        self.setup_edges()
        self.graph = self.workflow.compile(checkpointer=self.checkpointer)

    # ============== M16修复：节点函数提取为类方法 ==============

    async def _parse_input_node(self, state: AgentState) -> Dict[str, Any]:
        """Parse user intent and extract information.

        M16修复：从setup_nodes内部提取为类方法，便于测试和复用。
        """
        print("[进入节点: parse_input - 解析师节点]")
        # Use injected parser instance
        parser = self.parser
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
                "clarification_loop_count": 0,  # 成功解析后重置澄清循环计数器
                "context_window": state.get("context_window", []) + [
                    {"agent": "parse_input", "action": "parsed_intent", "intent": intent}
                ]
            }

        # H6修复：区分异常类型
        except IntentParseError as e:
            return {
                "error_count": state.get("error_count", 0) + 1,
                "last_error": f"Intent parse error: {e}",
                "last_error_type": "IntentParseError",
                "last_error_trace": traceback.format_exc(),
                "validation_errors": state.get("validation_errors", []) + [str(e)],
                "is_recoverable": True,
            }
        except ValidationError as e:
            return {
                "error_count": state.get("error_count", 0) + 1,
                "last_error": f"Validation error: {e}",
                "last_error_type": "ValidationError",
                "last_error_trace": traceback.format_exc(),
                "validation_errors": state.get("validation_errors", []) + [str(e)],
                "is_recoverable": False,
            }
        except Exception as e:
            wrapped = wrap_exception(e, {"node": "parse_input"})
            return {
                "error_count": state.get("error_count", 0) + 1,
                "last_error": f"{type(wrapped).__name__}: {e}",
                "last_error_type": type(wrapped).__name__,
                "last_error_trace": traceback.format_exc(),
                "validation_errors": state.get("validation_errors", []) + [str(e)],
                "is_recoverable": is_recoverable(wrapped),
            }

    async def _clarify_node(self, state: AgentState) -> Dict[str, Any]:
        """Handle missing information by asking for clarification.

        M16修复：从setup_nodes内部提取为类方法，便于测试和复用。
        """
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

        # Use injected parser instance
        parser = self.parser
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

    async def _plan_task_node(self, state: AgentState) -> Dict[str, Any]:
        """Plan execution tasks based on intent.

        M16修复：从setup_nodes内部提取为类方法，便于测试和复用。
        """
        print("[进入节点: plan_task - 任务规划节点]")

        try:
            # Use injected executor instance
            if self.executor:
                tasks = await self.executor.create_execution_plan(state.get("user_intent", {}))
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

        except ExecutionPlanError as e:
            return {
                "error_count": state.get("error_count", 0) + 1,
                "last_error": f"Execution plan error: {e}",
                "last_error_type": "ExecutionPlanError",
                "last_error_trace": traceback.format_exc(),
                "validation_errors": state.get("validation_errors", []) + [str(e)],
                "is_recoverable": False,
            }
        except ValidationError as e:
            return {
                "error_count": state.get("error_count", 0) + 1,
                "last_error": f"Validation error: {e}",
                "last_error_type": "ValidationError",
                "last_error_trace": traceback.format_exc(),
                "validation_errors": state.get("validation_errors", []) + [str(e)],
                "is_recoverable": False,
            }
        except Exception as e:
            wrapped = wrap_exception(e, {"node": "plan_task"})
            return {
                "error_count": state.get("error_count", 0) + 1,
                "last_error": f"{type(wrapped).__name__}: {e}",
                "last_error_type": type(wrapped).__name__,
                "last_error_trace": traceback.format_exc(),
                "validation_errors": state.get("validation_errors", []) + [str(e)],
                "is_recoverable": is_recoverable(wrapped),
            }

    async def _execute_task_node(self, state: AgentState) -> Dict[str, Any]:
        """Execute tasks using tools.

        M16修复：从setup_nodes内部提取为类方法，便于测试和复用。
        """
        print("[进入节点: execute_task - 执行器节点]")

        # Use injected executor instance
        executor = self.executor
        if executor is None:
            from supply_chain_agent.agents.executor import ExecutorAgent
            executor = ExecutorAgent()

        if not state.get("task_queue"):
            return {"execution_complete": True}

        # M8修复：改进链式执行模式判断逻辑
        user_intent = state.get("user_intent", {})
        intent_level_2 = user_intent.get("intent_level_2", "")
        task_queue = state.get("task_queue", [])

        TOOL_DEPENDENCIES = {
            "approve_work_order": ["query_work_order"],
        }

        def _needs_chain_execution(tasks: List[str], intent: str) -> bool:
            if intent == "审批工单":
                return True
            if state.get("use_chain_execution", False):
                return True
            task_names = [t.get("name", t) if isinstance(t, dict) else t for t in tasks]
            for task in task_names:
                if task in TOOL_DEPENDENCIES:
                    deps = TOOL_DEPENDENCIES[task]
                    if any(dep in task_names for dep in deps):
                        return True
            return False

        use_chain_execution = _needs_chain_execution(task_queue, intent_level_2)

        try:
            if use_chain_execution and len(state.get("task_queue", [])) > 1:
                print(f"🔗 使用链式执行模式，执行计划: {state.get('task_queue', [])}")

                chain_result = await executor.execute_plan_with_llm_feedback(
                    execution_plan=state.get("task_queue", []),
                    initial_slots=state.get("extracted_slots", {}),
                    intent=user_intent
                )

                updates = {
                    "tool_results": chain_result.get("results", {}),
                    "task_queue": [],
                    "current_task": None,
                    "execution_complete": chain_result.get("success", False),
                    "chain_execution_result": chain_result,
                }

                if not chain_result.get("success", False):
                    updates["execution_failed"] = True
                    updates["error_count"] = state.get("error_count", 0) + 1
                    updates["last_error"] = chain_result.get("error", "链式执行失败")

                context_item = {
                    "agent": "execute_task",
                    "action": "chain_execution",
                    "plan": state.get("task_queue", []),
                    "result": chain_result
                }
                updates["context_window"] = state.get("context_window", []) + [context_item]

                return updates

            # 普通执行模式
            task = state["task_queue"][0]
            result = await executor.execute_task(task, state.get("extracted_slots", {}))

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

            context_item = {"agent": "execute_task", "action": "executed_task", "task": task, "result": result}
            updates["context_window"] = state.get("context_window", []) + [context_item]

            return updates

        except ToolExecutionError as e:
            updates = {
                "error_count": state.get("error_count", 0) + 1,
                "last_error": f"Tool execution error: {e}",
                "last_error_type": "ToolExecutionError",
                "last_error_trace": traceback.format_exc(),
                "validation_errors": state.get("validation_errors", []) + [str(e)],
                "is_recoverable": True,
            }
            if state.get("error_count", 0) < 3:
                return updates
            else:
                updates["execution_failed"] = True
                return updates
        except CircuitBreakerOpenError as e:
            updates = {
                "error_count": state.get("error_count", 0) + 1,
                "last_error": f"Circuit breaker open: {e}",
                "last_error_type": "CircuitBreakerOpenError",
                "last_error_trace": traceback.format_exc(),
                "is_recoverable": True,
                "circuit_breaker_recovery_time": e.recovery_time,
            }
            updates["execution_failed"] = True
            return updates
        except RecoverableError as e:
            updates = {
                "error_count": state.get("error_count", 0) + 1,
                "last_error": f"Recoverable error: {e}",
                "last_error_type": type(e).__name__,
                "last_error_trace": traceback.format_exc(),
                "is_recoverable": True,
            }
            if state.get("error_count", 0) < 3:
                return updates
            else:
                updates["execution_failed"] = True
                return updates
        except UnrecoverableError as e:
            return {
                "error_count": state.get("error_count", 0) + 1,
                "last_error": f"Unrecoverable error: {e}",
                "last_error_type": type(e).__name__,
                "last_error_trace": traceback.format_exc(),
                "is_recoverable": False,
                "execution_failed": True,
            }
        except Exception as e:
            wrapped = wrap_exception(e, {"node": "execute_task", "task": state.get("current_task")})
            updates = {
                "error_count": state.get("error_count", 0) + 1,
                "last_error": f"{type(wrapped).__name__}: {e}",
                "last_error_type": type(wrapped).__name__,
                "last_error_trace": traceback.format_exc(),
                "validation_errors": state.get("validation_errors", []) + [str(e)],
                "is_recoverable": is_recoverable(wrapped),
            }
            if state.get("error_count", 0) < 3:
                return updates
            else:
                updates["execution_failed"] = True
                return updates

    async def _retry_node(self, state: AgentState) -> Dict[str, Any]:
        """Handle retry logic for failed tasks.

        M16修复：从setup_nodes内部提取为类方法，便于测试和复用。
        """
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

    async def _audit_node(self, state: AgentState) -> Dict[str, Any]:
        """Audit tool execution results.

        M16修复：从setup_nodes内部提取为类方法，便于测试和复用。
        """
        print("[进入节点: audit - 审计员节点]")

        auditor = self.auditor
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

        except SupplyChainError as e:
            return {
                "audit_results": {"passed": False, "issues": [str(e)]},
                "error_count": state.get("error_count", 0) + 1,
                "last_error": f"Audit error: {e}",
                "last_error_type": type(e).__name__,
                "last_error_trace": traceback.format_exc(),
                "is_recoverable": is_recoverable(e),
            }
        except Exception as e:
            wrapped = wrap_exception(e, {"node": "audit"})
            return {
                "audit_results": {"passed": False, "issues": [str(e)]},
                "error_count": state.get("error_count", 0) + 1,
                "last_error": f"Audit error: {wrapped}",
                "last_error_type": type(wrapped).__name__,
                "last_error_trace": traceback.format_exc(),
                "is_recoverable": is_recoverable(wrapped),
            }

    async def _generate_report_node(self, state: AgentState) -> Dict[str, Any]:
        """Generate final report and response card.

        M16修复：从setup_nodes内部提取为类方法，便于测试和复用。
        L4/L5修复：重构长函数，使用辅助方法减少嵌套层级。
        """
        print("[进入节点: generate_report - 报告生成节点]")

        report_generator = self._get_report_generator()

        if state.get("from_error_handler", False):
            print("[报告生成节点] 处理来自错误处理节点的请求")
            error_code = state.get("error_code", "GENERAL_FALLBACK")
            template_params = state.get("error_template_params", {})
            return await self._handle_error_response(state, report_generator, error_code, template_params)

        try:
            tool_results = state.get("tool_results", {})
            extracted_slots = state.get("extracted_slots", {})

            error_responses = await self._collect_tool_errors(
                tool_results, extracted_slots, report_generator, state
            )

            if error_responses:
                return self._build_error_report(error_responses, state)

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

        except SupplyChainError as e:
            error_code = "WORKFLOW_EXECUTION_FAILED"
            fallback_response = await report_generator.generate_fallback_response(
                error_code,
                trace_id=str(hash(str(e)))
            )
            return {
                "messages": state.get("messages", []) + [{
                    "role": "assistant",
                    "content": fallback_response.get("message", f"抱歉，系统在处理您的请求时遇到问题：{str(e)}")
                }],
                "error_count": state.get("error_count", 0) + 1,
                "last_error": f"Report generation error: {e}",
                "last_error_type": type(e).__name__,
                "last_error_trace": traceback.format_exc(),
                "error_code": error_code,
                "is_recoverable": is_recoverable(e),
            }
        except Exception as e:
            wrapped = wrap_exception(e, {"node": "generate_report"})
            error_code = "WORKFLOW_EXECUTION_FAILED"
            fallback_response = await report_generator.generate_fallback_response(
                error_code,
                trace_id=str(hash(str(e)))
            )
            return {
                "messages": state.get("messages", []) + [{
                    "role": "assistant",
                    "content": fallback_response.get("message", f"抱歉，系统在处理您的请求时遇到问题：{str(e)}")
                }],
                "error_count": state.get("error_count", 0) + 1,
                "last_error": f"{type(wrapped).__name__}: {e}",
                "last_error_type": type(wrapped).__name__,
                "last_error_trace": traceback.format_exc(),
                "error_code": error_code,
                "is_recoverable": is_recoverable(wrapped),
            }

    async def _handle_error_node(self, state: AgentState) -> Dict[str, Any]:
        """Handle errors and generate error code for report generation.

        M16修复：从setup_nodes内部提取为类方法，便于测试和复用。
        """
        print("[进入节点: handle_error - 错误处理节点]")
        last_error = state.get("last_error", "")
        error_count = state.get("error_count", 0)
        validation_errors = state.get("validation_errors", [])

        report_generator = self.report_generator
        if report_generator is None:
            from supply_chain_agent.agents.report_generator import ReportGenerator
            report_generator = ReportGenerator()

        from supply_chain_agent.prompts.fallback_templates import determine_error_code
        error_code = determine_error_code(
            error_detail=last_error,
            tool_name="workflow",
            error_count=error_count,
            validation_errors=validation_errors,
            max_clarification_reached=state.get("max_clarification_reached", False)
        )

        extracted_slots = state.get("extracted_slots", {})
        missing_slots = state.get("missing_slots", [])

        template_params = report_generator.extract_template_params(
            tool_name="workflow",
            error_detail=last_error,
            extracted_slots=extracted_slots,
            tool_results=state.get("tool_results", {}),
            missing_slots=missing_slots
        )

        if error_code == "GENERAL_FALLBACK":
            import hashlib
            trace_id = hashlib.md5(f"{last_error}{error_count}".encode()).hexdigest()[:12]
            template_params["trace_id"] = trace_id

        return {
            "error_code": error_code,
            "error_template_params": template_params,
            "from_error_handler": True,
            "context_window": state.get("context_window", []) + [
                {
                    "agent": "handle_error",
                    "action": "determined_error_code",
                    "error_code": error_code,
                    "last_error": last_error,
                    "error_count": error_count
                }
            ]
        }

    # ============== L4/L5修复：提取辅助方法 ==============

    def _get_report_generator(self):
        """获取或创建report_generator实例"""
        if self.report_generator is None:
            from supply_chain_agent.agents.report_generator import ReportGenerator
            return ReportGenerator()
        return self.report_generator

    async def _handle_error_response(
        self,
        state: AgentState,
        report_generator,
        error_code: str,
        template_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """L4修复：处理错误响应生成（提取辅助方法）"""
        fallback_response = await report_generator.generate_fallback_response(
            error_code,
            tool_results=state.get("tool_results", {}),
            **template_params
        )

        error_message = fallback_response.get("message", "系统遇到错误，请稍后重试。")
        severity = fallback_response.get("severity", "warning")

        return {
            "final_report": {
                "summary": error_message,
                "error_code": error_code,
                "severity": severity,
                "from_error_handler": True
            },
            "response_card": {
                "summary": error_message,
                "error_code": error_code,
                "severity": severity
            },
            "messages": state.get("messages", []) + [{
                "role": "assistant",
                "content": error_message
            }],
            "context_window": state.get("context_window", []) + [
                {
                    "agent": "generate_report",
                    "action": "generated_error_report_from_handler",
                    "error_code": error_code,
                    "severity": severity
                }
            ]
        }

    async def _collect_tool_errors(
        self,
        tool_results: Dict[str, Any],
        extracted_slots: Dict[str, Any],
        report_generator,
        state: AgentState
    ) -> List[Dict[str, Any]]:
        """L4修复：收集工具错误（提取辅助方法）"""
        error_responses = []

        for tool_name, result in tool_results.items():
            if isinstance(result, dict) and (result.get("error") or result.get("success") == False):
                error_detail = result.get("error", "未知错误")
                if isinstance(error_detail, dict):
                    error_detail = error_detail.get("message", str(error_detail))

                error_code = report_generator.determine_error_code_from_result(tool_name, error_detail)
                template_params = report_generator.extract_template_params(
                    tool_name=tool_name,
                    error_detail=error_detail,
                    extracted_slots=extracted_slots,
                    tool_results=tool_results,
                    missing_slots=state.get("missing_slots", [])
                )

                fallback_response = await report_generator.generate_fallback_response(
                    error_code,
                    tool_results=tool_results,
                    **template_params
                )

                error_responses.append({
                    "tool_name": tool_name,
                    "error_code": error_code,
                    "message": fallback_response.get("message", ""),
                    "severity": fallback_response.get("severity", "warning")
                })

        return error_responses

    def _build_error_report(
        self,
        error_responses: List[Dict[str, Any]],
        state: AgentState
    ) -> Dict[str, Any]:
        """L4修复：构建错误报告（提取辅助方法）"""
        error_messages = [resp["message"] for resp in error_responses]
        error_codes = [resp["error_code"] for resp in error_responses]
        primary_error_code = error_codes[0] if error_codes else "WORKFLOW_EXECUTION_FAILED"

        if len(error_messages) == 1:
            error_response = error_messages[0]
        else:
            error_response = "⚠️ **查询结果**\n\n"
            error_response += "\n\n---\n\n".join(error_messages)

        return {
            "final_report": {
                "summary": error_response,
                "errors": error_responses,
                "error_codes": error_codes
            },
            "response_card": {
                "summary": error_response,
                "error_code": primary_error_code
            },
            "messages": state.get("messages", []) + [{
                "role": "assistant",
                "content": error_response
            }],
            "context_window": state.get("context_window", []) + [
                {
                    "agent": "generate_report",
                    "action": "generated_error_report",
                    "errors": error_responses,
                    "error_codes": error_codes
                }
            ]
        }

    def setup_nodes(self):
        """
        Setup all nodes in the graph.

        M16说明：节点函数定义在方法内部的原因
        ==========================================
        8个节点函数（约580行）定义在setup_nodes()方法内部，
        这种设计有以下考量：

        **当前设计的优点**:
        1. 闭包访问self：节点函数可直接访问self.parser/executor等实例
        2. 避免循环导入：节点函数在运行时动态绑定，不依赖模块级导入
        3. 状态隔离：每次setup_nodes()调用创建新的节点函数实例

        **潜在改进方案**:
        1. 将节点函数提取为类方法（需处理self绑定）
        2. 使用functools.partial绑定依赖
        3. 引入节点注册机制

        **重构建议**（后续优化）:
        ```python
        # 方案：节点作为类方法
        async def _parse_input_node(self, state: AgentState) -> Dict[str, Any]:
            ...

        def setup_nodes(self):
            self.workflow.add_node("parse_input", self._parse_input_node)
        ```

        当前保持现有设计，避免破坏核心工作流逻辑。
        """
        # Node 1: Parser Agent (解析师)
        async def parse_input_node(state: AgentState) -> Dict[str, Any]:
            """Parse user intent and extract information."""
            print("[进入节点: parse_input - 解析师节点]")
            # Use injected parser instance
            parser = self.parser
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
                    "clarification_loop_count": 0,  # 成功解析后重置澄清循环计数器
                    "context_window": state.get("context_window", []) + [
                        {"agent": "parse_input", "action": "parsed_intent", "intent": intent}
                    ]
                }

            # H6修复：区分异常类型
            except IntentParseError as e:
                # 意图解析错误 - 可恢复，让用户重新输入
                return {
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Intent parse error: {e}",
                    "last_error_type": "IntentParseError",
                    "last_error_trace": traceback.format_exc(),
                    "validation_errors": state.get("validation_errors", []) + [str(e)],
                    "is_recoverable": True,
                }
            except ValidationError as e:
                # 验证错误 - 不可恢复，需用户提供正确输入
                return {
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Validation error: {e}",
                    "last_error_type": "ValidationError",
                    "last_error_trace": traceback.format_exc(),
                    "validation_errors": state.get("validation_errors", []) + [str(e)],
                    "is_recoverable": False,
                }
            except Exception as e:
                # 其他未知异常 - 包装后处理
                wrapped = wrap_exception(e, {"node": "parse_input"})
                return {
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"{type(wrapped).__name__}: {e}",
                    "last_error_type": type(wrapped).__name__,
                    "last_error_trace": traceback.format_exc(),
                    "validation_errors": state.get("validation_errors", []) + [str(e)],
                    "is_recoverable": is_recoverable(wrapped),
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

            # Use injected parser instance
            parser = self.parser
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
                # Use injected executor instance
                if self.executor:
                    tasks = await self.executor.create_execution_plan(state.get("user_intent", {}))
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

            # H6修复：区分异常类型
            except ExecutionPlanError as e:
                # 执行计划错误 - 不可恢复
                return {
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Execution plan error: {e}",
                    "last_error_type": "ExecutionPlanError",
                    "last_error_trace": traceback.format_exc(),
                    "validation_errors": state.get("validation_errors", []) + [str(e)],
                    "is_recoverable": False,
                }
            except ValidationError as e:
                # 验证错误 - 不可恢复
                return {
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Validation error: {e}",
                    "last_error_type": "ValidationError",
                    "last_error_trace": traceback.format_exc(),
                    "validation_errors": state.get("validation_errors", []) + [str(e)],
                    "is_recoverable": False,
                }
            except Exception as e:
                # 其他未知异常 - 包装后处理
                wrapped = wrap_exception(e, {"node": "plan_task"})
                return {
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"{type(wrapped).__name__}: {e}",
                    "last_error_type": type(wrapped).__name__,
                    "last_error_trace": traceback.format_exc(),
                    "validation_errors": state.get("validation_errors", []) + [str(e)],
                    "is_recoverable": is_recoverable(wrapped),
                }

        # Node 4: Executor Agent (调度员)
        async def execute_task_node(state: AgentState) -> Dict[str, Any]:
            """Execute tasks using tools.

            支持两种执行模式：
            1. 普通模式：逐个执行任务队列中的工具
            2. 链式执行模式（审批工单）：执行每个工具后，将结果发送给LLM解析获取下一步入参
            """
            print("[进入节点: execute_task - 执行器节点]")

            # Use injected executor instance
            executor = self.executor
            if executor is None:
                from supply_chain_agent.agents.executor import ExecutorAgent
                executor = ExecutorAgent()

            if not state.get("task_queue"):
                return {"execution_complete": True}

            # M8修复：改进链式执行模式判断逻辑
            # 链式执行仅用于需要前一步结果作为后一步输入的场景
            # 并行工具（如订单查询+物流查询）不需要链式执行
            user_intent = state.get("user_intent", {})
            intent_level_2 = user_intent.get("intent_level_2", "")
            task_queue = state.get("task_queue", [])

            # 判断是否需要链式执行的条件：
            # 1. 审批工单：需要先查询工单状态，再执行审批
            # 2. 显式标记：state中设置了use_chain_execution
            # 3. 数据依赖：工具间存在数据传递（通过TOOL_DEPENDENCIES定义）
            TOOL_DEPENDENCIES = {
                # 审批工单链：查询状态 → 审批操作
                "approve_work_order": ["query_work_order"],
            }

            def _needs_chain_execution(tasks: List[str], intent: str) -> bool:
                """判断任务列表是否需要链式执行"""
                # 审批工单需要链式
                if intent == "审批工单":
                    return True
                # 显式标记
                if state.get("use_chain_execution", False):
                    return True
                # 检查工具依赖关系
                task_names = [t.get("name", t) if isinstance(t, dict) else t for t in tasks]
                for task in task_names:
                    if task in TOOL_DEPENDENCIES:
                        deps = TOOL_DEPENDENCIES[task]
                        if any(dep in task_names for dep in deps):
                            return True
                return False

            use_chain_execution = _needs_chain_execution(task_queue, intent_level_2)

            try:
                # 链式执行模式：一次性执行所有工具，每步LLM解析结果
                if use_chain_execution and len(state.get("task_queue", [])) > 1:
                    print(f"🔗 使用链式执行模式，执行计划: {state.get('task_queue', [])}")

                    chain_result = await executor.execute_plan_with_llm_feedback(
                        execution_plan=state.get("task_queue", []),
                        initial_slots=state.get("extracted_slots", {}),
                        intent=user_intent
                    )

                    # 构建更新状态
                    updates = {
                        "tool_results": chain_result.get("results", {}),
                        "task_queue": [],  # 清空任务队列
                        "current_task": None,
                        "execution_complete": chain_result.get("success", False),
                        "chain_execution_result": chain_result,
                    }

                    if not chain_result.get("success", False):
                        updates["execution_failed"] = True
                        updates["error_count"] = state.get("error_count", 0) + 1
                        updates["last_error"] = chain_result.get("error", "链式执行失败")

                    # Add to context
                    context_item = {
                        "agent": "execute_task",
                        "action": "chain_execution",
                        "plan": state.get("task_queue", []),
                        "result": chain_result
                    }
                    updates["context_window"] = state.get("context_window", []) + [context_item]

                    return updates

                # 普通执行模式：逐个执行
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

            # H6修复：区分异常类型
            except ToolExecutionError as e:
                # 工具执行错误 - 可能可恢复，根据错误类型判断
                updates = {
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Tool execution error: {e}",
                    "last_error_type": "ToolExecutionError",
                    "last_error_trace": traceback.format_exc(),
                    "validation_errors": state.get("validation_errors", []) + [str(e)],
                    "is_recoverable": True,  # 工具执行错误通常可重试
                }
                if state.get("error_count", 0) < 3:
                    return updates
                else:
                    updates["execution_failed"] = True
                    return updates
            except CircuitBreakerOpenError as e:
                # 熔断器打开 - 等待后可恢复
                updates = {
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Circuit breaker open: {e}",
                    "last_error_type": "CircuitBreakerOpenError",
                    "last_error_trace": traceback.format_exc(),
                    "is_recoverable": True,
                    "circuit_breaker_recovery_time": e.recovery_time,
                }
                updates["execution_failed"] = True  # 熔断器打开时不重试，直接失败
                return updates
            except RecoverableError as e:
                # 其他可恢复错误
                updates = {
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Recoverable error: {e}",
                    "last_error_type": type(e).__name__,
                    "last_error_trace": traceback.format_exc(),
                    "is_recoverable": True,
                }
                if state.get("error_count", 0) < 3:
                    return updates
                else:
                    updates["execution_failed"] = True
                    return updates
            except UnrecoverableError as e:
                # 不可恢复错误 - 直接失败
                return {
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Unrecoverable error: {e}",
                    "last_error_type": type(e).__name__,
                    "last_error_trace": traceback.format_exc(),
                    "is_recoverable": False,
                    "execution_failed": True,
                }
            except Exception as e:
                # 其他未知异常 - 包装后处理
                wrapped = wrap_exception(e, {"node": "execute_task", "task": state.get("current_task")})
                updates = {
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"{type(wrapped).__name__}: {e}",
                    "last_error_type": type(wrapped).__name__,
                    "last_error_trace": traceback.format_exc(),
                    "validation_errors": state.get("validation_errors", []) + [str(e)],
                    "is_recoverable": is_recoverable(wrapped),
                }
                if state.get("error_count", 0) < 3:
                    return updates
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

            # Use injected auditor instance
            auditor = self.auditor
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

            # H6修复：区分异常类型
            except SupplyChainError as e:
                # 已知业务异常
                return {
                    "audit_results": {"passed": False, "issues": [str(e)]},
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Audit error: {e}",
                    "last_error_type": type(e).__name__,
                    "last_error_trace": traceback.format_exc(),
                    "is_recoverable": is_recoverable(e),
                }
            except Exception as e:
                # 未知异常 - 包装后处理
                wrapped = wrap_exception(e, {"node": "audit"})
                return {
                    "audit_results": {"passed": False, "issues": [str(e)]},
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Audit error: {wrapped}",
                    "last_error_type": type(wrapped).__name__,
                    "last_error_trace": traceback.format_exc(),
                    "is_recoverable": is_recoverable(wrapped),
                }

        # Node 7: Report Generator
        async def generate_report_node(state: AgentState) -> Dict[str, Any]:
            """
            Generate final report and response card.

            L4/L5修复：重构长函数，使用辅助方法减少嵌套层级。
            """
            print("[进入节点: generate_report - 报告生成节点]")

            report_generator = self._get_report_generator()

            # 检查是否从 handle_error_node 进入
            if state.get("from_error_handler", False):
                print("[报告生成节点] 处理来自错误处理节点的请求")
                error_code = state.get("error_code", "GENERAL_FALLBACK")
                template_params = state.get("error_template_params", {})
                return await self._handle_error_response(state, report_generator, error_code, template_params)

            try:
                # 检查工具错误
                tool_results = state.get("tool_results", {})
                extracted_slots = state.get("extracted_slots", {})

                error_responses = await self._collect_tool_errors(
                    tool_results, extracted_slots, report_generator, state
                )

                # 如果有错误，生成错误报告
                if error_responses:
                    return self._build_error_report(error_responses, state)

                # 正常报告生成
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

            # H6修复：区分异常类型
            except SupplyChainError as e:
                # 已知业务异常
                error_code = "WORKFLOW_EXECUTION_FAILED"
                fallback_response = await report_generator.generate_fallback_response(
                    error_code,
                    trace_id=str(hash(str(e)))
                )
                return {
                    "messages": state.get("messages", []) + [{
                        "role": "assistant",
                        "content": fallback_response.get("message", f"抱歉，系统在处理您的请求时遇到问题：{str(e)}")
                    }],
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"Report generation error: {e}",
                    "last_error_type": type(e).__name__,
                    "last_error_trace": traceback.format_exc(),
                    "error_code": error_code,
                    "is_recoverable": is_recoverable(e),
                }
            except Exception as e:
                # 未知异常 - 包装后处理
                wrapped = wrap_exception(e, {"node": "generate_report"})
                error_code = "WORKFLOW_EXECUTION_FAILED"
                fallback_response = await report_generator.generate_fallback_response(
                    error_code,
                    trace_id=str(hash(str(e)))
                )
                return {
                    "messages": state.get("messages", []) + [{
                        "role": "assistant",
                        "content": fallback_response.get("message", f"抱歉，系统在处理您的请求时遇到问题：{str(e)}")
                    }],
                    "error_count": state.get("error_count", 0) + 1,
                    "last_error": f"{type(wrapped).__name__}: {e}",
                    "last_error_type": type(wrapped).__name__,
                    "last_error_trace": traceback.format_exc(),
                    "error_code": error_code,
                    "is_recoverable": is_recoverable(wrapped),
                }

        # Node 8: Error Handler
        async def handle_error_node(state: AgentState) -> Dict[str, Any]:
            """Handle errors and generate error code for report generation.

            此节点不直接生成响应，而是根据错误类型生成错误编码，
            然后路由到 generate_report_node 生成响应。
            """
            print("[进入节点: handle_error - 错误处理节点]")
            last_error = state.get("last_error", "")
            error_count = state.get("error_count", 0)
            validation_errors = state.get("validation_errors", [])

            # Use injected report_generator instance
            report_generator = self.report_generator
            if report_generator is None:
                from supply_chain_agent.agents.report_generator import ReportGenerator
                report_generator = ReportGenerator()

            # 使用统一的错误代码确定函数（解决M19重复定义问题）
            from supply_chain_agent.prompts.fallback_templates import determine_error_code
            error_code = determine_error_code(
                error_detail=last_error,
                tool_name="workflow",
                error_count=error_count,
                validation_errors=validation_errors,
                max_clarification_reached=state.get("max_clarification_reached", False)
            )

            # 提取模板参数
            extracted_slots = state.get("extracted_slots", {})
            missing_slots = state.get("missing_slots", [])

            template_params = report_generator.extract_template_params(
                tool_name="workflow",
                error_detail=last_error,
                extracted_slots=extracted_slots,
                tool_results=state.get("tool_results", {}),
                missing_slots=missing_slots
            )

            # 生成追踪ID（用于通用错误）
            if error_code == "GENERAL_FALLBACK":
                import hashlib
                trace_id = hashlib.md5(f"{last_error}{error_count}".encode()).hexdigest()[:12]
                template_params["trace_id"] = trace_id

            return {
                "error_code": error_code,
                "error_template_params": template_params,
                "from_error_handler": True,  # 标记来自错误处理节点
                "context_window": state.get("context_window", []) + [
                    {
                        "agent": "handle_error",
                        "action": "determined_error_code",
                        "error_code": error_code,
                        "last_error": last_error,
                        "error_count": error_count
                    }
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

        # From error handler, route to generate_report for response generation
        self.workflow.add_edge("handle_error", "generate_report")

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
        from supply_chain_agent.common.protocols import InterruptInfo

        config = {"configurable": {"thread_id": thread_id}}
        state_snapshot = self.graph.get_state(config)
        if state_snapshot and hasattr(state_snapshot, 'values'):
            # Check for __interrupt__ in state values
            interrupts = state_snapshot.values.get('__interrupt__')
            if interrupts:
                # Return the first interrupt info
                for interrupt_data in interrupts:
                    info = InterruptInfo.from_langgraph_interrupt(interrupt_data)
                    return info.to_dict()
        return None

    def check_interrupt_in_result(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check if result contains interrupt information.

        Args:
            result: The workflow result from ainvoke

        Returns:
            Interrupt info dict or None
        """
        from supply_chain_agent.common.protocols import InterruptInfo

        interrupts = result.get('__interrupt__')
        if interrupts:
            # Return the first interrupt info
            for interrupt_data in interrupts:
                info = InterruptInfo.from_langgraph_interrupt(interrupt_data)
                return info.to_dict()
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

    # ============== M1修复：工作流控制逻辑移到Workflow类 ==============

    # 节点元数据常量（从Orchestrator移过来）
    NODE_METADATA = {
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

    async def process_with_events(
        self,
        user_input: str,
        thread_id: str = "default",
        emit_event: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        M1修复：处理工作流并发送事件（从Orchestrator移过来）。

        Args:
            user_input: 用户输入
            thread_id: 线程ID
            emit_event: 事件发送回调

        Returns:
            最终状态
        """
        initial_state = state_manager.create_initial_state(user_input)
        config = {"configurable": {"thread_id": thread_id}}

        node_metadata = self.NODE_METADATA
        current_state = initial_state
        step_counter = 0

        async def emit(event_type: str, data: Dict[str, Any]):
            if emit_event:
                if asyncio.iscoroutinefunction(emit_event):
                    await emit_event(event_type, data)
                else:
                    emit_event(event_type, data)

        # Stream the workflow execution
        async for event in self.graph.astream(initial_state, config=config):
            for node_name, node_output in event.items():
                if node_name == "__interrupt__":
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

                    await emit("step_start", {
                        "stepId": step_id,
                        "agentType": metadata["agentType"],
                        "title": metadata["title"],
                        "description": metadata["description"]
                    })

                    if node_name == "execute_task" and isinstance(node_output, dict):
                        tool_results = node_output.get("tool_results", {})
                        for tool_name, tool_result in tool_results.items():
                            await emit("tool_call", {
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

                    await emit("step_end", {"stepId": step_id})

                current_state = {**current_state, **node_output} if isinstance(node_output, dict) else current_state

        return current_state

    async def resume_with_events(
        self,
        user_input: str,
        thread_id: str = "default",
        emit_event: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        M1修复：恢复工作流并发送事件（从Orchestrator移过来）。

        Args:
            user_input: 用户澄清输入
            thread_id: 线程ID
            emit_event: 事件发送回调

        Returns:
            最终状态
        """
        from langgraph.types import Command

        config = {"configurable": {"thread_id": thread_id}}
        node_metadata = self.NODE_METADATA
        step_counter = 0
        current_state = {}

        async def emit(event_type: str, data: Dict[str, Any]):
            if emit_event:
                if asyncio.iscoroutinefunction(emit_event):
                    await emit_event(event_type, data)
                else:
                    emit_event(event_type, data)

        async for event in self.graph.astream(Command(resume=user_input), config=config):
            for node_name, node_output in event.items():
                if node_name == "__interrupt__":
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

                    await emit("step_start", {
                        "stepId": step_id,
                        "agentType": metadata["agentType"],
                        "title": metadata["title"],
                        "description": metadata["description"]
                    })

                    if node_name == "execute_task" and isinstance(node_output, dict):
                        tool_results = node_output.get("tool_results", {})
                        for tool_name, tool_result in tool_results.items():
                            await emit("tool_call", {
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

                    await emit("step_end", {"stepId": step_id})

                current_state = {**current_state, **node_output} if isinstance(node_output, dict) else current_state

        return current_state


# Global workflow instance (lazy initialization)
_workflow_instance: Optional[SupplyChainWorkflow] = None


def get_workflow(
    parser=None,
    executor=None,
    auditor=None,
    report_generator=None
) -> SupplyChainWorkflow:
    """
    Get or create workflow instance.

    Args:
        parser: ParserAgent instance for intent parsing
        executor: ExecutorAgent instance for task execution
        auditor: AuditorAgent instance for result auditing
        report_generator: ReportGenerator instance for report generation

    Returns:
        SupplyChainWorkflow instance
    """
    global _workflow_instance
    # 如果提供了所有 agents，创建新实例
    if all([parser, executor, auditor, report_generator]):
        _workflow_instance = SupplyChainWorkflow(
            parser=parser,
            executor=executor,
            auditor=auditor,
            report_generator=report_generator
        )
    elif _workflow_instance is None:
        # 没有提供 agents 且没有现有实例，创建默认实例
        _workflow_instance = SupplyChainWorkflow()
    return _workflow_instance


def reset_workflow():
    """
    H4修复：重置工作流单例（用于测试）
    """
    global _workflow_instance
    _workflow_instance = None


# Backward compatibility: global workflow property
class _WorkflowProxy:
    """Proxy for backward compatibility with global workflow access."""
    def __getattr__(self, name):
        return getattr(get_workflow(), name)


workflow = _WorkflowProxy()
