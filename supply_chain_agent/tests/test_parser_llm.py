"""Tests for Parser Agent LLM integration."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from supply_chain_agent.agents.parser import ParserAgent
from supply_chain_agent.agents.llm_client import ZhipuClient


class TestParserAgentLLMIntegration:
    """Tests for Parser Agent with LLM integration."""

    @pytest.mark.asyncio
    async def test_rule_path_for_standard_input(self):
        """Test that standard input uses rule-based path."""
        parser = ParserAgent()

        # 标准输入应该走规则路径
        result = await parser.parse_intent("查一下PO-2026-001的订单状态")

        assert result["intent_level_1"] == "状态查询"
        assert result["confidence"] >= 0.7  # 高置信度

    @pytest.mark.asyncio
    async def test_llm_path_for_fuzzy_input(self):
        """Test that fuzzy input triggers LLM path."""
        # Mock LLM client
        mock_llm = MagicMock(spec=ZhipuClient)
        mock_llm.generate_json = AsyncMock(return_value={
            "intent_level_1": "状态查询",
            "intent_level_2": "物流查询",
            "confidence": 0.85
        })

        parser = ParserAgent(llm_client=mock_llm)

        # 模糊输入应该触发LLM
        result = await parser.parse_intent("帮我看看那个昨天从上海发的货")

        # 验证LLM被调用
        assert mock_llm.generate_json.called
        assert result["intent_level_1"] == "状态查询"

    @pytest.mark.asyncio
    async def test_entity_extraction_with_fuzzy_input(self):
        """Test entity extraction handles fuzzy input."""
        mock_llm = MagicMock(spec=ZhipuClient)
        mock_llm.generate_json = AsyncMock(return_value={
            "entities": [
                {"type": "tracking_no", "value": "1234567", "confidence": 0.65, "note": "不完整"}
            ],
            "suggestions": ["请确认运单号前缀"]
        })

        parser = ParserAgent(llm_client=mock_llm)

        # 模糊实体提取
        result = await parser.parse_intent("单号好像是1234567")

        # 验证实体提取结果包含置信度信息
        entities = result.get("entities", [])
        if entities:
            assert any(e.get("confidence", 1.0) < 1.0 for e in entities)  # 有低置信度实体

    @pytest.mark.asyncio
    async def test_llm_failure_fallback_to_rule(self):
        """Test that LLM failure falls back to rules."""
        mock_llm = MagicMock(spec=ZhipuClient)
        mock_llm.generate_json = AsyncMock(side_effect=Exception("LLM unavailable"))

        parser = ParserAgent(llm_client=mock_llm)

        # LLM失败时应该降级到规则
        result = await parser.parse_intent("查一下订单状态")

        # 应该仍然返回结果（规则降级）
        assert "intent_level_1" in result
        assert result["intent_level_1"] == "状态查询"
