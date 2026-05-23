#!/usr/bin/env python3
"""
Data Loader - Unified data loading from dataset directory.

This module provides a centralized interface for loading all data
from /root/Supply-Chain-Agent/dataset/ into the system.
"""

import os
import sys
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from supply_chain_agent.data.supply_chain_db import (
    create_schema,
    import_csv_data,
    load_entity_mappings,
    load_fallback_templates,
    load_agent_config,
    get_statistics,
    get_connection
)

# Data directory (relative to project root)
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dataset")


class DataLoader:
    """Unified data loader for all data sources."""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or DATA_DIR
        self.business_data_dir = os.path.join(self.data_dir, "BusinessData")
        self.sop_data_dir = os.path.join(self.data_dir, "SOPData")
        self.other_data_dir = os.path.join(self.data_dir, "OtherData")

    def load_all(self, force: bool = False) -> Dict[str, Any]:
        """
        Load all data into the system.

        Args:
            force: If True, reload even if data already exists

        Returns:
            Summary of loaded data
        """
        results = {
            "schema": False,
            "business_data": 0,
            "entity_mappings": 0,
            "fallback_templates": 0,
            "config": 0,
            "sop_documents": 0
        }

        print("=" * 60)
        print("Supply Chain Agent - Data Initialization")
        print("=" * 60)

        # 1. Create database schema
        print("\n[1/5] Creating database schema...")
        try:
            create_schema()
            results["schema"] = True
        except Exception as e:
            print(f"  ❌ Failed to create schema: {e}")
            return results

        # 2. Load business data (CSV)
        print("\n[2/5] Loading business data...")
        csv_path = os.path.join(self.business_data_dir, "DataCoSupplyChainDataset.csv")
        if os.path.exists(csv_path):
            try:
                import_csv_data(csv_path)
                results["business_data"] = 1
            except Exception as e:
                print(f"  ❌ Failed to load business data: {e}")
        else:
            print(f"  ⚠️ CSV file not found: {csv_path}")

        # 3. Load entity mappings
        print("\n[3/5] Loading entity mappings...")
        try:
            count = load_entity_mappings()
            results["entity_mappings"] = count
        except Exception as e:
            print(f"  ❌ Failed to load entity mappings: {e}")

        # 4. Load fallback templates
        print("\n[4/5] Loading fallback templates...")
        try:
            count = load_fallback_templates()
            results["fallback_templates"] = count
        except Exception as e:
            print(f"  ❌ Failed to load fallback templates: {e}")

        # 5. Load agent config
        print("\n[5/5] Loading agent configuration...")
        try:
            count = load_agent_config()
            results["config"] = count
        except Exception as e:
            print(f"  ❌ Failed to load config: {e}")

        # Print summary
        print("\n" + "=" * 60)
        print("Data Loading Summary")
        print("=" * 60)
        print(f"  Schema created: {'✓' if results['schema'] else '✗'}")
        print(f"  Business data: {'✓' if results['business_data'] else '✗'}")
        print(f"  Entity mappings: {results['entity_mappings']} records")
        print(f"  Fallback templates: {results['fallback_templates']} records")
        print(f"  Config items: {results['config']} items")
        print("=" * 60)

        return results

    def load_sop_documents(self) -> int:
        """
        Load SOP documents into vector store.
        This is called separately after vector store is initialized.

        Returns:
            Number of documents loaded
        """
        print("\nLoading SOP documents into vector store...")

        if not os.path.exists(self.sop_data_dir):
            print(f"  ⚠️ SOP directory not found: {self.sop_data_dir}")
            return 0

        # Import vector store
        try:
            from supply_chain_agent.memory.vector_store import memory_manager
            return memory_manager.long_term.load_sop_documents(self.sop_data_dir)
        except Exception as e:
            print(f"  ❌ Failed to load SOP documents: {e}")
            import traceback
            traceback.print_exc()
            return 0

    def verify_data(self) -> Dict[str, Any]:
        """Verify that all required data is loaded."""
        print("\nVerifying data integrity...")

        stats = get_statistics()

        issues = []

        # Check required tables have data
        if stats.get('customers', 0) == 0:
            issues.append("No customers in database")
        if stats.get('orders', 0) == 0:
            issues.append("No orders in database")
        if stats.get('products', 0) == 0:
            issues.append("No products in database")

        # Check entity mappings
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM entity_mappings")
            if cursor.fetchone()[0] == 0:
                issues.append("No entity mappings loaded")

            # Check fallback templates
            cursor.execute("SELECT COUNT(*) FROM fallback_templates")
            if cursor.fetchone()[0] == 0:
                issues.append("No fallback templates loaded")

            # Check config
            cursor.execute("SELECT COUNT(*) FROM agent_config")
            if cursor.fetchone()[0] == 0:
                issues.append("No agent config loaded")

        if issues:
            print("  ⚠️ Data verification issues:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print("  ✓ All required data is loaded")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "stats": stats
        }

    def get_data_paths(self) -> Dict[str, str]:
        """Get paths to all data files."""
        return {
            "business_csv": os.path.join(self.business_data_dir, "DataCoSupplyChainDataset.csv"),
            "entity_mapping_csv": os.path.join(self.other_data_dir, "EntityMapping.csv"),
            "fallback_template_csv": os.path.join(self.other_data_dir, "FallbackResponseTemplate.csv"),
            "config_yaml": os.path.join(self.other_data_dir, "config.yaml"),
            "sop_dir": self.sop_data_dir
        }


def initialize_all_data(force: bool = False) -> Dict[str, Any]:
    """
    Initialize all data from dataset directory.

    This is the main entry point for data initialization.
    """
    loader = DataLoader()
    results = loader.load_all(force=force)
    loader.verify_data()

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize Supply Chain Agent data")
    parser.add_argument("--force", action="store_true", help="Force reload all data")
    parser.add_argument("--verify", action="store_true", help="Only verify existing data")
    parser.add_argument("--sop", action="store_true", help="Load SOP documents into vector store")

    args = parser.parse_args()

    loader = DataLoader()

    if args.verify:
        loader.verify_data()
    elif args.sop:
        loader.load_sop_documents()
    else:
        initialize_all_data(force=args.force)
        # Also load SOP documents
        print("\n" + "=" * 60)
        loader.load_sop_documents()
