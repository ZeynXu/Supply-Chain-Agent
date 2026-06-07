"""
Parser Agent (解析师)

Responsible for understanding user intent and extracting relevant information.
Enhanced with LLM integration for fuzzy input handling.
Entity extraction powered by BERT NER model.
Entity mappings loaded from database (dataset/OtherData/EntityMapping.csv).

M4修复：三层意图识别架构说明
=============================
意图识别采用三层流水线架构：

**第一层：规则引擎（快速路径）**
- 使用正则表达式匹配意图模式
- 使用关键词映射表识别实体
- 置信度>=0.75时直接返回，跳过后续层

**第二层：BERT NER（精确提取，可选）**
- 当规则引擎置信度不足时启用
- 使用预训练BERT模型提取命名实体
- 模型文件不存在时自动降级到规则层

**第三层：LLM（兜底）**
- 当规则+NER都无法确定意图时启用
- 同时完成意图分类和实体提取
- 适用于模糊、非标准输入

**触发条件**:
- 规则层置信度 < threshold (0.75) → 进入第二层
- NER实体为空且置信度 < 0.7 → 进入第三层
- 显式配置 `intent_rule_first=False` → 直接进入第三层
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

# H4修复：导入ServiceContainer
from supply_chain_agent.common.service_container import ServiceContainer


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

    # L15修复：否定词列表，用于排除误判
    NEGATION_PATTERNS = [
        r"不想|不要|不希望|无需|不用",
        r"不是.*?(查询|查|看)",
        r"取消|撤销",
        r"暂时不需要",
    ]

    # M24修复：意图缓存配置
    INTENT_CACHE_MAX_SIZE = 100  # 最大缓存条目
    INTENT_CACHE_TTL_SECONDS = 3600  # 缓存过期时间（1小时）

    def __init__(self, llm_client: Optional['LLMClient'] = None, use_bert_ner: bool = False):
        """
        Initialize ParserAgent with optional LLM client and BERT NER.

        Args:
            llm_client: LLM客户端实例（可选，默认从配置创建）
            use_bert_ner: 是否使用BERT NER进行实体识别（默认False，使用规则）
        """
        # M24修复：改进意图缓存，支持LRU和过期
        self.intent_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_order: List[str] = []  # LRU顺序

        # H4修复：LLM客户端通过ServiceContainer获取
        if llm_client is not None:
            self._llm_client = llm_client
        else:
            self._llm_client = ServiceContainer.get_llm_client() if LLM_AVAILABLE else None
        self.llm_enabled = LLM_AVAILABLE and settings.intent_rule_first

        # BERT NER - 初始化时检查可用性
        self.use_bert_ner = use_bert_ner and BERT_NER_AVAILABLE
        self._bert_ner = None
        self._bert_ner_available = False  # 新增：跟踪BERT NER是否真正可用

        if self.use_bert_ner:
            try:
                # H4修复：通过ServiceContainer获取NER模型
                self._bert_ner = ServiceContainer.get_ner_instance()
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

    # M24修复：缓存管理方法
    def _get_cache_key(self, text: str, context_hash: str = "") -> str:
        """
        生成缓存键，考虑上下文

        Args:
            text: 用户输入
            context_hash: 上下文hash（可选）

        Returns:
            缓存键
        """
        import hashlib
        content = f"{text}:{context_hash}" if context_hash else text
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _get_cached_intent(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        从缓存获取意图（带过期检查）

        Args:
            cache_key: 缓存键

        Returns:
            缓存的意图结果，或None
        """
        import time

        # 检查过期
        if cache_key in self._cache_timestamps:
            age = time.time() - self._cache_timestamps[cache_key]
            if age > self.INTENT_CACHE_TTL_SECONDS:
                # 过期，删除
                del self.intent_cache[cache_key]
                del self._cache_timestamps[cache_key]
                if cache_key in self._cache_order:
                    self._cache_order.remove(cache_key)
                return None

        if cache_key in self.intent_cache:
            # 更新LRU顺序
            if cache_key in self._cache_order:
                self._cache_order.remove(cache_key)
            self._cache_order.append(cache_key)
            return self.intent_cache[cache_key]
        return None

    def _set_cached_intent(self, cache_key: str, intent: Dict[str, Any]):
        """
        存入意图缓存（带LRU淘汰）

        Args:
            cache_key: 缓存键
            intent: 意图结果
        """
        import time

        # LRU淘汰
        while len(self.intent_cache) >= self.INTENT_CACHE_MAX_SIZE:
            if self._cache_order:
                oldest = self._cache_order.pop(0)
                self.intent_cache.pop(oldest, None)
                self._cache_timestamps.pop(oldest, None)
            else:
                break

        self.intent_cache[cache_key] = intent
        self._cache_timestamps[cache_key] = time.time()
        self._cache_order.append(cache_key)

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

        M4修复：明确三层架构的执行逻辑
        ================================
        **第一层：规则引擎（快速路径）**
        - 意图模式匹配（一级+二级）
        - 规则实体提取
        - 置信度 >= 0.75 时跳过后续层

        **第二层：BERT NER（精确提取，条件触发）**
        - 触发条件：规则层置信度 < 0.75 或 规则实体为空
        - 使用BERT模型提取命名实体
        - 模型不可用时自动跳过

        **第三层：LLM（兜底）**
        - 触发条件：
          1. 第一层+第二层后置信度仍 < 0.7，或
          2. 实体仍为空且是复杂意图
        - 同时完成意图分类和实体提取

        Args:
            text: User input text

        Returns:
            Structured intent information
        """
        # Clean text
        cleaned_text = text.strip()

        # M24修复：使用改进的缓存机制
        cache_key = self._get_cache_key(cleaned_text)
        cached_intent = self._get_cached_intent(cache_key)
        if cached_intent is not None:
            return cached_intent

        # 初始化结果变量
        intent_level_1 = "信息查询"
        intent_level_2 = "未知"
        entities = []
        confidence = 0.0
        used_llm = False
        used_ner = False

        # ========== 第一层：规则引擎（始终执行）==========
        intent_level_1 = self._detect_intent_level_1(cleaned_text)
        intent_level_2 = self._detect_intent_level_2(cleaned_text, intent_level_1)

        # 规则实体提取
        rule_entities = self._extract_entities_by_rules(cleaned_text, intent_level_1)
        rule_confidence = self._calculate_confidence(cleaned_text, intent_level_1, intent_level_2)

        entities = rule_entities
        confidence = rule_confidence

        # 判断是否跳过后续层（快速路径）
        # 条件：置信度 >= 0.75 且 有实体 或 意图明确不需要实体
        skip_further_layers = self._can_skip_further_layers(
            confidence, entities, intent_level_1, intent_level_2
        )

        # ========== 第二层：BERT NER（条件触发）==========
        ner_entities = []
        ner_triggered = False

        if not skip_further_layers and self._should_trigger_ner(confidence, entities):
            ner_triggered = True
            ner_entities = self._extract_entities_by_ner(cleaned_text, intent_level_1)

            if ner_entities:
                # 合并NER实体（规则未覆盖的）
                entities = self._merge_entities(rule_entities, ner_entities)
                used_ner = True
                # NER提取成功，提升置信度
                confidence = min(1.0, confidence + 0.1)

        # ========== 第三层：LLM（条件触发）==========
        # 触发条件：置信度仍低 或 实体为空且需要实体
        should_trigger_llm = self._should_trigger_llm(
            confidence, entities, intent_level_1, intent_level_2
        )

        if not skip_further_layers and should_trigger_llm and self.llm_client:
            try:
                llm_result = await self._llm_classify_and_extract(cleaned_text)

                if llm_result:
                    # 融合LLM结果
                    llm_intent_1 = llm_result.get("intent_level_1")
                    llm_intent_2 = llm_result.get("intent_level_2")
                    llm_confidence = llm_result.get("confidence", 0.0)
                    llm_entities = llm_result.get("entities", [])

                    # 如果LLM置信度更高，使用LLM的意图
                    if llm_confidence > confidence:
                        intent_level_1 = llm_intent_1 or intent_level_1
                        intent_level_2 = llm_intent_2 or intent_level_2
                        confidence = llm_confidence

                    # 合并LLM实体
                    if llm_entities:
                        entities = self._merge_entities(entities, llm_entities)
                        used_llm = True

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
            "used_ner": used_ner,
            "layer_triggered": {
                "layer1_rules": True,
                "layer2_ner": ner_triggered,
                "layer3_llm": used_llm
            },
            "bert_ner_available": self._bert_ner_available,
            "timestamp": self._get_timestamp()
        }

        # M24修复：使用改进的缓存机制
        self._set_cached_intent(cache_key, intent)

        return intent

    # M4修复：明确各层触发条件的方法

    def _can_skip_further_layers(self, confidence: float, entities: List[Dict],
                                  intent_level_1: str, intent_level_2: str) -> bool:
        """
        判断是否可以跳过后续层（快速路径）。

        条件：
        1. 置信度 >= 0.75 且有实体，或
        2. 意图类型不需要复杂实体提取
        """
        # 高置信度且有实体
        if confidence >= 0.75 and len(entities) > 0:
            return True

        # 某些意图类型不需要复杂实体提取
        simple_intents = ["客户订单查询", "客户统计查询"]
        if intent_level_2 in simple_intents and confidence >= 0.6:
            return True

        return False

    def _should_trigger_ner(self, confidence: float, entities: List[Dict]) -> bool:
        """
        判断是否应触发NER层。

        条件：
        1. 规则层置信度 < 0.75，或
        2. 规则实体为空
        """
        if not self.use_bert_ner or not self._bert_ner_available:
            return False

        # 置信度不足
        if confidence < 0.75:
            return True

        # 无实体
        if len(entities) == 0:
            return True

        return False

    def _should_trigger_llm(self, confidence: float, entities: List[Dict],
                            intent_level_1: str, intent_level_2: str) -> bool:
        """
        判断是否应触发LLM层。

        条件：
        1. 置信度 < 0.7，或
        2. 实体为空且意图需要实体
        """
        # 置信度不足
        if confidence < 0.7:
            return True

        # 需要实体但无实体
        requires_entities = intent_level_1 in ["工单管理", "异常上报"]
        if requires_entities and len(entities) == 0:
            return True

        return False

    def _extract_entities_by_rules(self, text: str, intent_level_1: str) -> List[Dict[str, str]]:
        """
        M4修复：仅使用规则提取实体（第一层）。
        """
        entities = []
        extracted_keys = set()

        for entity_type, pattern in self.ENTITY_PATTERNS.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                if match.lastindex and match.lastindex >= 1:
                    value = match.group(1)
                else:
                    value = match.group()

                entity_key = (entity_type, value)
                if entity_key in extracted_keys:
                    continue

                extracted_keys.add(entity_key)
                entities.append({
                    "type": entity_type,
                    "value": value,
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 0.95,
                    "source": "rules"
                })

        # 特殊处理：审批动作和备注
        if intent_level_1 == "工单管理":
            entities.extend(self._extract_approval_entities(text, extracted_keys))

        return entities

    def _extract_entities_by_ner(self, text: str, intent_level_1: str) -> List[Dict[str, str]]:
        """
        M4修复：仅使用BERT NER提取实体（第二层）。
        """
        if not self._bert_ner or not self._bert_ner_available:
            return []

        try:
            ner_entities = self._bert_ner.extract_for_intent(text, intent_level_1)
            for e in ner_entities:
                e["source"] = "ner"
            return ner_entities
        except Exception as e:
            print(f"⚠️ BERT NER提取失败: {e}")
            return []

    def _merge_entities(self, base_entities: List[Dict], new_entities: List[Dict]) -> List[Dict]:
        """
        M4修复：合并实体列表，避免重复。
        """
        merged = list(base_entities)
        existing_keys = {(e["type"], e["value"]) for e in merged}

        for entity in new_entities:
            key = (entity.get("type"), entity.get("value"))
            if key not in existing_keys:
                existing_keys.add(key)
                merged.append(entity)

        return merged

    def _extract_approval_entities(self, text: str, extracted_keys: set) -> List[Dict[str, str]]:
        """提取审批相关的特殊实体。"""
        entities = []

        # 提取动作
        for action_type, pattern in self.ACTION_PATTERNS.items():
            if re.search(pattern, text):
                if not any(("action", action_type) == key for key in extracted_keys):
                    entities.append({
                        "type": "action",
                        "value": action_type,
                        "start": 0,
                        "end": 0,
                        "confidence": 0.95,
                        "source": "rules"
                    })
                break

        # 提取备注
        inline_comment_patterns = [
            r"(?:通过|批准|同意)[，,]?\s*([一-龥A-Za-z0-9，。！？、]+)",
            r"(?:拒绝|驳回)[，,]?\s*([一-龥A-Za-z0-9，。！？、]+)",
        ]
        for pattern in inline_comment_patterns:
            match = re.search(pattern, text)
            if match:
                comment_value = match.group(1).strip()
                if not any(("comment", comment_value) == key for key in extracted_keys):
                    entities.append({
                        "type": "comment",
                        "value": comment_value,
                        "start": match.start(1),
                        "end": match.end(1),
                        "confidence": 0.9,
                        "source": "rules"
                    })
                break

        return entities

    def _detect_intent_level_1(self, text: str) -> str:
        """
        Detect first level intent.

        L15修复：添加否定词检查，避免误判
        """
        text_lower = text.lower()

        # L15修复：检查否定词，如果匹配则跳过意图检测
        for neg_pattern in self.NEGATION_PATTERNS:
            if re.search(neg_pattern, text_lower):
                # 包含否定词，返回默认意图
                return "信息查询"

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
        # 使用(类型,值)元组作为去重键，避免相同值不同类型的实体被错误跳过
        extracted_keys = set()

        # Step 1: 规则提取 (始终执行，作为基础)
        for entity_type, pattern in self.ENTITY_PATTERNS.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # 对于有捕获组的模式，使用捕获组；否则使用整个匹配
                if match.lastindex and match.lastindex >= 1:
                    value = match.group(1)  # 使用第一个捕获组
                else:
                    value = match.group()

                # 使用(类型,值)元组去重
                entity_key = (entity_type, value)
                if entity_key in extracted_keys:
                    continue

                extracted_keys.add(entity_key)
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
                    entity_key = (entity.get("type"), entity.get("value"))
                    if entity_key not in extracted_keys:
                        extracted_keys.add(entity_key)
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
            "审批工单": ["work_order_id"],  # 只需要工单号，不要求action
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

        置信度计算规则（改进版）：
        - 基础分: 0.3（规则匹配起始点，表示最低可信度）
        - 一级意图模式命中: +0.35（核心意图识别贡献）
        - 二级意图关键词命中: +0.25（细化意图分类贡献）
        - 多模式匹配加成: 每额外命中一个模式+0.05（最高+0.1）
        - 文本特征修正: 基于特征完整性而非单纯长度

        置信度分级：
        - 0.9+: 高置信度（模式完全匹配）
        - 0.7-0.9: 中等置信度（基本模式匹配）
        - 0.5-0.7: 低置信度（部分匹配）
        - 0.5以下: 极低置信度（几乎无匹配）
        """
        confidence = 0.3  # 基础分：规则匹配的起始可信度

        # 一级意图模式匹配加分
        intent_info = self.INTENT_PATTERNS.get(intent_level_1, {})
        patterns = intent_info.get("patterns", [])
        matched_patterns = 0
        for pattern in patterns:
            if re.search(pattern, text.lower()):
                matched_patterns += 1

        # 首个模式命中给予主要分数
        if matched_patterns > 0:
            confidence += 0.35
            # 额外模式匹配给予加成（最高0.1）
            confidence += min(0.1, (matched_patterns - 1) * 0.05)

        # 二级意图关键词命中加分
        if intent_level_2 != "未知":
            confidence += 0.25

        # 文本特征修正（替代简单长度判断）
        # 考虑文本的信息密度：包含数字、特定关键词等
        text_lower = text.lower()
        feature_score = 0.0

        # 包含数字（如订单号、客户ID）增加可信度
        if re.search(r'\d+', text):
            feature_score += 0.05

        # 包含领域关键词增加可信度
        domain_keywords = ['订单', '客户', '物流', '产品', '工单', '审批', '查询', '状态']
        if any(kw in text_lower for kw in domain_keywords):
            feature_score += 0.05

        confidence += feature_score

        # 短文本惩罚（小于3个字符几乎无法准确识别意图）
        if len(text) < 3:
            confidence -= 0.15
        elif len(text) < 5:
            confidence -= 0.05

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
        # M30修复：使用局部变量确保类型安全
        llm = self.llm_client
        if not llm:
            return None

        try:
            print("🔄 使用LLM进行意图识别+实体提取")
            # 使用合并的prompt模板
            prompt = COMBINED_INTENT_ENTITY_PROMPT.replace("{user_input}", text)
            result = await llm.generate_json(prompt)

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
            # 审批工单只需要工单号，action由用户在查看分析建议后手动确认
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
            # action已移除，审批动作由用户在查看分析建议后手动确认
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
        from supply_chain_agent.common.protocols import get_slot_description

        if not missing_slots:
            return "请提供更多信息。"

        prompts = []
        for slot in missing_slots:
            description = get_slot_description(slot)
            prompts.append(f"请提供{description}")

        if len(prompts) == 1:
            return prompts[0]
        else:
            return "请提供以下信息：\n" + "\n".join(f"- {prompt}" for prompt in prompts)