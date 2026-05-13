#!/usr/bin/env python3
"""
Supply Chain Agent - Project Runner

This script provides easy access to all project components.
"""

import sys
import os
import argparse


def print_banner():
    """Print project banner."""
    banner = """
╔══════════════════════════════════════════════════════════╗
║      🤖 智能供应链工单处理Agent系统                      ║
║      L3级自主Agent | 协作副驾驶 | 多智能体协作           ║
╚══════════════════════════════════════════════════════════╝

📋 项目特性:
  • 四Agent星型拓扑架构 (总控+解析+调度+审计)
  • 三级记忆系统 (短期+工作+长期)
  • MCP工具集成与熔断机制
  • LangGraph工作流编排
  • 四维评估体系 (效果/效率/体验/稳定性)

🛠️  可用命令:
  run-api        启动REST API (FastAPI)
  run-mcp        启动MCP工具服务器
  run-cli        启动命令行界面
  test           运行测试套件
  test-with-mcp  运行测试套件 (带MCP服务器)
  eval           运行系统评估

📁 项目结构:
  agents/         Agent定义 (总控/解析/调度/审计)
  tools/          MCP工具实现
  graph/          LangGraph工作流
  memory/         记忆系统 (向量库+SQLite)
  tests/          测试套件
    """
    print(banner)


def run_api():
    """Run REST API."""
    print("🚀 启动REST API (FastAPI)...")
    os.system("python -m supply_chain_agent.app")


def run_mcp():
    """Run MCP server."""
    print("🚀 启动MCP工具服务器...")
    os.system("python -m supply_chain_agent.tools.server")


def run_cli():
    """Run CLI interface."""
    print("🚀 启动命令行界面...")
    os.system("python -m supply_chain_agent --mode cli")


def run_tests(with_server=False):
    """Run tests."""
    if with_server:
        print("🧪 运行测试套件 (带MCP服务器)...")
        os.system("python -m supply_chain_agent.tests.run_all_tests with-server")
    else:
        print("🧪 运行测试套件...")
        os.system("python -m supply_chain_agent.tests.run_all_tests")


def run_evaluation():
    """Run evaluation."""
    print("📊 运行系统评估...")
    os.system("python -m supply_chain_agent.tests.evaluation")


def check_dependencies():
    """Check if dependencies are installed."""
    print("🔍 检查依赖...")
    try:
        import fastapi
        import langgraph
        import chromadb
        print("✅ 所有依赖已安装")
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return False
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Supply Chain Agent System",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "command",
        choices=[
            "api", "mcp", "cli", "test",
            "test-with-mcp", "eval", "help"
        ],
        help="要执行的命令"
    )

    args = parser.parse_args()

    # Print banner
    print_banner()

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Execute command
    if args.command == "api":
        run_api()
    elif args.command == "mcp":
        run_mcp()
    elif args.command == "cli":
        run_cli()
    elif args.command == "test":
        run_tests(with_server=False)
    elif args.command == "test-with-mcp":
        run_tests(with_server=True)
    elif args.command == "eval":
        run_evaluation()
    elif args.command == "help":
        print_banner()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print_banner()
        print("请指定一个命令，例如: python run.py api")
        print("使用 'python run.py help' 查看所有命令")
    else:
        main()