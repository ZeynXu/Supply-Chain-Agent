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
        if tool_name == "query_order_status":
            audit_result = await self._audit_order_status(result)
            issues.extend(audit_result.get("issues", []))
            warnings.extend(audit_result.get("warnings", []))
            notifications.extend(audit_result.get("notifications", []))

        elif tool_name == "get_logistics_trace":
            audit_result = await self._audit_logistics_trace(result)
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

        # Check required fields
        required_fields = ["order_id", "status", "amount"]
        for field in required_fields:
            if field not in result:
                issues.append(f"订单查询结果缺少必要字段: {field}")

        # Check status validity
        valid_statuses = ["待付款", "待发货", "已发货", "运输中", "已收货", "已完成", "已取消"]
        status = result.get("status", "")
        if status and status not in valid_statuses:
            warnings.append(f"订单状态异常: {status}")

        # Check amount
        amount = result.get("amount", 0)
        if amount > 100000:
            notifications.append(f"高价值订单: ¥{amount:,.2f}")

        # Check cancellation
        if status == "已取消":
            warnings.append("订单已取消")

        return {"issues": issues, "warnings": warnings, "notifications": notifications}

    async def _audit_logistics_trace(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Audit logistics trace query result."""
        issues = []
        warnings = []
        notifications = []

        # Check required fields
        required_fields = ["tracking_no", "status", "current_location"]
        for field in required_fields:
            if field not in result:
                issues.append(f"物流查询结果缺少必要字段: {field}")

        # Check tracking number
        tracking_no = result.get("tracking_no", "")
        if not tracking_no or len(tracking_no) < 8:
            issues.append("运单号无效或过短")

        # Check delivery time
        eta = result.get("eta")
        if eta:
            try:
                eta_date = datetime.fromisoformat(eta.replace('Z', '+00:00'))
                today = datetime.now()
                if eta_date - today > timedelta(days=30):
                    warnings.append(f"预计送达时间异常延迟: {eta}")
            except (ValueError, TypeError):
                warnings.append("预计送达时间格式无效")

        # Check status
        status = result.get("status", "")
        valid_statuses = ["已揽收", "运输中", "到达中转场", "派送中", "已签收", "已退回"]
        if status and status not in valid_statuses:
            warnings.append(f"物流状态异常: {status}")

        # Check for long delay
        events = result.get("events", [])
        if events:
            last_event = events[-1]
            event_time = last_event.get("timestamp")
            if event_time:
                try:
                    event_date = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                    today = datetime.now()
                    if today - event_date > timedelta(days=7):
                        warnings.append("物流信息超过7天未更新")
                except (ValueError, TypeError):
                    pass

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

        # Check if order and logistics results match
        if "query_order_status" in tool_results and "get_logistics_trace" in tool_results:
            order_result = tool_results["query_order_status"]
            logistics_result = tool_results["get_logistics_trace"]

            order_tracking = order_result.get("tracking_no")
            logistics_tracking = logistics_result.get("tracking_no")

            if order_tracking and logistics_tracking and order_tracking != logistics_tracking:
                issues.append("订单运单号与物流查询运单号不匹配")

        return issues

    async def _check_data_consistency(self, tool_results: Dict[str, Any]) -> List[str]:
        """Check data consistency within results."""
        issues = []

        for tool_name, result in tool_results.items():
            # Check for contradictory information
            if tool_name == "query_order_status":
                status = result.get("status", "")
                tracking_no = result.get("tracking_no", "")

                if status == "待发货" and tracking_no:
                    issues.append("订单状态为待发货但已有运单号，可能数据不一致")

                elif status == "已发货" and not tracking_no:
                    issues.append("订单状态为已发货但缺少运单号")

        return issues

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

        Args:
            tool_results: Results from tool execution

        Returns:
            Risk score from 0.0 (low risk) to 1.0 (high risk)
        """
        audit_result = await self.audit_results(tool_results)

        # Calculate risk based on issues
        issue_count = audit_result.get("issue_count", 0)
        warning_count = audit_result.get("warning_count", 0)

        # Weight issues more heavily than warnings
        risk_score = (issue_count * 0.7 + warning_count * 0.3) / 10.0

        # Cap at 1.0
        return min(1.0, max(0.0, risk_score))

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