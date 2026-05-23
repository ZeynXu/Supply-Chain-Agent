#!/usr/bin/env python3
"""
Supply Chain Database - SQLite database for supply chain data.

This module provides database access for the supply chain agent system.
All data is loaded from /root/Supply-Chain-Agent/dataset/ directory.
No mock data is used.
"""

import sqlite3
import pandas as pd
import os
import yaml
import json
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
from datetime import datetime


# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), "supply_chain.db")

# Data directory (relative to project root)
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dataset")


def get_db_path() -> str:
    """Get the database path."""
    return DB_PATH


@contextmanager
def get_connection():
    """Get a database connection context manager."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def create_schema():
    """Create the database schema with normalized tables."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Customers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY,
                customer_fname TEXT,
                customer_lname TEXT,
                customer_email TEXT,
                customer_segment TEXT,
                customer_city TEXT,
                customer_country TEXT,
                customer_state TEXT,
                customer_street TEXT,
                customer_zipcode INTEGER,
                latitude REAL,
                longitude REAL
            )
        """)

        # Categories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                category_id INTEGER PRIMARY KEY,
                category_name TEXT
            )
        """)

        # Departments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                department_id INTEGER PRIMARY KEY,
                department_name TEXT
            )
        """)

        # Products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_card_id INTEGER PRIMARY KEY,
                product_name TEXT,
                product_price REAL,
                product_status INTEGER,
                product_category_id INTEGER,
                product_description TEXT,
                FOREIGN KEY (product_category_id) REFERENCES categories(category_id)
            )
        """)

        # Orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                order_date TEXT,
                order_status TEXT,
                order_city TEXT,
                order_country TEXT,
                order_region TEXT,
                order_state TEXT,
                order_zipcode TEXT,
                delivery_status TEXT,
                late_delivery_risk INTEGER,
                type TEXT,
                market TEXT,
                benefit_per_order REAL,
                sales_per_customer REAL,
                order_profit_per_order REAL,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        """)

        # Order items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                order_item_id INTEGER PRIMARY KEY,
                order_id INTEGER,
                product_card_id INTEGER,
                order_item_discount REAL,
                order_item_discount_rate REAL,
                order_item_product_price REAL,
                order_item_profit_ratio REAL,
                order_item_quantity INTEGER,
                sales REAL,
                order_item_total REAL,
                benefit_per_order REAL,
                sales_per_customer REAL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                FOREIGN KEY (product_card_id) REFERENCES products(product_card_id)
            )
        """)

        # Shipping table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shipping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                days_for_shipping_real INTEGER,
                days_for_shipment_scheduled INTEGER,
                shipping_mode TEXT,
                shipping_date TEXT,
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            )
        """)

        # Work orders table (new)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_orders (
                work_order_id TEXT PRIMARY KEY,
                order_id TEXT,
                work_type TEXT NOT NULL,
                status TEXT DEFAULT '待处理',
                priority TEXT DEFAULT '中',
                description TEXT,
                assigned_to TEXT,
                created_by TEXT DEFAULT 'Agent System',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                timeline TEXT
            )
        """)

        # Issues table (new)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                issue_id TEXT PRIMARY KEY,
                issue_type TEXT NOT NULL,
                description TEXT,
                urgency TEXT DEFAULT '中',
                affected_order TEXT,
                reported_by TEXT,
                status TEXT DEFAULT '待处理',
                assigned_to TEXT DEFAULT '异常处理组',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updates TEXT
            )
        """)

        # Entity mappings table (new)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entity_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                standard_name TEXT NOT NULL,
                alias TEXT NOT NULL,
                description TEXT,
                UNIQUE(standard_name, alias)
            )
        """)

        # Fallback templates table (new)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fallback_templates (
                error_code TEXT PRIMARY KEY,
                error_name TEXT,
                scenario TEXT,
                severity TEXT DEFAULT 'info',
                template TEXT NOT NULL,
                notes TEXT
            )
        """)

        # Agent config table (new)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_config (
                config_key TEXT PRIMARY KEY,
                config_value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for faster queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(order_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_card_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shipping_order ON shipping(order_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_orders_status ON work_orders(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_mappings_standard ON entity_mappings(standard_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_mappings_alias ON entity_mappings(alias)")

        conn.commit()
        print("✓ Database schema created successfully")


def import_csv_data(csv_path: str):
    """Import CSV data into the database."""
    print(f"Importing data from {csv_path}...")

    # Read CSV with multiple encoding attempts
    df = None
    for encoding in ['utf-8', 'latin-1', 'gbk', 'cp1252', 'iso-8859-1']:
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
            print(f"  Successfully read CSV with {encoding} encoding")
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"  Error with {encoding}: {e}")
            continue

    if df is None:
        raise ValueError(f"Failed to read CSV file with any encoding: {csv_path}")

    print(f"  Total rows in CSV: {len(df)}")

    # Normalize column names: replace spaces with underscores
    df.columns = df.columns.str.replace(' ', '_')

    with get_connection() as conn:
        # Import customers (unique customers)
        customers_df = df[[
            'Customer_Id', 'Customer_Fname', 'Customer_Lname', 'Customer_Email',
            'Customer_Segment', 'Customer_City', 'Customer_Country', 'Customer_State',
            'Customer_Street', 'Customer_Zipcode', 'Latitude', 'Longitude'
        ]].drop_duplicates(subset=['Customer_Id'])

        customers_df.to_sql('customers', conn, if_exists='replace', index=False)
        print(f"  ✓ Imported {len(customers_df)} customers")

        # Import categories (unique categories)
        categories_df = df[['Category_Id', 'Category_Name']].drop_duplicates(subset=['Category_Id'])
        categories_df.to_sql('categories', conn, if_exists='replace', index=False)
        print(f"  ✓ Imported {len(categories_df)} categories")

        # Import departments (unique departments)
        departments_df = df[['Department_Id', 'Department_Name']].drop_duplicates(subset=['Department_Id'])
        departments_df.to_sql('departments', conn, if_exists='replace', index=False)
        print(f"  ✓ Imported {len(departments_df)} departments")

        # Import products (unique products)
        products_df = df[[
            'Product_Card_Id', 'Product_Name', 'Product_Price', 'Product_Status', 'Product_Category_Id'
        ]].drop_duplicates(subset=['Product_Card_Id'])
        products_df.to_sql('products', conn, if_exists='replace', index=False)
        print(f"  ✓ Imported {len(products_df)} products")

        # Import orders (unique orders)
        orders_df = df[[
            'Order_Id', 'Order_Customer_Id', 'order_date_(DateOrders)', 'Order_Status',
            'Order_City', 'Order_Country', 'Order_Region', 'Order_State', 'Order_Zipcode',
            'Delivery_Status', 'Late_delivery_risk', 'Type', 'Market',
            'Benefit_per_order', 'Sales_per_customer', 'Order_Profit_Per_Order'
        ]].drop_duplicates(subset=['Order_Id'])

        # Rename columns for database
        orders_df.columns = [
            'order_id', 'customer_id', 'order_date', 'order_status',
            'order_city', 'order_country', 'order_region', 'order_state', 'order_zipcode',
            'delivery_status', 'late_delivery_risk', 'type', 'market',
            'benefit_per_order', 'sales_per_customer', 'order_profit_per_order'
        ]
        orders_df.to_sql('orders', conn, if_exists='replace', index=False)
        print(f"  ✓ Imported {len(orders_df)} orders")

        # Import order items
        order_items_df = df[[
            'Order_Item_Id', 'Order_Id', 'Product_Card_Id', 'Order_Item_Discount',
            'Order_Item_Discount_Rate', 'Order_Item_Product_Price', 'Order_Item_Profit_Ratio',
            'Order_Item_Quantity', 'Sales', 'Order_Item_Total', 'Benefit_per_order', 'Sales_per_customer'
        ]]

        order_items_df.columns = [
            'order_item_id', 'order_id', 'product_card_id', 'order_item_discount',
            'order_item_discount_rate', 'order_item_product_price', 'order_item_profit_ratio',
            'order_item_quantity', 'sales', 'order_item_total', 'benefit_per_order', 'sales_per_customer'
        ]
        order_items_df.to_sql('order_items', conn, if_exists='replace', index=False)
        print(f"  ✓ Imported {len(order_items_df)} order items")

        # Import shipping
        shipping_df = df[[
            'Order_Id', 'Days_for_shipping_(real)', 'Days_for_shipment_(scheduled)',
            'Shipping_Mode', 'shipping_date_(DateOrders)'
        ]]
        shipping_df.columns = [
            'order_id', 'days_for_shipping_real', 'days_for_shipment_scheduled',
            'shipping_mode', 'shipping_date'
        ]
        # Add unique id
        shipping_df = shipping_df.reset_index()
        shipping_df.columns = ['id', 'order_id', 'days_for_shipping_real', 'days_for_shipment_scheduled',
                               'shipping_mode', 'shipping_date']
        shipping_df.to_sql('shipping', conn, if_exists='replace', index=False)
        print(f"  ✓ Imported {len(shipping_df)} shipping records")

        conn.commit()

    print("✓ Data import completed successfully")


def load_entity_mappings(csv_path: str = None):
    """Load entity mappings from CSV file."""
    if csv_path is None:
        csv_path = os.path.join(DATA_DIR, "OtherData", "EntityMapping.csv")

    if not os.path.exists(csv_path):
        print(f"⚠️ Entity mapping file not found: {csv_path}")
        return 0

    print(f"Loading entity mappings from {csv_path}...")

    df = pd.read_csv(csv_path, encoding='utf-8')

    with get_connection() as conn:
        cursor = conn.cursor()

        count = 0
        for _, row in df.iterrows():
            standard_name = row.iloc[0]  # 标准实体名
            aliases = row.iloc[1]  # 别名（口语化表达）
            description = row.iloc[2] if len(row) > 2 else None  # 说明

            # Split aliases by Chinese comma or regular comma
            alias_list = str(aliases).replace('，', ',').split(',')

            for alias in alias_list:
                alias = alias.strip()
                if alias:
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO entity_mappings (standard_name, alias, description)
                            VALUES (?, ?, ?)
                        """, (standard_name, alias, description))
                        count += 1
                    except Exception as e:
                        print(f"  Warning: Failed to insert mapping {standard_name} -> {alias}: {e}")

        conn.commit()
        print(f"  ✓ Loaded {count} entity mappings")

    return count


