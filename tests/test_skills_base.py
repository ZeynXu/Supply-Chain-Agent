"""Skill 基础设施测试"""
import pytest
import os
import tempfile
from supply_chain_agent.skills.base import SkillLoader, SkillLoadError


class TestSkillLoader:
    """SkillLoader 测试"""

    def test_load_skill_success(self, tmp_path):
        """测试成功加载 skill"""
        # 创建临时 skill 目录
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-skill
description: Test skill
---
# Test Skill
Content here.
""")

        loader = SkillLoader(skills_dir=str(tmp_path))
        content = loader.load_skill("test_skill")

        assert "Test Skill" in content
        assert "Content here." in content

    def test_load_skill_not_found(self, tmp_path):
        """测试 skill 不存在时抛出异常"""
        loader = SkillLoader(skills_dir=str(tmp_path))

        with pytest.raises(SkillLoadError):
            loader.load_skill("nonexistent")

    def test_load_skill_cached(self, tmp_path):
        """测试 skill 缓存"""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("# Test Skill")

        loader = SkillLoader(skills_dir=str(tmp_path))

        # 第一次加载
        content1 = loader.load_skill("test_skill")
        # 第二次加载（应从缓存）
        content2 = loader.load_skill("test_skill")

        assert content1 == content2
        assert loader.get_cache_stats()["hits"] == 1

    def test_load_procedure_success(self, tmp_path):
        """测试成功加载子流程"""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        proc_dir = skill_dir / "procedures"
        proc_dir.mkdir()
        proc_file = proc_dir / "test_proc.md"
        proc_file.write_text("# Test Procedure")

        loader = SkillLoader(skills_dir=str(tmp_path))
        content = loader.load_procedure("test_skill", "test_proc")

        assert "Test Procedure" in content

    def test_load_procedure_not_found(self, tmp_path):
        """测试子流程不存在时抛出异常"""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        # 不创建 procedures 目录

        loader = SkillLoader(skills_dir=str(tmp_path))

        with pytest.raises(SkillLoadError):
            loader.load_procedure("test_skill", "nonexistent_proc")

    def test_cache_stats(self, tmp_path):
        """测试缓存统计"""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("# Test Skill")

        loader = SkillLoader(skills_dir=str(tmp_path))

        # 初始状态
        stats = loader.get_cache_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["size"] == 0
        assert stats["hit_rate"] == 0.0

        # 加载一次
        loader.load_skill("test_skill")
        stats = loader.get_cache_stats()
        assert stats["misses"] == 1
        assert stats["size"] == 1

        # 再次加载（命中缓存）
        loader.load_skill("test_skill")
        stats = loader.get_cache_stats()
        assert stats["hits"] == 1
        assert stats["hit_rate"] == 0.5

    def test_clear_cache(self, tmp_path):
        """测试清空缓存"""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("# Test Skill")

        loader = SkillLoader(skills_dir=str(tmp_path))
        loader.load_skill("test_skill")

        # 清空缓存
        loader.clear_cache()
        stats = loader.get_cache_stats()

        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["size"] == 0

    def test_skill_exists(self, tmp_path):
        """测试检查 skill 是否存在"""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("# Test Skill")

        loader = SkillLoader(skills_dir=str(tmp_path))

        assert loader.skill_exists("test_skill") is True
        assert loader.skill_exists("nonexistent") is False

    def test_default_skills_dir(self):
        """测试默认 skills 目录"""
        loader = SkillLoader()
        # 默认目录应该是 supply_chain_agent/skills
        assert "skills" in str(loader.skills_dir)
