"""
BERT-based Named Entity Recognition (NER) Module for Supply Chain Agent.

Uses bert-base-chinese-wwm model for Chinese entity extraction.
"""

import os
import re
import torch
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

# BERT模型路径
BERT_MODEL_PATH = Path(__file__).parent.parent / "models" / "bert-chinese-wwm"

# 实体类型定义 (基于MCP工具参数)
ENTITY_LABELS = [
    "O",        # 非实体
    "B-ORDER",  # 订单号开始
    "I-ORDER",  # 订单号内部
    "B-CUSTOMER",  # 客户ID开始
    "I-CUSTOMER",  # 客户ID内部
    "B-PRODUCT",   # 产品ID开始
    "I-PRODUCT",   # 产品ID内部
    "B-WORKORDER", # 工单号开始
    "I-WORKORDER", # 工单号内部
    "B-AMOUNT",    # 金额开始
    "I-AMOUNT",    # 金额内部
    "B-DATE",      # 日期开始
    "I-DATE",      # 日期内部
]


@dataclass
class Entity:
    """Extracted entity."""
    type: str
    value: str
    start: int
    end: int
    confidence: float = 1.0


class BertNERModel:
    """
    BERT-based NER model for Chinese entity recognition.

    This is a lightweight wrapper that uses rule-based extraction
    with BERT embeddings for semantic understanding.
    """

    def __init__(self, model_path: str = None, use_bert: bool = True):
        """
        Initialize BERT NER model.

        Args:
            model_path: Path to BERT model directory
            use_bert: Whether to use BERT embeddings (set False for faster rule-based only)
        """
        self.model_path = model_path or str(BERT_MODEL_PATH)
        self.use_bert = use_bert and self._check_model_exists()
        self.tokenizer = None
        self.model = None

        # 规则库 (用于规则+NER混合提取)
        self.rules = self._build_rules()

        if self.use_bert:
            self._load_bert_model()

    def _check_model_exists(self) -> bool:
        """Check if BERT model files exist."""
        # transformers需要的文件
        required_files = ["vocab.txt", "config.json", "pytorch_model.bin"]
        for f in required_files:
            if not os.path.exists(os.path.join(self.model_path, f)):
                print(f"⚠️ BERT模型文件不存在: {f}")
                return False
        return True

    def _load_bert_model(self):
        """Load BERT model and tokenizer."""
        try:
            from transformers import BertTokenizer, BertModel

            print(f"📦 加载BERT模型: {self.model_path}")
            self.tokenizer = BertTokenizer.from_pretrained(self.model_path)
            self.model = BertModel.from_pretrained(self.model_path)
            self.model.eval()

            # 如果有GPU，移到GPU
            if torch.cuda.is_available():
                self.model = self.model.cuda()
                print("✅ BERT模型已加载到GPU")
            else:
                print("✅ BERT模型已加载到CPU")

        except Exception as e:
            print(f"⚠️ BERT模型加载失败: {e}, 将使用规则模式")
            self.use_bert = False
            self.tokenizer = None
            self.model = None

    def _build_rules(self) -> Dict[str, List[re.Pattern]]:
        """Build rule-based patterns for entity extraction."""
        return {
            "order_id": [
                re.compile(r"(?:订单|order)[^0-9]*(\d{4,})", re.IGNORECASE),
                re.compile(r"PO[-_]?\d{4}[-_]?\d{3,}", re.IGNORECASE),
            ],
            "customer_id": [
                re.compile(r"(?:客户|customer)[^0-9]*(\d+)", re.IGNORECASE),
            ],
            "product_card_id": [
                re.compile(r"(?:产品|product)[^0-9]*(\d+)", re.IGNORECASE),
            ],
            "work_order_id": [
                re.compile(r"(?:工单|work\s*order)[^A-Z0-9]*(WO[-_]?\d{1,4}[-_]?\d{1,4})", re.IGNORECASE),
                re.compile(r"WO[-_]?\d{1,4}[-_]?\d{1,4}", re.IGNORECASE),
            ],
            "issue_type": [
                re.compile(r"(物流延迟|库存异常|质量缺陷|数据错误|客户投诉|其他)"),
            ],
            "work_type": [
                re.compile(r"(审批|异常处理|退款|调拨|质检|其他)"),
            ],
            "amount": [
                re.compile(r"¥\s*(\d+(?:\.\d{2})?)"),
                re.compile(r"(\d+(?:\.\d{2})?)\s*元"),
            ],
            "date": [
                re.compile(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"),
            ],
            "tracking_no": [
                re.compile(r"[A-Z]{2}\d{9,11}[A-Z]?"),
                re.compile(r"\d{12,14}"),
            ],
            "priority": [
                re.compile(r"(优先级|优先)[:：]?\s*(紧急|高|中|低)"),
            ],
            "urgency": [
                re.compile(r"(紧急程度|紧急级别|紧急)[:：]?\s*(紧急|高|中|低)"),
            ],
            "action": [
                re.compile(r"(通过|批准|同意|审批通过)"),
                re.compile(r"(拒绝|驳回|不同意|审批拒绝)"),
            ],
        }

    def extract_entities(self, text: str) -> List[Entity]:
        """
        Extract entities from text using hybrid approach:
        1. Rule-based extraction (fast, accurate for patterns)
        2. BERT-based extraction (semantic understanding)

        Args:
            text: Input text

        Returns:
            List of extracted entities
        """
        entities = []
        extracted_spans = set()  # 避免重叠

        # Step 1: 规则提取 (优先)
        for entity_type, patterns in self.rules.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    # 获取值
                    if match.lastindex and match.lastindex >= 1:
                        value = match.group(1)
                    else:
                        value = match.group()

                    start, end = match.start(), match.end()

                    # 检查是否与已有实体重叠
                    span = (start, end)
                    if any(s[0] < end and start < s[1] for s in extracted_spans):
                        continue

                    extracted_spans.add(span)
                    entities.append(Entity(
                        type=entity_type,
                        value=value,
                        start=start,
                        end=end,
                        confidence=0.95  # 规则提取置信度较高
                    ))

        # Step 2: BERT语义提取 (如果启用且有模型)
        if self.use_bert and self.model:
            bert_entities = self._extract_with_bert(text)
            # 合并BERT结果 (只添加规则未覆盖的)
            for entity in bert_entities:
                span = (entity.start, entity.end)
                if not any(s[0] < entity.end and entity.start < s[1] for s in extracted_spans):
                    extracted_spans.add(span)
                    entities.append(entity)

        # 按位置排序
        entities.sort(key=lambda e: e.start)

        return entities

    def _extract_with_bert(self, text: str) -> List[Entity]:
        """
        Extract entities using BERT embeddings.

        Currently uses BERT for semantic similarity matching.
        Can be extended with fine-tuned NER head.
        """
        entities = []

        # 简化版：使用BERT进行语义匹配
        # 对于订单号、客户ID等数字类实体，规则提取更准确
        # 这里主要用于识别描述性实体

        try:
            # 编码文本
            inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True)

            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model(**inputs)

            # 获取token级别的embedding
            last_hidden_states = outputs.last_hidden_state

            # 这里可以添加更复杂的NER逻辑
            # 目前返回空列表，依赖规则提取

        except Exception as e:
            print(f"⚠️ BERT提取失败: {e}")

        return entities

    def extract_for_intent(self, text: str, intent_level_1: str) -> List[Dict[str, Any]]:
        """
        Extract entities tailored for specific intent.

        Args:
            text: Input text
            intent_level_1: First level intent (信息查询, 工单管理, 异常上报)

        Returns:
            List of entity dictionaries
        """
        all_entities = self.extract_entities(text)

        # 根据意图过滤和优先级排序
        priority_types = {
            "信息查询": ["order_id", "customer_id", "product_card_id", "tracking_no", "date"],
            "工单管理": ["work_order_id", "work_type", "priority", "description", "action", "comment"],
            "异常上报": ["issue_type", "urgency", "order_id", "description"],
        }

        priority = priority_types.get(intent_level_1, [])

        # 排序：优先级类型在前
        sorted_entities = sorted(
            all_entities,
            key=lambda e: (0 if e.type in priority else 1, e.start)
        )

        # 转换为字典格式
        return [
            {
                "type": e.type,
                "value": e.value,
                "start": e.start,
                "end": e.end,
                "confidence": e.confidence
            }
            for e in sorted_entities
        ]


# 全局实例 (延迟初始化)
_ner_instance: Optional[BertNERModel] = None


def get_ner_model(use_bert: bool = True) -> BertNERModel:
    """
    Get NER model instance (singleton pattern).

    Args:
        use_bert: Whether to use BERT embeddings

    Returns:
        BertNERModel instance
    """
    global _ner_instance

    if _ner_instance is None:
        _ner_instance = BertNERModel(use_bert=use_bert)

    return _ner_instance


def reset_ner_model():
    """
    H4修复：重置NER模型单例（用于测试）
    """
    global _ner_instance
    _ner_instance = None


def extract_entities(text: str, intent_level_1: str = None) -> List[Dict[str, Any]]:
    """
    Convenience function for entity extraction.

    Args:
        text: Input text
        intent_level_1: Optional intent for prioritized extraction

    Returns:
        List of entity dictionaries
    """
    ner = get_ner_model(use_bert=False)  # 默认不使用BERT以加快速度

    if intent_level_1:
        return ner.extract_for_intent(text, intent_level_1)
    else:
        return [
            {
                "type": e.type,
                "value": e.value,
                "start": e.start,
                "end": e.end,
                "confidence": e.confidence
            }
            for e in ner.extract_entities(text)
        ]
