"""
Executor Agent (调度员)

Responsible for tool orchestration and concurrent control.
Enhanced with intelligent retry mechanism and circuit breaker.

Task Classification:
- Level 1: 信息查询、工单管理、异常上报
- Level 2: Based on MCP tools provided
"""

from typing import Dict, Any, List, Optional, Callable, Awaitable
import asyncio
from dataclasses import dataclass
import time
import json
from pathlib import Path

from supply_chain_agent.config import settings
from supply_chain_agent.tools.client import get_tool_client

# H4修复：导入ServiceContainer
from supply_chain_agent.common.service_container import ServiceContainer

# M37修复：导入统一有效值定义
from supply_chain_agent.common.valid_values import (
    VALID_WORK_TYPES,
    VALID_PRIORITIES,
    VALID_ISSUE_TYPES,
    VALID_URGENCIES,
    VALID_APPROVE_ACTIONS,
)

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

# 导入LLM客户端
try:
    from supply_chain_agent.agents.llm_client import get_llm_client
    LLM_CLIENT_AVAILABLE = True
except ImportError:
    LLM_CLIENT_AVAILABLE = False
    print("⚠️ LLM Client not available")

# 导入Prompt模板
try:
    from supply_chain_agent.prompts.execution_plan import (
        APPROVAL_PLAN_PROMPT,
        TOOL_PARAM_EXTRACTION_PROMPT,
        INITIAL_PARAM_GENERATION_PROMPT
    )
    # L7修复：导入降级Prompt模板
    from supply_chain_agent.prompts.fallback import TOOL_PARAM_EXTRACTION_FALLBACK
    PROMPTS_AVAILABLE = True