def load_fallback_templates(csv_path: str = None):
    """Load fallback response templates from CSV file."""
    if csv_path is None:
        csv_path = os.path.join(DATA_DIR, "OtherData", "FallbackResponseTemplate.csv")

    if not os.path.exists(csv_path):
        print(f"⚠️ Fallback template file not found: {csv_path}")
        return 0

    print(f"Loading fallback templates from {csv_path}...")

    df = pd.read_csv(csv_path, encoding='utf-8')

    with get_connection() as conn:
        cursor = conn.cursor()

        count = 0
        for _, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO fallback_templates
                    (error_code, error_name, scenario, severity, template, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    row.get('错误编码', row.iloc[1] if len(row) > 1 else None),
                    row.get('场景描述', row.iloc[2] if len(row) > 2 else None),
                    row.get('场景描述', row.iloc[2] if len(row) > 2 else None),
                    row.get('严重等级', 'info'),
                    row.get('回复模板', row.iloc[4] if len(row) > 4 else None),
                    row.get('备注', row.iloc[5] if len(row) > 5 else None)
                ))
                count += 1
            except Exception as e:
                print(f"  Warning: Failed to insert template: {e}")

        conn.commit()
        print(f"  ✓ Loaded {count} fallback templates")

    return count


def load_agent_config(yaml_path: str = None):
    """Load agent configuration from YAML file."""
    if yaml_path is None:
        yaml_path = os.path.join(DATA_DIR, "OtherData", "config.yaml")

    if not os.path.exists(yaml_path):
        print(f"⚠️ Config file not found: {yaml_path}")
        return 0

    print(f"Loading agent config from {yaml_path}...")

    with open(yaml_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    with get_connection() as conn:
        cursor = conn.cursor()

        count = 0

        def flatten_config(d, prefix=''):
            items = []
            for k, v in d.items():
                key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    items.extend(flatten_config(v, key))
                else:
                    items.append((key, json.dumps(v) if not isinstance(v, str) else v))
            return items

        for key, value in flatten_config(config):
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO agent_config (config_key, config_value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (key, value))
                count += 1
            except Exception as e:
                print(f"  Warning: Failed to insert config {key}: {e}")

        conn.commit()
        print(f"  ✓ Loaded {count} config items")

    return count


# ============== Query Functions ==============

def get_order_by_id(order_id: int) -> Optional[Dict[str, Any]]:
    """Get order by ID with related information."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT o.*, c.customer_fname, c.customer_lname, c.customer_city, c.customer_country
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.customer_id
            WHERE o.order_id = ?
        """, (order_id,))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def get_orders_by_status(status: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get orders by status."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT o.*, c.customer_fname, c.customer_lname
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.customer_id
            WHERE o.order_status = ?
            LIMIT ?
        """, (status, limit))

        return [dict(row) for row in cursor.fetchall()]


def get_order_items(order_id: int) -> List[Dict[str, Any]]:
    """Get order items for an order."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT oi.*, p.product_name, p.product_price, c.category_name
            FROM order_items oi
            LEFT JOIN products p ON oi.product_card_id = p.product_card_id
            LEFT JOIN categories c ON p.product_category_id = c.category_id
            WHERE oi.order_id = ?
        """, (order_id,))

        return [dict(row) for row in cursor.fetchall()]


def get_shipping_info(order_id: int) -> Optional[Dict[str, Any]]:
    """Get shipping information for an order."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM shipping WHERE order_id = ?
        """, (order_id,))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def get_customer_by_id(customer_id: int) -> Optional[Dict[str, Any]]:
    """Get customer by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def get_product_by_id(product_card_id: int) -> Optional[Dict[str, Any]]:
    """Get product by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT p.*, c.category_name
            FROM products p
            LEFT JOIN categories c ON p.product_category_id = c.category_id
            WHERE p.product_card_id = ?
        """, (product_card_id,))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def get_statistics() -> Dict[str, Any]:
    """Get database statistics."""
    with get_connection() as conn:
        cursor = conn.cursor()

        stats = {}

        # Count records in each table
        for table in ['customers', 'categories', 'departments', 'products', 'orders', 'order_items', 'shipping', 'work_orders', 'issues']:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cursor.fetchone()[0]

        # Order status distribution
        cursor.execute("""
            SELECT order_status, COUNT(*) as count
            FROM orders
            GROUP BY order_status
            ORDER BY count DESC
        """)
        stats['order_status_distribution'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Delivery status distribution
        cursor.execute("""
            SELECT delivery_status, COUNT(*) as count
            FROM orders
            GROUP BY delivery_status
            ORDER BY count DESC
        """)
        stats['delivery_status_distribution'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Late delivery risk
        cursor.execute("""
            SELECT late_delivery_risk, COUNT(*) as count
            FROM orders
            GROUP BY late_delivery_risk
        """)
        stats['late_delivery_risk'] = {row[0]: row[1] for row in cursor.fetchall()}

        return stats


def search_orders(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search orders by various criteria."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Try to match order ID if query is numeric
        try:
            order_id = int(query)
            cursor.execute("""
                SELECT o.*, c.customer_fname, c.customer_lname
                FROM orders o
                LEFT JOIN customers c ON o.customer_id = c.customer_id
                WHERE o.order_id = ?
            """, (order_id,))
            results = cursor.fetchall()
            if results:
                return [dict(row) for row in results]
        except ValueError:
            pass

        # Search by status, city, country, etc.
        cursor.execute("""
            SELECT o.*, c.customer_fname, c.customer_lname
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.customer_id
            WHERE o.order_status LIKE ?
               OR o.order_city LIKE ?
               OR o.order_country LIKE ?
               OR o.delivery_status LIKE ?
            LIMIT ?
        """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", limit))

        return [dict(row) for row in cursor.fetchall()]


def get_sample_orders_for_testing(limit: int = 10) -> List[Dict[str, Any]]:
    """Get a sample of orders for testing purposes."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Get orders with different statuses for testing
        cursor.execute("""
            SELECT o.*, c.customer_fname, c.customer_lname, c.customer_city, c.customer_country,
                   s.shipping_mode, s.days_for_shipping_real, s.days_for_shipment_scheduled
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.customer_id
            LEFT JOIN shipping s ON o.order_id = s.order_id
            ORDER BY RANDOM()
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]


# ============== Work Order Functions ==============

def create_work_order(work_order_id: str, work_type: str, description: str,
                      priority: str = "中", order_id: str = None,
                      assigned_to: str = None, created_by: str = "Agent System") -> Dict[str, Any]:
    """Create a new work order."""
    with get_connection() as conn:
        cursor = conn.cursor()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timeline = json.dumps([{
            "timestamp": now,
            "actor": created_by,
            "action": "创建工单"
        }])

        cursor.execute("""
            INSERT INTO work_orders
            (work_order_id, order_id, work_type, status, priority, description,
             assigned_to, created_by, created_at, updated_at, timeline)
            VALUES (?, ?, ?, '待处理', ?, ?, ?, ?, ?, ?, ?)
        """, (work_order_id, order_id, work_type, priority, description,
              assigned_to, created_by, now, now, timeline))

        conn.commit()

        return get_work_order(work_order_id)


def get_work_order(work_order_id: str) -> Optional[Dict[str, Any]]:
    """Get work order by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM work_orders WHERE work_order_id = ?", (work_order_id,))

        row = cursor.fetchone()
        if row:
            result = dict(row)
            # Parse timeline JSON
            if result.get('timeline'):
                try:
                    result['timeline'] = json.loads(result['timeline'])
                except:
                    pass
            return result
        return None


def list_work_orders(status: str = None, limit: int = 50) -> List[Dict[str, Any]]:
    """List work orders, optionally filtered by status."""
    with get_connection() as conn:
        cursor = conn.cursor()

        if status:
            cursor.execute("""
                SELECT * FROM work_orders WHERE status = ?
                ORDER BY created_at DESC LIMIT ?
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT * FROM work_orders
                ORDER BY created_at DESC LIMIT ?
            """, (limit,))

        results = []
        for row in cursor.fetchall():
            result = dict(row)
            if result.get('timeline'):
                try:
                    result['timeline'] = json.loads(result['timeline'])
                except:
                    pass
            results.append(result)

        return results


def update_work_order(work_order_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    """Update work order fields."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Build update query
        updates = []
        values = []

        for key, value in kwargs.items():
            if key in ['status', 'priority', 'description', 'assigned_to']:
                updates.append(f"{key} = ?")
                values.append(value)

        if updates:
            updates.append("updated_at = ?")
            values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            values.append(work_order_id)

            cursor.execute(f"""
                UPDATE work_orders SET {', '.join(updates)}
                WHERE work_order_id = ?
            """, values)

            conn.commit()

        return get_work_order(work_order_id)


def add_work_order_timeline_event(work_order_id: str, actor: str, action: str) -> bool:
    """Add a timeline event to a work order."""
    work_order = get_work_order(work_order_id)
    if not work_order:
        return False

    timeline = work_order.get('timeline', [])
    if isinstance(timeline, str):
        try:
            timeline = json.loads(timeline)
        except:
            timeline = []

    timeline.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "actor": actor,
        "action": action
    })

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE work_orders SET timeline = ?, updated_at = ?
            WHERE work_order_id = ?
        """, (json.dumps(timeline), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), work_order_id))
        conn.commit()

    return True


# ============== Issue Functions ==============

def create_issue(issue_id: str, issue_type: str, description: str,
                 urgency: str = "中", affected_order: str = None,
                 reported_by: str = "Agent System") -> Dict[str, Any]:
    """Create a new issue report."""
    with get_connection() as conn:
        cursor = conn.cursor()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updates = json.dumps([{
            "timestamp": now,
            "user": reported_by,
            "action": "创建问题报告",
            "details": f"自动创建{issue_type}问题报告"
        }])

        cursor.execute("""
            INSERT INTO issues
            (issue_id, issue_type, description, urgency, affected_order,
             reported_by, status, assigned_to, created_at, updated_at, updates)
            VALUES (?, ?, ?, ?, ?, ?, '待处理', '异常处理组', ?, ?, ?)
        """, (issue_id, issue_type, description, urgency, affected_order,
              reported_by, now, now, updates))

        conn.commit()

        return get_issue(issue_id)


def get_issue(issue_id: str) -> Optional[Dict[str, Any]]:
    """Get issue by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM issues WHERE issue_id = ?", (issue_id,))

        row = cursor.fetchone()
        if row:
            result = dict(row)
            if result.get('updates'):
                try:
                    result['updates'] = json.loads(result['updates'])
                except:
                    pass
            return result
        return None


def list_issues(status: str = None, limit: int = 50) -> List[Dict[str, Any]]:
    """List issues, optionally filtered by status."""
    with get_connection() as conn:
        cursor = conn.cursor()

        if status:
            cursor.execute("""
                SELECT * FROM issues WHERE status = ?
                ORDER BY created_at DESC LIMIT ?
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT * FROM issues
                ORDER BY created_at DESC LIMIT ?
            """, (limit,))

        results = []
        for row in cursor.fetchall():
            result = dict(row)
            if result.get('updates'):
                try:
                    result['updates'] = json.loads(result['updates'])
                except:
                    pass
            results.append(result)

        return results


# ============== Entity Mapping Functions ==============

def get_entity_mappings() -> Dict[str, List[str]]:
    """Get all entity mappings as a dictionary."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT standard_name, alias FROM entity_mappings")

        mappings = {}
        for row in cursor.fetchall():
            standard_name = row[0]
            alias = row[1]
            if standard_name not in mappings:
                mappings[standard_name] = []
            mappings[standard_name].append(alias)

        return mappings


def resolve_entity_alias(alias: str) -> Optional[str]:
    """Resolve an alias to its standard entity name."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT standard_name FROM entity_mappings WHERE alias = ?", (alias,))

        row = cursor.fetchone()
        if row:
            return row[0]
        return None


