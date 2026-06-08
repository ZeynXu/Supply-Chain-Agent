"""
LLM Judge评分器

使用LLM对Agent输出进行主观质量评分。
支持多种LLM Provider（智谱、OpenAI、Anthropic）。
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional

from ..config import LLMJudgeConfig
from ..core.base import QualityScore, EvalContext
from .rubrics import (
    JudgeRubric,
    get_default_rubric,
    get_supply_chain_rubric,
    DEFAULT_JUDGE_PROMPT,
    SIMPLIFIED_JUDGE_PROMPT
)

logger = logging.getLogger(__name__)


class LLMJudge:
    """
    LLM Judge评分器

    对Agent输出的主观质量维度（帮助性、清晰度、忠实度）进行自动化评分。
    """

    def __init__(
        self,
        config: Optional[LLMJudgeConfig] = None,
        rubric: Optional[JudgeRubric] = None
    ):
        """
        初始化

        Args:
            config: LLM Judge配置
            rubric: 评分标准
        """
        self.config = config or LLMJudgeConfig()
        self.rubric = rubric or get_supply_chain_rubric()
        self._client = None

    @property
    def client(self):
        """延迟初始化LLM客户端"""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _create_client(self):
        """创建LLM客户端"""
        provider = self.config.provider.lower()

        if provider == "zhipu":
            return self._create_zhipu_client()
        elif provider == "openai":
            return self._create_openai_client()
        elif provider == "anthropic":
            return self._create_anthropic_client()
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    def _create_zhipu_client(self):
        """创建智谱AI客户端"""
        try:
            from zhipuai import ZhipuAI
            return ZhipuAI(api_key=self.config.api_key)
        except ImportError:
            logger.warning("zhipuai not installed, using mock mode")
            return None

    def _create_openai_client(self):
        """创建OpenAI客户端"""
        try:
            import openai
            return openai.AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url
            )
        except ImportError:
            logger.warning("openai not installed, using mock mode")
            return None

    def _create_anthropic_client(self):
        """创建Anthropic客户端"""
        try:
            import anthropic
            return anthropic.AsyncAnthropic(api_key=self.config.api_key)
        except ImportError:
            logger.warning("anthropic not installed, using mock mode")
            return None

    async def score(
        self,
        user_query: str,
        agent_response: str,
        context: Optional[EvalContext] = None,
        use_simplified: bool = False
    ) -> QualityScore:
        """
        评分主入口

        Args:
            user_query: 用户查询
            agent_response: Agent响应
            context: 评估上下文（可选，用于忠实度评估）
            use_simplified: 是否使用简化Prompt

        Returns:
            QualityScore: 质量评分结果
        """
        if not agent_response or len(agent_response.strip()) < 5:
            return QualityScore(
                helpfulness=1.0,
                clarity=1.0,
                faithfulness=1.0,
                reasoning="响应内容过短或为空",
                confidence=0.5
            )

        prompt = self._build_judge_prompt(user_query, agent_response, context, use_simplified)

        try:
            response = await self._call_llm(prompt)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"LLM Judge failed: {e}")
            return self._get_fallback_score(str(e))

    def _build_judge_prompt(
        self,
        user_query: str,
        agent_response: str,
        context: Optional[EvalContext],
        use_simplified: bool
    ) -> str:
        """构建评分Prompt"""
        if use_simplified:
            return SIMPLIFIED_JUDGE_PROMPT.format(
                user_query=user_query,
                agent_response=agent_response
            )

        # 构建上下文部分
        context_section = ""
        if context:
            context_parts = []
            if context.intent:
                intent_str = f"意图：{context.intent.get('intent_level_1', '')}/{context.intent.get('intent_level_2', '')}"
                context_parts.append(intent_str)
            if context.tool_calls:
                tools = [tc.get("tool_name", "") for tc in context.tool_calls]
                context_parts.append(f"调用的工具：{', '.join(tools)}")
            if context_parts:
                context_section = "**上下文信息：**\n" + "\n".join(context_parts)

        return DEFAULT_JUDGE_PROMPT.format(
            user_query=user_query,
            agent_response=agent_response,
            context_section=context_section,
            rubrics=self.rubric.get_full_prompt()
        )

    async def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        provider = self.config.provider.lower()

        if provider == "zhipu":
            return await self._call_zhipu(prompt)
        elif provider == "openai":
            return await self._call_openai(prompt)
        elif provider == "anthropic":
            return await self._call_anthropic(prompt)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    async def _call_zhipu(self, prompt: str) -> str:
        """调用智谱AI"""
        if self.client is None:
            return self._mock_response()

        try:
            # 智谱API是同步的，用run_in_executor包装
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens
                )
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Zhipu API call failed: {e}")
            raise

    async def _call_openai(self, prompt: str) -> str:
        """调用OpenAI"""
        if self.client is None:
            return self._mock_response()

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise

    async def _call_anthropic(self, prompt: str) -> str:
        """调用Anthropic"""
        if self.client is None:
            return self._mock_response()

        try:
            response = await self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            raise

    def _mock_response(self) -> str:
        """返回模拟响应（用于测试）"""
        return json.dumps({
            "helpfulness": 4.0,
            "clarity": 4.0,
            "faithfulness": 4.0,
            "reasoning": "Mock response for testing",
            "confidence": 0.8
        })

    def _parse_response(self, response: str) -> QualityScore:
        """解析LLM响应"""
        try:
            # 尝试提取JSON
            json_str = self._extract_json(response)
            data = json.loads(json_str)

            return QualityScore(
                helpfulness=float(data.get("helpfulness", 3.0)),
                clarity=float(data.get("clarity", 3.0)),
                faithfulness=float(data.get("faithfulness", 3.0)),
                reasoning=str(data.get("reasoning", "")),
                confidence=float(data.get("confidence", 0.5))
            )
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return self._get_fallback_score(f"JSON解析失败: {response[:100]}")
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return self._get_fallback_score(str(e))

    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON"""
        # 尝试直接解析
        text = text.strip()
        if text.startswith("{"):
            return text

        # 尝试提取代码块中的JSON
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        # 尝试找到第一个{和最后一个}
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return text[start:end+1]

        return text

    def _get_fallback_score(self, reason: str) -> QualityScore:
        """获取降级评分"""
        return QualityScore(
            helpfulness=3.0,
            clarity=3.0,
            faithfulness=3.0,
            reasoning=f"评分降级: {reason}",
            confidence=0.3
        )

    async def score_batch(
        self,
        samples: list[Dict[str, str]],
        use_simplified: bool = True
    ) -> list[QualityScore]:
        """
        批量评分

        Args:
            samples: 样本列表，每个样本包含 user_query 和 agent_response
            use_simplified: 是否使用简化Prompt

        Returns:
            评分结果列表
        """
        results = []
        for sample in samples:
            score = await self.score(
                sample.get("user_query", ""),
                sample.get("agent_response", ""),
                use_simplified=use_simplified
            )
            results.append(score)
        return results
