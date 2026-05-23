"""
Supply Chain Data Package - Database access module.

All data is loaded from /root/Supply-Chain-Agent/dataset/ directory.
No mock data is used.
"""

from .supply_chain_db import (
    # Connection
    get_db_path,
    get_connection,
    # Order queries
    get_order_by_id,
    get_orders_by_status,
    get_order_items,
    search_orders,
    get_sample_orders_for_testing,
    # Shipping
    get_shipping_info,
    # Customer
    get_customer_by_id,
    # Product
    get_product_by_id,
    # Statistics
    get_statistics,
    # Work orders
    create_work_order,
    get_work_order,
    list_work_orders,
    update_work_order,
    add_work_order_timeline_event,
    # Issues
    create_issue,
    get_issue,
    list_issues,
    # Entity mappings
    get_entity_mappings,
    resolve_entity_alias,
    # Fallback templates
    get_fallback_template,
    render_fallback_template,
    # Config
    get_config,
    get_all_config,
    # Data loading
    create_schema,
    import_csv_data,
    load_entity_mappings,
    load_fallback_templates,
    load_agent_config,
    initialize_database,
)

from .data_loader import (
    DataLoader,
    initialize_all_data,
)

__all__ = [
    # Connection
    "get_db_path",
    "get_connection",
    # Order queries
    "get_order_by_id",
    "get_orders_by_status",
    "get_order_items",
    "search_orders",
    "get_sample_orders_for_testing",
    # Shipping
    "get_shipping_info",
    # Customer
    "get_customer_by_id",
    # Product
    "get_product_by_id",
    # Statistics
    "get_statistics",
    # Work orders
    "create_work_order",
    "get_work_order",
    "list_work_orders",
    "update_work_order",
    "add_work_order_timeline_event",
    # Issues
    "create_issue",
    "get_issue",
    "list_issues",
    # Entity mappings
    "get_entity_mappings",
    "resolve_entity_alias",
    # Fallback templates
    "get_fallback_template",
    "render_fallback_template",
    # Config
    "get_config",
    "get_all_config",
    # Data loading
    "create_schema",
    "import_csv_data",
    "load_entity_mappings",
    "load_fallback_templates",
    "load_agent_config",
    "initialize_database",
    # Data loader
    "DataLoader",
    "initialize_all_data",
]