# ============== Fallback Template Functions ==============

def get_fallback_template(error_code: str) -> Optional[Dict[str, Any]]:
    """Get fallback template by error code."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM fallback_templates WHERE error_code = ?", (error_code,))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def render_fallback_template(error_code: str, **kwargs) -> str:
    """Render a fallback template with provided variables."""
    template = get_fallback_template(error_code)
    if not template:
        return f"系统错误: {error_code}"

    text = template.get('template', '')

    # Replace placeholders like {order_id}
    for key, value in kwargs.items():
        text = text.replace(f'{{{key}}}', str(value))

    return text


# ============== Config Functions ==============

def get_config(key: str, default: Any = None) -> Any:
    """Get config value by key."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT config_value FROM agent_config WHERE config_key = ?", (key,))

        row = cursor.fetchone()
        if row:
            value = row[0]
            # Try to parse JSON
            try:
                return json.loads(value)
            except:
                return value
        return default


def get_all_config() -> Dict[str, Any]:
    """Get all config as a dictionary."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT config_key, config_value FROM agent_config")

        config = {}
        for row in cursor.fetchall():
            key = row[0]
            value = row[1]
            # Try to parse JSON
            try:
                value = json.loads(value)
            except:
                pass

            # Build nested structure
            parts = key.split('.')
            d = config
            for part in parts[:-1]:
                if part not in d:
                    d[part] = {}
                d = d[part]
            d[parts[-1]] = value

        return config


# ============== Initialization ==============

def initialize_database(csv_path: str = None):
    """Initialize the database with schema and optionally import data."""
    create_schema()

    if csv_path is None:
        csv_path = os.path.join(DATA_DIR, "BusinessData", "DataCoSupplyChainDataset.csv")

    if csv_path and os.path.exists(csv_path):
        import_csv_data(csv_path)

    # Load additional data
    load_entity_mappings()
    load_fallback_templates()
    load_agent_config()

    stats = get_statistics()
    print(f"\nDatabase statistics:")
    for table, count in stats.items():
        if isinstance(count, dict):
            print(f"  {table}:")
            for k, v in count.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {table}: {count} records")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = None

    initialize_database(csv_path)
