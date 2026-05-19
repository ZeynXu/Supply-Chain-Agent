#!/usr/bin/env python3
"""
Integration test cases generated from real supply chain data.

Tests the complete supply chain agent workflow using data from
the imported DataCoSupplyChainDataset.
"""

import asyncio
import sys
import os
import pytest
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supply_chain_agent.data.supply_chain_db import (
    get_order_by_id,
    get_orders_by_status,
    get_order_items,
    get_shipping_info,
    get_customer_by_id,
    get_product_by_id,
    get_statistics,
    get_sample_orders_for_testing,
    search_orders,
)
from supply_chain_agent.tools.server import MCPServer, DATABASE_AVAILABLE
from supply_chain_agent.tools.client import ToolClient


# ============================================================
# Test data generators from real database
# ============================================================

def get_late_delivery_orders(limit=5):
    """Get orders with late delivery from database."""
    sample = get_sample_orders_for_testing(50)
    late_orders = [o for o in sample if o.get("delivery_status") == "Late delivery"]
    return late_orders[:limit]


def get_advance_shipping_orders(limit=5):
    """Get orders with advance shipping from database."""
    sample = get_sample_orders_for_testing(50)
    advance_orders = [o for o in sample if o.get("delivery_status") == "Advance shipping"]
    return advance_orders[:limit]


def get_complete_orders(limit=5):
    """Get completed orders from database."""
    return get_orders_by_status("COMPLETE", limit=limit)


def get_pending_orders(limit=5):
    """Get pending orders from database."""
    return get_orders_by_status("PENDING", limit=limit)


def get_canceled_orders(limit=5):
    """Get canceled orders from database."""
    return get_orders_by_status("CANCELED", limit=limit)


# ============================================================
# Database Layer Tests
# ============================================================

class TestDatabaseLayer:
    """Test the database access layer with real data."""

    def test_database_has_data(self):
        """Verify database has been populated with CSV data."""
        stats = get_statistics()
        assert stats["orders"] > 4000, f"Expected >4000 orders, got {stats['orders']}"
        assert stats["customers"] > 3000, f"Expected >3000 customers, got {stats['customers']}"
        assert stats["products"] > 50, f"Expected >50 products, got {stats['products']}"
        assert stats["order_items"] > 5000, f"Expected >5000 order items, got {stats['order_items']}"

    def test_order_statuses_covered(self):
        """Verify all order statuses from CSV are present."""
        stats = get_statistics()
        expected_statuses = ["COMPLETE", "PROCESSING", "PENDING", "CLOSED", "CANCELED"]
        status_dist = stats.get("order_status_distribution", {})

        for status in expected_statuses:
            assert status in status_dist, f"Missing order status: {status}"
            print(f"  {status}: {status_dist[status]} orders")

    def test_delivery_statuses_covered(self):
        """Verify all delivery statuses from CSV are present."""
        stats = get_statistics()
        expected_statuses = ["Late delivery", "Advance shipping", "Shipping on time", "Shipping canceled"]
        delivery_dist = stats.get("delivery_status_distribution", {})

        for status in expected_statuses:
            assert status in delivery_dist, f"Missing delivery status: {status}"
            print(f"  {status}: {delivery_dist[status]} orders")

    def test_order_with_customer_info(self):
        """Test that order queries include customer information."""
        orders = get_sample_orders_for_testing(5)

        for order in orders:
            if order.get("customer_id"):
                customer = get_customer_by_id(order["customer_id"])
                if customer:
                    # Customer table uses Customer_Id (with capital letters)
                    assert customer.get("Customer_Id") == order.get("customer_id")
                    print(f"  Order {order['order_id']} -> Customer: {customer.get('Customer_Fname')} {customer.get('Customer_Lname')}")
                    return

    def test_order_with_items(self):
        """Test that orders have associated items."""
        orders = get_sample_orders_for_testing(5)

        for order in orders:
            items = get_order_items(order["order_id"])
            if items:
                assert len(items) > 0
                # Product name might be in different cases or None
                product_name = items[0].get("product_name") or items[0].get("Product_Name")
                print(f"  Order {order['order_id']} has {len(items)} items")
                if product_name:
                    print(f"    First item: {product_name}")
                return

    def test_order_with_shipping(self):
        """Test that orders have shipping information."""
        orders = get_sample_orders_for_testing(10)

        for order in orders:
            shipping = get_shipping_info(order["order_id"])
            if shipping:
                assert shipping.get("shipping_mode") is not None
                print(f"  Order {order['order_id']} ships via {shipping.get('shipping_mode')}")
                return


