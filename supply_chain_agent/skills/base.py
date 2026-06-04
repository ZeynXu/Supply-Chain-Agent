"""
Skill 基础设施

提供 Skill 加载和解析功能。
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path


class SkillLoadError(Exception):
    """Skill 加载异常"""
    pass


class SkillLoader:
    """
    Skill 加载器

    负责加载和解析 skill 文件，支持缓存机制。
    """

    def __init__(self, skills_dir: Optional[str] = None):
        """
        初始化 SkillLoader

        Args:
            skills_dir: skill 目录路径，默认为 supply_chain_agent/skills
        """
        if skills_dir is None:
            # 默认使用 supply_chain_agent/skills 目录
            self.skills_dir = Path(__file__).parent
        else:
            self.skills_dir = Path(skills_dir)

        # 缓存
        self._cache: Dict[str, str] = {}
        self._cache_stats = {"hits": 0, "misses": 0}

    def load_skill(self, skill_name: str) -> str:
        """
        加载 skill 主文件内容

        Args:
            skill_name: skill 名称（目录名）

        Returns:
            skill 文件内容

        Raises:
            SkillLoadError: skill 不存在或读取失败
        """
        cache_key = f"skill:{skill_name}"

        # 检查缓存
        if cache_key in self._cache:
            self._cache_stats["hits"] += 1
            return self._cache[cache_key]

        # 构建文件路径
        skill_path = self.skills_dir / skill_name / "SKILL.md"

        if not skill_path.exists():
            raise SkillLoadError(f"Skill not found: {skill_name} (path: {skill_path})")

        try:
            content = skill_path.read_text(encoding="utf-8")
            # 存入缓存
            self._cache[cache_key] = content
            self._cache_stats["misses"] += 1
            return content
        except Exception as e:
            raise SkillLoadError(f"Failed to load skill {skill_name}: {e}")

    def load_procedure(self, skill_name: str, procedure_name: str) -> str:
        """
        加载子流程文件

        Args:
            skill_name: skill 名称
            procedure_name: 子流程名称（不含 .md 后缀）

        Returns:
            子流程文件内容

        Raises:
            SkillLoadError: 子流程不存在或读取失败
        """
        cache_key = f"proc:{skill_name}:{procedure_name}"

        # 检查缓存
        if cache_key in self._cache:
            self._cache_stats["hits"] += 1
            return self._cache[cache_key]

        # 构建文件路径
        proc_path = self.skills_dir / skill_name / "procedures" / f"{procedure_name}.md"

        if not proc_path.exists():
            raise SkillLoadError(
                f"Procedure not found: {procedure_name} in skill {skill_name}"
            )

        try:
            content = proc_path.read_text(encoding="utf-8")
            # 存入缓存
            self._cache[cache_key] = content
            self._cache_stats["misses"] += 1
            return content
        except Exception as e:
            raise SkillLoadError(
                f"Failed to load procedure {procedure_name} in skill {skill_name}: {e}"
            )

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            "hits": self._cache_stats["hits"],
            "misses": self._cache_stats["misses"],
            "size": len(self._cache),
            "hit_rate": (
                self._cache_stats["hits"] /
                (self._cache_stats["hits"] + self._cache_stats["misses"])
                if (self._cache_stats["hits"] + self._cache_stats["misses"]) > 0
                else 0.0
            )
        }

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._cache_stats = {"hits": 0, "misses": 0}

    def skill_exists(self, skill_name: str) -> bool:
        """检查 skill 是否存在"""
        skill_path = self.skills_dir / skill_name / "SKILL.md"
        return skill_path.exists()
