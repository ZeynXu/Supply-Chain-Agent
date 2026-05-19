#!/usr/bin/env python3
"""
Test cases generated from real supply chain data.

This module contains test cases derived from the imported CSV data.
"""

import asyncio
import sys
import os
import pytest
import random

# Add parent directory to path
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


class TestDatabaseConnection:
    """Test database connection and basic queries."""

    def test_database_available(self):
        """Test that database is available."""
        assert DATABASE_AVAILABLE, "Database should be available"

    def test_get_statistics(self):
        """Test getting database statistics."""
        stats = get_statistics()
        assert stats is not None
        assert stats["orders"] > 0
        assert stats["customers"] > 0
        assert stats["products"] > 0
        print(f"\nDatabase statistics:")
        print(f"  Orders: {stats['orders']}")
        print(f"  Customers: {stats['customers']}")
        print(f"  Products: {stats['products']}")
        print(f"  Order status distribution: {stats['order_status_distribution']}")


class TestOrderQueries:
    """Test order-related queries."""

    @pytest.mark.asyncio
    async def test_query_order_by_id(self):
        """Test querying order by ID."""
        # Get a sample order
        sample_orders = get_sample_orders_for_testing(1)
        assert len(sample_orders) > 0, "Should have at least one order"

        order = sample_orders[0]
        order_id = order["order_id"]

        # Query the order
        result = get_order_by_id(order_id)
        assert result is not None
        assert result["order_id"] == order_id
        print(f"\nQueried order {order_id}:")
        print(f"  Status: {result.get('order_status')}")
        print(f"  Delivery Status: {result.get('delivery_status')}")

    @pytest.mark.asyncio
    async def test_query_orders_by_status(self):
        """Test querying orders by status."""
        # Test each status
        statuses = ["COMPLETE", "PROCESSING", "PENDING", "CLOSED"]
        for status in statuses:
            orders = get_orders_by_status(status, limit=5)
            print(f"\nOrders with status '{status}': {len(orders)} found")
            if orders:
                assert all(o["order_status"] == status for o in orders)

    @pytest.mark.asyncio
    async def test_query_order_items(self):
        """Test querying order items."""
        # Get a sample order with items
        sample_orders = get_sample_orders_for_testing(1)
        order_id = sample_orders[0]["order_id"]

        items = get_order_items(order_id)
        assert items is not None
        print(f"\nOrder {order_id} has {len(items)} items:")
        for item in items[:3]:
            print(f"  - {item.get('product_name')}: {item.get('order_item_quantity')} x ${item.get('order_item_product_price', 0):.2f}")


class TestShippingQueries:
    """Test shipping-related queries."""

    @pytest.mark.asyncio
    async def test_query_shipping_info(self):
        """Test querying shipping information."""
        sample_orders = get_sample_orders_for_testing(5)

        for order in sample_orders:
            shipping = get_shipping_info(order["order_id"])
            if shipping:
                print(f"\nOrder {order['order_id']} shipping:")
                print(f"  Mode: {shipping.get('shipping_mode')}")
                print(f"  Days (real): {shipping.get('days_for_shipping_real')}")
                print(f"  Days (scheduled): {shipping.get('days_for_shipment_scheduled')}")
                break


class TestMCPToolsWithDatabase:
    """Test MCP tools using real database data."""

    @pytest.fixture
    def server(self):
        """Create MCP server instance."""
        return MCPServer()

    @pytest.mark.asyncio
    async def test_query_order_status_tool(self, server):
        """Test query_order_status tool with real data."""
        # Get a sample order
        sample_orders = get_sample_orders_for_testing(1)
        order_id = str(sample_orders[0]["order_id"])

        result = await server.mcp.call_tool("query_order_status", {"order_id": order_id})

        if hasattr(result, "structured_content"):
            data = result.structured_content
            assert data is not None
            print(f"\nTool query result for order {order_id}:")
            print(f"  Order ID: {data.get('order_id')}")
            print(f"  Status: {data.get('status')}")
            print(f"  Amount: ${data.get('amount', 0):.2f}")

    @pytest.mark.asyncio
    async def test_get_logistics_trace_tool(self, server):
        """Test get_logistics_trace tool with real data."""
        # Get a sample order
        sample_orders = get_sample_orders_for_testing(1)
        order_id = sample_orders[0]["order_id"]

        # Generate tracking number
        tracking_no = f"SF{order_id:010d}"

        result = await server.mcp.call_tool("get_logistics_trace", {"tracking_no": tracking_no})

        if hasattr(result, "structured_content"):
            data = result.structured_content
            assert data is not None
            print(f"\nLogistics trace for {tracking_no}:")
            print(f"  Status: {data.get('status')}")
            print(f"  Current Location: {data.get('current_location')}")
            print(f"  Events: {len(data.get('events', []))}")

    @pytest.mark.asyncio
    async def test_multiple_order_queries(self, server):
        """Test querying multiple orders."""
        sample_orders = get_sample_orders_for_testing(5)

        print(f"\nQuerying {len(sample_orders)} orders:")
        for order in sample_orders:
            order_id = str(order["order_id"])
            result = await server.mcp.call_tool("query_order_status", {"order_id": order_id})

            if hasattr(result, "structured_content"):
                data = result.structured_content
                if data:
                    print(f"  Order {order_id}: {data.get('status')} - ${data.get('amount', 0):.2f}")


