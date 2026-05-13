#!/usr/bin/env python3
"""
Comprehensive test runner for Supply Chain Agent.

Runs all tests and generates evaluation reports.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supply_chain_agent.tests.test_agents import main as test_agents
from supply_chain_agent.tests.evaluation import run_evaluation


async def run_all_tests():
    """Run all tests."""
    print("🔧 Supply Chain Agent - 综合测试套件")
    print("=" * 60)

    # Run agent tests
    print("\n1. 运行Agent单元测试...")
    try:
        await test_agents()
    except Exception as e:
        print(f"⚠️ Agent测试失败: {e}")

    # Run evaluation
    print("\n2. 运行系统评估...")
    try:
        report = await run_evaluation()

        # Check if meets PRD requirements
        overall_score = report["summary"]["overall_score"]
        targets_met = report["summary"]["targets_met"]

        print(f"\n📈 PRD符合度评估:")
        print(f"   总体得分: {overall_score:.1%}")
        print(f"   目标达成: {targets_met}")
        print(f"   评估结果: {report['summary']['assessment']}")

        if overall_score >= 0.65:
            print("✅ 系统符合PRD Phase 1要求，可以进入下一阶段")
        else:
            print("⚠️  系统未完全达到PRD Phase 1要求，需要优化")

    except Exception as e:
        print(f"❌ 评估失败: {e}")

    print("\n" + "=" * 60)
    print("测试套件运行完成!")
    print("=" * 60)


def main():
    """Main entry point."""
    # Check if we should run with MCP server
    run_with_server = len(sys.argv) > 1 and sys.argv[1] == "with-server"

    if run_with_server:
        print("启动MCP服务器并运行测试...")
        import subprocess
        import time

        # Start MCP server in background
        server_process = subprocess.Popen(
            [sys.executable, "-m", "supply_chain_agent.tools", "server"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for server to start
        time.sleep(3)

        try:
            # Run tests
            asyncio.run(run_all_tests())
        finally:
            # Kill server
            server_process.terminate()
            server_process.wait()
    else:
        # Run tests only (assume MCP server is running)
        asyncio.run(run_all_tests())


if __name__ == "__main__":
    main()