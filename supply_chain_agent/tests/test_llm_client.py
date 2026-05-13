"""Tests for LLM client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from supply_chain_agent.agents.llm_client import (
    LLMClient,
    ZhipuClient,
    OpenAIClient,
    get_llm_client,
    reset_llm_client,
)


class TestZhipuClient:
    """Tests for ZhipuAI client."""

    @pytest.mark.asyncio
    async def test_generate_returns_text(self):
        """Test that generate returns text from API response."""
        client = ZhipuClient(api_key="test-key", base_url="https://api.test.com/v4")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "测试响应"}}]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await client.generate("测试prompt")

        assert result == "测试响应"

    @pytest.mark.asyncio
    async def test_generate_json_returns_dict(self):
        """Test that generate_json returns parsed JSON."""
        client = ZhipuClient(api_key="test-key", base_url="https://api.test.com/v4")

        expected_json = {"intent_level_1": "状态查询", "confidence": 0.9}
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps(expected_json)}}]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await client.generate_json("测试prompt", {})

        assert result == expected_json

    @pytest.mark.asyncio
    async def test_generate_json_extracts_from_markdown(self):
        """Test that generate_json can extract JSON from markdown code blocks."""
        client = ZhipuClient(api_key="test-key", base_url="https://api.test.com/v4")

        expected_json = {"intent_level_1": "状态查询", "confidence": 0.9}
        markdown_response = f"```json\n{json.dumps(expected_json)}\n```"
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": markdown_response}}]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await client.generate_json("测试prompt", {})

        assert result == expected_json


class TestOpenAIClient:
    """Tests for OpenAI-compatible client."""

    @pytest.mark.asyncio
    async def test_generate_returns_text(self):
        """Test that generate returns text from API response."""
        client = OpenAIClient(
            api_key="test-key",
            base_url="https://api.custom.com/v1",
            model="custom-model"
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "测试响应"}}]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await client.generate("测试prompt")

        assert result == "测试响应"


class TestGetLLMClient:
    """Tests for LLM client factory."""

    def test_returns_zhipu_by_default(self, monkeypatch):
        """Test that factory returns Zhipu client by default."""
        from supply_chain_agent.config import Settings

        mock_settings = Settings()
        mock_settings.llm_provider = "zhipu"
        mock_settings.llm_api_key = "test-key"
        mock_settings.llm_base_url = "https://open.bigmodel.cn/api/paas/v4"
        mock_settings.llm_model = "glm-4.7"
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 65536

        # Reset singleton before test
        reset_llm_client()

        # Patch the config module's settings import
        monkeypatch.setattr("supply_chain_agent.config.settings", mock_settings)

        client = get_llm_client()
        assert isinstance(client, ZhipuClient)

    def test_returns_openai_when_configured(self, monkeypatch):
        """Test that factory returns OpenAI client when configured."""
        from supply_chain_agent.config import Settings

        mock_settings = Settings()
        mock_settings.llm_provider = "openai"
        mock_settings.llm_api_key = "test-key"
        mock_settings.llm_base_url = "https://api.custom.com/v1"
        mock_settings.llm_model = "gpt-4"
        mock_settings.llm_temperature = 0.7
        mock_settings.llm_max_tokens = 4096

        # Reset singleton before test
        reset_llm_client()

        # Patch the config module's settings import
        monkeypatch.setattr("supply_chain_agent.config.settings", mock_settings)

        client = get_llm_client()
        assert isinstance(client, OpenAIClient)