class TestDataIntegrity:
    """Test data integrity and relationships."""

    def test_order_customer_relationship(self):
        """Test that orders have valid customer references."""
        sample_orders = get_sample_orders_for_testing(10)

        valid_count = 0
        for order in sample_orders:
            customer_id = order.get("customer_id")
            if customer_id:
                customer = get_customer_by_id(customer_id)
                if customer:
                    valid_count += 1

        print(f"\nOrder-Customer relationship check:")
        print(f"  Valid relationships: {valid_count}/{len(sample_orders)}")
        assert valid_count > 0, "Should have at least some valid customer references"

    def test_order_item_product_relationship(self):
        """Test that order items have valid product references."""
        sample_orders = get_sample_orders_for_testing(5)

        valid_count = 0
        total_items = 0
        for order in sample_orders:
            items = get_order_items(order["order_id"])
            for item in items:
                total_items += 1
                product_id = item.get("product_card_id")
                if product_id:
                    product = get_product_by_id(product_id)
                    if product:
                        valid_count += 1

        print(f"\nOrder Item-Product relationship check:")
        print(f"  Valid relationships: {valid_count}/{total_items}")
        assert valid_count > 0, "Should have at least some valid product references"

    def test_order_status_distribution(self):
        """Test order status distribution matches expectations."""
        stats = get_statistics()
        status_dist = stats.get("order_status_distribution", {})

        print(f"\nOrder status distribution:")
        for status, count in status_dist.items():
            print(f"  {status}: {count}")

        # Verify we have the expected statuses
        assert "COMPLETE" in status_dist
        assert "PROCESSING" in status_dist
        assert "PENDING" in status_dist

    def test_delivery_status_distribution(self):
        """Test delivery status distribution."""
        stats = get_statistics()
        delivery_dist = stats.get("delivery_status_distribution", {})

        print(f"\nDelivery status distribution:")
        for status, count in delivery_dist.items():
            print(f"  {status}: {count}")

        # Verify we have various delivery statuses
        assert len(delivery_dist) > 0


class TestSearchFunctionality:
    """Test search functionality."""

    def test_search_by_status(self):
        """Test searching orders by status."""
        results = search_orders("COMPLETE", limit=5)
        print(f"\nSearch for 'COMPLETE': {len(results)} results")
        assert len(results) > 0

    def test_search_by_country(self):
        """Test searching orders by country."""
        results = search_orders("Indonesia", limit=5)
        print(f"\nSearch for 'Indonesia': {len(results)} results")
        # May or may not have results depending on data

    def test_search_by_order_id(self):
        """Test searching by order ID."""
        sample_orders = get_sample_orders_for_testing(1)
        order_id = str(sample_orders[0]["order_id"])

        results = search_orders(order_id, limit=5)
        print(f"\nSearch for order ID {order_id}: {len(results)} results")
        assert len(results) > 0


async def run_all_tests():
    """Run all tests manually."""
    print("=" * 60)
    print("Supply Chain Database Tests")
    print("=" * 60)

    # Database connection tests
    print("\n1. Testing database connection...")
    test_db = TestDatabaseConnection()
    test_db.test_database_available()
    test_db.test_get_statistics()

    # Order query tests
    print("\n2. Testing order queries...")
    test_orders = TestOrderQueries()
    await test_orders.test_query_order_by_id()
    await test_orders.test_query_orders_by_status()
    await test_orders.test_query_order_items()

    # Shipping query tests
    print("\n3. Testing shipping queries...")
    test_shipping = TestShippingQueries()
    await test_shipping.test_query_shipping_info()

    # MCP tool tests
    print("\n4. Testing MCP tools with database...")
    test_mcp = TestMCPToolsWithDatabase()
    server = MCPServer()
    await test_mcp.test_query_order_status_tool(server)
    await test_mcp.test_get_logistics_trace_tool(server)
    await test_mcp.test_multiple_order_queries(server)

    # Data integrity tests
    print("\n5. Testing data integrity...")
    test_integrity = TestDataIntegrity()
    test_integrity.test_order_customer_relationship()
    test_integrity.test_order_item_product_relationship()
    test_integrity.test_order_status_distribution()
    test_integrity.test_delivery_status_distribution()

    # Search tests
    print("\n6. Testing search functionality...")
    test_search = TestSearchFunctionality()
    test_search.test_search_by_status()
    test_search.test_search_by_country()
    test_search.test_search_by_order_id()

    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
