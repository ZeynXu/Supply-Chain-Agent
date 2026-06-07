"""
LangGraph State definition for Supply Chain Agent.

Defines the global state that is shared among all agents in the graph.
"""

from typing import Dict, Any, List, Optional, TypedDict, Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import operator


# ============== 具体类型定义（M29修复：替代Dict[str, Any]）==============

class CircuitBreakerState(TypedDict, total=False):
    """熔断器状态"""
    is_open: bool
    failure_count: int
    last_failure_time: float
    recovery_timeout: float


class ToolResultData(TypedDict, total=False):
    """工具执行结果数据"""
    success: bool
    data: Dict[str, Any]
    error: Optional[str]
    execution_time_ms: float


class ErrorTemplateParams(TypedDict, total=False):
    """错误模板参数"""
    order_id: Optional[str]
    customer_id: Optional[str]
    error_detail: Optional[str]
    trace_id: Optional[str]


# ============== 分组状态定义 ==============

class ConversationState(TypedDict, total=False):
    """对话相关状态"""
    messages: Annotated[List[Dict[str, str]], operator.add]


class IntentState(TypedDict, total=False):
    """意图识别相关状态"""
    user_intent: Dict[str, Any]
    extracted_slots: Dict[str, Any]
    missing_slots: List[str]


class ExecutionState(TypedDict, total=False):
    """任务执行相关状态"""
    task_queue: List[str]
    current_task: Optional[str]
    tool_results: Dict[str, ToolResultData]


class AuditState(TypedDict, total=False):
    """审计验证相关状态"""
    audit_results: Dict[str, Any]
    validation_errors: List[str]


class MemoryState(TypedDict, total=False):
    """记忆上下文相关状态"""
    context_window: List[Dict[str, Any]]
    long_term_memory_refs: List[str]


class ErrorState(TypedDict, total=False):
    """错误处理相关状态"""
    error_count: int
    last_error: Optional[str]
    last_error_type: Optional[str]
    last_error_trace: Optional[str]
    circuit_breakers: Dict[str, CircuitBreakerState]
    error_code: Optional[str]
    error_template_params: ErrorTemplateParams
    from_error_handler: bool


class OutputState(TypedDict, total=False):
    """输出相关状态"""
    final_report: Optional[Dict[str, Any]]
    response_card: Optional[Dict[str, Any]]


class ClarificationState(TypedDict, total=False):
    """澄清相关状态"""
    waiting_for_input: bool
    clarification_prompt: Optional[str]
    clarification_received: bool
    clarification_loop_count: int
    max_clarification_reached: bool


# ============== 完整状态定义 ==============

class AgentState(TypedDict):
    """
    全局状态，按功能分组管理。

    包含以下分组：
    - conversation: 对话历史
    - intent: 意图识别
    - execution: 任务执行
    - audit: 审计验证
    - memory: 记忆上下文
    - error: 错误处理
    - output: 输出结果
    - clarification: 澄清处理
    - approval: 审批分析
    """
    # Conversation history
    messages: Annotated[List[Dict[str, str]], operator.add]

    # Intent recognition
    user_intent: Dict[str, Any]
    extracted_slots: Dict[str, Any]
    missing_slots: List[str]

    # Task execution
    task_queue: List[str]
    current_task: Optional[str]
    tool_results: Dict[str, Any]

    # Audit and validation
    audit_results: Dict[str, Any]
    validation_errors: List[str]

    # Memory and context
    context_window: List[Dict[str, Any]]
    long_term_memory_refs: List[str]

    # Error handling
    error_count: int
    last_error: Optional[str]
    last_error_type: Optional[str]
    last_error_trace: Optional[str]
    circuit_breakers: Dict[str, Dict[str, Any]]

    # Error code and template params (from handle_error_node)
    error_code: Optional[str]
    error_template_params: Dict[str, Any]
    from_error_handler: bool

    # Final output
    final_report: Optional[Dict[str, Any]]
    response_card: Optional[Dict[str, Any]]

    # Human-in-the-loop: waiting for user clarification
    waiting_for_input: bool
    clarification_prompt: Optional[str]
    clarification_received: bool

    # Clarification loop counter
    clarification_loop_count: int

    # Max clarification loops reached flag
    max_clarification_reached: bool

    # Approval analysis result (审批工单专用)
    approval_analysis: Optional[Dict[str, Any]]


