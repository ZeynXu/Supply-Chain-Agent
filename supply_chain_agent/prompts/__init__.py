"""Prompt templates for LLM integration."""

from supply_chain_agent.prompts.intent import INTENT_CLASSIFICATION_PROMPT
from supply_chain_agent.prompts.entity import ENTITY_EXTRACTION_PROMPT
from supply_chain_agent.prompts.fallback import FALLBACK_RESPONSE_PROMPT

__all__ = [
    "INTENT_CLASSIFICATION_PROMPT",
    "ENTITY_EXTRACTION_PROMPT",
    "FALLBACK_RESPONSE_PROMPT",
]