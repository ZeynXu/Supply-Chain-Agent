"""
Executor Agent (调度员)

Responsible for tool orchestration and concurrent control.
Enhanced with intelligent retry mechanism and circuit breaker.
"""

from typing import Dict, Any, List, Optional
import asyncio
from dataclasses import dataclass
import time

from supply_chain_agent.config import settings
from supply_chain_agent.tools.client import get_tool_client

# 导入重试管理器
try:
    from supply_chain_agent.agents.retry_manager import (
        RetryManager,
        RetryConfig,
        CircuitBreakerConfig,
        RetryStrategyType,
        ErrorSeverity
    )
    RETRY_MANAGER_AVAILABLE = True
except ImportError:
    RETRY_MANAGER_AVAILABLE = False
    print("⚠️ RetryManager not available, using basic retry logic")


@dataclass
class Task:
    """Task definition for execution."""
    name: str
    tool_name: str
    parameters: Dict[str, Any]
    priority: int = 1
    timeout: int = 10
    retry_count: int = 0
    max_retries: int = 3


class ExecutorAgent:
    """Executor agent for tool orchestration and execution."""

    # Tool mapping for different intents (supports both intent_level_1 and intent_level_2)
    TOOL_MAPPING = {
        # intent_level_2 mappings (more specific)
        "物流查询": ["query_order_status", "get_logistics_trace"],
        "订单状态查询": ["query_order_status"],
        "合同查询": ["search_contract_template"],
        "审批流转": ["approve_work_order"],
        "审批处理": ["approve_work_order"],
        "审批通过": ["approve_work_order"],
        "审批拒绝": ["approve_work_order"],
        "工单创建": ["create_work_order"],
        "质量检验工单": ["create_work_order"],
        "生产跟踪工单": ["create_work_order"],
        "物流异常工单": ["create_work_order"],
        "通用工单": ["create_work_order"],
        "异常上报": ["report_issue"],
        "物流异常": ["report_issue"],
        "质量异常": ["report_issue"],
        "生产异常": ["report_issue"],
        "通用异常": ["report_issue"],
        # intent_level_1 mappings (fallback)
        "状态查询": ["query_order_status"],
    }

    def __init__(self):
        self.task_queue: List[Task] = []
        self.execution_history: List[Dict[str, Any]] = []

        # 初始化重试管理器
        if RETRY_MANAGER_AVAILABLE:
            # 配置重试策略
            retry_config = RetryConfig(
                max_retries=3,
                base_delay_ms=1000,
                max_delay_ms=10000,
                strategy=RetryStrategyType.EXPONENTIAL_BACKOFF,
                jitter_factor=0.1,
                retry_on_exceptions=["connection_error", "rate_limit", "server_error", "service_unavailable"]
            )

            # 配置熔断器
            circuit_breaker_config = CircuitBreakerConfig(
                failure_threshold=5,
                failure_window_seconds=60,
                recovery_timeout_seconds=30,
                success_threshold=3,
                half_open_timeout_seconds=10
            )

            self.retry_manager = RetryManager(retry_config, circuit_breaker_config)
        else:
            self.retry_manager = None

    async def execute_task(self, task_name: str, extracted_slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a specific task.

        Args:
            task_name: Name of the task to execute
            extracted_slots: Extracted information from user input

        Returns:
            Task execution result
        """
        # Map task to tool and parameters
        tool_name, parameters = self._map_task_to_tool(task_name, extracted_slots)

        # Create task
        task = Task(
            name=task_name,
            tool_name=tool_name,
            parameters=parameters,
            priority=self._get_task_priority(task_name)
        )

        # Execute task
        result = await self._execute_tool(task)

        # Record execution
        self.execution_history.append({
            "task": task_name,
            "tool": tool_name,
            "parameters": parameters,
            "result": result,
            "timestamp": self._get_timestamp()
        })

        return result

    def _map_task_to_tool(self, task_name: str, extracted_slots: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """Map task name to tool and parameters."""
        # Default mapping
        if task_name == "query_order_status":
            return "query_order_status", {"order_id": extracted_slots.get("order_id")}
        elif task_name == "get_logistics_trace":
            return "get_logistics_trace", {"tracking_no": extracted_slots.get("tracking_no")}
        elif task_name == "search_contract_template":
            return "search_contract_template", {"query": extracted_slots.get("query", ""), "top_k": 2}
        elif task_name == "approve_work_order":
            return "approve_work_order", {
                "order_id": extracted_slots.get("work_order_id"),
                "comment": extracted_slots.get("comment", "系统自动审批")
            }
        elif task_name == "create_work_order":
            return "create_work_order", {
                "work_type": extracted_slots.get("work_type"),
                "description": extracted_slots.get("description"),
                "priority": extracted_slots.get("priority", "中"),
                "assigned_to": extracted_slots.get("assigned_to"),
                "order_id": extracted_slots.get("order_id")
            }
        elif task_name == "report_issue":
            return "report_issue", {
                "issue_type": extracted_slots.get("issue_type"),
                "description": extracted_slots.get("description"),
                "urgency": extracted_slots.get("urgency", "中"),
                "affected_order": extracted_slots.get("order_id"),  # 使用order_id作为affected_order
                "reported_by": extracted_slots.get("reported_by")
            }

        # Fallback: try to use task_name as tool_name
        return task_name, extracted_slots

    def _get_task_priority(self, task_name: str) -> int:
        """Get priority for a task."""
        priority_map = {
            "query_order_status": 1,
            "get_logistics_trace": 2,
            "search_contract_template": 3,
            "approve_work_order": 0,  # Lowest priority as it requires confirmation
            "create_work_order": 1,
            "report_issue": 2  # 异常上报优先级较高
        }
        return priority_map.get(task_name, 1)

    async def _execute_tool(self, task: Task) -> Dict[str, Any]:
        """Execute a tool with intelligent retry logic."""
        client = await get_tool_client()

        # 使用智能重试管理器（如果可用）
        if self.retry_manager and RETRY_MANAGER_AVAILABLE:
            try:
                # 使用retry_manager执行带重试和熔断器的调用
                result = await self.retry_manager.execute_with_retry(
                    func=client.call_tool,
                    func_name=f"tool_{task.tool_name}",
                    circuit_breaker_name=f"tool_{task.tool_name}",
                    tool_name=task.tool_name,
                    **task.parameters
                )

                # Check if approval requires confirmation
                if task.tool_name == "approve_work_order":
                    if result.get("requires_confirmation", False):
                        result["needs_user_confirmation"] = True
                        result["confirmation_message"] = result.get("confirmation_message", "需要用户确认")

                # 记录执行成功
                self._record_tool_execution(task, result, True)
                return result

            except Exception as e:
                print(f"⚠️ 智能重试机制处理后仍失败: {task.name} - {e}")

                # 获取错误统计
                stats = self.retry_manager.get_statistics(f"tool_{task.tool_name}") if self.retry_manager else {}

                error_result = {
                    "error": f"任务执行失败: {str(e)}",
                    "task": task.name,
                    "tool": task.tool_name,
                    "attempts": stats.get("total_retries", task.max_retries) + 1,
                    "success": False,
                    "retry_stats": stats,
                    "error_type": "intelligent_retry_failed"
                }

                self._record_tool_execution(task, error_result, False)
                return error_result

        # 降级：使用基础重试逻辑（兼容性）
        return await self._execute_tool_basic(task, client)

    async def _execute_tool_basic(self, task: Task, client) -> Dict[str, Any]:
        """基本重试逻辑（降级方案）"""
        for attempt in range(task.max_retries + 1):
            try:
                print(f"🔧 执行任务: {task.name} (尝试 {attempt + 1}/{task.max_retries + 1})")

                # Call the tool
                result = await client.call_tool(task.tool_name, **task.parameters)

                # Check if approval requires confirmation
                if task.tool_name == "approve_work_order":
                    if result.get("requires_confirmation", False):
                        result["needs_user_confirmation"] = True
                        result["confirmation_message"] = result.get("confirmation_message", "需要用户确认")

                self._record_tool_execution(task, result, True)
                return result

            except Exception as e:
                print(f"⚠️ 任务执行失败: {task.name} - {e}")

                if attempt < task.max_retries:
                    # 指数退避等待
                    wait_time = 2 ** attempt
                    print(f"⏰ 等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    # 最大重试次数达到
                    error_result = {
                        "error": f"任务执行失败: {str(e)}",
                        "task": task.name,
                        "tool": task.tool_name,
                        "attempts": attempt + 1,
                        "success": False,
                        "error_type": "basic_retry_exhausted"
                    }

                    self._record_tool_execution(task, error_result, False)
                    return error_result

        # 不应该到达这里
        error_result = {"error": "未知错误", "success": False, "error_type": "unknown"}
        self._record_tool_execution(task, error_result, False)
        return error_result

    def _record_tool_execution(self, task: Task, result: Dict[str, Any], success: bool):
        """记录工具执行结果"""
        execution_record = {
            "task": task.name,
            "tool": task.tool_name,
            "parameters": task.parameters,
            "result": result,
            "success": success,
            "timestamp": time.time(),
            "timestamp_human": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # 如果可用，添加重试统计信息
        if self.retry_manager and RETRY_MANAGER_AVAILABLE:
            stats = self.retry_manager.get_statistics(f"tool_{task.tool_name}")
            execution_record["retry_stats"] = stats

        self.execution_history.append(execution_record)

        # 保持执行历史大小
        if len(self.execution_history) > 100:  # 最多保留100条记录
            self.execution_history = self.execution_history[-100:]

    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计信息"""
        if not self.execution_history:
            return {"total_executions": 0, "success_rate": 0.0}

        success_count = sum(1 for record in self.execution_history if record.get("success", False))
        total_count = len(self.execution_history)
        success_rate = success_count / total_count if total_count > 0 else 0.0

        # 按工具分类统计
        tool_stats = {}
        for record in self.execution_history:
            tool_name = record.get("tool", "unknown")
            if tool_name not in tool_stats:
                tool_stats[tool_name] = {"executions": 0, "successes": 0, "failures": 0}

            tool_stats[tool_name]["executions"] += 1
            if record.get("success", False):
                tool_stats[tool_name]["successes"] += 1
            else:
                tool_stats[tool_name]["failures"] += 1

        # 添加重试管理器统计（如果可用）
        retry_stats = {}
        if self.retry_manager and RETRY_MANAGER_AVAILABLE:
            retry_stats = self.retry_manager.get_statistics()

        return {
            "total_executions": total_count,
            "success_count": success_count,
            "failure_count": total_count - success_count,
            "success_rate": round(success_rate * 100, 2),
            "tool_statistics": tool_stats,
            "retry_statistics": retry_stats,
            "last_update": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    async def create_execution_plan(self, intent: Dict[str, Any]) -> List[str]:
        """
        Create execution plan based on intent.

        Args:
            intent: Parsed user intent containing intent_level_1, intent_level_2, and entities

        Returns:
            List of task names to execute
        """
        intent_level_1 = intent.get("intent_level_1", "")
        intent_level_2 = intent.get("intent_level_2", "")
        extracted_slots = intent.get("entities", [])

        # Convert entities to slot dict
        slot_dict = {}
        for entity in extracted_slots:
            if isinstance(entity, dict):
                slot_dict[entity.get("type")] = entity.get("value")

        # First try intent_level_2 (more specific), then intent_level_1 (fallback)
        tasks = self.TOOL_MAPPING.get(intent_level_2,
                                        self.TOOL_MAPPING.get(intent_level_1, []))

        # Filter tasks based on available slots
        filtered_tasks = []
        for task in tasks:
            if self._can_execute_task(task, slot_dict):
                filtered_tasks.append(task)

        if filtered_tasks:
            return filtered_tasks

        # Default plan for unknown intents
        return ["query_order_status"]  # Default fallback

    def _can_execute_task(self, task_name: str, slots: Dict[str, Any]) -> bool:
        """Check if a task can be executed with available slots."""
        required_params = {
            "query_order_status": ["order_id"],
            "get_logistics_trace": ["tracking_no"],
            "approve_work_order": ["work_order_id"],
            "create_work_order": ["work_type", "description"],
            "report_issue": ["issue_type", "description"]
        }

        if task_name in required_params:
            for param in required_params[task_name]:
                if param not in slots or not slots[param]:
                    return False

        return True

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()

    async def execute_concurrent_tasks(self, tasks: List[str], extracted_slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute multiple tasks concurrently.

        Args:
            tasks: List of task names
            extracted_slots: Extracted information

        Returns:
            Combined results
        """
        # Create task objects
        task_objects = []
        for task_name in tasks:
            tool_name, parameters = self._map_task_to_tool(task_name, extracted_slots)
            task = Task(
                name=task_name,
                tool_name=tool_name,
                parameters=parameters
            )
            task_objects.append(task)

        # Execute tasks concurrently
        results = {}
        tasks_to_execute = []

        for task in task_objects:
            # Create async task
            async def execute_and_record(t):
                result = await self._execute_tool(t)
                return t.name, result

            tasks_to_execute.append(execute_and_record(task))

        # Wait for all tasks to complete
        if tasks_to_execute:
            completed = await asyncio.gather(*tasks_to_execute, return_exceptions=True)

            for task_result in completed:
                if isinstance(task_result, Exception):
                    print(f"并发任务执行异常: {task_result}")
                else:
                    task_name, result = task_result
                    results[task_name] = result

        return results

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of execution history."""
        total_tasks = len(self.execution_history)
        successful_tasks = sum(1 for task in self.execution_history if task.get("result", {}).get("success", True))
        failed_tasks = total_tasks - successful_tasks

        return {
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": successful_tasks / total_tasks if total_tasks > 0 else 0,
            "recent_tasks": self.execution_history[-5:] if self.execution_history else []
        }