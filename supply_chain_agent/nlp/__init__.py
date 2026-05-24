"""
NLP Module for Supply Chain Agent.

Provides natural language processing capabilities:
- BERT-based Named Entity Recognition
- Entity extraction for Chinese text
"""

from supply_chain_agent.nlp.bert_ner import (
    BertNERModel,
    Entity,
    get_ner_model,
    extract_entities,
    BERT_MODEL_PATH,
)

__all__ = [
    "BertNERModel",
    "Entity",
    "get_ner_model",
    "extract_entities",
    "BERT_MODEL_PATH",
]
