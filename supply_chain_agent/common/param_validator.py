"""
统一参数验证工具（L12修复：集中MCP工具参数校验逻辑）

提供工具参数的统一验证，供MCPServer和ExecutorAgent共同使用。
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    message: str
    missing_params: List[str] = None
    invalid_params: List[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "message": self.message,
            "missing_params": self.missing_params or [],
            "invalid_params": self.invalid_params or []
        }


# 工具参数定义（单一来源）
TOOL_PARAM_SPECS = {
    "query_customer": {
        "required": ["customer_id"],
        "types": {"customer_id": int},
        "ranges": {"customer_id": (1, None)}
    },
    "query_customer_orders": {
        "required": ["customer_id"],
        "optional": ["limit", "offset"],
        "types": {"customer_id": int, "limit": int, "offset": int},
        "ranges": {"limit": (1, 100), "offset": (0, None)}
    },
    "query_order": {
        "required": ["order_id"],
        "types": {"order_id": int},
        "ranges": {"order_id": (1, None)}
    },
    "query_order_items": {
        "required": ["order_id"],
        "types": {"order_id": int},
        "ranges": {"order_id": (1, None)}
    },
    "query_product": {
        "required": ["product_card_id"],
        "types": {"product_card_id": int},
        "ranges": {"product_card_id": (1, None)}
    },
    "query_shipment": {
        "required": ["order_id"],
        "types": {"order_id": int},
        "ranges": {"order_id": (1, None)}
    },
    "query_customer_statistics": {
        "required": ["customer_id"],
        "types": {"customer_id": int},
        "ranges": {"customer_id": (1, None)}
    },
    "create_work_order": {
        "required": ["work_type", "description"],
        "optional": ["priority", "order_id", "assigned_to"],
        "types": {"work_type": str, "description": str, "priority": str},
        "valid_values": {
            "work_type": ["审批", "异常处理", "退款", "调拨", "质检", "其他"],
            "priority": ["高", "中", "低"]
        }
    },
    "approve_work_order": {
        "required": ["work_order_id", "action"],
        "optional": ["comment", "approver"],
        "types": {"work_order_id": int, "action": str, "comment": str, "approver": str},
        "valid_values": {
            "action": ["approve", "reject", "escalate"]
        }
    },
    "report_issue": {
        "required": ["issue_type", "description"],
        "optional": ["urgency", "affected_order", "reported_by"],
        "types": {"issue_type": str, "description": str, "urgency": str},
        "valid_values": {
            "issue_type": ["物流延迟", "库存异常", "质量缺陷", "数据错误", "客户投诉", "其他"],
            "urgency": ["高", "中", "低"]
        }
    }
}


def validate_tool_params(tool_name: str, params: Dict[str, Any]) -> ValidationResult:
    """
    统一验证工具参数。

    Args:
        tool_name: 工具名称
        params: 参数字典

    Returns:
        ValidationResult: 验证结果
    """
    if tool_name not in TOOL_PARAM_SPECS:
        return ValidationResult(valid=True, message=f"工具 {tool_name} 无参数规范，跳过验证")

    spec = TOOL_PARAM_SPECS[tool_name]
    missing_params = []
    invalid_params = []

    # 检查必填参数
    for param in spec.get("required", []):
        value = params.get(param)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing_params.append(param)

    # 检查类型
    for param, expected_type in spec.get("types", {}).items():
        value = params.get(param)
        if value is not None and not isinstance(value, expected_type):
            # 尝试类型转换
            try:
                if expected_type == int and isinstance(value, str):
                    int(value)
                elif expected_type == str:
                    str(value)
                else:
                    invalid_params.append(f"{param}(期望{expected_type.__name__})")
            except (ValueError, TypeError):
                invalid_params.append(f"{param}(期望{expected_type.__name__})")

    # 检查范围
    for param, (min_val, max_val) in spec.get("ranges", {}).items():
        value = params.get(param)
        if value is not None:
            try:
                num_val = int(value) if isinstance(value, str) else value
                if min_val is not None and num_val < min_val:
                    invalid_params.append(f"{param}(最小值{min_val})")
                if max_val is not None and num_val > max_val:
                    invalid_params.append(f"{param}(最大值{max_val})")
            except (ValueError, TypeError):
                pass

    # 检查有效值
    for param, valid_values in spec.get("valid_values", {}).items():
        value = params.get(param)
        if value is not None and value not in valid_values:
            invalid_params.append(f"{param}(有效值:{','.join(valid_values[:3])}...)")

    # 构建结果
    if missing_params or invalid_params:
        messages = []
        if missing_params:
            messages.append(f"缺少必填参数: {', '.join(missing_params)}")
        if invalid_params:
            messages.append(f"无效参数: {', '.join(invalid_params)}")
        return ValidationResult(
            valid=False,
            message="; ".join(messages),
            missing_params=missing_params,
            invalid_params=invalid_params
        )

    return ValidationResult(valid=True, message="参数验证通过")


def get_tool_required_params(tool_name: str) -> List[str]:
    """获取工具的必填参数列表"""
    if tool_name not in TOOL_PARAM_SPECS:
        return []
    return TOOL_PARAM_SPECS[tool_name].get("required", [])


def get_tool_param_spec(tool_name: str) -> Optional[Dict[str, Any]]:
    """获取工具的参数规范"""
    return TOOL_PARAM_SPECS.get(tool_name)


__all__ = [
    "validate_tool_params",
    "get_tool_required_params",
    "get_tool_param_spec",
    "TOOL_PARAM_SPECS",
    "ValidationResult"
]
