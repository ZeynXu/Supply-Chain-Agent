# tests/test_approval_workflow_skill_integration.py
"""审批工单 Skill 集成测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestApprovalWorkflowSkillIntegration:
    """审批工单 Skill 集成测试"""

    @pytest.mark.asyncio
    async def test_full_approval_workflow_with_skill(self):
        """测试完整的审批工单流程（使用 skill）"""
        from supply_chain_agent.agents.executor import ExecutorAgent
        from supply_chain_agent.config import settings

        # 确保启用 skill 模式
        assert settings.use_skill_for_approval is True

        executor = ExecutorAgent()

        # Mock LLM client
        mock_llm = MagicMock()
        mock_llm.generate_with_skill = AsyncMock(return_value={
            "tasks": [
                {"name": "查询工单", "tool": "query_work_order"},
                {"name": "查询订单", "tool": "query_order"},
                {"name": "查询客户统计", "tool": "query_customer_statistics"}
            ]
        })

        with patch.object(executor, "_get_llm_client_for_skill", return_value=mock_llm):
            intent = {
                "intent_level_1": "工单管理",
                "intent_level_2": "审批工单",
                "entities": [
                    {"type": "work_order_id", "value": "WO-0001"},
                    {"type": "action", "value": "approve"}
                ]
            }

            plan = await executor.create_execution_plan(intent)

            assert "query_work_order" in plan
            assert "query_order" in plan
            assert "query_customer_statistics" in plan

    @pytest.mark.asyncio
    async def test_skill_fallback_on_missing_skill(self):
        """测试 skill 不存在时的降级"""
        from supply_chain_agent.agents.executor import ExecutorAgent
        from supply_chain_agent.skills.base import SkillLoadError

        executor = ExecutorAgent()

        # Mock skill method to fail
        with patch.object(
            executor,
            "_generate_approval_plan_with_skill",
            side_effect=SkillLoadError("Skill not found")
        ):
            with patch.object(
                executor,
                "_generate_approval_plan_with_prompt",
                return_value=["query_work_order", "query_order", "query_customer_statistics"]
            ):
                intent = {
                    "intent_level_2": "审批工单",
                    "entities": []
                }

                plan = await executor._generate_approval_plan_with_llm(intent)

                assert len(plan) == 3

    def test_skill_loader_can_load_approval_workflow(self):
        """测试 SkillLoader 可以加载 approval_workflow skill"""
        from supply_chain_agent.skills.base import SkillLoader

        loader = SkillLoader()

        # 检查 skill 是否存在
        assert loader.skill_exists("approval_workflow"), \
            "approval_workflow skill should exist"

        # 加载 skill
        content = loader.load_skill("approval_workflow")

        assert "审批工单流程" in content
        assert "query_work_order" in content
        assert "query_order" in content
        assert "query_customer_statistics" in content

    def test_config_skill_settings(self):
        """测试 skill 配置项"""
        from supply_chain_agent.config import settings

        assert hasattr(settings, "use_skill_for_approval")
        assert hasattr(settings, "skill_fallback_to_prompt")
        assert settings.use_skill_for_approval is True
        assert settings.skill_fallback_to_prompt is True

    def test_llm_client_has_skill_methods(self):
        """测试 LLMClient 有 skill 相关方法"""
        from supply_chain_agent.agents.llm_client import CachedLLMClient

        # 检查方法存在
        assert hasattr(CachedLLMClient, "load_skill")
        assert hasattr(CachedLLMClient, "generate_with_skill")
        assert hasattr(CachedLLMClient, "_build_skill_prompt")