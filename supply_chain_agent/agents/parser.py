"""
Parser Agent (解析师)

Responsible for understanding user intent and extracting relevant information.
Enhanced with LLM integration for fuzzy input handling.
Entity extraction powered by BERT NER model.
Entity mappings loaded from database (dataset/OtherData/EntityMapping.csv).
"""

from typing import Dict, Any, List, Optional
import re
import json
from dataclasses import dataclass

from supply_chain_agent.config import settings

# BERT NER 导入
try:
    from supply_chain_agent.nlp.bert_ner import get_ner_model, extract_entities as bert_extract_entities
    BERT_NER_AVAILABLE = True
except ImportError:
    BERT_NER_AVAILABLE = False
    print("⚠️ BERT NER not available, using rule-based entity extraction only")

# LLM相关导入
try:
    from supply_chain_agent.agents.llm_client import LLMClient, get_llm_client
    from supply_chain_agent.prompts.intent import INTENT_CLASSIFICATION_PROMPT
    from supply_chain_agent.prompts.entity import ENTITY_EXTRACTION_PROMPT
    from supply_chain_agent.prompts.combined import COMBINED_INTENT_ENTITY_PROMPT
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("⚠️ LLM integration not available, using rule-based only")


@dataclass
class Intent:
    """Structured intent representation."""
    level_1: str  # 信息查询、工单管理、异常上报
    level_2: str  # 订单查询、物流查询、创建工单、审批工单、上报问题等
    entities: List[Dict[str, str]]
    required_slots: List[str]
    confidence: float


