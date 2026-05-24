"""
Executor Agent (调度员)

Responsible for tool orchestration and concurrent control.
Enhanced with intelligent retry mechanism and circuit breaker.

Task Classification:
- Level 1: 信息查询、工单管理、异常上报
- Level 2: Based on MCP tools provided
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

    # ==========================================
    # Task Classification
    # ==========================================

    # 一级任务分类
    LEVEL_1_TASKS = {
        "信息查询": "查询客户、订单、产品、物流等信息",
        "工单管理": "创建和审批工单",
        "异常上报": "上报供应链过程中的问题"
    }

    # 二级任务分类
    LEVEL_2_TASKS = {
        # 信息查询类
        "客户查询": {"tool": "query_customer", "level1": "信息查询"},
        "客户订单查询": {"tool": "query_customer_orders", "level1": "信息查询"},
        "订单查询": {"tool": "query_order", "level1": "信息查询"},
        "订单明细查询": {"tool": "query_order_items", "level1": "信息查询"},
        "产品查询": {"tool": "query_product", "level1": "信息查询"},
        "物流查询": {"tool": "query_shipment", "level1": "信息查询"},
        "客户统计查询": {"tool": "query_customer_statistics", "level1": "信息查询"},
        # 工单管理类
        "创建工单": {"tool": "create_work_order", "level1": "工单管理"},
        "审批工单": {"tool": "approve_work_order", "level1": "工单管理"},
        # 异常上报类
        "上报问题": {"tool": "report_issue", "level1": "异常上报"},
    }

    # Tool mapping for intent parsing (intent_level_2 -> tool_name)
    TOOL_MAPPING = {
        # 信息查询类
        "客户查询": "query_customer",
        "客户订单查询": "query_customer_orders",
        "订单查询": "query_order",
        "订单明细查询": "query_order_items",
        "产品查询": "query_product",
        "物流查询": "query_shipment",
        "客户统计查询": "query_customer_statistics",
        # 工单管理类
        "创建工单": "create_work_order",
        "审批工单": "approve_work_order",
        # 异常上报类
        "上报问题": "report_issue",
        # 兼容旧版intent映射
        "信息查询": "query_order",
        "工单管理": "create_work_order",
        "异常上报": "report_issue",
    }

    # MCP工具参数定义
    TOOL_PARAMS = {
        "query_customer": {
            "required": ["customer_id"],
            "optional": []
        },
        "query_customer_orders": {
            "required": ["customer_id"],
            "optional": ["limit", "offset"]
        },
        "query_order": {
            "required": ["order_id"],
            "optional": []
        },
        "query_order_items": {
            "required": ["order_id"],
            "optional": []
        },
        "query_product": {
            "required": ["product_card_id"],
            "optional": []
        },
        "query_shipment": {
            "required": ["order_id"],
            "optional": []
        },
        "query_customer_statistics": {
            "required": ["customer_id"],
            "optional": []
        },
        "create_work_order": {
            "required": ["work_type", "description"],
            "optional": ["priority", "order_id", "assigned_to"]
        },
        "approve_work_order": {
            "required": ["work_order_id", "action"],
            "optional": ["comment", "approver"]
        },
        "report_issue": {
            "required": ["issue_type", "description"],
            "optional": ["urgency", "affected_order", "reported_by"]
        },
    }

    # 有效值定义 (来自MCP Server)
    VALID_WORK_TYPES = ["审批", "异常处理", "退款", "调拨", "质检", "其他"]
    VALID_PRIORITIES = ["高", "中", "低"]
    VALID_ISSUE_TYPES = ["物流延迟", "库存异常", "质量缺陷", "数据错误", "客户投诉", "其他"]
    VALID_URGENCIES = ["高", "中", "低"]
    VALID_APPROVE_ACTIONS = ["approve", "reject", "escalate"]

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

    def get_available_tools(self) -> Dict[str, Any]:
        """获取所有可用工具及其参数定义"""
        return {
            "level_1_tasks": self.LEVEL_1_TASKS,
            "level_2_tasks": self.LEVEL_2_TASKS,
            "tool_params": self.TOOL_PARAMS,
            "valid_values": {
                "work_types": self.VALID_WORK_TYPES,
                "priorities": self.VALID_PRIORITIES,
                "issue_types": self.VALID_ISSUE_TYPES,
                "urgencies": self.VALID_URGENCIES,
                "approve_actions": self.VALID_APPROVE_ACTIONS
            }
        }

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

        # Validate parameters
        validation_result = self._validate_tool_params(tool_name, parameters)
        if not validation_result["valid"]:
            return {
                "error": validation_result["message"],
                "task": task_name,
                "tool": tool_name,
                "success": False,
                "error_type": "validation_failed"
            }

        # Create task
        task = Task(
            name=task_name,
            tool_name=tool_name,
            parameters=parameters,
            priority=self._get_task_priority(tool_name)
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
        """Map task name to tool and parameters based on MCP tool definitions."""

        # Get tool name from mapping
        tool_name = self.TOOL_MAPPING.get(task_name, task_name)

        # Build parameters based on tool type
        if tool_name == "query_customer":
            return "query_customer", {
                "customer_id": extracted_slots.get("customer_id")
            }

        elif tool_name == "query_customer_orders":
            return "query_customer_orders", {
                "customer_id": extracted_slots.get("customer_id"),
                "limit": extracted_slots.get("limit", 20),
                "offset": extracted_slots.get("offset", 0)
            }

        elif tool_name == "query_order":
            return "query_order", {
                "order_id": extracted_slots.get("order_id")
            }

        elif tool_name == "query_order_items":
            return "query_order_items", {
                "order_id": extracted_slots.get("order_id")
            }

        elif tool_name == "query_product":
            return "query_product", {
                "product_card_id": extracted_slots.get("product_card_id")
            }

        elif tool_name == "query_shipment":
            return "query_shipment", {
                "order_id": extracted_slots.get("order_id")
            }

        elif tool_name == "query_customer_statistics":
            return "query_customer_statistics", {
                "customer_id": extracted_slots.get("customer_id")
            }

        elif tool_name == "create_work_order":
            work_type = extracted_slots.get("work_type", "其他")
            # 验证work_type
            if work_type not in self.VALID_WORK_TYPES:
                work_type = "其他"

            priority = extracted_slots.get("priority", "中")
            if priority not in self.VALID_PRIORITIES:
                priority = "中"

            params = {
                "work_type": work_type,
                "description": extracted_slots.get("description", ""),
                "priority": priority,
            }
            # 只有有值时才添加可选参数
            if extracted_slots.get("order_id"):
                params["order_id"] = extracted_slots.get("order_id")
            if extracted_slots.get("assigned_to"):
                params["assigned_to"] = extracted_slots.get("assigned_to")

            return "create_work_order", params

        elif tool_name == "approve_work_order":
            action = extracted_slots.get("action", "approve")
            if action not in self.VALID_APPROVE_ACTIONS:
                action = "approve"

            return "approve_work_order", {
                "work_order_id": extracted_slots.get("work_order_id"),
                "action": action,
                "comment": extracted_slots.get("comment", ""),
                "approver": extracted_slots.get("approver", "Agent System")
            }

        elif tool_name == "report_issue":
            issue_type = extracted_slots.get("issue_type", "其他")
            if issue_type not in self.VALID_ISSUE_TYPES:
                issue_type = "其他"

            urgency = extracted_slots.get("urgency", "中")
            if urgency not in self.VALID_URGENCIES:
                urgency = "中"

            params = {
                "issue_type": issue_type,
                "description": extracted_slots.get("description", ""),
                "urgency": urgency,
                "reported_by": extracted_slots.get("reported_by", "Agent System")
            }
            # 只有有值时才添加可选参数
            if extracted_slots.get("order_id"):
                params["affected_order"] = extracted_slots.get("order_id")

            return "report_issue", params

        # Fallback: return task_name as tool_name with extracted slots
        return tool_name, extracted_slots

    def _validate_tool_params(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate tool parameters against required params."""
        if tool_name not in self.TOOL_PARAMS:
            return {"valid": True, "message": "Unknown tool, skipping validation"}

        required_params = self.TOOL_PARAMS[tool_name]["required"]
        missing_params = []

        for param in required_params:
            value = parameters.get(param)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing_params.append(param)

        if missing_params:
            return {
                "valid": False,
                "message": f"缺少必要参数: {', '.join(missing_params)}"
            }

        return {"valid": True, "message": "参数验证通过"}

    def _get_task_priority(self, tool_name: str) -> int:
        """Get priority for a task based on tool type."""
        priority_map = {
            # 信息查询类 (优先级较低)
            "query_customer": 3,
            "query_customer_orders": 3,
            "query_order": 2,
            "query_order_items": 3,
            "query_product": 3,
            "query_shipment": 2,
            "query_customer_statistics": 3,
            # 工单管理类
            "create_work_order": 1,
            "approve_work_order": 0,  # 需要确认，优先级最低
            # 异常上报类 (优先级最高)
            "report_issue": 0  # 异常上报优先级最高
        }
        return priority_map.get(tool_name, 2)

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

        # 按一级任务分类统计
        level1_stats = {}
        for record in self.execution_history:
            tool_name = record.get("tool", "unknown")
            level1 = self._get_level1_by_tool(tool_name)
            if level1 not in level1_stats:
                level1_stats[level1] = {"executions": 0, "successes": 0, "failures": 0}

            level1_stats[level1]["executions"] += 1
            if record.get("success", False):
                level1_stats[level1]["successes"] += 1
            else:
                level1_stats[level1]["failures"] += 1

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
            "level1_statistics": level1_stats,
            "retry_statistics": retry_stats,
            "last_update": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def _get_level1_by_tool(self, tool_name: str) -> str:
        """根据工具名获取一级任务分类"""
        for task_name, task_info in self.LEVEL_2_TASKS.items():
            if task_info["tool"] == tool_name:
                return task_info["level1"]
        return "其他"

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
        tool_name = self.TOOL_MAPPING.get(intent_level_2,
                                          self.TOOL_MAPPING.get(intent_level_1, ""))

        if tool_name and self._can_execute_tool(tool_name, slot_dict):
            return [tool_name]

        # Default plan for unknown intents
        return ["query_order"]  # Default fallback

    def _can_execute_tool(self, tool_name: str, slots: Dict[str, Any]) -> bool:
        """Check if a tool can be executed with available slots."""
        if tool_name not in self.TOOL_PARAMS:
            return False

        required_params = self.TOOL_PARAMS[tool_name]["required"]

        for param in required_params:
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

            # Validate parameters
            validation_result = self._validate_tool_params(tool_name, parameters)
            if not validation_result["valid"]:
                continue  # Skip invalid tasks

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
        successful_tasks = sum(1 for task in self.execution_history if task.get("success", False))
        failed_tasks = total_tasks - successful_tasks

        return {
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": successful_tasks / total_tasks if total_tasks > 0 else 0,
            "recent_tasks": self.execution_history[-5:] if self.execution_history else []
        }
