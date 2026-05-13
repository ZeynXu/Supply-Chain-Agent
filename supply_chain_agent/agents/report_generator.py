"""
Report Generator (报告生成器)

Responsible for generating reports and response cards.
"""

from typing import Dict, Any, List
from datetime import datetime


class ReportGenerator:
    """Generator for reports and response cards."""

    def __init__(self):
        """Initialize report generator."""
        pass

    async def generate_report(self, intent: Dict[str, Any],
                             tool_results: Dict[str, Any],
                             audit_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comprehensive report from results.

        Args:
            intent: User intent
            tool_results: Tool execution results
            audit_results: Audit results

        Returns:
            Structured report
        """
        intent_type = intent.get("intent_level_1", "unknown")
        intent_subtype = intent.get("intent_level_2", "unknown")

        report = {
            "intent": {
                "type": intent_type,
                "subtype": intent_subtype,
                "confidence": intent.get("confidence", 0.0)
            },
            "execution": {
                "tools_executed": list(tool_results.keys()),
                "success_count": sum(1 for r in tool_results.values() if "error" not in r),
                "total_count": len(tool_results)
            },
            "audit": audit_results,
            "timestamp": self._get_timestamp(),
            "summary": self._generate_summary(intent, tool_results, audit_results)
        }

        # Add detailed results
        if intent_subtype == "物流查询":
            report["details"] = self._extract_logistics_details(tool_results)
        elif intent_subtype == "订单状态查询":
            report["details"] = self._extract_order_details(tool_results)

        return report

    async def generate_response_card(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate multi-modal response card.

        Args:
            report: Generated report

        Returns:
            Response card structure
        """
        intent_type = report["intent"]["type"]
        summary = report.get("summary", "")

        card = {
            "summary": summary,
            "intent": intent_type,
            "timestamp": report["timestamp"],
            "confidence": report["intent"]["confidence"],
            "audit_passed": report["audit"].get("passed", False),
            "sections": []
        }

        # Add sections based on intent
        if intent_type == "状态查询":
            card["sections"].extend(self._create_query_sections(report))
        elif intent_type == "审批流转":
            card["sections"].extend(self._create_approval_sections(report))

        # Add actions if applicable
        if report["audit"].get("passed", False):
            card["actions"] = self._create_actions(report)

        return card

    async def generate_error_response(self, state: Dict[str, Any]) -> str:
        """
        Generate helpful error response.

        Args:
            state: Current agent state

        Returns:
            Error response
        """
        error_count = state.get("error_count", 0)
        last_error = state.get("last_error", "未知错误")

        if error_count >= 3:
            return (
                "⚠️ **系统遇到多次错误**\n\n"
                "我们已尝试处理您的请求3次，但均未成功。\n"
                "建议您：\n"
                "1. 检查输入信息是否正确\n"
                "2. 稍后重试\n"
                "3. 联系客服人员\n\n"
                f"最后错误: {last_error}"
            )
        else:
            return (
                "🔄 **系统暂时遇到问题**\n\n"
                "正在尝试重新处理您的请求...\n"
                "如果问题持续，请稍后重试或联系技术支持。\n\n"
                f"错误详情: {last_error}"
            )

    # ==================== Helper methods ====================

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        return datetime.now().isoformat()

    def _format_response_card(self, card: Dict[str, Any]) -> str:
        """Format response card as text."""
        summary = card.get("summary", "")
        sections = card.get("sections", [])

        response = f"## {summary}\n\n"

        for section in sections:
            title = section.get("title", "")
            content = section.get("content", "")
            response += f"### {title}\n{content}\n\n"

        actions = card.get("actions", [])
        if actions:
            response += "### 可选操作\n"
            for action in actions:
                response += f"- **{action.get('label', '')}**: {action.get('description', '')}\n"

        return response

    def _generate_summary(self, intent: Dict[str, Any],
                         tool_results: Dict[str, Any],
                         audit_results: Dict[str, Any]) -> str:
        """Generate summary from results."""
        intent_type = intent.get("intent_level_1", "查询")
        intent_subtype = intent.get("intent_level_2", "")

        if intent_subtype == "物流查询":
            if "get_logistics_trace" in tool_results:
                logistics_data = tool_results["get_logistics_trace"]
                tracking_no = logistics_data.get("tracking_no", "")
                status = logistics_data.get("status", "")
                current_location = logistics_data.get("current_location", "")
                eta = logistics_data.get("eta", "")
                return f"运单 {tracking_no} 状态: {status}，当前位置: {current_location}，预计到达: {eta}"
            elif "query_order_status" in tool_results:
                order_data = tool_results["query_order_status"]
                order_id = order_data.get("order_id", "")
                status = order_data.get("status", "")
                tracking_no = order_data.get("tracking_no", "")
                return f"订单 {order_id} 状态: {status}，运单号: {tracking_no}"

        elif intent_subtype == "订单状态查询":
            if "query_order_status" in tool_results:
                order_data = tool_results["query_order_status"]
                order_id = order_data.get("order_id", "")
                status = order_data.get("status", "")
                return f"订单 {order_id} 当前状态: {status}"

        return f"{intent_type}处理完成"

    def _extract_logistics_details(self, tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """Extract logistics details from tool results."""
        details = {}

        if "query_order_status" in tool_results:
            order_data = tool_results["query_order_status"]
            details["order"] = {
                "id": order_data.get("order_id"),
                "status": order_data.get("status"),
                "amount": order_data.get("amount"),
                "supplier": order_data.get("supplier"),
                "tracking_no": order_data.get("tracking_no")
            }

        if "get_logistics_trace" in tool_results:
            logistics_data = tool_results["get_logistics_trace"]
            details["logistics"] = {
                "tracking_no": logistics_data.get("tracking_no"),
                "status": logistics_data.get("status"),
                "current_location": logistics_data.get("current_location"),
                "eta": logistics_data.get("eta"),
                "carrier": logistics_data.get("carrier", "")
            }

        return details

    def _extract_order_details(self, tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """Extract order details from tool results."""
        if "query_order_status" in tool_results:
            order_data = tool_results["query_order_status"]
            return {
                "order": {
                    "id": order_data.get("order_id"),
                    "customer": order_data.get("customer"),
                    "supplier": order_data.get("supplier"),
                    "status": order_data.get("status"),
                    "amount": order_data.get("amount"),
                    "order_date": order_data.get("order_date"),
                    "expected_delivery": order_data.get("expected_delivery")
                }
            }
        return {}

    def _create_query_sections(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create sections for query response card."""
        sections = []

        details = report.get("details", {})
        if "order" in details:
            order = details["order"]
            sections.append({
                "title": "订单信息",
                "content": f"""
                    - **订单号**: {order.get('id', 'N/A')}
                    - **状态**: {order.get('status', 'N/A')}
                    - **供应商**: {order.get('supplier', 'N/A')}
                    - **金额**: ¥{order.get('amount', 0):,.2f}
                """
            })

        if "logistics" in details:
            logistics = details["logistics"]
            sections.append({
                "title": "物流信息",
                "content": f"""
                    - **运单号**: {logistics.get('tracking_no', 'N/A')}
                    - **状态**: {logistics.get('status', 'N/A')}
                    - **当前位置**: {logistics.get('current_location', 'N/A')}
                    - **预计到达**: {logistics.get('eta', 'N/A')}
                """
            })

        return sections

    def _create_approval_sections(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create sections for approval response card."""
        sections = [{
            "title": "审批准备完成",
            "content": "已为您准备好审批表单，请确认信息后提交。"
        }]
        return sections

    def _create_actions(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create action buttons for response card."""
        intent_type = report["intent"]["type"]

        if intent_type == "审批流转":
            return [{
                "label": "确认提交审批",
                "description": "提交工单审批申请",
                "action": "confirm_approval"
            }, {
                "label": "修改审批意见",
                "description": "修改审批意见后重新提交",
                "action": "edit_comment"
            }]

        elif intent_type == "状态查询":
            return [{
                "label": "刷新状态",
                "description": "重新查询最新状态",
                "action": "refresh_status"
            }]

        return []