class ParserAgent:
    """Parser agent for intent recognition and information extraction."""

    # Intent patterns (一级任务分类)
    INTENT_PATTERNS = {
        "信息查询": {
            "patterns": [
                r"查(一下|询)?.*?(订单|状态|货|客户|产品|物流)",
                r"订单.*?(状态|在哪|到哪)",
                r"物流.*?(查询|跟踪|轨迹)",
                r"(客户|产品).*?(信息|查询)",
                r"统计.*?(数据|信息)"
            ],
            "entities": ["order_id", "customer_id", "product_card_id"],
            "required_slots": []
        },
        "工单管理": {
            "patterns": [
                r"创建.*?(工单|任务|申请)",
                r"新建.*?(工单|任务|申请|请求)",
                r"提交.*?(工单|任务|申请|处理|审批)",
                r"开.*?(工单|任务)",
                r"审批.*?(工单|申请)",
                r"通过.*?(请求|申请)",
                r"拒绝.*?(工单|请求)"
            ],
            "entities": ["work_order_id", "work_type", "priority", "description", "action", "comment"],
            "required_slots": []
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

    # Entity extraction patterns (base patterns)
    ENTITY_PATTERNS = {
        "order_id": r"(?:订单|order)[^0-9]*(\d{4,})",  # 匹配 "订单77202" 或 "order 77202"
        "customer_id": r"(?:客户|customer)[^0-9]*(\d+)",  # 匹配 "客户123"
        "product_card_id": r"(?:产品|product)[^0-9]*(\d+)",  # 匹配 "产品456"
        "tracking_no": r"[A-Z]{2}\d{9,11}[A-Z]?|\d{12,14}",
        "customer_name": r"(客户|公司)[:：]\s*([一-龥A-Za-z]+)",
        "work_order_id": r"WO[-_]?\d+(?:[-_]\d+)?",  # 匹配 WO-0001, WO-2026-001, WO-20260526-001
        "work_type": r"(质检|审批|异常处理|退款|调拨|质量检验|生产跟踪|入库检验|维护任务|紧急响应|其他)",  # 包含MCP有效类型和常见简称
        "issue_type": r"(物流延迟|库存异常|质量缺陷|数据错误|客户投诉|其他|货物损坏|供应短缺|生产异常|系统故障)",  # 基于MCP有效类型
        "quality_issue": r"质量问题",
        "logistics_issue": r"物流异常",
        "priority": r"(优先级|优先)[:：]?\s*(紧急|高|中|低)",
        "urgency": r"(紧急程度|紧急级别|紧急)[:：]?\s*(紧急|高|中|低)",
        "amount": r"¥\s*(\d+(?:\.\d{2})?)",  # 只匹配带¥符号的金额
        "date": r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",
        "comment": r"(意见|理由|原因|说明|备注)[:：]?\s*([一-龥A-Za-z0-9，。！？、]+)",
    }

    # Action patterns for approval
    ACTION_PATTERNS = {
        "approve": r"(通过|批准|同意|审批通过)",
        "reject": r"(拒绝|驳回|不同意|审批拒绝)",
    }

    def __init__(self, llm_client: Optional['LLMClient'] = None, use_bert_ner: bool = False):
        """
        Initialize ParserAgent with optional LLM client and BERT NER.

        Args:
            llm_client: LLM客户端实例（可选，默认从配置创建）
            use_bert_ner: 是否使用BERT NER进行实体识别（默认False，使用规则）
        """
        self.intent_cache = {}

        # LLM客户端
        self._llm_client = llm_client
        self.llm_enabled = LLM_AVAILABLE and settings.intent_rule_first

        # BERT NER - 初始化时检查可用性
        self.use_bert_ner = use_bert_ner and BERT_NER_AVAILABLE
        self._bert_ner = None
        self._bert_ner_available = False  # 新增：跟踪BERT NER是否真正可用

        if self.use_bert_ner:
            try:
                self._bert_ner = get_ner_model(use_bert=True)
                # 验证模型是否真正加载成功
                if self._bert_ner and self._bert_ner.model is not None:
                    self._bert_ner_available = True
                    print("✅ BERT NER已启用并可用")
                else:
                    print("⚠️ BERT NER模型未正确加载，将跳过第二层，直接使用LLM")
                    self.use_bert_ner = False
            except Exception as e:
                print(f"⚠️ BERT NER初始化失败: {e}，将跳过第二层，直接使用LLM")
                self.use_bert_ner = False
                self._bert_ner_available = False

        # Load entity mappings from database
        self._entity_mappings = None
        self._load_entity_mappings()

    def _load_entity_mappings(self):
        """Load entity mappings from database."""
        try:
            from supply_chain_agent.data.supply_chain_db import get_entity_mappings
            mappings = get_entity_mappings()
            if mappings:
                self._entity_mappings = mappings
                # Extend entity patterns with loaded mappings
                self._extend_entity_patterns()
        except Exception as e:
            # Database may not be initialized yet
            pass

    def _extend_entity_patterns(self):
        """Extend entity patterns with loaded mappings."""
        if not self._entity_mappings:
            return

        # Add patterns for common aliases
        for standard_name, aliases in self._entity_mappings.items():
            # Skip if already have a pattern for this entity
            if standard_name in self.ENTITY_PATTERNS:
                continue

            # Create a pattern that matches any of the aliases
            # This helps with Chinese natural language queries
            # For now, we just store the mappings for lookup
            pass

    def resolve_entity_alias(self, alias: str) -> Optional[str]:
        """
        Resolve an alias to its standard entity name.

        Args:
            alias: The alias to resolve

        Returns:
            Standard entity name or None
        """
        if not self._entity_mappings:
            return None

        for standard_name, aliases in self._entity_mappings.items():
            if alias in aliases or alias == standard_name:
                return standard_name

        return None

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
        Parse user intent from text with 3-layer architecture.

        第一层：规则引擎 - 意图模式匹配（一级+二级）+ 置信度计算
        第二层：BERT NER - 实体提取
        第三层：LLM - 意图分类 + 实体提取（规则未命中/置信度低/实体为空时触发）

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

        # ========== 第一层：规则引擎 - 意图模式匹配 ==========
        intent_level_1 = self._detect_intent_level_1(cleaned_text)
        intent_level_2 = self._detect_intent_level_2(cleaned_text, intent_level_1)
        confidence = self._calculate_confidence(cleaned_text, intent_level_1, intent_level_2)

        # 判断是否需要LLM补充意图识别（第一层判断）
        needs_llm_for_intent = self._needs_llm_intent(cleaned_text, intent_level_1, intent_level_2, confidence)
        used_llm = False
        entities = []

        # ========== 第二层：实体提取 ==========
        # 始终执行第二层，不再跳过
        entities = self._extract_entities(cleaned_text, intent_level_1)

        # 如果第二层未提取到实体，可能需要LLM补充实体
        needs_llm_for_entities = len(entities) == 0

        # ========== 第三层：LLM（如果需要）==========
        # 触发条件：意图识别需要LLM 或 实体提取为空
        needs_llm = needs_llm_for_intent or needs_llm_for_entities

        if needs_llm and self.llm_client:
            try:
                # LLM同时进行意图识别和实体提取（单次调用）
                llm_result = await self._llm_classify_and_extract(cleaned_text)

                # 融合LLM结果
                if llm_result:
                    intent_level_1 = llm_result.get("intent_level_1", intent_level_1)
                    intent_level_2 = llm_result.get("intent_level_2", intent_level_2)
                    confidence = llm_result.get("confidence", confidence)
                    used_llm = True

                    # 使用LLM返回的实体
                    llm_entities = llm_result.get("entities", [])
                    if llm_entities:
                        entities = llm_entities

            except Exception as e:
                print(f"⚠️ LLM intent classification failed: {e}, using rule-based result")

        # Determine required slots
        required_slots = self._get_required_slots(intent_level_1, intent_level_2)

        # Construct intent object
        intent = {
            "intent_level_1": intent_level_1,
            "intent_level_2": intent_level_2,
            "entities": entities,
            "required_slots": required_slots,
            "missing_slots": [slot for slot in required_slots if slot not in {e["type"] for e in entities}],
            "confidence": confidence,
            "raw_text": cleaned_text,
            "used_llm": used_llm,
            "used_ner": not used_llm and len(entities) > 0,
            "bert_ner_available": self._bert_ner_available,
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

        # Default to 信息查询 if contains query-like words
        query_keywords = ["查", "问", "看", "找", "状态", "进度", "信息"]
        if any(keyword in text_lower for keyword in query_keywords):
            return "信息查询"

        # Default
        return "信息查询"

    def _detect_intent_level_2(self, text: str, level_1_intent: str) -> str:
        """Detect second level intent based on MCP tools."""
        text_lower = text.lower()

        if level_1_intent == "信息查询":
            # 基于MCP工具的二级分类
            if "客户" in text_lower and ("订单" in text_lower or "统计" in text_lower):
                return "客户订单查询"
            elif "客户" in text_lower and "统计" in text_lower:
                return "客户统计查询"
            elif "客户" in text_lower:
                return "客户查询"
            elif "物流" in text_lower or "快递" in text_lower or "运" in text_lower:
                return "物流查询"
            elif "订单" in text_lower and "明细" in text_lower:
                return "订单明细查询"
            elif "订单" in text_lower or "采购" in text_lower:
                return "订单查询"
            elif "产品" in text_lower:
                return "产品查询"
            else:
                return "订单查询"  # 默认

        elif level_1_intent == "工单管理":
            if "审批" in text_lower or "通过" in text_lower or "拒绝" in text_lower:
                return "审批工单"
            else:
                return "创建工单"

        elif level_1_intent == "异常上报":
            return "上报问题"

        return "未知"

    def _extract_entities(self, text: str, intent_level_1: str) -> List[Dict[str, str]]:
        """Extract entities from text using rules and optional BERT NER."""
        entities = []
        extracted_values = set()  # 防止重复提取

        # Step 1: 规则提取 (始终执行，作为基础)
        for entity_type, pattern in self.ENTITY_PATTERNS.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # 对于有捕获组的模式，使用捕获组；否则使用整个匹配
                if match.lastindex and match.lastindex >= 1:
                    value = match.group(1)  # 使用第一个捕获组
                else:
                    value = match.group()

                # 避免重复提取
                if value in extracted_values:
                    continue

                extracted_values.add(value)
                entities.append({
                    "type": entity_type,
                    "value": value,
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 0.95  # 规则提取置信度较高
                })

        # Step 2: BERT NER提取 (如果启用)
        if self.use_bert_ner and self._bert_ner:
            try:
                bert_entities = self._bert_ner.extract_for_intent(text, intent_level_1)
                # 合并BERT结果，只添加规则未覆盖的
                for entity in bert_entities:
                    if entity["value"] not in extracted_values:
                        extracted_values.add(entity["value"])
                        entities.append(entity)
            except Exception as e:
                print(f"⚠️ BERT NER提取失败: {e}")

        # Special handling for approval intent - extract action and inline comment
        if intent_level_1 == "工单管理":
            # Check for action (approve/reject) for approval workflow
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
        if intent_level_1 == "工单管理":
            # Pattern: 创建XXX工单，YYY -> description = "YYY"
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
                if intent_level_1 == "工单管理":
                    entity["type"] = "work_type"
                elif intent_level_1 == "异常上报":
                    entity["type"] = "issue_type"

            # Map logistics_issue to appropriate type based on intent
            elif entity_type == "logistics_issue":
                if intent_level_1 == "工单管理":
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
                    if intent_level_1 == "工单管理":
                        entity["type"] = "priority"
                    elif intent_level_1 == "异常上报":
                        entity["type"] = "urgency"

            processed.append(entity)

        return processed

    def _extract_entities_with_ner(self, text: str, intent_level_1: str) -> List[Dict[str, str]]:
        """
        使用BERT NER提取实体（第二层）

        Args:
            text: 用户输入文本
            intent_level_1: 一级意图

        Returns:
            实体列表（如果BERT NER不可用，返回空列表）
        """
        entities = []

        # 使用BERT NER提取
        if self._bert_ner_available and self._bert_ner:
            try:
                bert_entities = self._bert_ner.extract_for_intent(text, intent_level_1)
                entities.extend(bert_entities)
            except Exception as e:
                print(f"⚠️ BERT NER failed: {e}")

        # 注意：如果BERT NER不可用，返回空列表
        # parse_intent() 会检测到实体为空，触发LLM补充

        return entities

    def _get_required_slots(self, intent_level_1: str, intent_level_2: str) -> List[str]:
        """
        获取意图所需的必填槽位（不依赖实体）

        Args:
            intent_level_1: 一级意图
            intent_level_2: 二级意图

        Returns:
            必填槽位列表
        """
        required_slots = []

        # 二级任务对应的必填参数（基于MCP工具参数定义）
        slot_mapping = {
            "客户查询": ["customer_id"],
            "客户订单查询": ["customer_id"],
            "客户统计查询": ["customer_id"],
            "订单查询": ["order_id"],
            "订单明细查询": ["order_id"],
            "物流查询": ["order_id"],
            "产品查询": ["product_card_id"],
            "创建工单": ["work_type", "description"],
            "审批工单": ["work_order_id", "action"],
            "上报问题": ["issue_type", "description"],
        }

        required_slots = slot_mapping.get(intent_level_2, [])

        # 添加一级意图基础槽位
        if intent_level_1 in self.INTENT_PATTERNS:
            base_slots = self.INTENT_PATTERNS[intent_level_1].get("required_slots", [])
            required_slots.extend(base_slots)

        return list(set(required_slots))  # Remove duplicates

    def _calculate_confidence(self, text: str, intent_level_1: str,
                            intent_level_2: str) -> float:
        """
        计算意图识别置信度（仅基于规则匹配，不依赖实体）

        置信度计算规则：
        - 基础分: 0.4
        - 一级意图模式命中: +0.2
        - 二级意图关键词命中: +0.2
        - 文本长度合理(>=5): +0.1
        - 短文本惩罚(<5): -0.1
        """
        confidence = 0.4  # Base confidence

        # 一级意图模式匹配加分
        intent_info = self.INTENT_PATTERNS.get(intent_level_1, {})
        patterns = intent_info.get("patterns", [])
        for pattern in patterns:
            if re.search(pattern, text.lower()):
                confidence += 0.2
                break

        # 二级意图关键词命中加分
        if intent_level_2 != "未知":
            confidence += 0.2

        # 文本长度调整
        if len(text) >= 5:
            confidence += 0.1
        else:
            confidence -= 0.1

        return max(0.1, min(1.0, confidence))  # Clamp between 0.1 and 1.0

    def _needs_llm_intent(self, text: str, intent_level_1: str, intent_level_2: str, confidence: float) -> bool:
        """
        判断是否需要LLM补充

        触发条件：
        1. 一级意图未匹配到任何模式（返回默认值）
        2. 二级意图为"未知"
        3. 置信度低于阈值
        """
        # 规则未命中任何一级意图模式（使用默认值）
        intent_info = self.INTENT_PATTERNS.get(intent_level_1, {})
        patterns = intent_info.get("patterns", [])
        pattern_matched = any(re.search(p, text.lower()) for p in patterns)

        if not pattern_matched:
            return True  # 规则未命中，需要LLM

        # 二级意图未知
        if intent_level_2 == "未知":
            return True

        # 置信度低于阈值
        if confidence < settings.intent_confidence_threshold:
            return True

        return False

    async def _llm_classify_and_extract(self, text: str) -> Optional[Dict[str, Any]]:
        """
        使用LLM同时进行意图识别和实体提取

        Args:
            text: 用户输入文本

        Returns:
            包含意图和实体的字典，格式：
            {
                "intent_level_1": str,
                "intent_level_2": str,
                "confidence": float,
                "entities": List[Dict]
            }
        """
        if not self.llm_client:
            return None

        try:
            print("🔄 使用LLM进行意图识别+实体提取")
            # 使用合并的prompt模板
            prompt = COMBINED_INTENT_ENTITY_PROMPT.replace("{user_input}", text)
            result = await self.llm_client.generate_json(prompt)

            # 标准化实体格式
            entities = result.get("entities", [])
            standardized_entities = []
            for e in entities:
                standardized_entities.append({
                    "type": e.get("type", "unknown"),
                    "value": e.get("value", ""),
                    "confidence": e.get("confidence", 1.0),
                    "note": e.get("note", ""),
                    "start": 0,
                    "end": len(e.get("value", ""))
                })

            return {
                "intent_level_1": result.get("intent_level_1", "信息查询"),
                "intent_level_2": result.get("intent_level_2", "未知"),
                "confidence": result.get("confidence", 0.5),
                "entities": standardized_entities
            }
        except Exception as e:
            print(f"⚠️ LLM combined classification error: {e}")
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
        intent_level_2 = intent.get("intent_level_2", "")

        # Validate entities based on intent
        if intent_level_1 == "信息查询":
            query_entities = [e for e in entities if e["type"] in ["order_id", "customer_id", "product_card_id"]]
            if not query_entities:
                issues.append("信息查询需要提供订单号、客户ID或产品ID")
        elif intent_level_2 == "审批工单":
            work_order_entities = [e for e in entities if e["type"] == "work_order_id"]
            if not work_order_entities:
                issues.append("审批工单需要提供工单号")
        elif intent_level_2 == "创建工单":
            work_type_entities = [e for e in entities if e["type"] == "work_type"]
            desc_entities = [e for e in entities if e["type"] == "description"]
            if not work_type_entities:
                issues.append("创建工单需要指定工单类型")
            if not desc_entities:
                issues.append("创建工单需要提供描述")
        elif intent_level_2 == "上报问题":
            issue_type_entities = [e for e in entities if e["type"] == "issue_type"]
            desc_entities = [e for e in entities if e["type"] == "description"]
            if not issue_type_entities:
                issues.append("上报问题需要指定问题类型")
            if not desc_entities:
                issues.append("上报问题需要提供描述")

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
            "order_id": "请问您要查询哪个订单？请输入订单号（数字ID）",
            "customer_id": "请问您要查询哪个客户？请输入客户ID（数字ID）",
            "product_card_id": "请问您要查询哪个产品？请输入产品卡片ID（数字ID）",
            "work_order_id": "请问您要审批哪个工单？请输入工单号",
            "action": "请问审批动作是什么？（approve/reject/escalate）",
            "comment": "请输入审批意见",
            "work_type": "请问要创建什么类型的工单？（审批/异常处理/退款/调拨/质检/其他）",
            "description": "请描述具体内容",
            "issue_type": "请问是什么类型的问题？（物流延迟/库存异常/质量缺陷/数据错误/客户投诉/其他）",
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
            "customer_id": "客户ID",
            "product_card_id": "产品卡片ID",
            "work_order_id": "工单号",
            "action": "审批动作",
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