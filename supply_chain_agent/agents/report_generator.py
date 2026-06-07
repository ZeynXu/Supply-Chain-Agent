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
                             audit_results: Dict[str, Any],
                             approval_analysis: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate comprehensive report from results.

        Args:
            intent: User intent
            tool_results: Tool execution results
            audit_results: Audit results
            approval_analysis: 审批分析结果（审批工单专用）

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
            "summary": self._generate_summary(intent, tool_results, audit_results, approval_analysis)
        }

        # 审批工单：不添加查询工具结果，只使用分析结果
        intent_subtype = intent.get("intent_level_2", "")
        if intent_subtype != "审批工单":
            # 非审批工单，添加查询工具结果
            report["details"] = tool_results

        # 添加审批分析结果（如果有）
        if approval_analysis:
            report["approval_analysis"] = approval_analysis

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
        intent_subtype = report["intent"].get("subtype", "")
        summary = report.get("summary", "")

        card = {
            "summary": summary,
            "intent": intent_type,
            "intent_subtype": intent_subtype,
            "timestamp": report["timestamp"],
            "confidence": report["intent"]["confidence"],
            "audit_passed": report["audit"].get("passed", False),
            "sections": []
        }

        # Add sections based on intent
        if intent_type == "信息查询":
            card["sections"].extend(self._create_query_sections(report))
        elif intent_type == "工单管理":
            # 审批工单：只显示分析结果，不显示查询工具结果
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
                         audit_results: Dict[str, Any],
                         approval_analysis: Dict[str, Any] = None) -> str:
        """Generate summary from results using field mapping."""
        intent_type = intent.get("intent_level_1", "查询")
        intent_subtype = intent.get("intent_level_2", "")

        # 审批工单：使用分析结果的摘要
        if intent_subtype == "审批工单" and approval_analysis:
            analysis = approval_analysis.get("analysis", {})
            summary = analysis.get("summary", "审批分析完成")

            # 添加建议信息
            recommendation = analysis.get("recommendation", {})
            action = recommendation.get("action", "unknown")
            action_map = {
                "approve": "建议通过",
                "reject": "建议拒绝",
                "escalate": "建议上报"
            }
            action_text = action_map.get(action, "待定")

            return f"📋 {summary}\n\n💡 **审批建议**: {action_text}"

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
        sections = []

        # 检查是否有审批分析结果
        approval_analysis = report.get("approval_analysis")
        if approval_analysis:
            analysis = approval_analysis.get("analysis", {})

            # 1. 工单概况
            # 兼容两种格式：简化格式和详细格式
            work_order_analysis = analysis.get("work_order_analysis", {})
            if work_order_analysis:
                # 详细格式
                content_lines = []
                content_lines.append(f"- **工单类型**: {work_order_analysis.get('work_type', '未知')}")
                content_lines.append(f"- **当前状态**: {work_order_analysis.get('status', '未知')}")
                content_lines.append(f"- **优先级**: {work_order_analysis.get('priority', '未知')}")
                content_lines.append(f"- **订单金额**: {work_order_analysis.get('order_amount', '未知')}")
                content_lines.append(f"- **订单利润**: {work_order_analysis.get('order_profit', '未知')}")
                content_lines.append(f"- **客户ID**: {work_order_analysis.get('customer_id', '未知')}")
                content_lines.append(f"- **客户类型**: {work_order_analysis.get('customer_type', '未知')}")

                sections.append({
                    "title": "📋 工单概况",
                    "content": "\n".join(content_lines)
                })

            # 2. 风险评估
            risk_level = analysis.get("risk_level")
            risk_assessment = analysis.get("risk_assessment", {})
            if risk_level or risk_assessment:
                content_lines = []

                # 风险等级（支持两种格式）
                if risk_level:
                    risk_emoji = {"A级": "🟢", "B级": "🔵", "C级": "🟡", "D级": "🟠", "E级": "🔴"}.get(risk_level, "⚪")
                    content_lines.append(f"- **风险等级**: {risk_emoji} {risk_level}")
                elif risk_assessment.get("risk_level"):
                    rl = risk_assessment.get("risk_level")
                    risk_emoji = {"A级": "🟢", "B级": "🔵", "C级": "🟡", "D级": "🟠", "E级": "🔴"}.get(rl, "⚪")
                    content_lines.append(f"- **风险等级**: {risk_emoji} {rl}")

                # 其他风险评估字段（详细格式）
                if risk_assessment.get("delivery_status"):
                    content_lines.append(f"- **发货状态**: {risk_assessment.get('delivery_status')}")
                if risk_assessment.get("quota_usage"):
                    content_lines.append(f"- **履约额度**: {risk_assessment.get('quota_usage')}")

                # 风险因素
                risk_factors = analysis.get("risk_factors") or risk_assessment.get("risk_factors", [])
                if risk_factors:
                    content_lines.append("- **风险因素**:")
                    for factor in risk_factors:
                        content_lines.append(f"  - {factor}")

                if content_lines:
                    sections.append({
                        "title": "⚠️ 风险评估",
                        "content": "\n".join(content_lines)
                    })

            # 3. 审批层级（简化格式）或合规检查（详细格式）
            approval_level = analysis.get("approval_level")
            compliance_check = analysis.get("compliance_check", {})
            if approval_level or compliance_check:
                content_lines = []

                if approval_level:
                    # 简化格式
                    content_lines.append(f"- **审批层级**: {approval_level}")
                elif compliance_check.get("approval_level"):
                    content_lines.append(f"- **审批层级**: {compliance_check.get('approval_level')}")

                # 详细格式的其他字段
                if compliance_check:
                    materials_complete = compliance_check.get("materials_complete")
                    if materials_complete is not None:
                        complete_status = "✅ 齐全" if materials_complete else "❌ 不完整"
                        content_lines.append(f"- **材料状态**: {complete_status}")

                    missing_materials = compliance_check.get("missing_materials", [])
                    if missing_materials:
                        content_lines.append("- **缺失材料**:")
                        for m in missing_materials:
                            content_lines.append(f"  - {m}")

                    special_conditions = compliance_check.get("special_conditions", [])
                    if special_conditions:
                        content_lines.append("- **特殊条件**:")
                        for c in special_conditions:
                            content_lines.append(f"  - {c}")

                if content_lines:
                    sections.append({
                        "title": "📑 审批要求",
                        "content": "\n".join(content_lines)
                    })

            # 4. 审批建议
            recommendation = analysis.get("recommendation", {})
            if recommendation:
                action = recommendation.get("action", "unknown")
                action_map = {
                    "approve": ("通过", "✅"),
                    "reject": ("拒绝", "❌"),
                    "escalate": ("上报", "⬆️")
                }
                action_text, action_emoji = action_map.get(action, ("待定", "❓"))

                content_lines = []
                content_lines.append(f"- **建议操作**: {action_emoji} {action_text}")
                content_lines.append(f"- **建议理由**: {recommendation.get('reason', '无')}")

                risk_warnings = recommendation.get("risk_warnings", [])
                if risk_warnings:
                    content_lines.append("- **风险提示**:")
                    for w in risk_warnings:
                        content_lines.append(f"  - ⚠️ {w}")

                additional_actions = recommendation.get("additional_actions", [])
                if additional_actions:
                    content_lines.append("- **建议措施**:")
                    for a in additional_actions:
                        content_lines.append(f"  - {a}")

                sections.append({
                    "title": "💡 审批建议",
                    "content": "\n".join(content_lines)
                })

            # 添加置信度信息
            confidence = analysis.get("confidence", 0)
            if confidence:
                sections.append({
                    "title": "📊 分析置信度",
                    "content": f"本次分析置信度: **{confidence * 100:.1f}%**"
                })

        else:
            # 没有分析结果时的默认展示
            sections.append({
                "title": "审批准备完成",
                "content": "已为您准备好审批表单，请确认信息后提交。"
            })

        return sections

    def _create_actions(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create action buttons for response card."""
        intent_type = report["intent"]["type"]
        intent_subtype = report["intent"].get("subtype", "")

        if intent_type == "工单管理" and intent_subtype == "审批工单":
            # 获取审批建议
            approval_analysis = report.get("approval_analysis", {})
            analysis = approval_analysis.get("analysis", {})
            recommendation = analysis.get("recommendation", {})
            suggested_action = recommendation.get("action", "unknown")

            # 根据建议的action提供对应的确认按钮
            actions = []

            if suggested_action == "approve":
                actions.append({
                    "label": "✅ 确认通过",
                    "description": "按照建议通过审批",
                    "action": "confirm_approve"
                })
            elif suggested_action == "reject":
                actions.append({
                    "label": "❌ 确认拒绝",
                    "description": "按照建议拒绝审批",
                    "action": "confirm_reject"
                })
            elif suggested_action == "escalate":
                actions.append({
                    "label": "⬆️ 上报审批",
                    "description": "上报给上级审批人",
                    "action": "confirm_escalate"
                })

            # 始终提供其他选项
            actions.append({
                "label": "🔄 选择其他操作",
                "description": "选择不同的审批操作",
                "action": "choose_other_action"
            })
            actions.append({
                "label": "📝 修改审批意见",
                "description": "添加或修改审批意见",
                "action": "edit_comment"
            })

            return actions

        elif intent_type == "工单管理":
            return [{
                "label": "确认提交",
                "description": "提交工单申请",
                "action": "confirm_submission"
            }, {
                "label": "修改内容",
                "description": "修改工单内容后重新提交",
                "action": "edit_content"
            }]

        elif intent_type == "信息查询":
            return [{
                "label": "刷新状态",
                "description": "重新查询最新状态",
                "action": "refresh_status"
            }]

        return []
