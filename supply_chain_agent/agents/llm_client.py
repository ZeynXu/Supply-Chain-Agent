"""
LLM Client for Supply Chain Agent.

Provides unified interface for different LLM providers:
- ZhipuAI (default, GLM-4.7)
- OpenAI-compatible APIs (custom models via llm_base_url)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import json
import httpx
import asyncio
import time


# 重试配置
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0  # 秒
_RETRY_MAX_DELAY = 10.0  # 秒
_REQUEST_TIMEOUT = 120.0  # 秒（增加超时时间，支持复杂分析任务）


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


def _calculate_retry_delay(attempt: int) -> float:
    """计算重试延迟（指数退避）"""
    delay = _RETRY_BASE_DELAY * (2 ** attempt)
    return min(delay, _RETRY_MAX_DELAY)


async def _execute_with_retry(
    func,
    *args,
    max_retries: int = _MAX_RETRIES,
    **kwargs
) -> Any:
    """
    带重试的执行函数

    Args:
        func: 要执行的异步函数
        max_retries: 最大重试次数
        *args, **kwargs: 函数参数

    Returns:
        函数执行结果

    Raises:
        Exception: 所有重试都失败后抛出最后一次异常
    """
    # M33修复：敏感信息脱敏函数
    def _sanitize_error_msg(msg: str) -> str:
        """脱敏错误消息中的敏感信息"""
        import re
        # 脱敏API密钥（匹配常见格式）
        msg = re.sub(r'(api[_-]?key["\s:=]+)["\']?[\w-]{20,}["\']?', r'\1[REDACTED]', msg, flags=re.IGNORECASE)
        # 脱敏Bearer token
        msg = re.sub(r'Bearer\s+[\w.-]+', 'Bearer [REDACTED]', msg)
        # 脱敏邮箱
        msg = re.sub(r'[\w.+-]+@[\w.-]+\.\w+', '[EMAIL REDACTED]', msg)
        return msg

    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.NetworkError) as e:
            last_error = e
            if attempt < max_retries:
                delay = _calculate_retry_delay(attempt)
                print(f"⚠️ LLM请求失败 (尝试 {attempt + 1}/{max_retries + 1}): {type(e).__name__}, {delay:.1f}秒后重试")
                await asyncio.sleep(delay)
            else:
                raise
        except httpx.HTTPStatusError as e:
            # 对于HTTP状态错误，某些情况不应重试
            if e.response.status_code in (400, 401, 403, 404, 422):
                # 客户端错误，不重试
                raise
            last_error = e
            if attempt < max_retries:
                delay = _calculate_retry_delay(attempt)
                print(f"⚠️ LLM HTTP错误 {e.response.status_code} (尝试 {attempt + 1}/{max_retries + 1}), {delay:.1f}秒后重试")
                await asyncio.sleep(delay)
            else:
                raise
        except Exception as e:
            # 其他异常不重试（M33：脱敏错误消息）
            error_msg = _sanitize_error_msg(str(e))
            raise type(e)(error_msg) from None

    raise last_error


class ZhipuClient(LLMClient):
    """智谱AI客户端（默认使用GLM-4.7）"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://open.bigmodel.cn/api/paas/v4",
        model: str = "glm-4.7",
        temperature: float = 0.7,
        max_tokens: int = 65536,
        thinking_enabled: bool = True  # 是否启用 thinking 模式
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.thinking_enabled = thinking_enabled

    async def _do_generate(self, prompt: str, json_mode: bool = False, max_tokens_override: int = None, thinking_override: bool = None) -> str:
        """实际执行HTTP请求（内部方法）"""
        json_prompt = prompt
        if json_mode:
            json_prompt = prompt + "\n\n请直接输出JSON格式的结果，不要包含其他文字说明。"

        # 使用覆盖参数或默认值
        actual_max_tokens = max_tokens_override if max_tokens_override is not None else self.max_tokens
        actual_thinking = thinking_override if thinking_override is not None else self.thinking_enabled

        request_body = {
            "model": self.model,
            "messages": [{"role": "user", "content": json_prompt}],
            "temperature": self.temperature,
            "max_tokens": actual_max_tokens,
        }
        if actual_thinking:
            request_body["thinking"] = {"type": "enabled"}

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": self.api_key
                },
                json=request_body
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def generate(self, prompt: str) -> str:
        """生成文本响应（带重试）"""
        return await _execute_with_retry(self._do_generate, prompt, json_mode=False)

    async def generate_json(self, prompt: str, schema: Optional[Dict] = None) -> Dict:
        """生成JSON格式响应（带重试）"""
        content = await _execute_with_retry(self._do_generate, prompt, json_mode=True)

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

    async def generate_json_fast(self, prompt: str, max_tokens: int = 1024) -> Dict:
        """
        快速生成JSON格式响应（优化版）

        用于简单的结构化输出任务，关闭 thinking 模式，减少 token 数量。

        Args:
            prompt: 输入 prompt
            max_tokens: 最大 token 数，默认 1024

        Returns:
            JSON 格式的响应

        Raises:
            json.JSONDecodeError: 如果输出被截断导致 JSON 解析失败
        """
        # 关闭 thinking 模式，减少 max_tokens
        content = await _execute_with_retry(
            self._do_generate, prompt,
            json_mode=True,
            max_tokens_override=max_tokens,
            thinking_override=False
        )

        # 尝试解析JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            # 检查是否可能是输出截断
            if len(content) >= max_tokens * 3:  # 粗略估计：1 token ≈ 3 chars
                print(f"⚠️ 输出可能被截断 (max_tokens={max_tokens}), 尝试增加限制重试...")
                # 尝试双倍 token 重试
                content = await _execute_with_retry(
                    self._do_generate, prompt,
                    json_mode=True,
                    max_tokens_override=max_tokens * 2,
                    thinking_override=False
                )
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    pass

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

    async def _do_generate(self, prompt: str, json_mode: bool = False) -> str:
        """实际执行HTTP请求（内部方法）"""
        request_body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        if json_mode:
            request_body["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=request_body
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def generate(self, prompt: str) -> str:
        """生成文本响应（带重试）"""
        return await _execute_with_retry(self._do_generate, prompt, json_mode=False)

    async def generate_json(self, prompt: str, schema: Optional[Dict] = None) -> Dict:
        """生成JSON格式响应（带重试）"""
        content = await _execute_with_retry(self._do_generate, prompt, json_mode=True)
        return json.loads(content)


# M23修复：LLM响应缓存
from functools import lru_cache
import hashlib

# LLM响应缓存（最多缓存100个不同的prompt）
# 注意：缓存键基于prompt内容的hash，避免内存泄漏
_LLM_CACHE_MAX_SIZE = 100


def _get_cache_key(prompt: str, json_mode: bool = False) -> str:
    """生成缓存键"""
    content = f"{prompt}:{json_mode}"
    return hashlib.md5(content.encode()).hexdigest()


class CachedLLMClient(LLMClient):
    """
    M23修复：带缓存的LLM客户端包装器

    对于相同的prompt，直接返回缓存结果，避免重复调用LLM。
    """

    def __init__(self, inner_client: LLMClient, cache_size: int = _LLM_CACHE_MAX_SIZE):
        self.inner = inner_client
        self._cache: Dict[str, str] = {}
        self._cache_order: List[str] = []  # LRU顺序
        self._cache_size = cache_size
        self._cache_hits = 0
        self._cache_misses = 0
        # Skill 支持
        try:
            from supply_chain_agent.skills.base import SkillLoader
            self._skill_loader = SkillLoader()
        except ImportError:
            self._skill_loader = None

    def _get_cached(self, key: str) -> Optional[str]:
        """从缓存获取"""
        if key in self._cache:
            # 更新LRU顺序
            self._cache_order.remove(key)
            self._cache_order.append(key)
            self._cache_hits += 1
            return self._cache[key]
        return None

    def _set_cached(self, key: str, value: str):
        """存入缓存"""
        if key in self._cache:
            self._cache_order.remove(key)
        self._cache[key] = value
        self._cache_order.append(key)
        # LRU淘汰
        while len(self._cache) > self._cache_size:
            oldest = self._cache_order.pop(0)
            del self._cache[oldest]

    async def generate(self, prompt: str) -> str:
        """生成文本响应（带缓存）"""
        key = _get_cache_key(prompt, json_mode=False)
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        result = await self.inner.generate(prompt)
        self._set_cached(key, result)
        self._cache_misses += 1
        return result

    async def generate_json(self, prompt: str, schema: Optional[Dict] = None) -> Dict:
        """生成JSON格式响应（带缓存）"""
        key = _get_cache_key(prompt, json_mode=True)
        cached = self._get_cached(key)
        if cached is not None:
            return json.loads(cached)
        result = await self.inner.generate_json(prompt, schema)
        self._set_cached(key, json.dumps(result, ensure_ascii=False))
        self._cache_misses += 1
        return result

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0
        return {
            "cache_size": len(self._cache),
            "max_size": self._cache_size,
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": hit_rate
        }

    def load_skill(self, skill_name: str) -> str:
        """
        加载 skill 内容

        Args:
            skill_name: skill 名称

        Returns:
            skill 文件内容

        Raises:
            RuntimeError: skill loader 未初始化
        """
        if self._skill_loader is None:
            raise RuntimeError("SkillLoader not initialized")
        return self._skill_loader.load_skill(skill_name)

    def _build_skill_prompt(
        self,
        skill_content: str,
        prompt: str,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        构建 skill 上下文 prompt

        Args:
            skill_content: skill 文件内容
            prompt: 用户 prompt
            additional_context: 额外上下文

        Returns:
            完整的 prompt
        """
        # 精简 prompt，只包含必要信息
        full_prompt = f"""## 流程指导

{skill_content}

## 任务

{prompt}

## 输出格式

直接输出工具名称列表的 JSON 数组，如：
["query_work_order", "query_order", "query_customer_statistics"]
"""
        if additional_context and len(additional_context) > 0:
            full_prompt += f"""
## 可用参数

{json.dumps(additional_context.get("entities", {}), ensure_ascii=False)}
"""
        return full_prompt

    async def generate_with_skill(
        self,
        prompt: str,
        skill_name: str,
        additional_context: Optional[Dict[str, Any]] = None,
        fast_mode: bool = True,
        max_tokens: int = 1024
    ) -> Dict:
        """
        带 skill 上下文生成响应

        Args:
            prompt: 用户 prompt
            skill_name: skill 名称
            additional_context: 额外上下文
            fast_mode: 是否使用快速模式（关闭 thinking，减少 token），默认 True
            max_tokens: 最大 token 数，默认 1024

        Returns:
            JSON 格式的响应
        """
        skill_content = self.load_skill(skill_name)
        full_prompt = self._build_skill_prompt(skill_content, prompt, additional_context)

        if fast_mode and hasattr(self.inner, 'generate_json_fast'):
            # 使用快速生成模式
            return await self.inner.generate_json_fast(full_prompt, max_tokens=max_tokens)
        else:
            return await self.generate_json(full_prompt)


# 单例实例
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """工厂方法：根据配置创建客户端（单例模式，带缓存）"""
    global _llm_client

    if _llm_client is not None:
        return _llm_client

    from supply_chain_agent.config import settings

    if not settings.llm_api_key:
        raise ValueError("LLM API key not configured. Set SCA_LLM_API_KEY environment variable.")

    # 创建底层客户端
    inner_client: LLMClient
    if settings.llm_provider == "zhipu":
        inner_client = ZhipuClient(
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
        inner_client = OpenAIClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens
        )
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}. Supported: zhipu, openai")

    # M23修复：包装为带缓存的客户端
    _llm_client = CachedLLMClient(inner_client)

    return _llm_client


def reset_llm_client():
    """重置LLM客户端单例（用于测试）"""
    global _llm_client
    _llm_client = None


def reload_llm_client() -> LLMClient:
    """
    M36修复：重新加载LLM客户端（支持配置热更新）

    强制重新读取配置并创建新的LLM客户端实例。
    用于不重启服务的情况下切换模型或更新API密钥。

    Returns:
        新的LLMClient实例
    """
    global _llm_client
    _llm_client = None
    print("[LLMClient] 配置已重新加载，创建新客户端实例")
    return get_llm_client()


def update_llm_config(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None
) -> LLMClient:
    """
    M36修复：更新LLM配置并重新创建客户端

    Args:
        api_key: 新的API密钥（可选）
        model: 新的模型名称（可选）
        provider: 新的提供商（可选）
        base_url: 新的API地址（可选）
        temperature: 新的温度参数（可选）
        max_tokens: 新的最大token数（可选）

    Returns:
        更新后的LLMClient实例
    """
    from supply_chain_agent.config import settings

    # 更新settings中的配置
    if api_key is not None:
        settings.llm_api_key = api_key
    if model is not None:
        settings.llm_model = model
    if provider is not None:
        settings.llm_provider = provider
    if base_url is not None:
        settings.llm_base_url = base_url
    if temperature is not None:
        settings.llm_temperature = temperature
    if max_tokens is not None:
        settings.llm_max_tokens = max_tokens

    # 重新创建客户端
    return reload_llm_client()
