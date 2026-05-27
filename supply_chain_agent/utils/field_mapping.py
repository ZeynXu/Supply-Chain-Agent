"""
Field Mapping Utility (字段映射工具)

Loads field name mappings from CSV and provides formatting utilities.
"""

import csv
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path


class FieldMapping:
    """Manages field name mappings between English and Chinese."""

    _instance = None
    _mappings: Dict[str, Dict[str, Any]] = {}

    def __new__(cls):
        """Singleton pattern to ensure mappings are loaded only once."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_mappings()
        return cls._instance

    def _load_mappings(self):
        """Load field mappings from CSV file."""
        # Find the mapping file - use absolute path based on project root
        # The mapping file is at /root/Supply-Chain-Agent/dataset/OtherData/FieldMapping.csv
        current_dir = Path(__file__).resolve()

        # Navigate to project root (supply_chain_agent is 2 levels up from this file)
        project_root = current_dir.parent.parent.parent

        mapping_file = project_root / "dataset" / "OtherData" / "FieldMapping.csv"

        if not mapping_file.exists():
            print(f"⚠️ FieldMapping.csv not found at {mapping_file}")
            return

        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    field_name = row.get('英文字段名', '').strip()
                    if field_name:
                        self._mappings[field_name] = {
                            'chinese_name': row.get('中文字段名', field_name).strip(),
                            'field_type': row.get('字段类型', 'string').strip(),
                            'description': row.get('说明', '').strip()
                        }
            # print(f"✅ 已加载 {len(self._mappings)} 个字段映射")
        except Exception as e:
            print(f"⚠️ 加载字段映射失败: {e}")

    def get_chinese_name(self, field_name: str) -> str:
        """
        Get Chinese name for a field.

        Args:
            field_name: English field name

        Returns:
            Chinese field name, or original name if not found
        """
        if field_name in self._mappings:
            return self._mappings[field_name]['chinese_name']
        # Return field name with slight formatting if not found
        return field_name

    def get_field_type(self, field_name: str) -> str:
        """
        Get field type for formatting purposes.

        Args:
            field_name: Field name

        Returns:
            Field type (string, number, datetime)
        """
        if field_name in self._mappings:
            return self._mappings[field_name]['field_type']
        return 'string'

    def format_field_value(self, field_name: str, value: Any) -> str:
        """
        Format a field value based on its type.

        Args:
            field_name: Field name
            value: Field value

        Returns:
            Formatted string value
        """
        if value is None:
            return "N/A"

        field_type = self.get_field_type(field_name)

        if field_type == 'datetime':
            if isinstance(value, str):
                # Try to parse and format datetime strings
                try:
                    # Handle ISO format
                    if 'T' in value:
                        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        return dt.strftime('%Y-%m-%d %H:%M:%S')
                    # Handle date only
                    return value.split(' ')[0] if ' ' in value else value
                except:
                    return value
            return str(value)

        elif field_type == 'number':
            if isinstance(value, (int, float)):
                # Format numbers with appropriate decimal places
                if isinstance(value, float) and value != int(value):
                    return f"{value:.2f}"
                return str(int(value))
            return str(value)

        else:
            return str(value)

    def format_result_as_markdown(self, result: Dict[str, Any], title: str = "查询结果") -> str:
        """
        Format a result dictionary as Markdown key-value list.

        Args:
            result: Dictionary of field names to values
            title: Section title

        Returns:
            Markdown formatted string
        """
        if not result:
            return f"### {title}\n\n暂无数据"

        lines = [f"### {title}"]

        # Sort fields: put ID fields first, then other fields
        id_fields = []
        other_fields = []

        for field_name in result.keys():
            if field_name.endswith('_id') or field_name == 'id':
                id_fields.append(field_name)
            else:
                other_fields.append(field_name)

        # Format ID fields first (each on its own line with blank line after)
        for field_name in id_fields:
            value = result[field_name]
            chinese_name = self.get_chinese_name(field_name)
            formatted_value = self.format_field_value(field_name, value)
            lines.append(f"- **`{chinese_name}`**: {formatted_value}")

        # Format other fields (each on its own line)
        for field_name in sorted(other_fields):
            value = result[field_name]
            chinese_name = self.get_chinese_name(field_name)
            formatted_value = self.format_field_value(field_name, value)
            lines.append(f"- **`{chinese_name}`**: {formatted_value}")

        # Use double newlines to ensure proper line breaks in display
        return "\n\n".join(lines)

    def format_tool_results_as_markdown(self, tool_results: Dict[str, Any], intent_type: str = "") -> str:
        """
        Format multiple tool results as a single Markdown output.

        Args:
            tool_results: Dictionary of tool_name -> result
            intent_type: Intent type for title selection

        Returns:
            Markdown formatted string
        """
        if not tool_results:
            return "暂无查询结果"

        sections = []

        # Title mapping based on tool name
        tool_titles = {
            'query_customer': '客户信息',
            'query_order': '订单信息',
            'query_shipment': '物流信息',
            'query_product': '产品信息',
            'query_customer_orders': '客户订单列表',
            'query_order_items': '订单明细',
            'query_customer_statistics': '客户统计信息'
        }

        for tool_name, result in tool_results.items():
            if isinstance(result, dict):
                # Skip error results
                if result.get('error') or result.get('success') == False:
                    continue

                title = tool_titles.get(tool_name, tool_name.replace('query_', '').replace('_', ' ').title())

                # Handle list results (like customer orders)
                if 'orders' in result and isinstance(result['orders'], list):
                    sections.append(self._format_orders_list(result['orders'], title))
                elif 'items' in result and isinstance(result['items'], list):
                    sections.append(self._format_items_list(result['items'], title))
                else:
                    sections.append(self.format_result_as_markdown(result, title))

        if not sections:
            return "暂无有效查询结果"

        return "\n\n".join(sections)

    def _format_orders_list(self, orders: List[Dict], title: str) -> str:
        """Format a list of orders as Markdown."""
        lines = [f"### {title}", f"共 {len(orders)} 条记录"]

        for i, order in enumerate(orders[:10], 1):  # Limit to 10 orders
            order_id = order.get('order_id', 'N/A')
            status = order.get('order_status', 'N/A')
            date = order.get('order_date', 'N/A')
            if isinstance(date, str) and ' ' in date:
                date = date.split(' ')[0]

            lines.append(f"{i}. **订单号**: {order_id} | **状态**: {status} | **日期**: {date}")

        if len(orders) > 10:
            lines.append(f"... 还有 {len(orders) - 10} 条记录未显示")

        # Use double newlines for proper line breaks
        return "\n\n".join(lines)

    def _format_items_list(self, items: List[Dict], title: str) -> str:
        """Format a list of order items as Markdown."""
        lines = [f"### {title}", f"共 {len(items)} 条记录"]

        for i, item in enumerate(items, 1):
            # Build item details using field mapping
            item_parts = []
            for field_name, value in item.items():
                if value is not None:
                    chinese_name = self.get_chinese_name(field_name)
                    formatted_value = self.format_field_value(field_name, value)
                    item_parts.append(f"- **`{chinese_name}`**: {formatted_value}")

            lines.append(f"{i}. {' | '.join(item_parts[:4])}")  # Show first 4 fields per line

        # Use double newlines for proper line breaks
        return "\n\n".join(lines)


# Global instance
field_mapping = FieldMapping()


# Convenience functions
def get_chinese_name(field_name: str) -> str:
    """Get Chinese name for a field."""
    return field_mapping.get_chinese_name(field_name)


def format_field_value(field_name: str, value: Any) -> str:
    """Format a field value."""
    return field_mapping.format_field_value(field_name, value)


def format_result_as_markdown(result: Dict[str, Any], title: str = "查询结果") -> str:
    """Format result as Markdown."""
    return field_mapping.format_result_as_markdown(result, title)


def format_tool_results_as_markdown(tool_results: Dict[str, Any], intent_type: str = "") -> str:
    """Format multiple tool results as Markdown."""
    return field_mapping.format_tool_results_as_markdown(tool_results, intent_type)
