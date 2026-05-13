"""
Main entry point for Supply Chain Agent system.

This module provides the main application entry point and CLI interface.
"""

import asyncio
import sys
import threading
import time
from typing import Optional

import uvicorn
from dotenv import load_dotenv

from supply_chain_agent.app import create_app
from supply_chain_agent.agents.parser import ParserAgent
from supply_chain_agent.agents.executor import ExecutorAgent
from supply_chain_agent.agents.auditor import AuditorAgent
from supply_chain_agent.agents.report_generator import ReportGenerator
from supply_chain_agent.agents.orchestrator import OrchestratorAgent
from supply_chain_agent.tools.server import run_mcp_server


def _run_mcp_server_in_thread(port: int):
    """Run MCP server in a separate thread (blocking)."""
    run_mcp_server(port=port)


async def main():
    """Main entry point for the Supply Chain Agent system."""
    load_dotenv()

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Supply Chain Agent System")
    parser.add_argument("--mode", choices=["cli", "web", "mcp"], default="web",
                       help="Run mode: cli, web, or mcp server")
    parser.add_argument("--port", type=int, default=8000,
                       help="Port for web server (default: 8000)")
    parser.add_argument("--mcp-port", type=int, default=8001,
                       help="Port for MCP server (default: 8001)")
    parser.add_argument("--no-mcp", action="store_true",
                       help="Disable automatic MCP server startup (useful for debugging)")

    args = parser.parse_args()

    if args.mode == "mcp":
        print(f"Starting MCP server on port {args.mcp_port}...")
        run_mcp_server(port=args.mcp_port)
    elif args.mode == "web":
        # Start MCP server in background thread (unless --no-mcp is specified)
        mcp_thread = None
        if not args.no_mcp:
            print(f"Starting MCP server on port {args.mcp_port}...")
            mcp_thread = threading.Thread(
                target=_run_mcp_server_in_thread,
                args=(args.mcp_port,),
                daemon=True
            )
            mcp_thread.start()
            # Give MCP server a moment to start
            time.sleep(2)
            print(f"MCP server started on port {args.mcp_port}")

        app = create_app()
        print(f"Starting web server on http://localhost:{args.port}...")
        config = uvicorn.Config(app, host="0.0.0.0", port=args.port)
        server = uvicorn.Server(config)
        await server.serve()
    elif args.mode == "cli":
        # Start MCP server in background for CLI mode too
        mcp_thread = None
        if not args.no_mcp:
            print("Starting MCP server...")
            mcp_thread = threading.Thread(
                target=_run_mcp_server_in_thread,
                args=(args.mcp_port,),
                daemon=True
            )
            mcp_thread.start()
            time.sleep(2)

        print("Supply Chain Agent CLI Mode")
        print("Type 'exit' to quit")
        print("-" * 40)

        # Create all agent instances with dependency injection
        parser = ParserAgent()
        executor = ExecutorAgent()
        auditor = AuditorAgent()
        report_generator = ReportGenerator()

        orchestrator = OrchestratorAgent(
            parser=parser,
            executor=executor,
            auditor=auditor,
            report_generator=report_generator
        )

        while True:
            try:
                user_input = input("\n用户: ").strip()
                if user_input.lower() in ["exit", "quit", "退出"]:
                    print("再见！")
                    break

                if not user_input:
                    continue

                print("\nAgent: ", end="", flush=True)
                response = await orchestrator.process(user_input)
                print(response)

            except KeyboardInterrupt:
                print("\n\n再见！")
                break
            except Exception as e:
                print(f"\n错误: {e}")


if __name__ == "__main__":
    asyncio.run(main())