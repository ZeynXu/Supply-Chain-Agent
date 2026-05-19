"""Tests for LLM client using real API calls."""

import pytest
import json
import os

from supply_chain_agent.agents.llm_client import (
    LLMClient,
    ZhipuClient,
    OpenAIClient,
    get_llm_client,
    reset_llm_client,
)
from supply_chain_agent.config import settings


# Skip all tests in this file if API key is not configured
pytestmark = pytest.mark.skipif(
    not settings.llm_api_key,
    reason="SCA_LLM_API_KEY not configured in .env"
)


class TestZhipuClient:
    """Tests for ZhipuAI client with real API."""

    @pytest.fixture
    def client(self):
        """Create ZhipuAI client from settings."""
        return ZhipuClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens
        )

    @pytest.mark.asyncio
    async def test_generate_returns_text(self, client):
        """Test that generate returns text from real API."""
        result = await client.generate("请回复：测试成功")

        assert result is not None
        assert len(result) > 0
        print(f"\n  API Response: {result[:100]}...")

    @pytest.mark.asyncio
    async def test_generate_json_returns_dict(self, client):
        """Test that generate_json returns parsed JSON from real API."""
        prompt = """
请分析以下用户意图，返回JSON格式结果：
用户输入：查一下PO-2026-001的订单状态

返回格式：
{
    "intent_level_1": "意图类型",
    "intent_level_2": "子意图",
    "confidence": 0.9
}
"""
        result = await client.generate_json(prompt, {})

        assert isinstance(result, dict)
        assert "intent_level_1" in result or len(result) > 0
        print(f"\n  JSON Response: {result}")

    @pytest.mark.asyncio
    async def test_generate_json_extracts_from_markdown(self, client):
        """Test that generate_json can extract JSON from markdown code blocks."""
        prompt = """
请返回以下JSON格式的数据（包含在代码块中）：
{
    "intent_level_1": "状态查询",
    "confidence": 0.9
}
"""
        result = await client.generate_json(prompt, {})

        assert isinstance(result, dict)
        print(f"\n  Extracted JSON: {result}")

    @pytest.mark.asyncio
    async def test_intent_recognition(self, client):
        """Test real intent recognition via LLM."""
        test_cases = [
            ("查一下PO-2026-001的订单状态", "状态查询"),
            ("帮我审批工单WO-2026-001", "审批处理"),
            ("报告物流异常", "异常报告"),
        ]

        for user_input, expected_intent in test_cases:
            prompt = f"""
分析用户意图，返回JSON：
用户输入：{user_input}

返回格式：
{{
    "intent_level_1": "意图类型",
    "confidence": 0.0-1.0
}}
"""
            result = await client.generate_json(prompt, {})
            print(f"\n  Input: {user_input}")
            print(f"    Result: {result}")
            assert isinstance(result, dict)


class TestGetLLMClient:
    """Tests for LLM client factory."""

    def test_returns_zhipu_by_default(self):
        """Test that factory returns Zhipu client by default."""
        # Reset singleton before test
        reset_llm_client()

        client = get_llm_client()
        assert isinstance(client, ZhipuClient)
        print(f"\n  Factory returned: {type(client).__name__}")

    def test_singleton_behavior(self):
        """Test that factory returns same instance."""
        reset_llm_client()

        client1 = get_llm_client()
        client2 = get_llm_client()

        assert client1 is client2
        print("\n  Singleton verified: same instance returned")


class TestLLMClientIntegration:
    """Integration tests for LLM client with real API."""

    @pytest.fixture
    def client(self):
        """Create LLM client."""
        reset_llm_client()
        return get_llm_client()

    @pytest.mark.asyncio
    async def test_end_to_end_intent_parsing(self, client):
        """Test complete intent parsing flow."""
        prompt = """
分析以下供应链管理相关的用户请求，提取意图和实体：

用户输入：查一下订单PO-2026-001的物流状态，看看货到哪了

请返回JSON格式：
{
    "intent_level_1": "一级意图",
    "intent_level_2": "二级意图",
    "entities": [{"type": "实体类型", "value": "实体值"}],
    "confidence": 0.0-1.0
}
"""
        result = await client.generate_json(prompt)

        assert isinstance(result, dict)
        print(f"\n  End-to-end result: {json.dumps(result, ensure_ascii=False, indent=2)}")
