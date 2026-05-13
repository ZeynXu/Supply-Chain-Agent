#!/usr/bin/env python3
"""
Test script for MCP tools.
"""

import asyncio
import sys
import os
import threading
import time

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supply_chain_agent.tools.server import run_mcp_server, run_mcp_server_async
from supply_chain_agent.tools.client import ToolClient


@pytest.mark.asyncio
async def test_tools():
    """Test MCP tools."""
    print("Testing MCP Tools...")
    print("=" * 50)

    async with ToolClient() as client:
        # Test 1: Query order status
        print("\nTest 1: Query order status")
        print("-" * 30)
        try:
            result = await client.query_order_status("PO-2026-001")
            print(f"✓ Order query successful")
            print(f"  Order ID: {result.get('order_id')}")
            print(f"  Status: {result.get('status')}")
            print(f"  Amount: ¥{result.get('amount', 0):,.2f}")
        except Exception as e:
            print(f"✗ Order query failed: {e}")

        # Test 2: Get logistics trace
        print("\nTest 2: Get logistics trace")
        print("-" * 30)
        try:
            result = await client.get_logistics_trace("SF1234567890")
            print(f"✓ Logistics query successful")
            print(f"  Tracking No: {result.get('tracking_no')}")
            print(f"  Status: {result.get('status')}")
            print(f"  Current Location: {result.get('current_location')}")
        except Exception as e:
            print(f"✗ Logistics query failed: {e}")

        # Test 3: Search contract templates
        print("\nTest 3: Search contract templates")
        print("-" * 30)
        try:
            result = await client.search_contract_template("质量保证", top_k=1)
            templates = result.get("templates", [])
            print(f"✓ Contract search successful (found {len(templates)} templates)")
            if templates:
                print(f"  Template: {templates[0].get('title')}")
        except Exception as e:
            print(f"✗ Contract search failed: {e}")

        # Test 4: Check health
        print("\nTest 4: Check tool health")
        print("-" * 30)
        try:
            result = await client.check_health()
            print(f"✓ Health check successful")
            if "tools" in result:
                for tool_name, status in result["tools"].items():
                    print(f"  {tool_name}: {'✅' if status.get('healthy') else '❌'}")
        except Exception as e:
            print(f"✗ Health check failed: {e}")

        # Test 5: Test circuit breaker (simulate failures)
        print("\nTest 5: Testing circuit breaker with invalid order")
        print("-" * 30)
        for i in range(3):
            try:
                result = await client.query_order_status("INVALID-ORDER")
                print(f"  Attempt {i+1}: Unexpected success")
            except Exception as e:
                print(f"  Attempt {i+1}: Failed as expected - {e}")

        # Test 6: Test fallback mechanism
        print("\nTest 6: Testing fallback mechanism")
        print("-" * 30)
        try:
            result = await client.query_order_status("ANOTHER-INVALID")
            print(f"✓ Fallback mechanism working")
            print(f"  Status: {result.get('status')}")
            print(f"  Note: {result.get('note', 'No note')}")
        except Exception as e:
            print(f"✗ Fallback failed: {e}")

    print("\n" + "=" * 50)
    print("All tests completed!")


def run_server_and_test():
    """Run MCP server and test tools."""
    # Start server in background thread (since run_mcp_server is now synchronous)
    server_thread = threading.Thread(
        target=run_mcp_server,
        args=(8001,),
        daemon=True
    )
    server_thread.start()

    # Wait for server to start
    time.sleep(2)

    try:
        # Run tests
        asyncio.run(test_tools())
    finally:
        # Server thread will be terminated when main thread exits
        pass


if __name__ == "__main__":
    print("Supply Chain Agent - MCP Tools Test")
    print("=" * 50)

    # Check if we should run server or just test
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        print("Starting MCP server only...")
        run_mcp_server(port=8001)
    elif len(sys.argv) > 1 and sys.argv[1] == "test-only":
        print("Testing MCP tools (server must be running)...")
        asyncio.run(test_tools())
    else:
        print("Running server and tests...")
        run_server_and_test()