class StateManager:
    """Manages the global state for the Agent workflow."""

    def __init__(self, db_path: str = "./supply_chain_agent/data/checkpoints.db"):
        """
        Initialize the state manager.

        Args:
            db_path: Path to SQLite database for checkpoints
        """
        self.db_path = db_path
        self.checkpointer = MemorySaver()

    def create_initial_state(self, user_input: str) -> AgentState:
        """
        Create initial state from user input.

        Args:
            user_input: User's initial query

        Returns:
            Initial agent state
        """
        return {
            # Conversation
            "messages": [
                {"role": "user", "content": user_input}
            ],
            # Intent
            "user_intent": {},
            "extracted_slots": {},
            "missing_slots": [],
            # Execution
            "task_queue": [],
            "current_task": None,
            "tool_results": {},
            # Audit
            "audit_results": {},
            "validation_errors": [],
            # Memory
            "context_window": [],
            "long_term_memory_refs": [],
            # Error
            "error_count": 0,
            "last_error": None,
            "last_error_type": None,
            "last_error_trace": None,
            "circuit_breakers": {},
            "error_code": None,
            "error_template_params": {},
            "from_error_handler": False,
            # Output
            "final_report": None,
            "response_card": None,
            # Clarification
            "waiting_for_input": False,
            "clarification_prompt": None,
            "clarification_received": False,
            "clarification_loop_count": 0,
            "max_clarification_reached": False,
            # Approval analysis
            "approval_analysis": None
        }

    def update_state_intent(self, state: AgentState, intent: Dict[str, Any]) -> AgentState:
        """Update state with parsed intent."""
        state["user_intent"] = intent

        # Extract entities and slots
        if "entities" in intent:
            for entity in intent["entities"]:
                if isinstance(entity, dict) and "type" in entity and "value" in entity:
                    state["extracted_slots"][entity["type"]] = entity["value"]

        # Check for missing slots
        if "required_slots" in intent:
            for slot in intent["required_slots"]:
                if slot not in state["extracted_slots"]:
                    state["missing_slots"].append(slot)

        return state

    def update_state_task_queue(self, state: AgentState, tasks: List[str]) -> AgentState:
        """Update task queue in state."""
        state["task_queue"] = tasks
        if tasks:
            state["current_task"] = tasks[0]
        return state

    def update_tool_results(self, state: AgentState, tool_name: str, result: Dict[str, Any]) -> AgentState:
        """Update tool results in state."""
        state["tool_results"][tool_name] = result
        return state

    def update_audit_results(self, state: AgentState, audit: Dict[str, Any]) -> AgentState:
        """Update audit results in state."""
        state["audit_results"] = audit
        return state

    def add_error(self, state: AgentState, error: str) -> AgentState:
        """Add error to state."""
        state["error_count"] += 1
        state["last_error"] = error
        state["validation_errors"].append(error)
        return state

    def add_to_context(self, state: AgentState, item: Dict[str, Any]) -> AgentState:
        """Add item to context window."""
        # Maintain context window size
        if len(state["context_window"]) >= 20:  # Configurable
            state["context_window"] = state["context_window"][1:]
        state["context_window"].append(item)
        return state

    def update_final_report(self, state: AgentState, report: Dict[str, Any]) -> AgentState:
        """Update final report in state."""
        state["final_report"] = report
        return state

    def update_response_card(self, state: AgentState, card: Dict[str, Any]) -> AgentState:
        """Update response card in state."""
        state["response_card"] = card
        return state

    def update_approval_analysis(self, state: AgentState, analysis: Dict[str, Any]) -> AgentState:
        """Update approval analysis in state."""
        state["approval_analysis"] = analysis
        return state

    def get_state_summary(self, state: AgentState) -> Dict[str, Any]:
        """Get a summary of the current state."""
        return {
            "has_intent": bool(state["user_intent"]),
            "intent_type": state["user_intent"].get("intent_level_1", "unknown"),
            "missing_slots_count": len(state["missing_slots"]),
            "task_queue_length": len(state["task_queue"]),
            "current_task": state["current_task"],
            "tool_results_count": len(state["tool_results"]),
            "audit_passed": state["audit_results"].get("passed", False),
            "error_count": state["error_count"],
            "has_final_report": state["final_report"] is not None,
            "has_response_card": state["response_card"] is not None,
            "has_approval_analysis": state.get("approval_analysis") is not None
        }

    def is_ready_for_execution(self, state: AgentState) -> bool:
        """Check if state is ready for tool execution."""
        return (
            bool(state.get("user_intent")) and
            len(state.get("missing_slots", [])) == 0 and
            len(state.get("task_queue", [])) > 0
        )

    def is_ready_for_audit(self, state: AgentState) -> bool:
        """Check if state is ready for audit."""
        return (
            len(state["tool_results"]) > 0 and
            state["current_task"] is None  # All tasks completed
        )

    def is_ready_for_response(self, state: AgentState) -> bool:
        """Check if state is ready for response generation."""
        return (
            state["audit_results"].get("passed", False) and
            len(state["tool_results"]) > 0
        )

    def should_retry(self, state: AgentState) -> bool:
        """Check if we should retry based on error count."""
        return state["error_count"] < 3  # Configurable

    def reset_for_retry(self, state: AgentState) -> AgentState:
        """Reset state for retry."""
        state["error_count"] = 0
        state["last_error"] = None
        state["validation_errors"] = []
        return state


# H4修复：使用getter函数管理单例
_state_manager_instance: Optional["StateManager"] = None


def get_state_manager() -> "StateManager":
    """获取状态管理器单例"""
    global _state_manager_instance
    if _state_manager_instance is None:
        _state_manager_instance = StateManager()
    return _state_manager_instance


def reset_state_manager():
    """重置状态管理器单例（用于测试）"""
    global _state_manager_instance
    _state_manager_instance = None


# 向后兼容：初始化默认实例
# 注意：新代码应使用 get_state_manager()，测试时使用 reset_state_manager()
state_manager = get_state_manager()