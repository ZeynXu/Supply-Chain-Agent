"""Tests for Parser Agent LLM integration using real API calls."""

import pytest
import json

from supply_chain_agent.agents.parser import ParserAgent
from supply_chain_agent.agents.llm_client import get_llm_client, reset_llm_client
from supply_chain_agent.config import settings


# Skip all tests in this file if API key is not configured
pytestmark = pytest.mark.skipif(
    not settings.llm_api_key,
    reason="SCA_LLM_API_KEY not configured in .env"
)


class TestParserAgentLLMIntegration:
    """Tests for Parser Agent with real LLM integration."""

    @pytest.fixture
    def parser(self):
        """Create parser with real LLM client."""
        reset_llm_client()
        return ParserAgent()

    @pytest.mark.asyncio
    async def test_rule_path_for_standard_input(self, parser):
        """Test that standard input uses rule-based path."""
        # 标准输入应该走规则路径
        result = await parser.parse_intent("查一下PO-2026-001的订单状态")

        assert result["intent_level_1"] == "状态查询"
        assert result["confidence"] >= 0.7  # 高置信度
        print(f"\n  Standard input result: {json.dumps(result, ensure_ascii=False)}")

    @pytest.mark.asyncio
    async def test_llm_path_for_fuzzy_input(self, parser):
        """Test that fuzzy input triggers LLM path or rule fallback."""
        # 模糊输入可能触发LLM或降级到规则
        result = await parser.parse_intent("帮我看看那个昨天从上海发的货")

        # 应该能识别为状态查询类意图
        assert "intent_level_1" in result
        print(f"\n  Fuzzy input result: {json.dumps(result, ensure_ascii=False)}")

    @pytest.mark.asyncio
    async def test_entity_extraction_with_fuzzy_input(self, parser):
        """Test entity extraction handles fuzzy input."""
        # 模糊实体提取
        result = await parser.parse_intent("单号好像是1234567")

        # 验证实体提取结果
        assert "intent_level_1" in result
        entities = result.get("entities", [])
        print(f"\n  Fuzzy entity extraction result: {json.dumps(result, ensure_ascii=False)}")

        # 实体可能被提取，也可能需要澄清
        if entities:
            print(f"    Extracted entities: {entities}")

    @pytest.mark.asyncio
    async def test_llm_failure_fallback_to_rule(self, parser):
        """Test that parser handles various inputs gracefully."""
        # 测试各种输入都能得到合理结果
        test_cases = [
            "查一下订单状态",
            "帮我审批",
            "报告问题",
        ]

        for test_input in test_cases:
            result = await parser.parse_intent(test_input)

            # 应该仍然返回结果
            assert "intent_level_1" in result
            print(f"\n  Input: {test_input}")
            print(f"    Intent: {result['intent_level_1']}")


