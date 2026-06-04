"""
M37修复：统一有效值定义

将分散在executor.py、server.py、supply_chain_db.py中的有效值定义集中管理。
"""

from typing import List, FrozenSet


# ==========================================
# 工单相关有效值
# ==========================================

# 工单类型
VALID_WORK_TYPES: List[str] = ["审批", "异常处理", "退款", "调拨", "质检", "其他"]
VALID_WORK_TYPES_SET: FrozenSet[str] = frozenset(VALID_WORK_TYPES)

# 工单优先级
VALID_PRIORITIES: List[str] = ["高", "中", "低"]
VALID_PRIORITIES_SET: FrozenSet[str] = frozenset(VALID_PRIORITIES)

# 工单状态
VALID_WORK_ORDER_STATUSES: List[str] = ["待处理", "待审批", "处理中", "已通过", "已拒绝", "已关闭"]
VALID_WORK_ORDER_STATUSES_SET: FrozenSet[str] = frozenset(VALID_WORK_ORDER_STATUSES)

# 审批动作
VALID_APPROVE_ACTIONS: List[str] = ["approve", "reject", "escalate"]
VALID_APPROVE_ACTIONS_SET: FrozenSet[str] = frozenset(VALID_APPROVE_ACTIONS)


# ==========================================
# 问题上报相关有效值
# ==========================================

# 问题类型
VALID_ISSUE_TYPES: List[str] = ["物流延迟", "库存异常", "质量缺陷", "数据错误", "客户投诉", "其他"]
VALID_ISSUE_TYPES_SET: FrozenSet[str] = frozenset(VALID_ISSUE_TYPES)

# 紧急程度
VALID_URGENCIES: List[str] = ["高", "中", "低"]
VALID_URGENCIES_SET: FrozenSet[str] = frozenset(VALID_URGENCIES)


# ==========================================
# 辅助函数
# ==========================================

def validate_work_type(work_type: str) -> bool:
    """验证工单类型是否有效"""
    return work_type in VALID_WORK_TYPES_SET


def validate_priority(priority: str) -> bool:
    """验证优先级是否有效"""
    return priority in VALID_PRIORITIES_SET


def validate_work_order_status(status: str) -> bool:
    """验证工单状态是否有效"""
    return status in VALID_WORK_ORDER_STATUSES_SET


def validate_approve_action(action: str) -> bool:
    """验证审批动作是否有效"""
    return action in VALID_APPROVE_ACTIONS_SET


def validate_issue_type(issue_type: str) -> bool:
    """验证问题类型是否有效"""
    return issue_type in VALID_ISSUE_TYPES_SET


def validate_urgency(urgency: str) -> bool:
    """验证紧急程度是否有效"""
    return urgency in VALID_URGENCIES_SET


def get_valid_work_types() -> List[str]:
    """获取有效工单类型列表"""
    return VALID_WORK_TYPES.copy()


def get_valid_priorities() -> List[str]:
    """获取有效优先级列表"""
    return VALID_PRIORITIES.copy()


def get_valid_work_order_statuses() -> List[str]:
    """获取有效工单状态列表"""
    return VALID_WORK_ORDER_STATUSES.copy()


def get_valid_approve_actions() -> List[str]:
    """获取有效审批动作列表"""
    return VALID_APPROVE_ACTIONS.copy()


def get_valid_issue_types() -> List[str]:
    """获取有效问题类型列表"""
    return VALID_ISSUE_TYPES.copy()


def get_valid_urgencies() -> List[str]:
    """获取有效紧急程度列表"""
    return VALID_URGENCIES.copy()


# ==========================================
# 所有有效值的映射（用于API返回）
# ==========================================

ALL_VALID_VALUES = {
    "work_types": VALID_WORK_TYPES,
    "priorities": VALID_PRIORITIES,
    "work_order_statuses": VALID_WORK_ORDER_STATUSES,
    "approve_actions": VALID_APPROVE_ACTIONS,
    "issue_types": VALID_ISSUE_TYPES,
    "urgencies": VALID_URGENCIES
}


__all__ = [
    # 列表常量
    "VALID_WORK_TYPES",
    "VALID_PRIORITIES",
    "VALID_WORK_ORDER_STATUSES",
    "VALID_APPROVE_ACTIONS",
    "VALID_ISSUE_TYPES",
    "VALID_URGENCIES",
    # 集合常量（用于快速查找）
    "VALID_WORK_TYPES_SET",
    "VALID_PRIORITIES_SET",
    "VALID_WORK_ORDER_STATUSES_SET",
    "VALID_APPROVE_ACTIONS_SET",
    "VALID_ISSUE_TYPES_SET",
    "VALID_URGENCIES_SET",
    # 验证函数
    "validate_work_type",
    "validate_priority",
    "validate_work_order_status",
    "validate_approve_action",
    "validate_issue_type",
    "validate_urgency",
    # 获取函数
    "get_valid_work_types",
    "get_valid_priorities",
    "get_valid_work_order_statuses",
    "get_valid_approve_actions",
    "get_valid_issue_types",
    "get_valid_urgencies",
    # 汇总映射
    "ALL_VALID_VALUES"
]
