#!/usr/bin/env python3
"""
Test script for Supply Chain Agent system.
"""

import asyncio
import sys
import os

import pytest

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supply_chain_agent.agents.orchestrator import OrchestratorAgent
from supply_chain_agent.agents.parser import ParserAgent
from supply_chain_agent.agents.executor import ExecutorAgent
from supply_chain_agent.agents.auditor import AuditorAgent
from supply_chain_agent.agents.report_generator import ReportGenerator
from supply_chain_agent.tests.test_mcp import test_tools


@pytest.mark.asyncio
async def test_parser_agent():
    """Test Parser Agent."""
    print("\n" + "="*60)
    print("测试 Parser Agent (解析师)")
    print("="*60)

    parser = ParserAgent()

    test_cases = [
        "查一下PO-2026-001的货到哪了？",
        "订单PO-2026-002状态怎么样？",
        "帮我审批工单WO-2026-001",
        "创建质量检验工单",
        "报告物流异常"
    ]

    for test_input in test_cases:
        print(f"\n输入: {test_input}")
        try:
            intent = await parser.parse_intent(test_input)
            validation = await parser.validate_intent(intent)

            print(f"  一级意图: {intent.get('intent_level_1')}")
            print(f"  二级意图: {intent.get('intent_level_2')}")
            print(f"  置信度: {intent.get('confidence'):.2f}")
            print(f"  实体: {[e.get('type') for e in intent.get('entities', [])]}")
            print(f"  验证结果: {'通过' if validation['valid'] else '失败'}")
            if validation['issues']:
                print(f"  问题: {validation['issues']}")

        except Exception as e:
            print(f"  错误: {e}")


@pytest.mark.asyncio
async def test_executor_agent():
    """Test Executor Agent."""
    print("\n" + "="*60)
    print("测试 Executor Agent (调度员)")
    print("="*60)

    executor = ExecutorAgent()

    # Test execution plan creation
    test_intent = {
        "intent_level_1": "状态查询",
        "intent_level_2": "物流查询",
        "entities": [
            {"type": "order_id", "value": "PO-2026-001"}
        ]
    }

    print("\n测试执行计划创建:")
    try:
        tasks = await executor.create_execution_plan(test_intent)
        print(f"  生成的执行计划: {tasks}")

        # Test task execution
        print("\n测试任务执行:")
        for task in tasks:
            print(f"  执行任务: {task}")
            try:
                result = await executor.execute_task(task, {"order_id": "PO-2026-001"})
                print(f"    结果: {result.get('order_id', 'N/A') if task == 'query_order_status' else result.get('tracking_no', 'N/A')}")
                print(f"    状态: {result.get('status', 'N/A')}")
            except Exception as e:
                print(f"    错误: {e}")

    except Exception as e:
        print(f"  错误: {e}")

    # Test execution summary
    print("\n执行摘要:")
    summary = executor.get_execution_summary()
    print(f"  总任务数: {summary['total_tasks']}")
    print(f"  成功率: {summary['success_rate']:.2%}")


@pytest.mark.asyncio
async def test_auditor_agent():
    """Test Auditor Agent."""
    print("\n" + "="*60)
    print("测试 Auditor Agent (审计员)")
    print("="*60)

    auditor = AuditorAgent()

    # Test with sample tool results
    tool_results = {
        "query_order_status": {
            "order_id": "PO-2026-001",
            "status": "已发货",
            "amount": 12500.0,
            "supplier": "XX科技",
            "tracking_no": "SF1234567890"
        },
        "get_logistics_trace": {
            "tracking_no": "SF1234567890",
            "status": "运输中",
            "current_location": "厦门中转场",
            "eta": "2026-04-23"
        }
    }

    print("\n测试结果审计:")
    try:
        audit_result = await auditor.audit_results(tool_results)
        print(f"  审计通过: {'是' if audit_result['passed'] else '否'}")
        print(f"  问题数量: {audit_result['issue_count']}")
        print(f"  警告数量: {audit_result['warning_count']}")

        if audit_result['issues']:
            print(f"  问题列表:")
            for issue in audit_result['issues']:
                print(f"    - {issue}")

        if audit_result['warnings']:
            print(f"  警告列表:")
            for warning in audit_result['warnings']:
                print(f"    - {warning}")

    except Exception as e:
        print(f"  错误: {e}")

    # Test risk score
    print("\n测试风险评分:")
    try:
        risk_score = await auditor.get_risk_score(tool_results)
        print(f"  风险评分: {risk_score:.2f}")

        audit_summary = auditor.get_audit_summary()
        print(f"  审计通过率: {audit_summary['pass_rate']:.2%}")

    except Exception as e:
        print(f"  错误: {e}")