# ============================================================
# MCP Tool Integration Tests
# ============================================================

class TestMCPToolIntegration:
    """Test MCP tools with real database data."""

    @pytest.fixture
    def server(self):
        """Create MCP server instance."""
        return MCPServer()

    @pytest.fixture
    def client(self):
        """Create tool client instance."""
        return ToolClient()

    @pytest.mark.asyncio
    async def test_query_complete_order(self, server):
        """Test querying a complete order via MCP tool."""
        complete_orders = get_complete_orders(1)
        assert len(complete_orders) > 0, "Need at least one complete order"

        order_id = str(complete_orders[0]["order_id"])
        result = await server.mcp.call_tool("query_order_status", {"order_id": order_id})

        if hasattr(result, "structured_content"):
            data = result.structured_content
            assert data is not None
            assert data.get("order_id") is not None
            print(f"\n  Complete order {order_id}: status={data.get('status')}")

    @pytest.mark.asyncio
    async def test_query_late_delivery_order(self, server):
        """Test querying a late delivery order via MCP tool."""
        late_orders = get_late_delivery_orders(1)
        if not late_orders:
            pytest.skip("No late delivery orders in sample")

        order_id = str(late_orders[0]["order_id"])
        result = await server.mcp.call_tool("query_order_status", {"order_id": order_id})

        if hasattr(result, "structured_content"):
            data = result.structured_content
            assert data is not None
            print(f"\n  Late delivery order {order_id}: delivery_status={data.get('delivery_status')}")

    @pytest.mark.asyncio
    async def test_logistics_trace_for_order(self, server):
        """Test logistics trace for an order."""
        orders = get_sample_orders_for_testing(1)
        order_id = orders[0]["order_id"]
        tracking_no = f"SF{order_id:010d}"

        result = await server.mcp.call_tool("get_logistics_trace", {"tracking_no": tracking_no})

        if hasattr(result, "structured_content"):
            data = result.structured_content
            assert data is not None
            print(f"\n  Logistics for {tracking_no}: status={data.get('status')}")

    @pytest.mark.asyncio
    async def test_create_work_order_with_real_data(self, server):
        """Test creating a work order referencing a real order."""
        orders = get_sample_orders_for_testing(1)
        order_id = str(orders[0]["order_id"])

        result = await server.mcp.call_tool("create_work_order", {
            "work_type": "质量检验",
            "description": f"对订单{order_id}到货质量进行抽检",
            "priority": "中",
            "order_id": order_id
        })

        if hasattr(result, "structured_content"):
            data = result.structured_content
            assert data is not None
            assert data.get("success") == True
            print(f"\n  Created work order for {order_id}: {data.get('message')}")

    @pytest.mark.asyncio
    async def test_report_issue_with_real_data(self, server):
        """Test reporting an issue with real order reference."""
        # Use a late delivery order
        late_orders = get_late_delivery_orders(1)
        if not late_orders:
            orders = get_sample_orders_for_testing(1)
            late_orders = orders

        order_id = str(late_orders[0]["order_id"])

        result = await server.mcp.call_tool("report_issue", {
            "issue_type": "物流延迟",
            "description": f"订单{order_id}物流延迟，需要跟进处理",
            "urgency": "高",
            "affected_order": order_id
        })

        if hasattr(result, "structured_content"):
            data = result.structured_content
            assert data is not None
            assert data.get("success") == True
            print(f"\n  Reported issue for {order_id}: {data.get('message')}")

    @pytest.mark.asyncio
    async def test_tool_client_with_database(self, client):
        """Test ToolClient with database-backed data."""
        # Query a real order
        orders = get_sample_orders_for_testing(1)
        order_id = str(orders[0]["order_id"])

        result = await client.query_order_status(order_id)
        assert result is not None
        print(f"\n  ToolClient query for {order_id}: {result.get('status', 'N/A')}")

    @pytest.mark.asyncio
    async def test_search_contract_template(self, server):
        """Test contract template search."""
        result = await server.mcp.call_tool("search_contract_template", {
            "query": "质量保证",
            "top_k": 2
        })

        if hasattr(result, "structured_content"):
            data = result.structured_content
            assert data is not None
            print(f"\n  Contract search: found {len(data.get('templates', []))} templates")