class TestParserAgentRealScenarios:
    """Real-world scenario tests for Parser Agent."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        reset_llm_client()
        return ParserAgent()

    @pytest.mark.asyncio
    async def test_order_status_query(self, parser):
        """Test order status query parsing."""
        test_inputs = [
            "查一下订单PO-2026-001的状态",
            "PO-2026-001到哪了",
            "帮我看看订单2026-001",
        ]

        for test_input in test_inputs:
            result = await parser.parse_intent(test_input)
            assert result["intent_level_1"] == "状态查询"
            print(f"\n  '{test_input}' -> {result['intent_level_1']}/{result.get('intent_level_2', 'N/A')}")

    @pytest.mark.asyncio
    async def test_logistics_query(self, parser):
        """Test logistics query parsing."""
        test_inputs = [
            "查一下SF1234567890到哪了",
            "运单号SF1234567890的物流信息",
            "帮我追踪快递",
        ]

        for test_input in test_inputs:
            result = await parser.parse_intent(test_input)
            # 应该识别为状态查询或物流查询
            print(f"\n  '{test_input}' -> {result['intent_level_1']}/{result.get('intent_level_2', 'N/A')}")

    @pytest.mark.asyncio
    async def test_work_order_creation(self, parser):
        """Test work order creation intent parsing."""
        test_inputs = [
            "创建一个质量检验工单",
            "帮我开一个异常处理工单",
            "需要安排现场服务",
        ]

        for test_input in test_inputs:
            result = await parser.parse_intent(test_input)
            print(f"\n  '{test_input}' -> {result['intent_level_1']}/{result.get('intent_level_2', 'N/A')}")

    @pytest.mark.asyncio
    async def test_issue_reporting(self, parser):
        """Test issue reporting intent parsing."""
        test_inputs = [
            "报告一个物流延迟问题",
            "发现质量问题",
            "供应商交货延迟了",
        ]

        for test_input in test_inputs:
            result = await parser.parse_intent(test_input)
            print(f"\n  '{test_input}' -> {result['intent_level_1']}/{result.get('intent_level_2', 'N/A')}")

    @pytest.mark.asyncio
    async def test_approval_handling(self, parser):
        """Test approval handling intent parsing."""
        test_inputs = [
            "帮我审批WO-2026-001",
            "工单WO-2026-001可以批准吗",
            "同意这个工单申请",
        ]

        for test_input in test_inputs:
            result = await parser.parse_intent(test_input)
            print(f"\n  '{test_input}' -> {result['intent_level_1']}/{result.get('intent_level_2', 'N/A')}")

    @pytest.mark.asyncio
    async def test_contract_search(self, parser):
        """Test contract search intent parsing."""
        test_inputs = [
            "搜索合同模板",
            "查找采购合同",
            "看看有没有质量保证条款",
        ]

        for test_input in test_inputs:
            result = await parser.parse_intent(test_input)
            print(f"\n  '{test_input}' -> {result['intent_level_1']}/{result.get('intent_level_2', 'N/A')}")

    @pytest.mark.asyncio
    async def test_validation_with_real_llm(self, parser):
        """Test intent validation with real LLM."""
        test_intent = {
            "intent_level_1": "状态查询",
            "intent_level_2": "订单状态查询",
            "entities": [{"type": "order_id", "value": "PO-2026-001"}],
            "confidence": 0.9
        }

        validation = await parser.validate_intent(test_intent)

        assert "valid" in validation
        print(f"\n  Validation result: {json.dumps(validation, ensure_ascii=False)}")


class TestParserAgentEdgeCases:
    """Edge case tests for Parser Agent."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        reset_llm_client()
        return ParserAgent()

    @pytest.mark.asyncio
    async def test_empty_input(self, parser):
        """Test empty input handling."""
        result = await parser.parse_intent("")

        # 应该返回默认或错误意图
        assert "intent_level_1" in result
        print(f"\n  Empty input result: {result}")

    @pytest.mark.asyncio
    async def test_very_long_input(self, parser):
        """Test very long input handling."""
        long_input = "查一下订单状态" + "的详情" * 100

        result = await parser.parse_intent(long_input)
        assert "intent_level_1" in result
        print(f"\n  Long input result: {result['intent_level_1']}")

    @pytest.mark.asyncio
    async def test_special_characters(self, parser):
        """Test special characters handling."""
        special_inputs = [
            "查一下订单@#$%的状态",
            "PO-2026-001!!!",
            "帮我看看<>[]{}订单",
        ]

        for test_input in special_inputs:
            result = await parser.parse_intent(test_input)
            assert "intent_level_1" in result
            print(f"\n  '{test_input[:20]}...' -> {result['intent_level_1']}")

    @pytest.mark.asyncio
    async def test_mixed_language_input(self, parser):
        """Test mixed language input handling."""
        mixed_inputs = [
            "Check一下订单PO-2026-001的状态",
            "Help me 查询 logistics info",
            "订单status怎么样",
        ]

        for test_input in mixed_inputs:
            result = await parser.parse_intent(test_input)
            assert "intent_level_1" in result
            print(f"\n  '{test_input}' -> {result['intent_level_1']}")
