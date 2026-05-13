"""
LLM Client for Supply Chain Agent.

Provides unified interface for different LLM providers:
- ZhipuAI (default, GLM-4.7)
- OpenAI-compatible APIs (custom models via llm_base_url)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json
import httpx


class LLMClient(ABC):
    """LLM客户端抽象基类"""

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """生成文本响应"""
        pass

    @abstractmethod
    async def generate_json(self, prompt: str, schema: Optional[Dict] = None) -> Dict:
        """生成JSON格式响应"""
        pass


class ZhipuClient(LLMClient):
    """智谱AI客户端（默认使用GLM-4.7）"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://open.bigmodel.cn/api/paas/v4",
        model: str = "glm-4.7",
        temperature: float = 0.7,
        max_tokens: int = 65536
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def generate(self, prompt: str) -> str:
        """生成文本响应"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": self.api_key
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "thinking": {"type": "enabled"}
                }
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def generate_json(self, prompt: str, schema: Optional[Dict] = None) -> Dict:
        """生成JSON格式响应"""
        # 在prompt中明确要求JSON输出
        json_prompt = prompt + "\n\n请直接输出JSON格式的结果，不要包含其他文字说明。"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": self.api_key
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": json_prompt}],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "thinking": {"type": "enabled"}
                }
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]

            # 尝试解析JSON，可能需要从markdown代码块中提取
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # 尝试从markdown代码块中提取
                if "```json" in content:
                    start = content.find("```json") + 7
                    end = content.find("```", start)
                    if end > start:
                        return json.loads(content[start:end].strip())
                elif "```" in content:
                    start = content.find("```") + 3
                    end = content.find("```", start)
                    if end > start:
                        return json.loads(content[start:end].strip())
                raise


class OpenAIClient(LLMClient):
    """OpenAI兼容客户端（用于自定义模型）"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 65536
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def generate(self, prompt: str) -> str:
        """生成文本响应"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens
                }
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def generate_json(self, prompt: str, schema: Optional[Dict] = None) -> Dict:
        """生成JSON格式响应"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "response_format": {"type": "json_object"}
                }
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)


# 单例实例
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """工厂方法：根据配置创建客户端（单例模式）"""
    global _llm_client

    if _llm_client is not None:
        return _llm_client

    from supply_chain_agent.config import settings

    if not settings.llm_api_key:
        raise ValueError("LLM API key not configured. Set SCA_LLM_API_KEY environment variable.")

    if settings.llm_provider == "zhipu":
        _llm_client = ZhipuClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens
        )
    elif settings.llm_provider == "openai":
        if not settings.llm_base_url:
            raise ValueError("llm_base_url must be configured for OpenAI provider")
        if not settings.llm_model:
            raise ValueError("llm_model must be configured for OpenAI provider")
        _llm_client = OpenAIClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens
        )
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}. Supported: zhipu, openai")

    return _llm_client


def reset_llm_client():
    """重置LLM客户端单例（用于测试）"""
    global _llm_client
    _llm_client = None
