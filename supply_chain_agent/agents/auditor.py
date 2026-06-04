"""
Auditor Agent (审计员)

Responsible for result validation and risk control.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from supply_chain_agent.config import settings


@dataclass
class AuditRule:
    """Audit rule definition."""
    name: str
    condition: str
    severity: str  # high, medium, low
    action: str  # reject, warn, notify


class AuditorAgent:
    """Auditor agent for result validation and risk control."""

    # Audit rules
    AUDIT_RULES = [
        AuditRule(
            name="missing_tracking_number",
            condition="物流查询结果缺少运单号",
            severity="high",
            action="reject"
        ),
        AuditRule(
            name="unusual_delivery_time",
            condition="预计送达时间异常（超过30天）",
            severity="medium",
            action="warn"
        ),
        AuditRule(
            name="order_cancelled",
            condition="订单状态为已取消",
            severity="medium",
            action="warn"
        ),
        AuditRule(
            name="high_value_order",
            condition="订单金额超过100,000",
            severity="low",
            action="notify"
        ),
        AuditRule(
            name="approval_without_comment",
            condition="审批操作缺少审批意见",
            severity="medium",
            action="reject"
        )
    ]

    def __init__(self):
        self.audit_history: List[Dict[str, Any]] = []

    async def audit_results(self, tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Audit tool execution results.

        Args:
            tool_results: Results from tool execution

        Returns:
            Audit results including pass/fail status and issues
        """
        issues = []
        warnings = []
        notifications = []

        # M9修复：应用审计规则
        rule_results = self._apply_audit_rules(tool_results)
        issues.extend(rule_results.get("issues", []))
        warnings.extend(rule_results.get("warnings", []))
        notifications.extend(rule_results.get("notifications", []))

        # Check each tool result
        for tool_name, result in tool_results.items():
            tool_audit = await self._audit_tool_result(tool_name, result)
            issues.extend(tool_audit.get("issues", []))
            warnings.extend(tool_audit.get("warnings", []))
            notifications.extend(tool_audit.get("notifications", []))

        # Cross-result validation
        cross_issues = await self._cross_result_validation(tool_results)
        issues.extend(cross_issues)

        # Data consistency check
        consistency_issues = await self._check_data_consistency(tool_results)
        issues.extend(consistency_issues)

        # Business logic validation
        business_issues = await self._validate_business_logic(tool_results)
        issues.extend(business_issues)

        # Determine overall result
        has_critical_issues = any("严重" in issue or "CRITICAL" in issue for issue in issues)
        passed = not has_critical_issues

        # Create audit record
        audit_record = {
            "timestamp": self._get_timestamp(),
            "tool_results": list(tool_results.keys()),
            "issues": issues,
            "warnings": warnings,
            "notifications": notifications,
            "passed": passed,
            "has_warnings": len(warnings) > 0,
            "issue_count": len(issues),
            "warning_count": len(warnings)
        }

        self.audit_history.append(audit_record)

        return audit_record

    def _apply_audit_rules(self, tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        M9修复：应用AUDIT_RULES进行审计

        Args:
            tool_results: 工具执行结果

        Returns:
            按严重程度分类的问题列表
        """
        issues = []
        warnings = []
        notifications = []

        for rule in self.AUDIT_RULES:
            triggered = False
            message = ""

            # 检查规则触发条件
            if rule.name == "missing_tracking_number":
                # 物流查询结果缺少运单号
                shipment = tool_results.get("query_shipment", {})
                if shipment and "tracking_number" not in shipment:
                    triggered = True
                    message = "物流查询结果缺少运单号"

            elif rule.name == "unusual_delivery_time":
                # 预计送达时间异常（超过30天）
                shipment = tool_results.get("query_shipment", {})
                if shipment:
                    from datetime import datetime
                    try:
                        eta = shipment.get("estimated_delivery_date")
                        if eta:
                            eta_date = datetime.strptime(eta, "%Y-%m-%d")
                            if (eta_date - datetime.now()).days > 30:
                                triggered = True
                                message = f"预计送达时间异常：{eta}（超过30天）"
                    except (ValueError, TypeError):
                        pass

            elif rule.name == "order_cancelled":
                # 订单状态为已取消
                order = tool_results.get("query_order", {})
                if order and order.get("order_status") == "CANCELED":
                    triggered = True
                    message = "订单状态为已取消"

            elif rule.name == "high_value_order":
                # 订单金额超过100,000
                order = tool_results.get("query_order", {})
                if order:
                    benefit = order.get("benefit_per_order", 0)
                    if benefit and benefit > 100000:
                        triggered = True
                        message = f"高价值订单：¥{benefit:,.2f}"

            elif rule.name == "approval_without_comment":
                # 审批操作缺少审批意见
                approval = tool_results.get("approve_work_order", {})
                if approval:
                    comment = approval.get("comment", "")
                    action = approval.get("action", "")
                    if action in ["approve", "reject"] and not comment:
                        triggered = True
                        message = f"审批操作({action})缺少审批意见"

            # 根据规则严重程度和动作分类
            if triggered:
                if rule.action == "reject":
                    issues.append(f"[{rule.severity.upper()}] {message}")
                elif rule.action == "warn":
                    warnings.append(message)
                elif rule.action == "notify":
                    notifications.append(message)

        return {"issues": issues, "warnings": warnings, "notifications": notifications}

    async def _audit_tool_result(self, tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Audit a single tool result."""
        issues = []
        warnings = []
        notifications = []

        # Check for errors
        if "error" in result:
            issues.append(f"工具 {tool_name} 执行错误: {result['error']}")
            return {"issues": issues, "warnings": warnings, "notifications": notifications}

        # Tool-specific audits
        if tool_name == "query_order":
            audit_result = await self._audit_order_status(result)
            issues.extend(audit_result.get("issues", []))
            warnings.extend(audit_result.get("warnings", []))
            notifications.extend(audit_result.get("notifications", []))

        elif tool_name == "query_shipment":
            audit_result = await self._audit_shipment(result)
            issues.extend(audit_result.get("issues", []))
            warnings.extend(audit_result.get("warnings", []))
            notifications.extend(audit_result.get("notifications", []))

        elif tool_name == "approve_work_order":
            audit_result = await self._audit_work_order_approval(result)
            issues.extend(audit_result.get("issues", []))
            warnings.extend(audit_result.get("warnings", []))
            notifications.extend(audit_result.get("notifications", []))

        return {"issues": issues, "warnings": warnings, "notifications": notifications}

    async def _audit_order_status(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Audit order status query result."""
        issues = []
        warnings = []
        notifications = []

        # Check required fields based on MCP query_order output
        required_fields = ["order_id", "order_status"]
        for field in required_fields:
            if field not in result:
                issues.append(f"订单查询结果缺少必要字段: {field}")

        # Check status validity
        valid_statuses = ["CANCELED", "CLOSED", "COMPLETE", "PROCESSING", "PENDING"]
        status = result.get("order_status", "")
        if status and status not in valid_statuses:
            warnings.append(f"订单状态异常: {status}")

        # Check benefit
        benefit = result.get("benefit_per_order", 0)
        if benefit and benefit > 100000:
            notifications.append(f"高价值订单: ¥{benefit:,.2f}")

        # Check cancellation
        if status == "CANCELED":
            warnings.append("订单已取消")

        return {"issues": issues, "warnings": warnings, "notifications": notifications}

    async def _audit_shipment(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Audit shipment query result based on MCP query_shipment output."""
        issues = []
        warnings = []
        notifications = []

        # Check required fields
        required_fields = ["order_id", "status_description"]
        for field in required_fields:
            if field not in result:
                issues.append(f"物流查询结果缺少必要字段: {field}")

        # Check delivery risk
        late_delivery_risk = result.get("late_delivery_risk")
        if late_delivery_risk == 1:
            warnings.append("存在延迟交付风险")

        # Check shipping date
        shipping_date = result.get("shipping_date")
        if not shipping_date:
            notifications.append("订单尚未发货")

        return {"issues": issues, "warnings": warnings, "notifications": notifications}

    async def _audit_work_order_approval(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Audit work order approval result."""
        issues = []
        warnings = []
        notifications = []

        # Check for confirmation requirement
        if result.get("requires_confirmation", False):
            if not result.get("confirmation_message"):
                issues.append("审批操作缺少确认信息")

        # Check work order status
        work_order = result.get("work_order", {})
        status = work_order.get("status", "")
        if status == "已完成":
            warnings.append("工单已完成，无需审批")
        elif status == "已取消":
            warnings.append("工单已取消，无需审批")

        # Check approver
        approver = result.get("approver", "")
        if not approver or approver == "系统":
            notifications.append("审批人为系统自动审批")

        return {"issues": issues, "warnings": warnings, "notifications": notifications}

    async def _cross_result_validation(self, tool_results: Dict[str, Any]) -> List[str]:
        """Validate consistency across multiple tool results."""
        issues = []

        # Check if order and shipment results match
        if "query_order" in tool_results and "query_shipment" in tool_results:
            order_result = tool_results["query_order"]
            shipment_result = tool_results["query_shipment"]

            order_id = order_result.get("order_id")
            shipment_order_id = shipment_result.get("order_id")

            if order_id and shipment_order_id and order_id != shipment_order_id:
                issues.append("订单ID与物流查询订单ID不匹配")

        return issues

    async def _check_data_consistency(self, tool_results: Dict[str, Any]) -> List[str]:
        """Check data consistency within results."""
        issues = []
        warnings = []

        for tool_name, result in tool_results.items():
            # Check for contradictory information
            if tool_name == "query_order":
                order_status = result.get("order_status", "")
                delivery_status = result.get("delivery_status", "")

                if order_status == "CANCELED" and delivery_status == "Shipping":
                    issues.append("订单已取消但配送状态为运输中，可能数据不一致")

                elif order_status == "PROCESSING" and delivery_status == "Late delivery":
                    warnings.append("订单处理中但配送已延迟")

        # 返回issues和warnings（warnings标记为警告级别）
        return issues + [f"[警告] {w}" for w in warnings]

    async def _validate_business_logic(self, tool_results: Dict[str, Any]) -> List[str]:
        """Validate business logic rules."""
        issues = []

        # Check if we're approving a cancelled order
        if "approve_work_order" in tool_results:
            approval_result = tool_results["approve_work_order"]
            work_order = approval_result.get("work_order", {})

            if work_order.get("status") == "已取消":
                issues.append("无法审批已取消的工单")

            # Check if work order has required approvals
            required_approvals = work_order.get("required_approvals", [])
            if required_approvals and len(required_approvals) > 2:
                warnings.append("工单需要多层审批，当前仅完成第一层")

        return issues

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        return datetime.now().isoformat()

    async def get_risk_score(self, tool_results: Dict[str, Any]) -> float:
        """
        Calculate risk score for tool results.

        改进后的风险评分计算：
        - 根据问题严重程度分级加权
        - 严重问题(CRITICAL): 权重 1.0
        - 中等问题(MEDIUM): 权重 0.5
        - 轻微问题(MINOR): 权重 0.2
        - 警告(WARNING): 权重 0.1

        Args:
            tool_results: Results from tool execution

        Returns:
            Risk score from 0.0 (low risk) to 1.0 (high risk)
        """
        audit_result = await self.audit_results(tool_results)

        issues = audit_result.get("issues", [])
        warnings = audit_result.get("warnings", [])

        # 按严重程度分类问题
        critical_count = 0
        medium_count = 0
        minor_count = 0

        for issue in issues:
            issue_upper = issue.upper()
            # 严重问题：包含严重、CRITICAL、错误、ERROR等关键词
            if "严重" in issue or "CRITICAL" in issue_upper or "错误" in issue or "ERROR" in issue_upper:
                critical_count += 1
            # 中等问题：包含中等、MEDIUM、异常、WARNING等关键词
            elif "中等" in issue or "MEDIUM" in issue_upper or "异常" in issue or "失败" in issue:
                medium_count += 1
            # 轻微问题：其他问题
            else:
                minor_count += 1

        # 按严重程度加权计算风险分数
        # 严重问题权重最高，每个贡献0.25（4个即达到满分）
        # 中等问题每个贡献0.1
        # 轻微问题每个贡献0.05
        # 警告每个贡献0.02
        weighted_score = (
            critical_count * 0.25 +
            medium_count * 0.1 +
            minor_count * 0.05 +
            len(warnings) * 0.02
        )

        # Cap at 1.0
        return min(1.0, max(0.0, weighted_score))

    def get_audit_summary(self) -> Dict[str, Any]:
        """Get summary of audit history."""
        total_audits = len(self.audit_history)
        passed_audits = sum(1 for audit in self.audit_history if audit.get("passed", False))
        failed_audits = total_audits - passed_audits

        # Count issues by severity
        critical_issues = 0
        warning_issues = 0

        for audit in self.audit_history:
            for issue in audit.get("issues", []):
                if "严重" in issue or "CRITICAL" in issue:
                    critical_issues += 1
                else:
                    warning_issues += 1

        return {
            "total_audits": total_audits,
            "passed_audits": passed_audits,
            "failed_audits": failed_audits,
            "pass_rate": passed_audits / total_audits if total_audits > 0 else 0,
            "critical_issues": critical_issues,
            "warning_issues": warning_issues,
            "recent_audits": self.audit_history[-5:] if self.audit_history else []
        }