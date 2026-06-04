"""LLMClient Skill 扩展测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestLLMClientSkillExtension:
    """LLMClient Skill 扩展测试"""

    def test_load_skill_success(self):
        """测试成功加载 skill"""
        from supply_chain_agent.agents.llm_client import CachedLLMClient
        from unittest.mock import MagicMock

        # 创建 mock 内部客户端
        mock_inner = MagicMock()
        client = CachedLLMClient(mock_inner)

        # 验证 skill loader 已初始化
        assert client._skill_loader is not None

    def test_load_skill_returns_content(self):
        """测试加载 skill 返回内容"""
        from supply_chain_agent.agents.llm_client import CachedLLMClient
        from unittest.mock import MagicMock

        mock_inner = MagicMock()
        client = CachedLLMClient(mock_inner)

        # 加载实际存在的 skill
        content = client.load_skill("approval_workflow")
        assert "审批工单流程" in content

    def test_build_skill_prompt(self):
        """测试构建 skill prompt"""
        from supply_chain_agent.agents.llm_client import CachedLLMClient
        from unittest.mock import MagicMock

        mock_inner = MagicMock()
        client = CachedLLMClient(mock_inner)

        skill_content = "# Test Skill\n\n## Steps\n1. Step one"
        prompt = "Generate plan"
        additional_context = {"entities": {"work_order_id": "WO-001"}}

        result = client._build_skill_prompt(skill_content, prompt, additional_context)

        assert "Test Skill" in result
        assert "Generate plan" in result
        assert "WO-001" in result

    @pytest.mark.asyncio
    async def test_generate_with_skill(self):
        """测试带 skill 上下文生成"""
        from supply_chain_agent.agents.llm_client import CachedLLMClient
        from unittest.mock import MagicMock, AsyncMock

        mock_inner = MagicMock()
        mock_inner.generate_json = AsyncMock(return_value={"tasks": [{"tool": "query_work_order"}]})
        client = CachedLLMClient(mock_inner)

        result = await client.generate_with_skill(
            prompt="Generate plan",
            skill_name="approval_workflow",
            additional_context={"entities": {}}
        )

        assert "tasks" in result