except ImportError:
    PROMPTS_AVAILABLE = False
    print("⚠️ Execution plan prompts not available")


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
        "工单查询": {"tool": "query_work_order", "level1": "信息查询"},
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
        "工单查询": "query_work_order",
        # 工单管理类
        "创建工单": "create_work_order",
        "审批工单": "approve_work_order",
        # 异常上报类
        "上报问题": "report_issue",
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
        "query_work_order": {
            "required": ["work_order_id"],
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

    # M37修复：有效值定义已移至 common/valid_values.py
    # 导入将在文件开头处理

    # AGENT.md 文件路径
    AGENT_MD_PATH = Path(__file__).parent / "AGENT.md"

    # 执行历史限制常量（M28修复）
    MAX_EXECUTION_HISTORY = 100

    def __init__(self, emit_event: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None):
        self.task_queue: List[Task] = []
        self.execution_history: List[Dict[str, Any]] = []
        self._emit_event = emit_event  # 事件发送回调
        self.task_queue: List[Task] = []
        self.execution_history: List[Dict[str, Any]] = []

        # 验证TOOL_PARAMS与MCP Server工具定义一致性（M18）
        self._validate_tool_params_consistency()

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

        # 缓存的AGENT.md内容
        self._agent_md_content: Optional[str] = None

    def set_emit_event(self, emit_event: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]]):
        """设置事件发送回调"""
        self._emit_event = emit_event

    async def _emit(self, event_type: str, data: Dict[str, Any]):
        """发送事件的辅助方法"""
        print(f"[Executor] 发送事件: {event_type}, data: {data}")
        if self._emit_event:
            try:
                await self._emit_event(event_type, data)
                print(f"[Executor] 事件发送成功: {event_type}")
            except Exception as e:
                print(f"⚠️ 发送事件失败: {e}")
        else:
            print(f"⚠️ _emit_event 未设置，无法发送事件")

    def _load_agent_md(self) -> str:
        """加载AGENT.md文件内容"""
        if self._agent_md_content is not None:
            return self._agent_md_content

        try:
            if self.AGENT_MD_PATH.exists():
                self._agent_md_content = self.AGENT_MD_PATH.read_text(encoding="utf-8")
                return self._agent_md_content
            else:
                print(f"⚠️ AGENT.md 文件不存在: {self.AGENT_MD_PATH}")
                return ""
        except Exception as e:
            print(f"⚠️ 加载 AGENT.md 失败: {e}")
            return ""

    async def _generate_approval_plan_with_llm_original(self, intent: Dict[str, Any]) -> List[str]:
        """
        使用LLM根据AGENT.md生成审批工单的执行计划。

        Args:
            intent: 解析后的意图，包含 intent_level_1, intent_level_2, entities

        Returns:
            任务名称列表
        """
        if not LLM_CLIENT_AVAILABLE:
            print("⚠️ LLM客户端不可用，使用默认审批流程")
            return self._get_default_approval_plan()

        if not PROMPTS_AVAILABLE:
            print("⚠️ Prompt模板不可用，使用默认审批流程")
            return self._get_default_approval_plan()

        # 加载AGENT.md作为上下文
        agent_md_content = self._load_agent_md()
        if not agent_md_content:
            print("⚠️ AGENT.md 内容为空，使用默认审批流程")
            return self._get_default_approval_plan()

        # 提取实体信息
        extracted_slots = intent.get("entities", [])
        slot_dict = {}
        for entity in extracted_slots:
            if isinstance(entity, dict):
                slot_dict[entity.get("type")] = entity.get("value")

        # 使用模板构建prompt
        prompt = APPROVAL_PLAN_PROMPT.format(
            agent_md_content=agent_md_content,
            entities=json.dumps(slot_dict, ensure_ascii=False, indent=2)
        )

        try:
            # H4修复：通过ServiceContainer获取LLM客户端
            llm_client = ServiceContainer.get_llm_client()
            result = await llm_client.generate_json(prompt)

            # 解析LLM返回的任务列表
            tasks = result.get("tasks", [])
            task_names = [task.get("tool", "") for task in tasks]

            print(f"📋 LLM生成的执行计划: {task_names}")

            return task_names

        except Exception as e:
            print(f"⚠️ LLM生成执行计划失败: {e}，使用默认审批流程")
            return self._get_default_approval_plan()

    def _get_default_approval_plan(self) -> List[str]:
        """获取默认的审批工单执行计划"""
        return [
            "query_work_order",
            "query_order",
            "query_customer_statistics"
        ]

    def _get_llm_client_for_skill(self):
        """获取用于 skill 的 LLM 客户端"""
        return ServiceContainer.get_llm_client()

    async def _generate_approval_plan_with_skill(self, intent: Dict[str, Any]) -> List[str]:
        """
        使用 skill 生成审批工单执行计划

        Args:
            intent: 解析后的意图

        Returns:
            任务名称列表
        """
        skill_name = "approval_workflow"
        skill_start_time = int(time.time() * 1000)

        # 发送 skill 加载开始事件
        await self._emit("skill_load", {
            "stepId": "plan_task-skill",
            "skillCall": {
                "id": f"skill-{skill_name}-{skill_start_time}",
                "name": skill_name,
                "displayName": "审批工单流程",
                "status": "running",
                "startTime": skill_start_time
            }
        })

        try:
            llm_client = self._get_llm_client_for_skill()

            # 提取实体信息
            extracted_slots = intent.get("entities", [])
            slot_dict = {}
            for entity in extracted_slots:
                if isinstance(entity, dict):
                    slot_dict[entity.get("type")] = entity.get("value")

            # 使用 skill 上下文生成计划（快速模式）
            result = await llm_client.generate_with_skill(
                prompt="根据流程指导，输出需要执行的工具列表。",
                skill_name=skill_name,
                additional_context={
                    "entities": slot_dict,
                },
                fast_mode=True,
                max_tokens=512  # 执行计划需要少量 token，512 有足够余量
            )

            # 解析 LLM 返回的任务列表
            # 处理 LLM 可能返回列表或字典的情况
            if isinstance(result, list):
                # LLM 直接返回了任务列表
                tasks = result
            elif isinstance(result, dict):
                # LLM 返回了包含 tasks 键的字典
                tasks = result.get("tasks", [])
            else:
                print(f"⚠️ LLM 返回格式异常: {type(result)}")
                tasks = []

            task_names = []
            for task in tasks:
                if isinstance(task, dict):
                    tool_name = task.get("tool", "")
                    if tool_name:
                        task_names.append(tool_name)
                elif isinstance(task, str):
                    # 任务可能是直接的字符串
                    task_names.append(task)

            print(f"📋 Skill 生成的执行计划: {task_names}")

            # 发送 skill 加载成功事件
            skill_end_time = int(time.time() * 1000)
            await self._emit("skill_load", {
                "stepId": "plan_task-skill",
                "skillCall": {
                    "id": f"skill-{skill_name}-{skill_start_time}",
                    "name": skill_name,
                    "displayName": "审批工单流程",
                    "status": "success",
                    "startTime": skill_start_time,
                    "endTime": skill_end_time,
                    "result": task_names
                }
            })

            return task_names

        except Exception as e:
            # 发送 skill 加载失败事件
            skill_end_time = int(time.time() * 1000)
            await self._emit("skill_load", {
                "stepId": "plan_task-skill",
                "skillCall": {
                    "id": f"skill-{skill_name}-{skill_start_time}",
                    "name": skill_name,
                    "displayName": "审批工单流程",
                    "status": "error",
                    "startTime": skill_start_time,
                    "endTime": skill_end_time,
                    "error": str(e)
                }
            })
            raise

        return task_names

    async def _generate_approval_plan_with_prompt(self, intent: Dict[str, Any]) -> List[str]:
        """
        使用 prompt 模板生成审批工单执行计划（fallback）

        Args:
            intent: 解析后的意图

        Returns:
            任务名称列表
        """
        # 使用现有的 prompt 模板方法
        return await self._generate_approval_plan_with_llm_original(intent)

    async def _generate_approval_plan_with_llm(self, intent: Dict[str, Any]) -> List[str]:
        """
        使用 LLM 根据 AGENT.md 生成审批工单的执行计划。

        支持两种模式：
        1. Skill 模式：使用 skill 文件作为上下文
        2. Prompt 模式：使用 prompt 模板（fallback）

        Args:
            intent: 解析后的意图，包含 intent_level_1, intent_level_2, entities

        Returns:
            任务名称列表
        """
        from supply_chain_agent.config import settings

        # 检查是否启用 skill 模式
        if settings.use_skill_for_approval:
            try:
                return await self._generate_approval_plan_with_skill(intent)
            except Exception as e:
                print(f"⚠️ Skill 模式失败: {e}")
                if settings.skill_fallback_to_prompt:
                    print("⬇️ 降级到 prompt 模式...")
                    return await self._generate_approval_plan_with_prompt(intent)
                raise

        # 使用 prompt 模式
        return await self._generate_approval_plan_with_prompt(intent)

    def get_available_tools(self) -> Dict[str, Any]:
        """获取所有可用工具及其参数定义"""
        return {
            "level_1_tasks": self.LEVEL_1_TASKS,
            "level_2_tasks": self.LEVEL_2_TASKS,
            "tool_params": self.TOOL_PARAMS,
            "valid_values": {
                # M37修复：使用模块级常量
                "work_types": VALID_WORK_TYPES,
                "priorities": VALID_PRIORITIES,
                "issue_types": VALID_ISSUE_TYPES,
                "urgencies": VALID_URGENCIES,
                "approve_actions": VALID_APPROVE_ACTIONS
            }
        }

    def _validate_tool_params_consistency(self):
        """
        验证TOOL_PARAMS与MCP Server工具定义一致性（解决M18）。

        注意：TOOL_PARAMS定义与MCPServer工具签名存在重复，
        此方法在初始化时验证一致性，确保两处定义同步。
        """
        try:
            from supply_chain_agent.tools.client import ToolClient
            # 获取MCP Server工具定义
            client = ToolClient()
            tool_defs = client.get_tool_definitions()

            # 验证工具名称一致性
            mcp_tools = set(tool_defs.keys())
            local_tools = set(self.TOOL_PARAMS.keys())

            missing_in_local = mcp_tools - local_tools
            if missing_in_local:
                print(f"⚠️ [M18] 工具定义不一致: MCP Server有但TOOL_PARAMS缺少: {missing_in_local}")

        except Exception as e:
            # 验证失败不影响初始化，仅记录日志
            pass

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
        """
        Map task name to tool and parameters based on MCP tool definitions.

        重构（M22）：使用映射表简化简单工具的参数构建，减少重复代码。
        """
        # Get tool name from mapping
        tool_name = self.TOOL_MAPPING.get(task_name, task_name)

        # 简单工具参数映射表（工具名 -> 参数名列表）
        SIMPLE_TOOL_PARAMS = {
            "query_customer": ["customer_id"],
            "query_customer_orders": ["customer_id", ("limit", 20), ("offset", 0)],
            "query_order": ["order_id"],
            "query_order_items": ["order_id"],
            "query_product": ["product_card_id"],
            "query_shipment": ["order_id"],
            "query_customer_statistics": ["customer_id"],
            "query_work_order": ["work_order_id"],
        }

        # 检查是否为简单工具
        if tool_name in SIMPLE_TOOL_PARAMS:
            params = {}
            for param_def in SIMPLE_TOOL_PARAMS[tool_name]:
                if isinstance(param_def, tuple):
                    # (param_name, default_value)
                    params[param_def[0]] = extracted_slots.get(param_def[0], param_def[1])
                else:
                    # param_name (no default)
                    params[param_def] = extracted_slots.get(param_def)
            return tool_name, params

        # 复杂工具：需要特殊验证逻辑
        if tool_name == "create_work_order":
            work_type = extracted_slots.get("work_type", "其他")
            if work_type not in VALID_WORK_TYPES:
                work_type = "其他"

            priority = extracted_slots.get("priority", "中")
            if priority not in VALID_PRIORITIES:
                priority = "中"

            params = {
                "work_type": work_type,
                "description": extracted_slots.get("description", ""),
                "priority": priority,
            }
            # 只有有值时才添加可选参数
            for opt_param in ["order_id", "assigned_to"]:
                if extracted_slots.get(opt_param):
                    params[opt_param] = extracted_slots.get(opt_param)

            return "create_work_order", params

        if tool_name == "approve_work_order":
            action = extracted_slots.get("action", "approve")
            if action not in VALID_APPROVE_ACTIONS:
                action = "approve"

            return "approve_work_order", {
                "work_order_id": extracted_slots.get("work_order_id"),
                "action": action,
                "comment": extracted_slots.get("comment", ""),
                "approver": extracted_slots.get("approver", "Agent System")
            }

        if tool_name == "report_issue":
            issue_type = extracted_slots.get("issue_type", "其他")
            if issue_type not in VALID_ISSUE_TYPES:
                issue_type = "其他"

            urgency = extracted_slots.get("urgency", "中")
            if urgency not in VALID_URGENCIES:
                urgency = "中"

            params = {
                "issue_type": issue_type,
                "description": extracted_slots.get("description", ""),
                "urgency": urgency,
                "reported_by": extracted_slots.get("reported_by", "Agent System")
            }
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
            "query_work_order": 2,
            # 工单管理类
            "create_work_order": 1,
            "approve_work_order": 0,  # 需要确认，优先级最低
            # 异常上报类 (优先级最高)
            "report_issue": 0  # 异常上报优先级最高
        }
        return priority_map.get(tool_name, 2)

    async def _execute_tool(self, task: Task) -> Dict[str, Any]:
        """Execute a tool with intelligent retry logic."""
        # H4修复：通过ServiceContainer获取tool_client
        # 注意：get_tool_client 是同步方法，不需要 await
        client = ServiceContainer.get_tool_client()

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

        # 保持执行历史大小（M28修复：使用常量，提前截断）
        if len(self.execution_history) > self.MAX_EXECUTION_HISTORY:
            # 保留最新的记录，删除旧的
            self.execution_history = self.execution_history[-self.MAX_EXECUTION_HISTORY:]

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

        Raises:
            ValueError: When intent is empty or invalid
        """
        intent_level_1 = intent.get("intent_level_1", "")
        intent_level_2 = intent.get("intent_level_2", "")
        extracted_slots = intent.get("entities", [])

        # 验证意图有效性
        if not intent_level_1 and not intent_level_2:
            print("⚠️ [执行计划] 意图为空，无法生成执行计划")
            return []

        # Convert entities to slot dict
        slot_dict = {}
        for entity in extracted_slots:
            if isinstance(entity, dict):
                slot_dict[entity.get("type")] = entity.get("value")

        # 特殊处理：审批工单 - 使用LLM + AGENT.md生成执行计划
        if intent_level_2 == "审批工单" or intent_level_1 == "工单管理" and "审批" in str(extracted_slots):
            print(f"🎯 检测到审批工单意图，使用LLM生成执行计划...")
            return await self._generate_approval_plan_with_llm(intent)

        # First try intent_level_2 (more specific), then intent_level_1 (fallback)
        tool_name = self.TOOL_MAPPING.get(intent_level_2,
                                          self.TOOL_MAPPING.get(intent_level_1, ""))

        if tool_name:
            if self._can_execute_tool(tool_name, slot_dict):
                print(f"📋 [执行计划] 意图 '{intent_level_1}/{intent_level_2}' 映射到工具: {tool_name}")
                return [tool_name]
            else:
                # 工具存在但参数不满足
                missing_params = self._get_missing_params(tool_name, slot_dict)
                print(f"⚠️ [执行计划] 工具 '{tool_name}' 缺少必要参数: {missing_params}")
                # 返回工具名，让后续流程处理参数缺失
                return [tool_name]

        # 未知意图的回退处理
        print(f"⚠️ [执行计划] 未知意图: level_1='{intent_level_1}', level_2='{intent_level_2}'")
        print(f"   可用意图映射: {list(self.TOOL_MAPPING.keys())[:10]}...")
        return []

    async def execute_plan_with_llm_feedback(
        self,
        execution_plan: List[str],
        initial_slots: Dict[str, Any],
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行工具计划，每一步都将结果发送给LLM解析获取下一步工具的入参。

        流程：
        1. 开始执行前，可选启动一个独立的LLM调用获取初始参数（如有则不改动）
        2. 依次执行每个工具
        3. 每执行完一个工具，将执行结果发送给LLM解析
        4. LLM输出下一步工具执行的入参
        5. 结合入参和当前待执行工具，继续工具执行
        6. 直至执行计划的所有工具执行完毕，或抛出异常退出

        Args:
            execution_plan: 工具名称列表，如 ['query_work_order', 'query_order', 'query_customer_statistics']
            initial_slots: 初始实体/槽位信息
            intent: 用户意图

        Returns:
            包含所有执行结果和最终状态的字典
        """
        if not execution_plan:
            print("⚠️ 执行计划为空，无需执行")
            return {
                "success": True,
                "results": {},
                "message": "执行计划为空"
            }

        print(f"📋 开始执行计划，共 {len(execution_plan)} 个工具: {execution_plan}")

        # 初始化执行状态
        current_slots = dict(initial_slots)  # 复制初始槽位
        all_results = {}  # 存储所有工具执行结果
        execution_context = {
            "intent": intent,
            "plan": execution_plan,
            "executed_tools": [],
            "current_step": 0
        }

        try:
            # 依次执行每个工具
            for step_index, tool_name in enumerate(execution_plan):
                execution_context["current_step"] = step_index + 1
                print(f"\n🔧 [步骤 {step_index + 1}/{len(execution_plan)}] 执行工具: {tool_name}")

                # 如果是第一步且需要LLM生成初始参数，可以在这里调用
                # 但用户说"如有则不改动"，所以保持现有逻辑

                # 使用当前槽位构建参数并执行工具
                tool_result = await self._execute_single_tool_with_slots(
                    tool_name,
                    current_slots,
                    execution_context
                )

                # 记录执行结果
                all_results[tool_name] = tool_result
                execution_context["executed_tools"].append(tool_name)

                # 检查执行是否成功
                if tool_result.get("error") or tool_result.get("success") == False:
                    error_msg = tool_result.get("error", "未知错误")
                    print(f"❌ 工具 {tool_name} 执行失败: {error_msg}")
                    # 执行失败，终止流程
                    return {
                        "success": False,
                        "results": all_results,
                        "error": f"工具 {tool_name} 执行失败: {error_msg}",
                        "failed_at_step": step_index + 1,
                        "execution_context": execution_context
                    }

                print(f"✅ 工具 {tool_name} 执行成功")

                # 如果还有下一个工具，将当前结果发送给LLM解析获取下一步入参
                if step_index < len(execution_plan) - 1:
                    next_tool_name = execution_plan[step_index + 1]
                    print(f"📤 将执行结果发送给LLM，解析下一步工具 {next_tool_name} 的入参...")

                    # 调用LLM解析结果并生成下一步参数
                    llm_params = await self._llm_parse_for_next_tool_params(
                        current_tool=tool_name,
                        current_result=tool_result,
                        next_tool=next_tool_name,
                        current_slots=current_slots,
                        execution_context=execution_context
                    )

                    if llm_params:
                        # 更新槽位，合并LLM生成的参数
                        current_slots.update(llm_params)
                        print(f"📥 LLM返回的参数: {llm_params}")
                    else:
                        print(f"⚠️ LLM未返回有效参数，继续使用当前槽位")

            # 所有工具执行完毕
            print(f"\n🎉 执行计划完成，共执行 {len(execution_plan)} 个工具")
            return {
                "success": True,
                "results": all_results,
                "final_slots": current_slots,
                "execution_context": execution_context
            }

        except Exception as e:
            print(f"❌ 执行计划异常: {e}")
            return {
                "success": False,
                "results": all_results,
                "error": f"执行计划异常: {str(e)}",
                "execution_context": execution_context
            }

    async def _execute_single_tool_with_slots(
        self,
        tool_name: str,
        slots: Dict[str, Any],
        execution_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        使用当前槽位执行单个工具。

        Args:
            tool_name: 工具名称
            slots: 当前槽位信息
            execution_context: 执行上下文

        Returns:
            工具执行结果
        """
        # 根据工具名称构建参数
        parameters = self._build_tool_parameters(tool_name, slots)

        # 验证参数
        validation_result = self._validate_tool_params(tool_name, parameters)
        if not validation_result["valid"]:
            return {
                "error": validation_result["message"],
                "tool": tool_name,
                "success": False,
                "error_type": "validation_failed"
            }

        # 创建任务并执行
        task = Task(
            name=tool_name,
            tool_name=tool_name,
            parameters=parameters,
            priority=self._get_task_priority(tool_name)
        )

        return await self._execute_tool(task)

    def _build_tool_parameters(self, tool_name: str, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据工具名称和当前槽位构建工具参数。

        Args:
            tool_name: 工具名称
            slots: 当前槽位信息

        Returns:
            工具参数字典
        """
        # 复用现有的映射逻辑
        _, parameters = self._map_task_to_tool(tool_name, slots)
        return parameters

    async def _llm_parse_for_next_tool_params(
        self,
        current_tool: str,
        current_result: Dict[str, Any],
        next_tool: str,
        current_slots: Dict[str, Any],
        execution_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        使用LLM解析当前工具执行结果，生成下一个工具的入参。

        Args:
            current_tool: 当前执行的工具名称
            current_result: 当前工具的执行结果
            next_tool: 下一个要执行的工具名称
            current_slots: 当前槽位信息
            execution_context: 执行上下文

        Returns:
            下一个工具的参数字典，或None如果解析失败
        """
        if not LLM_CLIENT_AVAILABLE:
            print("⚠️ LLM客户端不可用，无法解析结果")
            return None

        # 构建prompt
        prompt = self._build_llm_param_extraction_prompt(
            current_tool,
            current_result,
            next_tool,
            current_slots,
            execution_context
        )

        try:
            # H4修复：通过ServiceContainer获取LLM客户端
            llm_client = ServiceContainer.get_llm_client()
            result = await llm_client.generate_json(prompt)

            # 提取参数
            params = result.get("parameters", {})
            return params

        except Exception as e:
            print(f"⚠️ LLM解析参数失败: {e}")
            return None

    def _build_llm_param_extraction_prompt(
        self,
        current_tool: str,
        current_result: Dict[str, Any],
        next_tool: str,
        current_slots: Dict[str, Any],
        execution_context: Dict[str, Any]
    ) -> str:
        """
        构建用于LLM解析下一步工具参数的prompt。

        Args:
            current_tool: 当前工具名称
            current_result: 当前工具执行结果
            next_tool: 下一个工具名称
            current_slots: 当前槽位
            execution_context: 执行上下文

        Returns:
            构建好的prompt字符串
        """
        # 获取下一个工具的参数定义
        next_tool_params_def = self.TOOL_PARAMS.get(next_tool, {})
        required_params = next_tool_params_def.get("required", [])
        optional_params = next_tool_params_def.get("optional", [])

        # 如果有模板，使用模板
        if PROMPTS_AVAILABLE:
            prompt = TOOL_PARAM_EXTRACTION_PROMPT.format(
                execution_plan=json.dumps(execution_context.get("plan", []), ensure_ascii=False),
                executed_tools=json.dumps(execution_context.get("executed_tools", []), ensure_ascii=False),
                current_step=execution_context.get("current_step", 1),
                current_tool=current_tool,
                current_result=json.dumps(current_result, ensure_ascii=False, indent=2, default=str),
                next_tool=next_tool,
                required_params=json.dumps(required_params, ensure_ascii=False),
                optional_params=json.dumps(optional_params, ensure_ascii=False),
                current_slots=json.dumps(current_slots, ensure_ascii=False, indent=2)
            )
            return prompt

        # L7修复：使用模板文件中的降级Prompt，而非硬编码
        prompt = TOOL_PARAM_EXTRACTION_FALLBACK.format(
            execution_plan=json.dumps(execution_context.get("plan", []), ensure_ascii=False),
            executed_tools=json.dumps(execution_context.get("executed_tools", []), ensure_ascii=False),
            current_step=execution_context.get("current_step", 1),
            current_tool=current_tool,
            current_result=json.dumps(current_result, ensure_ascii=False, indent=2, default=str),
            next_tool=next_tool,
            required_params=json.dumps(required_params, ensure_ascii=False),
            optional_params=json.dumps(optional_params, ensure_ascii=False),
            current_slots=json.dumps(current_slots, ensure_ascii=False, indent=2)
        )
        return prompt

    def _can_execute_tool(self, tool_name: str, slots: Dict[str, Any]) -> bool:
        """Check if a tool can be executed with available slots."""
        if tool_name not in self.TOOL_PARAMS:
            return False

        required_params = self.TOOL_PARAMS[tool_name]["required"]

        for param in required_params:
            if param not in slots or not slots[param]:
                return False

        return True

    def _get_missing_params(self, tool_name: str, slots: Dict[str, Any]) -> List[str]:
        """
        Get list of missing required parameters for a tool.

        Args:
            tool_name: Name of the tool
            slots: Available slots/values

        Returns:
            List of missing parameter names
        """
        if tool_name not in self.TOOL_PARAMS:
            return []

        required_params = self.TOOL_PARAMS[tool_name]["required"]
        missing = []

        for param in required_params:
            if param not in slots or not slots[param]:
                missing.append(param)

        return missing

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