@pytest.mark.asyncio
async def test_orchestrator_agent():
    """Test Orchestrator Agent."""
    print("\n" + "="*60)
    print("测试 Orchestrator Agent (总控)")
    print("="*60)

    orchestrator = OrchestratorAgent()

    test_cases = [
        "查一下PO-2026-001的货到哪了？",
        "订单PO-2026-002状态",
        "帮我审批WO-2026-001，理由：质量合格"
    ]

    for test_input in test_cases:
        print(f"\n输入: {test_input}")
        try:
            response = await orchestrator.process(test_input)
            print(f"响应:\n{response}")
            print("-" * 40)

        except Exception as e:
            print(f"错误: {e}")


@pytest.mark.asyncio
async def test_full_workflow():
    """Test the complete workflow."""
    print("\n" + "="*60)
    print("测试完整工作流")
    print("="*60)

    from supply_chain_agent.graph.workflow import workflow

    test_input = "查一下PO-2026-001的物流状态"

    print(f"\n输入: {test_input}")
    try:
        final_state = await workflow.process(test_input)

        print(f"\n最终状态摘要:")
        state_summary = {
            "has_intent": bool(final_state.get("user_intent")),
            "intent_type": final_state.get("user_intent", {}).get("intent_level_1", "unknown"),
            "tool_results_count": len(final_state.get("tool_results", {})),
            "audit_passed": final_state.get("audit_results", {}).get("passed", False),
            "error_count": final_state.get("error_count", 0),
            "has_final_report": final_state.get("final_report") is not None,
            "has_response_card": final_state.get("response_card") is not None
        }

        for key, value in state_summary.items():
            print(f"  {key}: {value}")

        # Show conversation
        messages = final_state.get("messages", [])
        print(f"\n对话记录 ({len(messages)} 条消息):")
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:100] + "..." if len(msg.get("content", "")) > 100 else msg.get("content", "")
            print(f"  {role}: {content}")

    except Exception as e:
        print(f"工作流错误: {e}")


async def main():
    """Run all tests."""
    print("Supply Chain Agent - 系统测试")
    print("="*60)

    # First test MCP tools
    print("\n1. 测试 MCP 工具...")
    try:
        await test_tools()
    except Exception as e:
        print(f"MCP工具测试失败: {e}")
        print("请先启动MCP服务器: python -m supply_chain_agent.tools.test_mcp server")

    # Test individual agents
    await test_parser_agent()
    await test_executor_agent()
    await test_auditor_agent()

    # Test orchestrator (requires MCP server)
    try:
        await test_orchestrator_agent()
    except Exception as e:
        print(f"\nOrchestrator测试失败（可能需要MCP服务器）: {e}")

    # Test full workflow
    try:
        await test_full_workflow()
    except Exception as e:
        print(f"\n完整工作流测试失败: {e}")

    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)


if __name__ == "__main__":
    # Check if MCP server should be started
    if len(sys.argv) > 1 and sys.argv[1] == "with-server":
        print("启动MCP服务器并运行测试...")
        import subprocess
        import time

        # Start MCP server in background
        server_process = subprocess.Popen(
            [sys.executable, "-m", "supply_chain_agent.tools.test_mcp", "server"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for server to start
        time.sleep(3)

        try:
            # Run tests
            asyncio.run(main())
        finally:
            # Kill server
            server_process.terminate()
            server_process.wait()
    else:
        # Run tests only
        asyncio.run(main())


# === LLM Integration Tests ===

class TestLLMIntegration:
    """Integration tests for LLM features."""

    @pytest.mark.asyncio
    async def test_fuzzy_intent_recognition(self):
        """Test that fuzzy input is handled by LLM or fallback."""
        from supply_chain_agent.agents.parser import ParserAgent

        parser = ParserAgent()

        # 模糊输入
        result = await parser.parse_intent("帮我看看那个货到哪了")

        # 应该能识别为状态查询
        assert result["intent_level_1"] == "状态查询"

    @pytest.mark.asyncio
    async def test_fallback_no_fake_data(self):
        """Test that fallback response does not contain fake data."""
        from supply_chain_agent.tools.client import ToolClient

        client = ToolClient()

        # 模拟失败场景
        result = await client._fallback_response(
            user_input="查询订单PO-9999-999",
            intent_info={"intent_level_1": "状态查询", "intent_level_2": "订单状态查询"},
            error="Connection refused"
        )

        # 验证不包含假数据字段
        assert result.get("fallback") == True
        assert result.get("data_available") == False
        assert "message" in result  # 应该有提示消息
        # 不应该有假数据
        assert result.get("amount") is None
        assert result.get("supplier") is None