# ============================================================
# Scenario-Based Integration Tests
# ============================================================

class TestSupplyChainScenarios:
    """Test real-world supply chain scenarios using database data."""

    @pytest.fixture
    def client(self):
        """Create tool client instance."""
        return ToolClient()

    @pytest.mark.asyncio
    async def test_scenario_late_delivery_investigation(self, client):
        """
        Scenario: Investigate a late delivery order.
        1. Query order status
        2. Get logistics trace
        3. Report issue if late
        """
        late_orders = get_late_delivery_orders(1)
        if not late_orders:
            pytest.skip("No late delivery orders in sample")

        order = late_orders[0]
        order_id = str(order["order_id"])

        # Step 1: Query order status
        print(f"\n  Scenario: Investigating late delivery for order {order_id}")
        order_result = await client.query_order_status(order_id)
        assert order_result is not None
        print(f"    Step 1 - Order status: {order_result.get('status', 'N/A')}")

        # Step 2: Get logistics trace
        tracking_no = f"SF{order['order_id']:010d}"
        try:
            logistics_result = await client.get_logistics_trace(tracking_no)
            print(f"    Step 2 - Logistics status: {logistics_result.get('status', 'N/A')}")
        except Exception as e:
            print(f"    Step 2 - Logistics query failed: {e}")

        # Step 3: Report issue
        try:
            issue_result = await client.call_tool("report_issue",
                issue_type="物流延迟",
                description=f"订单{order_id}物流延迟，需要跟进处理",
                urgency="高",
                affected_order=order_id
            )
            print(f"    Step 3 - Issue reported: {issue_result}")
        except Exception as e:
            print(f"    Step 3 - Issue reporting failed: {e}")

    @pytest.mark.asyncio
    async def test_scenario_quality_inspection(self, client):
        """
        Scenario: Create a quality inspection work order.
        1. Query a completed order
        2. Create quality inspection work order
        """
        complete_orders = get_complete_orders(1)
        if not complete_orders:
            pytest.skip("No complete orders available")

        order = complete_orders[0]
        order_id = str(order["order_id"])

        # Step 1: Query order
        print(f"\n  Scenario: Quality inspection for order {order_id}")
        order_result = await client.query_order_status(order_id)
        assert order_result is not None
        print(f"    Step 1 - Order status: {order_result.get('status', 'N/A')}")

        # Step 2: Create work order
        try:
            wo_result = await client.call_tool("create_work_order",
                work_type="质量检验",
                description=f"对订单{order_id}到货质量进行抽检",
                priority="中",
                order_id=order_id
            )
            print(f"    Step 2 - Work order created")
        except Exception as e:
            print(f"    Step 2 - Work order creation failed: {e}")

    @pytest.mark.asyncio
    async def test_scenario_canceled_order_handling(self, client):
        """
        Scenario: Handle a canceled order.
        1. Query canceled order
        2. Create exception handling work order
        """
        canceled_orders = get_canceled_orders(1)
        if not canceled_orders:
            pytest.skip("No canceled orders available")

        order = canceled_orders[0]
        order_id = str(order["order_id"])

        # Step 1: Query order
        print(f"\n  Scenario: Handling canceled order {order_id}")
        order_result = await client.query_order_status(order_id)
        assert order_result is not None
        print(f"    Step 1 - Order status: {order_result.get('status', 'N/A')}")

        # Step 2: Create exception work order
        try:
            wo_result = await client.call_tool("create_work_order",
                work_type="异常处理",
                description=f"订单{order_id}已取消，需确认退款和退货流程",
                priority="高",
                order_id=order_id
            )
            print(f"    Step 2 - Exception work order created")
        except Exception as e:
            print(f"    Step 2 - Work order creation failed: {e}")

    @pytest.mark.asyncio
    async def test_scenario_bulk_order_check(self, client):
        """
        Scenario: Check status of multiple orders at once.
        """
        sample_orders = get_sample_orders_for_testing(10)

        print(f"\n  Scenario: Bulk order check for {len(sample_orders)} orders")
        results = {"success": 0, "failed": 0}

        for order in sample_orders:
            try:
                order_id = str(order["order_id"])
                result = await client.query_order_status(order_id)
                if result and not result.get("fallback"):
                    results["success"] += 1
                else:
                    results["failed"] += 1
            except Exception:
                results["failed"] += 1

        print(f"    Results: {results['success']} successful, {results['failed']} failed")
        assert results["success"] > 0, "At least some orders should be queryable"

    @pytest.mark.asyncio
    async def test_scenario_search_and_report(self, client):
        """
        Scenario: Search for orders in a specific region and report findings.
        """
        print(f"\n  Scenario: Search and report for problematic orders")

        # Get statistics about late deliveries
        stats = get_statistics()
        late_count = stats.get("delivery_status_distribution", {}).get("Late delivery", 0)
        total_orders = stats.get("orders", 1)
        late_pct = late_count / total_orders * 100

        print(f"    Late delivery rate: {late_pct:.1f}% ({late_count}/{total_orders})")

        # Get some late delivery orders
        late_orders = get_late_delivery_orders(3)

        for order in late_orders:
            order_id = str(order["order_id"])
            try:
                result = await client.query_order_status(order_id)
                print(f"    Order {order_id}: {result.get('status')} - Late delivery risk: {result.get('late_delivery_risk')}")
            except Exception as e:
                print(f"    Order {order_id}: Query failed - {e}")


