"""
Agent通信协议定义

提供Agent间统一的消息格式和通信协议，确保类型安全和可追溯性。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid


@dataclass
class AgentMessage:
    """
    Agent间统一消息格式。

    所有Agent间通信应使用此消息格式，确保：
    - 可追溯性：通过 correlation_id 追踪完整调用链
    - 类型安全：明确的发送者和接收者
    - 可扩展：payload 支持任意结构化数据
    """
    sender: str                          # 发送者名称
    receiver: str                        # 接收者名称
    action: str                          # 动作类型
    payload: Dict[str, Any]              # 消息内容
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])  # 关联ID
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict[str, Any] = field(default_factory=dict)  # 可选元数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "action": self.action,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """从字典创建消息"""
        return cls(
            sender=data.get("sender", "unknown"),
            receiver=data.get("receiver", "unknown"),
            action=data.get("action", "unknown"),
            payload=data.get("payload", {}),
            correlation_id=data.get("correlation_id", str(uuid.uuid4())[:8]),
            timestamp=data.get("timestamp", datetime.now().timestamp()),
            metadata=data.get("metadata", {})
        )


@dataclass
class IntentResult:
    """
    意图识别结果标准格式。

    Parser Agent 输出的标准结构，供后续 Agent 使用。
    """
    intent_level_1: str                  # 一级意图
    intent_level_2: str                  # 二级意图
    confidence: float                    # 置信度 (0.0-1.0)
    entities: List[Dict[str, str]]       # 提取的实体列表
    slots: Dict[str, Any]                # 填充的槽位
    missing_slots: List[str]             # 缺失的槽位
    raw_text: str                        # 原始文本
    needs_clarification: bool = False    # 是否需要澄清

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "intent_level_1": self.intent_level_1,
            "intent_level_2": self.intent_level_2,
            "confidence": self.confidence,
            "entities": self.entities,
            "slots": self.slots,
            "missing_slots": self.missing_slots,
            "raw_text": self.raw_text,
            "needs_clarification": self.needs_clarification
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntentResult":
        """从字典创建"""
        return cls(
            intent_level_1=data.get("intent_level_1", ""),
            intent_level_2=data.get("intent_level_2", ""),
            confidence=data.get("confidence", 0.0),
            entities=data.get("entities", []),
            slots=data.get("slots", {}),
            missing_slots=data.get("missing_slots", []),
            raw_text=data.get("raw_text", ""),
            needs_clarification=data.get("needs_clarification", False)
        )


@dataclass
class ToolResult:
    """
    工具执行结果标准格式。

    Executor Agent 输出的标准结构，供 Auditor 验证。
    """
    tool_name: str                       # 工具名称
    success: bool                        # 是否成功
    data: Dict[str, Any]                 # 返回数据
    error: Optional[str] = None          # 错误信息
    execution_time_ms: float = 0.0       # 执行时间(毫秒)
    fallback_used: bool = False          # 是否使用了降级

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "fallback_used": self.fallback_used
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolResult":
        """从字典创建"""
        return cls(
            tool_name=data.get("tool_name", ""),
            success=data.get("success", False),
            data=data.get("data", {}),
            error=data.get("error"),
            execution_time_ms=data.get("execution_time_ms", 0.0),
            fallback_used=data.get("fallback_used", False)
        )


@dataclass
class AuditResult:
    """
    审计结果标准格式。

    Auditor Agent 输出的标准结构，供 ReportGenerator 使用。
    """
    passed: bool                         # 是否通过
    issues: List[str]                    # 问题列表
    warnings: List[str]                  # 警告列表
    risk_score: float                    # 风险评分 (0.0-1.0)
    suggestions: List[str]               # 建议列表

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "passed": self.passed,
            "issues": self.issues,
            "warnings": self.warnings,
            "risk_score": self.risk_score,
            "suggestions": self.suggestions
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditResult":
        """从字典创建"""
        return cls(
            passed=data.get("passed", False),
            issues=data.get("issues", []),
            warnings=data.get("warnings", []),
            risk_score=data.get("risk_score", 0.0),
            suggestions=data.get("suggestions", [])
        )


@dataclass
class InterruptInfo:
    """
    中断信息统一格式。

    用于处理LangGraph中断的多种格式（dict/tuple/对象），
    提供统一的访问接口。

    LangGraph中断可能来自：
    1. Interrupt对象（有value属性）
    2. 元组格式：(resumable_value, interrupt_value)
    3. 字典格式：{"prompt": "...", "type": "..."}
    4. 字符串格式：直接作为prompt
    """
    prompt: str                          # 中断提示信息
    interrupt_type: str = "clarification"  # 中断类型
    resumable_value: Optional[Any] = None  # 可恢复值
    raw_data: Optional[Any] = None        # 原始数据（用于调试）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "prompt": self.prompt,
            "interrupt_type": self.interrupt_type,
            "resumable_value": self.resumable_value
        }

    @classmethod
    def from_langgraph_interrupt(cls, interrupt_data: Any) -> "InterruptInfo":
        """
        从LangGraph中断数据创建统一格式。

        处理多种中断格式：
        1. Interrupt对象（有value属性）
        2. 元组格式
        3. 字典格式
        4. 其他格式（尝试转换）

        Args:
            interrupt_data: LangGraph返回的中断数据

        Returns:
            标准化的InterruptInfo对象
        """
        # 情况1：Interrupt对象（有value属性）
        if hasattr(interrupt_data, 'value'):
            value = interrupt_data.value
            if isinstance(value, dict):
                return cls(
                    prompt=value.get("prompt", "请提供更多信息"),
                    interrupt_type=value.get("type", "clarification"),
                    raw_data=interrupt_data
                )
            return cls(
                prompt=str(value) if value else "请提供更多信息",
                raw_data=interrupt_data
            )

        # 情况2：元组格式
        if isinstance(interrupt_data, tuple):
            if len(interrupt_data) >= 2:
                # 元组可能是 (resumable, interrupt_value)
                second = interrupt_data[1]
                if isinstance(second, dict):
                    return cls(
                        prompt=second.get("prompt", "请提供更多信息"),
                        interrupt_type=second.get("type", "clarification"),
                        resumable_value=interrupt_data[0],
                        raw_data=interrupt_data
                    )
                return cls(
                    prompt=str(second),
                    resumable_value=interrupt_data[0],
                    raw_data=interrupt_data
                )
            elif len(interrupt_data) == 1:
                return cls(
                    prompt=str(interrupt_data[0]),
                    raw_data=interrupt_data
                )
            return cls(prompt="请提供更多信息", raw_data=interrupt_data)

        # 情况3：字典格式
        if isinstance(interrupt_data, dict):
            return cls(
                prompt=interrupt_data.get("prompt", "请提供更多信息"),
                interrupt_type=interrupt_data.get("type", "clarification"),
                raw_data=interrupt_data
            )

        # 情况4：其他格式（尝试转换）
        try:
            return cls(prompt=str(interrupt_data), raw_data=interrupt_data)
        except Exception:
            return cls(prompt="请提供更多信息", raw_data=interrupt_data)


# 常量定义：Agent名称
class AgentName:
    """Agent名称常量"""
    ORCHESTRATOR = "orchestrator"
    PARSER = "parser"
    EXECUTOR = "executor"
    AUDITOR = "auditor"
    REPORT_GENERATOR = "report_generator"


# M31修复：添加枚举类型替代字符串字面量
from enum import Enum, auto


class IntentType(str, Enum):
    """意图类型枚举（一级意图）"""
    INFO_QUERY = "信息查询"
    STATUS_QUERY = "状态查询"
    WORK_ORDER = "工单管理"
    RISK_ASSESSMENT = "风险评估"
    UNKNOWN = "未知"

    def __str__(self) -> str:
        return self.value


class NodeStatus(str, Enum):
    """节点返回状态枚举"""
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"
    NEEDS_CLARIFICATION = "needs_clarification"

    def __str__(self) -> str:
        return self.value


class InterruptType(str, Enum):
    """中断类型枚举"""
    CLARIFICATION = "clarification"
    APPROVAL = "approval"
    CONFIRMATION = "confirmation"

    def __str__(self) -> str:
        return self.value


# L9修复：验证错误严重程度枚举
class ValidationErrorSeverity(str, Enum):
    """验证错误严重程度"""
    CRITICAL = "critical"      # 阻断流程，必须修复
    WARNING = "warning"        # 警告，可继续但不推荐
    INFO = "info"              # 信息提示，不影响流程

    def __str__(self) -> str:
        return self.value


# L9修复：结构化验证错误
@dataclass
class ValidationError:
    """结构化验证错误（支持严重程度区分）"""
    message: str
    severity: str = "warning"  # critical/warning/info
    field: Optional[str] = None
    value: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "severity": self.severity,
            "field": self.field,
            "value": self.value
        }

    def is_blocking(self) -> bool:
        """是否阻断流程"""
        return self.severity == "critical"


# 常量定义：动作类型
class ActionType:
    """动作类型常量"""
    # Parser 动作
    PARSE_INTENT = "parse_intent"
    REQUEST_CLARIFICATION = "request_clarification"

    # Executor 动作
    EXECUTE_TOOL = "execute_tool"
    CREATE_PLAN = "create_plan"

    # Auditor 动作
    AUDIT_RESULTS = "audit_results"
    CALCULATE_RISK = "calculate_risk"

    # Orchestrator 动作
    PROCESS_INPUT = "process_input"
    HANDLE_ERROR = "handle_error"


# 字段映射常量（解决M20重复定义问题）
# 统一的槽位/字段中文描述映射
SLOT_DESCRIPTIONS = {
    # 订单相关
    "order_id": "订单号",
    "order_id_alias": ["orderId", "订单编号", "PO号"],

    # 客户相关
    "customer_id": "客户ID",
    "customer_id_alias": ["customerId", "客户编号"],
    "customer_name": "客户名称",

    # 产品相关
    "product_card_id": "产品卡片ID",
    "product_card_id_alias": ["productId", "产品编号", "产品ID"],

    # 物流相关
    "tracking_no": "运单号",
    "tracking_no_alias": ["tracking_number", "物流单号"],

    # 工单相关
    "work_order_id": "工单号",
    "work_order_id_alias": ["workOrderId", "工单编号"],
    "work_type": "工单类型",
    "description": "描述",

    # 审批相关
    "action": "审批动作",
    "comment": "审批意见",
    "approver": "审批人",

    # 问题上报相关
    "issue_type": "问题类型",
    "urgency": "紧急程度",

    # 分页相关
    "limit": "返回数量限制",
    "offset": "分页偏移量"
}


def get_slot_description(slot_name: str) -> str:
    """
    获取槽位的中文名称描述。

    Args:
        slot_name: 槽位名称

    Returns:
        中文描述，如果未找到则返回原名称
    """
    # 直接查找
    if slot_name in SLOT_DESCRIPTIONS:
        return SLOT_DESCRIPTIONS[slot_name]

    # 查找别名
    for key, value in SLOT_DESCRIPTIONS.items():
        if key.endswith("_alias") and slot_name in value:
            # 获取对应的主字段名称
            main_key = key.replace("_alias", "")
            return SLOT_DESCRIPTIONS.get(main_key, slot_name)

    return slot_name


def normalize_slot_name(slot_name: str) -> str:
    """
    标准化槽位名称（将别名转换为主名称）。

    Args:
        slot_name: 可能是别名的槽位名称

    Returns:
        标准化后的主名称
    """
    # 如果已经是主名称，直接返回
    if slot_name in SLOT_DESCRIPTIONS and not slot_name.endswith("_alias"):
        return slot_name

    # 查找别名映射
    for key, value in SLOT_DESCRIPTIONS.items():
        if key.endswith("_alias") and slot_name in value:
            return key.replace("_alias", "")

    return slot_name


# 导出
__all__ = [
    "AgentMessage",
    "IntentResult",
    "ToolResult",
    "AuditResult",
    "InterruptInfo",
    "AgentName",
    "ActionType",
    "SLOT_DESCRIPTIONS",
    "get_slot_description",
    "normalize_slot_name",
    # M31修复：新增枚举类型
    "IntentType",
    "NodeStatus",
    "InterruptType"
]
