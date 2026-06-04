"""ExecutorAgent Skill 集成测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestExecutorSkillIntegration:
    """ExecutorAgent Skill 集成测试"""

    @pytest.mark.asyncio
    async def test_generate_approval_plan_with_skill(self):
        """测试使用 skill 生成审批计划"""
        from supply_chain_agent.agents.executor import ExecutorAgent

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

        with patch.object(
            executor,
            "_get_llm_client_for_skill",
            return_value=mock_llm
        ):
            intent = {
                "intent_level_2": "审批工单",
                "entities": [{"type": "work_order_id", "value": "WO-0001"}]
            }

            result = await executor._generate_approval_plan_with_skill(intent)

            assert "query_work_order" in result
            assert "query_order" in result
            assert "query_customer_statistics" in result

    @pytest.mark.asyncio
    async def test_fallback_to_prompt_on_skill_error(self):
        """测试 skill 加载失败时降级到 prompt"""
        from supply_chain_agent.agents.executor import ExecutorAgent

        executor = ExecutorAgent()

        # Mock skill method to raise error
        with patch.object(
            executor,
            "_generate_approval_plan_with_skill",
            side_effect=Exception("Skill not found")
        ):
            with patch.object(
                executor,
                "_generate_approval_plan_with_prompt",
                return_value=["query_work_order", "query_order", "query_customer_statistics"]
            ) as mock_fallback:
                intent = {"intent_level_2": "审批工单", "entities": []}

                result = await executor._generate_approval_plan_with_llm(intent)

                mock_fallback.assert_called_once()
                assert len(result) == 3

    def test_get_llm_client_for_skill(self):
        """测试获取 LLM 客户端"""
        from supply_chain_agent.agents.executor import ExecutorAgent

        executor = ExecutorAgent()
        client = executor._get_llm_client_for_skill()

        assert client is not None