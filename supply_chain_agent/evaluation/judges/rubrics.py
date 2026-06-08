"""
LLM Judge评分标准

定义各维度的评分标准和Prompt模板。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class DimensionRubric:
    """单维度评分标准"""
    name: str
    description: str
    scale: Dict[int, str]  # 评分等级描述
    weight: float = 1.0

    def get_prompt(self) -> str:
        """获取评分Prompt"""
        scale_text = "\n".join([f"   - {k}分：{v}" for k, v in sorted(self.scale.items())])
        return f"""**{self.name}**：{self.description}
{scale_text}"""


@dataclass
class JudgeRubric:
    """LLM Judge评分标准"""
    helpfulness: DimensionRubric
    clarity: DimensionRubric
    faithfulness: DimensionRubric

    def get_full_prompt(self) -> str:
        """获取完整评分Prompt"""
        prompts = [
            self.helpfulness.get_prompt(),
            self.clarity.get_prompt(),
            self.faithfulness.get_prompt()
        ]
        return "\n\n".join(prompts)


def get_default_rubric() -> JudgeRubric:
    """获取默认评分标准"""
    helpfulness = DimensionRubric(
        name="帮助性（Helpfulness）",
        description="响应是否有效解决了用户的问题？",
        scale={
            5: "完全解决，提供了用户需要的所有信息",
            4: "基本解决，有小遗漏",
            3: "部分解决，需要补充信息",
            2: "帮助有限，信息不完整或有误",
            1: "无帮助，答非所问"
        },
        weight=1.0
    )

    clarity = DimensionRubric(
        name="清晰度（Clarity）",
        description="响应是否清晰易懂？",
        scale={
            5: "非常清晰，结构良好，语言准确",
            4: "基本清晰，有小的表达问题",
            3: "一般，需要仔细阅读才能理解",
            2: "不够清晰，表达混乱",
            1: "非常混乱，难以理解"
        },
        weight=1.0
    )

    faithfulness = DimensionRubric(
        name="忠实度（Faithfulness）",
        description="响应是否基于事实，无幻觉？",
        scale={
            5: "完全基于事实，准确无误",
            4: "基本准确，有小的表述问题",
            3: "大部分准确，有个别不准确处",
            2: "存在明显的幻觉或不准确信息",
            1: "大量幻觉或虚构信息"
        },
        weight=1.0
    )

    return JudgeRubric(
        helpfulness=helpfulness,
        clarity=clarity,
        faithfulness=faithfulness
    )


def get_supply_chain_rubric() -> JudgeRubric:
    """获取供应链场景专用评分标准"""
    helpfulness = DimensionRubric(
        name="帮助性（Helpfulness）",
        description="响应是否有效解决了供应链场景下的问题？",
        scale={
            5: "完全解决，提供了准确的订单/客户/物流信息，满足业务需求",
            4: "基本解决，信息基本准确，有小遗漏",
            3: "部分解决，信息不够完整或需要进一步查询",
            2: "帮助有限，信息不完整、有误或不够具体",
            1: "无帮助，答非所问或提供错误信息"
        },
        weight=1.0
    )

    clarity = DimensionRubric(
        name="清晰度（Clarity）",
        description="响应是否结构清晰、表达准确？",
        scale={
            5: "非常清晰，信息组织有序，关键数据突出",
            4: "基本清晰，结构合理",
            3: "一般，信息呈现不够直观",
            2: "不够清晰，信息分散或混乱",
            1: "非常混乱，难以理解"
        },
        weight=1.0
    )

    faithfulness = DimensionRubric(
        name="忠实度（Faithfulness）",
        description="响应是否基于真实数据，无虚构？",
        scale={
            5: "完全基于查询结果，数据准确无误",
            4: "基本准确，查询结果呈现正确",
            3: "大部分准确，有少量推断或表述偏差",
            2: "存在明显的数据错误或虚构",
            1: "大量虚构订单号、客户信息等"
        },
        weight=1.0
    )

    return JudgeRubric(
        helpfulness=helpfulness,
        clarity=clarity,
        faithfulness=faithfulness
    )


# 默认Prompt模板
DEFAULT_JUDGE_PROMPT = """你是一个专业的AI助手评估专家。请评估以下Agent响应的质量。

用户查询：
{user_query}

Agent响应：
{agent_response}

{context_section}

请从以下三个维度评分（1-5分）：

{rubrics}

请以JSON格式输出（不要输出其他内容）：
{{
    "helpfulness": <1-5>,
    "clarity": <1-5>,
    "faithfulness": <1-5>,
    "reasoning": "<评分理由，简明扼要>",
    "confidence": <0-1，表示评分置信度>
}}
"""


# 简化Prompt（用于快速评分）
SIMPLIFIED_JUDGE_PROMPT = """评估以下AI响应的质量。

用户问题：{user_query}
AI回复：{agent_response}

评分（1-5分）：
- 帮助性：响应是否解决问题
- 清晰度：表达是否清晰
- 忠实度：是否基于事实

仅输出JSON：{"helpfulness": <1-5>, "clarity": <1-5>, "faithfulness": <1-5>, "reasoning": "<理由>", "confidence": <0-1>}
"""
