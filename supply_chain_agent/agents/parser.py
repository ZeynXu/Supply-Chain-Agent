"""
Parser Agent (解析师)

Responsible for understanding user intent and extracting relevant information.
Enhanced with LLM integration for fuzzy input handling.
"""

from typing import Dict, Any, List, Optional
import re
import json
from dataclasses import dataclass

from supply_chain_agent.config import settings

# LLM相关导入
try:
    from supply_chain_agent.agents.llm_client import LLMClient, get_llm_client
    from supply_chain_agent.prompts.intent import INTENT_CLASSIFICATION_PROMPT
    from supply_chain_agent.prompts.entity import ENTITY_EXTRACTION_PROMPT
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("⚠️ LLM integration not available, using rule-based only")


@dataclass
class Intent:
    """Structured intent representation."""
    level_1: str  # 工单创建、状态查询、审批流转、异常上报
    level_2: str  # 订单状态、物流状态等
    entities: List[Dict[str, str]]
    required_slots: List[str]
    confidence: float


class ParserAgent:
    """Parser agent for intent recognition and information extraction."""

    # Intent patterns (simplified for demo)
    INTENT_PATTERNS = {
        "状态查询": {
            "patterns": [
                r"查(一下|询)?.*?(订单|状态|货)",
                r"订单.*?(状态|在哪|到哪)",
                r"物流.*?(查询|跟踪|轨迹)"
            ],
            "entities": ["order_id", "tracking_no", "customer_name"],
            "required_slots": []
        },
        "工单创建": {
            "patterns": [
                r"创建.*?(工单|任务|申请)",
                r"新建.*?(工单|任务|申请|请求)",
                r"提交.*?(工单|任务|申请|处理|审批)",
                r"开.*?(工单|任务)"
            ],
            "entities": ["work_type", "priority", "description"],
            "required_slots": ["work_type", "description"]
        },
        "审批流转": {
            "patterns": [
                r"审批.*?(工单|申请)",
                r"通过.*?(请求|申请)",
                r"拒绝.*?(工单|请求)"
            ],
            "entities": ["work_order_id", "action", "comment"],
            "required_slots": ["work_order_id", "action"]
        },
        "异常上报": {
            "patterns": [
                r"报告.*?(异常|问题|故障|错误)",
                r"上报.*?(异常|问题|故障|错误)",
                r"问题.*?(反馈|报告|上报)",
                r"反馈.*?(问题|异常|故障)"
            ],
            "entities": ["issue_type", "description", "urgency"],
            "required_slots": ["issue_type", "description"]
        }
    }

    # Entity extraction patterns
    ENTITY_PATTERNS = {
        "order_id": r"(PO|订单)[-_]?\d{4}[-_]?\d{3,}",
        "tracking_no": r"[A-Z]{2}\d{9,11}[A-Z]?|\d{12,14}",
        "customer_name": r"(客户|公司)[:：]\s*([一-龥A-Za-z]+)",
        "work_order_id": r"WO[-_]?\d{4}[-_]?\d{3,}",
        "work_type": r"(质量检验|生产跟踪|入库检验|维护任务|紧急响应)",
        "issue_type": r"(物流延迟|货物损坏|供应短缺|生产异常|系统故障|其他异常)",
        "quality_issue": r"质量问题",
        "logistics_issue": r"物流异常",
        "priority": r"(优先级|优先)[:：]?\s*(紧急|高|中|低)",
        "urgency": r"(紧急程度|紧急级别|紧急)[:：]?\s*(紧急|高|中|低)",
        "amount": r"¥?\s*(\d+(?:\.\d{2})?)",
        "date": r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",
        "comment": r"(意见|理由|原因|说明|备注)[:：]?\s*([一-龥A-Za-z0-9，。！？、]+)",
    }

    # Action patterns for approval
    ACTION_PATTERNS = {
        "approve": r"(通过|批准|同意|审批通过)",
        "reject": r"(拒绝|驳回|不同意|审批拒绝)",
    }

    def __init__(self, llm_client: Optional['LLMClient'] = None):
        """
        Initialize ParserAgent with optional LLM client.

        Args:
            llm_client: LLM客户端实例（可选，默认从配置创建）
        """
        self.intent_cache = {}

        # LLM客户端
        self._llm_client = llm_client
        self.llm_enabled = LLM_AVAILABLE and settings.intent_rule_first

    @property
    def llm_client(self) -> Optional['LLMClient']:
        """Lazy load LLM client."""
        if self._llm_client is None and LLM_AVAILABLE:
            try:
                self._llm_client = get_llm_client()
            except ValueError:
                # API key未配置
                pass
        return self._llm_client

    async def parse_intent(self, text: str) -> Dict[str, Any]:
        """
        Parse user intent from text.

        Args:
            text: User input text

        Returns:
            Structured intent information
        """
        # Clean text
        cleaned_text = text.strip()

        # Check cache
        if cleaned_text in self.intent_cache:
            return self.intent_cache[cleaned_text]

        # Detect intent level 1
        intent_level_1 = self._detect_intent_level_1(cleaned_text)

        # Detect intent level 2 (initial)
        intent_level_2 = self._detect_intent_level_2(cleaned_text, intent_level_1)

        # Extract entities
        entities = self._extract_entities(cleaned_text, intent_level_1)

        # Refine intent level 2 based on extracted entities
        intent_level_2 = self._refine_intent_level_2(cleaned_text, intent_level_1, intent_level_2, entities)

        # Determine required slots
        required_slots = self._get_required_slots(intent_level_1, intent_level_2, entities)

        # Calculate confidence
        confidence = self._calculate_confidence(cleaned_text, intent_level_1, entities)

        # 判断是否需要LLM补充
        needs_llm = self._needs_llm_intent(cleaned_text, confidence, entities)
        used_llm = False

        if needs_llm and self.llm_client:
            try:
                # 第二步：LLM意图识别
                llm_result = await self._llm_classify_intent(cleaned_text)

                # 融合LLM结果
                if llm_result:
                    intent_level_1 = llm_result.get("intent_level_1", intent_level_1)
                    intent_level_2 = llm_result.get("intent_level_2", intent_level_2)
                    confidence = llm_result.get("confidence", confidence)
                    used_llm = True

                    # 重新提取实体（LLM可能识别出更多）
                    llm_entities = await self._llm_extract_entities(cleaned_text)
                    if llm_entities:
                        entities = self._merge_entities(entities, llm_entities)

            except Exception as e:
                print(f"⚠️ LLM intent classification failed: {e}, using rule-based result")

        # Construct intent object
        intent = {
            "intent_level_1": intent_level_1,
            "intent_level_2": intent_level_2,
            "entities": entities,
            "required_slots": required_slots,
            "missing_slots": [slot for slot in required_slots if slot not in entities],
            "confidence": confidence,
            "raw_text": cleaned_text,
            "used_llm": used_llm,
            "timestamp": self._get_timestamp()
        }

        # Cache result
        self.intent_cache[cleaned_text] = intent

        return intent

    def _detect_intent_level_1(self, text: str) -> str:
        """Detect first level intent."""
        text_lower = text.lower()

        # Check each intent pattern
        for intent_name, intent_info in self.INTENT_PATTERNS.items():
            for pattern in intent_info["patterns"]:
                if re.search(pattern, text_lower):
                    return intent_name

        # Default to 状态查询 if contains query-like words
        query_keywords = ["查", "问", "看", "找", "状态", "进度"]
        if any(keyword in text_lower for keyword in query_keywords):
            return "状态查询"

        # Default
        return "状态查询"

    def _detect_intent_level_2(self, text: str, level_1_intent: str) -> str:
        """Detect second level intent."""
        text_lower = text.lower()

        if level_1_intent == "状态查询":
            if "物流" in text_lower or "快递" in text_lower or "运" in text_lower:
                return "物流查询"
            elif "订单" in text_lower or "采购" in text_lower:
                return "订单状态查询"
            elif "合同" in text_lower or "协议" in text_lower:
                return "合同查询"
            else:
                return "通用查询"

        elif level_1_intent == "工单创建":
            if "质量" in text_lower or "检验" in text_lower:
                return "质量检验工单"
            elif "生产" in text_lower or "制造" in text_lower:
                return "生产跟踪工单"
            elif "物流" in text_lower or "运输" in text_lower:
                return "物流异常工单"
            else:
                return "通用工单"

        elif level_1_intent == "审批流转":
            if "通过" in text_lower or "批准" in text_lower:
                return "审批通过"
            elif "拒绝" in text_lower or "驳回" in text_lower:
                return "审批拒绝"
            else:
                return "审批处理"

        elif level_1_intent == "异常上报":
            if "质量" in text_lower:
                return "质量异常"
            elif "物流" in text_lower:
                return "物流异常"
            elif "生产" in text_lower:
                return "生产异常"
            else:
                return "通用异常"

        return "未知"

    def _refine_intent_level_2(self, text: str, level_1_intent: str, level_2_intent: str,
                               entities: List[Dict[str, str]]) -> str:
        """Refine intent level 2 based on extracted entities."""
        text_lower = text.lower()

        # For status queries, refine based on entity types
        if level_1_intent == "状态查询":
            entity_types = {e["type"] for e in entities}

            # If we have order_id, it's an order status query
            if "order_id" in entity_types:
                # But if also have tracking_no, it's a logistics query
                if "tracking_no" in entity_types or "物流" in text_lower or "运" in text_lower:
                    return "物流查询"
                return "订单状态查询"

            # If we have tracking_no only, it's a logistics query
            if "tracking_no" in entity_types:
                return "物流查询"

            # If we have customer_name, it might be a contract query
            if "customer_name" in entity_types or "合同" in text_lower:
                return "合同查询"

        return level_2_intent

    def _extract_entities(self, text: str, intent_level_1: str) -> List[Dict[str, str]]:
        """Extract entities from text."""
        entities = []
        extracted_values = set()  # 防止重复提取

        # Extract using patterns
        for entity_type, pattern in self.ENTITY_PATTERNS.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                value = match.group()
                # 避免重复提取
                if value in extracted_values:
                    continue

                extracted_values.add(value)
                entities.append({
                    "type": entity_type,
                    "value": value,
                    "start": match.start(),
                    "end": match.end()
                })

        # Special handling for approval intent - extract action and inline comment
        if intent_level_1 == "审批流转":
            # Check for action (approve/reject)
            for action_type, pattern in self.ACTION_PATTERNS.items():
                if re.search(pattern, text):
                    # Check if we already have action entity
                    has_action = any(e["type"] == "action" for e in entities)
                    if not has_action:
                        entities.append({
                            "type": "action",
                            "value": action_type,
                            "start": 0,
                            "end": 0
                        })
                    break

            # Extract inline comment (text after the action keyword)
            # Pattern: 审批工单XXX通过，检验合格 -> comment = "检验合格"
            inline_comment_patterns = [
                r"(?:通过|批准|同意)[，,]?\s*([一-龥A-Za-z0-9，。！？、]+)",
                r"(?:拒绝|驳回)[，,]?\s*([一-龥A-Za-z0-9，。！？、]+)",
            ]
            for pattern in inline_comment_patterns:
                match = re.search(pattern, text)
                if match:
                    comment_value = match.group(1).strip()
                    # Check if we already have comment entity
                    has_comment = any(e["type"] == "comment" for e in entities)
                    if not has_comment and comment_value:
                        entities.append({
                            "type": "comment",
                            "value": comment_value,
                            "start": match.start(1),
                            "end": match.end(1)
                        })
                    break

        # Special handling for work order creation - extract inline description
        if intent_level_1 == "工单创建":
            # Pattern: 创建XXX工单，YYY -> description = "YYY"
            # Also: 订单XXX需要检验，检查到货质量
            desc_patterns = [
                r"(?:工单|任务)[，,]?\s*([一-龥A-Za-z0-9，。！？、]+)$",
                r"(?:需要|要求)[，,]?\s*([一-龥A-Za-z0-9，。！？、]+)[，,]?\s*([一-龥A-Za-z0-9，。！？、]+)$",
            ]
            for pattern in desc_patterns:
                desc_match = re.search(pattern, text)
                if desc_match:
                    # Get all captured groups and join them
                    groups = [g for g in desc_match.groups() if g]
                    if groups:
                        desc_value = "，".join(groups)
                        has_desc = any(e["type"] == "description" for e in entities)
                        if not has_desc and desc_value:
                            entities.append({
                                "type": "description",
                                "value": desc_value,
                                "start": desc_match.start(),
                                "end": desc_match.end()
                            })
                        break

        # Special handling for issue reporting - extract inline description
        if intent_level_1 == "异常上报":
            # Pattern: 报告XXX问题，YYY -> description = "YYY"
            desc_patterns = [
                r"(?:问题|异常)[，,]?\s*([一-龥A-Za-z0-9，。！？、]+)$",
                r"(?:订单[A-Z0-9-]+)?[，,]?\s*([一-龥A-Za-z0-9，。！？、]+)$",
            ]
            for pattern in desc_patterns:
                desc_match = re.search(pattern, text)
                if desc_match:
                    desc_value = desc_match.group(1).strip()
                    has_desc = any(e["type"] == "description" for e in entities)
                    if not has_desc and desc_value and len(desc_value) > 2:
                        entities.append({
                            "type": "description",
                            "value": desc_value,
                            "start": desc_match.start(1),
                            "end": desc_match.end(1)
                        })
                    break

        # Post-process entities to map special cases
        entities = self._post_process_entities(entities, intent_level_1)

        return entities

    def _post_process_entities(self, entities: List[Dict[str, str]], intent_level_1: str) -> List[Dict[str, str]]:
        """Post-process extracted entities."""
        processed = []

        for entity in entities:
            entity_type = entity["type"]
            value = entity["value"]

            # Map quality_issue to appropriate type based on intent
            if entity_type == "quality_issue":
                if intent_level_1 == "工单创建":
                    entity["type"] = "work_type"
                elif intent_level_1 == "异常上报":
                    entity["type"] = "issue_type"

            # Map logistics_issue to appropriate type based on intent
            elif entity_type == "logistics_issue":
                if intent_level_1 == "工单创建":
                    entity["type"] = "work_type"
                elif intent_level_1 == "异常上报":
                    entity["type"] = "issue_type"

            # Map priority/urgency based on intent
            elif entity_type in ["priority", "urgency"]:
                # Try to determine which one it is based on context
                if "优先级" in value or "优先" in value:
                    entity["type"] = "priority"
                elif "紧急程度" in value or "紧急级别" in value:
                    entity["type"] = "urgency"
                else:
                    # Default mapping based on intent
                    if intent_level_1 == "工单创建":
                        entity["type"] = "priority"
                    elif intent_level_1 == "异常上报":
                        entity["type"] = "urgency"

            processed.append(entity)

        return processed

    def _get_required_slots(self, intent_level_1: str, intent_level_2: str,
                           entities: List[Dict[str, str]]) -> List[str]:
        """Get required slots for the intent."""
        required_slots = []

        if intent_level_1 in self.INTENT_PATTERNS:
            base_slots = self.INTENT_PATTERNS[intent_level_1]["required_slots"]
            required_slots.extend(base_slots)

        # Add intent-specific slots
        if intent_level_1 == "状态查询" and intent_level_2 == "物流查询":
            required_slots.append("tracking_no")
        elif intent_level_1 == "状态查询" and intent_level_2 == "订单状态查询":
            required_slots.append("order_id")
        elif intent_level_1 == "审批流转":
            required_slots.append("work_order_id")
            # comment is optional - we can use a default if not provided
            # required_slots.append("comment")
        elif intent_level_1 == "工单创建":
            required_slots.append("work_type")
            required_slots.append("description")
            if intent_level_2 == "质量检验工单":
                required_slots.append("order_id")  # 质量检验通常关联订单
        elif intent_level_1 == "异常上报":
            required_slots.append("issue_type")
            required_slots.append("description")
            if intent_level_2 in ["物流异常", "质量异常"]:
                required_slots.append("order_id")  # 物流/质量异常通常关联订单

        return list(set(required_slots))  # Remove duplicates

    def _calculate_confidence(self, text: str, intent_level_1: str,
                            entities: List[Dict[str, str]]) -> float:
        """Calculate confidence score for intent detection."""
        confidence = 0.5  # Base confidence

        # Boost for pattern matches
        intent_info = self.INTENT_PATTERNS.get(intent_level_1, {})
        patterns = intent_info.get("patterns", [])
        for pattern in patterns:
            if re.search(pattern, text.lower()):
                confidence += 0.2
                break

        # Boost for extracted entities
        if entities:
            confidence += min(0.3, len(entities) * 0.1)

        # Penalty for very short queries
        if len(text) < 5:
            confidence -= 0.2

        return max(0.1, min(1.0, confidence))  # Clamp between 0.1 and 1.0

    def _needs_llm_intent(self, text: str, confidence: float, entities: List[Dict]) -> bool:
        """判断是否需要LLM补充意图识别"""
        # 置信度低于阈值
        if confidence < settings.intent_confidence_threshold:
            return True

        # 未提取到实体
        if not entities:
            return True

        # 包含模糊表达词
        fuzzy_words = ["好像", "可能", "大概", "应该", "不确定", "那个", "某个"]
        if any(word in text for word in fuzzy_words):
            return True

        return False

    async def _llm_classify_intent(self, text: str) -> Optional[Dict[str, Any]]:
        """使用LLM进行意图识别"""
        if not self.llm_client:
            return None

        try:
            # 使用简单的字符串替换，避免格式化问题
            prompt = INTENT_CLASSIFICATION_PROMPT.replace("{user_input}", text)
            result = await self.llm_client.generate_json(prompt)
            return result
        except Exception as e:
            print(f"⚠️ LLM intent classification error: {e}")
            return None

    async def _llm_extract_entities(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """使用LLM进行实体提取"""
        if not self.llm_client:
            return None

        try:
            # 使用简单的字符串替换，避免格式化问题
            prompt = ENTITY_EXTRACTION_PROMPT.replace("{user_input}", text)
            result = await self.llm_client.generate_json(prompt)
            entities = result.get("entities", [])

            # 标准化实体格式
            standardized = []
            for e in entities:
                standardized.append({
                    "type": e.get("type", "unknown"),
                    "value": e.get("value", ""),
                    "confidence": e.get("confidence", 1.0),
                    "note": e.get("note", ""),
                    "start": 0,
                    "end": len(e.get("value", ""))
                })

            return standardized
        except Exception as e:
            print(f"⚠️ LLM entity extraction error: {e}")
            return None

    def _merge_entities(
        self,
        rule_entities: List[Dict],
        llm_entities: List[Dict]
    ) -> List[Dict]:
        """融合规则和LLM提取的实体"""
        merged = list(rule_entities)
        existing_values = {e["value"]: i for i, e in enumerate(rule_entities)}

        for entity in llm_entities:
            value = entity["value"]
            if value in existing_values:
                # 如果实体已存在，更新为LLM的版本（包含更多信息）
                merged[existing_values[value]] = entity
            else:
                # 添加新实体
                merged.append(entity)

        return merged

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()

    async def validate_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parsed intent.

        Args:
            intent: Parsed intent

        Returns:
            Validation result
        """
        issues = []

        # Check required slots
        missing_slots = intent.get("missing_slots", [])
        if missing_slots:
            issues.append(f"缺少必要信息: {', '.join(missing_slots)}")

        # Check confidence
        confidence = intent.get("confidence", 0)
        if confidence < 0.3:
            issues.append("意图识别置信度过低")

        # Check entity consistency
        entities = intent.get("entities", [])
        intent_level_1 = intent.get("intent_level_1", "")

        # Validate entities based on intent
        if intent_level_1 == "状态查询":
            order_entities = [e for e in entities if e["type"] in ["order_id", "tracking_no"]]
            if not order_entities:
                issues.append("状态查询需要订单号或运单号")
        elif intent_level_1 == "工单创建":
            if intent_level_2 == "质量检验工单":
                order_entities = [e for e in entities if e["type"] == "order_id"]
                if not order_entities:
                    issues.append("质量检验工单需要关联订单号")
        elif intent_level_1 == "异常上报":
            if intent_level_2 in ["物流异常", "质量异常"]:
                order_entities = [e for e in entities if e["type"] == "order_id"]
                if not order_entities:
                    issues.append(f"{intent_level_2}需要关联订单号")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "requires_clarification": len(missing_slots) > 0,
            "clarification_prompts": self._generate_clarification_prompts(missing_slots)
        }

    def _generate_clarification_prompts(self, missing_slots: List[str]) -> List[str]:
        """Generate clarification prompts for missing slots."""
        prompts = []

        slot_prompts = {
            "order_id": "请问您要查询哪个订单？请输入订单号（例如：PO-2026-001）",
            "tracking_no": "请问您要查询哪个运单？请输入运单号",
            "work_order_id": "请问您要审批哪个工单？请输入工单号",
            "comment": "请输入审批意见",
            "work_type": "请问要创建什么类型的工单？",
            "description": "请描述工单的具体内容",
            "issue_type": "请问是什么类型的问题？",
            "urgency": "请问紧急程度如何？（高/中/低）"
        }

        for slot in missing_slots:
            if slot in slot_prompts:
                prompts.append(slot_prompts[slot])
            else:
                prompts.append(f"请提供{slot}信息")

        return prompts

    async def request_clarification(self, missing_slots: List[str]) -> str:
        """
        Request clarification for missing information.

        Args:
            missing_slots: List of missing slot names

        Returns:
            Clarification prompt
        """
        if not missing_slots:
            return "请提供更多信息。"

        slot_descriptions = {
            "order_id": "订单号",
            "tracking_no": "运单号",
            "work_order_id": "工单号",
            "comment": "审批意见",
            "work_type": "工单类型",
            "description": "描述",
            "issue_type": "问题类型",
            "urgency": "紧急程度"
        }

        prompts = []
        for slot in missing_slots:
            description = slot_descriptions.get(slot, slot)
            prompts.append(f"请提供{description}")

        if len(prompts) == 1:
            return prompts[0]
        else:
            return "请提供以下信息：\n" + "\n".join(f"- {prompt}" for prompt in prompts)