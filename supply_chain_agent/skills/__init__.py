"""
Skill 模块

提供渐进式披露的上下文工程技术，用于指导 LLM 完成特定任务。
"""

from supply_chain_agent.skills.base import SkillLoader, SkillLoadError

__all__ = ["SkillLoader", "SkillLoadError"]
