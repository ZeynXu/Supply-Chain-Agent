"""
Report Generator (报告生成器)

Responsible for generating reports and response cards.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re

from supply_chain_agent.utils.field_mapping import format_tool_results_as_markdown, format_result_as_markdown
from supply_chain_agent.prompts.fallback_templates import (
    get_fallback_response,
    ErrorCodes
)


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

        # Add detailed results - use raw tool_results directly
        report["details"] = tool_results

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
        if intent_type == "信息查询":
            card["sections"].extend(self._create_query_sections(report))
        elif intent_type == "工单管理":
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

    async def generate_fallback_response(
        self,
        error_code: str,
        tool_results: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate fallback response using fallback templates.

        根据错误编码调用 fallback_templates.py 中的降级响应方法。

        Args:
            error_code: 错误编码（来自 FallbackResponseTemplate.csv）
            tool_results: 工具执行结果（用于提取额外信息）
            **kwargs: 模板变量替换参数

        Returns:
            Dict 包含:
                - error_code: 错误编码
                - message: 响应消息
                - severity: 严重等级
                - scenario: 场景描述
        """
        # 调用 fallback_templates 中的方法获取响应
        result = get_fallback_response(error_code, **kwargs)

        return result

    def determine_error_code_from_result(
        self,
        tool_name: str,
        error_detail: str
    ) -> str:
        """
        根据工具名称和错误详情确定错误编码。

        重构（M19）：使用统一的 determine_error_code 函数。

        Args:
            tool_name: 工具名称
            error_detail: 错误详情

        Returns:
            错误编码
        """
        from supply_chain_agent.prompts.fallback_templates import determine_error_code
        return determine_error_code(error_detail, tool_name=tool_name)

    def extract_template_params(
        self,
        tool_name: str,
        error_detail: str,
        extracted_slots: Optional[Dict[str, Any]] = None,
        tool_results: Optional[Dict[str, Any]] = None,
        missing_slots: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        从 extracted_slots、tool_results 和错误详情中提取模板参数。

        Args:
            tool_name: 工具名称
            error_detail: 错误详情
            extracted_slots: 从用户输入中提取的实体（如 order_id、customer_id）
            tool_results: 工具执行结果（可能包含部分成功查询的数据）
            missing_slots: 缺失的槽位列表

        Returns:
            模板参数字典
        """
        params = {}
        extracted_slots = extracted_slots or {}
        tool_results = tool_results or {}
        missing_slots = missing_slots or []

        # 1. 从 extracted_slots 获取用户输入的实体
        # 订单号 - 可能有多种命名方式
        if "order_id" in extracted_slots:
            params["order_id"] = extracted_slots["order_id"]
        elif "orderId" in extracted_slots:
            params["order_id"] = extracted_slots["orderId"]
        elif "订单号" in extracted_slots:
            params["order_id"] = extracted_slots["订单号"]

        # 客户ID
        if "customer_id" in extracted_slots:
            params["customer_id"] = extracted_slots["customer_id"]
        elif "customerId" in extracted_slots:
            params["customer_id"] = extracted_slots["customerId"]
        elif "客户编号" in extracted_slots:
            params["customer_id"] = extracted_slots["客户编号"]

        # 产品ID
        if "product_card_id" in extracted_slots:
            params["product_card_id"] = extracted_slots["product_card_id"]
        elif "productId" in extracted_slots:
            params["product_card_id"] = extracted_slots["productId"]
        elif "产品编号" in extracted_slots:
            params["product_card_id"] = extracted_slots["产品编号"]

        # 运单号/追踪号
        if "tracking_no" in extracted_slots:
            params["tracking_no"] = extracted_slots["tracking_no"]
        elif "tracking_number" in extracted_slots:
            params["tracking_no"] = extracted_slots["tracking_number"]
        elif "运单号" in extracted_slots:
            params["tracking_no"] = extracted_slots["运单号"]

        # 客户名称
        if "customer_name" in extracted_slots:
            params["customer_name"] = extracted_slots["customer_name"]
        elif "客户名称" in extracted_slots:
            params["customer_name"] = extracted_slots["客户名称"]

        # 2. 从错误消息中提取信息（作为备用）
        # 提取订单号
        if "order_id" not in params:
            match = re.search(r'[Oo]rder[:\s]*(\S+)', error_detail)
            if match:
                params["order_id"] = match.group(1)
            match = re.search(r'订单[号:：]?\s*(\S+)', error_detail)
            if match:
                params["order_id"] = match.group(1)

        # 提取客户ID
        if "customer_id" not in params:
            match = re.search(r'[Cc]ustomer[:\s]*(\S+)', error_detail)
            if match:
                params["customer_id"] = match.group(1)

        # 提取产品ID
        if "product_card_id" not in params:
            match = re.search(r'[Pp]roduct[:\s]*(\S+)', error_detail)
            if match:
                params["product_card_id"] = match.group(1)

        # 3. 从 tool_results 获取部分成功查询的数据
        # 订单状态、发货状态等（用于 QUERY_ORDER_ITEMS_TIMEOUT、QUERY_SHIPMENT_TIMEOUT 等）
        for t_name, t_result in tool_results.items():
            if isinstance(t_result, dict) and not t_result.get("error"):
                # 从成功的订单查询中获取状态信息
                if "order" in t_name.lower() and "order_status" not in params:
                    if "order_status" in t_result:
                        params["order_status"] = t_result["order_status"]
                    if "delivery_status" in t_result:
                        params["delivery_status"] = t_result["delivery_status"]

                # 从成功的运输查询中获取物流信息
                if "shipment" in t_name.lower() or "shipping" in t_name.lower():
                    if "shipping_mode" not in params and "shipping_mode" in t_result:
                        params["shipping_mode"] = t_result["shipping_mode"]
                    if "days_for_shipment_scheduled" not in params and "days_for_shipment_scheduled" in t_result:
                        params["days_for_shipment_scheduled"] = t_result["days_for_shipment_scheduled"]

        # 4. 缺失槽位（用于 SLOT_FILLING_FAILED）
        if missing_slots:
            # 将 missing_slots 列表转换为中文描述
            slot_name_map = {
                "order_id": "订单编号",
                "customer_id": "客户编号",
                "product_card_id": "产品编号",
                "tracking_no": "运单号",
                "customer_name": "客户名称",
                "start_date": "开始日期",
                "end_date": "结束日期"
            }
            missing_slots_cn = [slot_name_map.get(s, s) for s in missing_slots]
            params["missing_slots"] = "、".join(missing_slots_cn)

        return params

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
        """Generate summary from results using field mapping."""
        intent_type = intent.get("intent_level_1", "查询")
        intent_subtype = intent.get("intent_level_2", "")

        # Title mapping based on intent subtype
        title_map = {
            "客户查询": "客户信息查询结果",
            "订单查询": "订单信息查询结果",
            "物流查询": "物流信息查询结果",
            "产品查询": "产品信息查询结果",
            "客户订单查询": "客户订单查询结果",
            "订单明细查询": "订单明细查询结果",
            "客户统计查询": "客户统计查询结果"
        }

        # Filter out error results
        valid_results = {}
        for tool_name, result in tool_results.items():
            if isinstance(result, dict):
                # Skip results with errors
                if result.get('error') or result.get('success') == False:
                    continue
                valid_results[tool_name] = result

        if not valid_results:
            return f"{intent_type}处理完成，但未获取到有效数据"

        # Use field mapping to format results as Markdown
        title = title_map.get(intent_subtype, f"{intent_type}查询结果")
        return format_tool_results_as_markdown(valid_results, intent_type)

    def _create_query_sections(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create sections for query response card using field mapping."""
        from supply_chain_agent.utils.field_mapping import get_chinese_name, format_field_value

        sections = []

        details = report.get("details", {})

        for tool_name, data in details.items():
            if not isinstance(data, dict):
                continue

            # Skip error results
            if data.get('error') or data.get('success') == False:
                continue

            # Determine section title
            title_map = {
                'query_customer': '客户信息',
                'query_order': '订单信息',
                'query_shipment': '物流信息',
                'query_product': '产品信息',
                'query_customer_orders': '客户订单',
                'query_order_items': '订单明细'
            }
            title = title_map.get(tool_name, '查询结果')

            # Build content using field mapping
            content_lines = []
            for field_name, value in data.items():
                if field_name in ['error', 'success', 'error_type']:
                    continue
                chinese_name = get_chinese_name(field_name)
                formatted_value = format_field_value(field_name, value)
                content_lines.append(f"- **{chinese_name}**: {formatted_value}")

            if content_lines:
                sections.append({
                    "title": title,
                    "content": "\n".join(content_lines)
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

        if intent_type == "工单管理":
            return [{
                "label": "确认提交审批",
                "description": "提交工单审批申请",
                "action": "confirm_approval"
            }, {
                "label": "修改审批意见",
                "description": "修改审批意见后重新提交",
                "action": "edit_comment"
            }]

        elif intent_type == "信息查询":
            return [{
                "label": "刷新状态",
                "description": "重新查询最新状态",
                "action": "refresh_status"
            }]

        return []