# ============================================================
# Run all integration tests
# ============================================================

async def run_integration_tests():
    """Run all integration tests manually."""
    print("=" * 60)
    print("Supply Chain Integration Tests (Real Data)")
    print("=" * 60)

    # Database layer tests
    print("\n1. Database Layer Tests")
    print("-" * 40)
    db_test = TestDatabaseLayer()
    db_test.test_database_has_data()
    db_test.test_order_statuses_covered()
    db_test.test_delivery_statuses_covered()
    db_test.test_order_with_customer_info()
    db_test.test_order_with_items()
    db_test.test_order_with_shipping()

    # MCP tool integration tests
    print("\n2. MCP Tool Integration Tests")
    print("-" * 40)
    mcp_test = TestMCPToolIntegration()
    server = MCPServer()
    client = ToolClient()

    await mcp_test.test_query_complete_order(server)
    await mcp_test.test_query_late_delivery_order(server)
    await mcp_test.test_logistics_trace_for_order(server)
    await mcp_test.test_create_work_order_with_real_data(server)
    await mcp_test.test_report_issue_with_real_data(server)
    await mcp_test.test_tool_client_with_database(client)
    await mcp_test.test_search_contract_template(server)

    # Scenario tests
    print("\n3. Scenario-Based Integration Tests")
    print("-" * 40)
    scenario_test = TestSupplyChainScenarios()

    await scenario_test.test_scenario_late_delivery_investigation(client)
    await scenario_test.test_scenario_quality_inspection(client)
    await scenario_test.test_scenario_canceled_order_handling(client)
    await scenario_test.test_scenario_bulk_order_check(client)
    await scenario_test.test_scenario_search_and_report(client)

    print("\n" + "=" * 60)
    print("All integration tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_integration_tests())
