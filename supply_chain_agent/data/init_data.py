#!/usr/bin/env python3
"""
Data Initialization Script for Supply Chain Agent.

This script initializes all data from /root/Supply-Chain-Agent/dataset/
into the database and vector store.

Usage:
    python -m supply_chain_agent.data.init_data
    python -m supply_chain_agent.data.init_data --force  # Force reload
    python -m supply_chain_agent.data.init_data --verify  # Only verify
"""

import argparse
import sys
import os

# Ensure the package can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from supply_chain_agent.data.data_loader import DataLoader, initialize_all_data


def main():
    parser = argparse.ArgumentParser(
        description="Initialize Supply Chain Agent data from dataset directory"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reload all data even if already exists"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Only verify existing data without loading"
    )
    parser.add_argument(
        "--sop-only",
        action="store_true",
        help="Only load SOP documents into vector store"
    )

    args = parser.parse_args()

    loader = DataLoader()

    if args.verify:
        print("=" * 60)
        print("Verifying existing data...")
        print("=" * 60)
        result = loader.verify_data()
        if result["valid"]:
            print("\n✅ All data is properly loaded")
            sys.exit(0)
        else:
            print("\n❌ Data verification failed:")
            for issue in result["issues"]:
                print(f"  - {issue}")
            sys.exit(1)

    if args.sop_only:
        print("=" * 60)
        print("Loading SOP documents only...")
        print("=" * 60)
        count = loader.load_sop_documents()
        if count > 0:
            print(f"\n✅ Loaded {count} SOP document chunks")
            sys.exit(0)
        else:
            print("\n❌ Failed to load SOP documents")
            sys.exit(1)

    # Full initialization
    print("=" * 60)
    print("Supply Chain Agent - Full Data Initialization")
    print("=" * 60)
    print("\nThis will:")
    print("  1. Create database schema")
    print("  2. Import business data from CSV")
    print("  3. Load entity mappings")
    print("  4. Load fallback response templates")
    print("  5. Load agent configuration")
    print("  6. Load SOP documents into vector store")
    print()

    results = initialize_all_data(force=args.force)

    # Also load SOP documents
    print("\n" + "=" * 60)
    print("Loading SOP documents into vector store...")
    print("=" * 60)
    sop_count = loader.load_sop_documents()

    # Final verification
    print("\n" + "=" * 60)
    print("Final Verification")
    print("=" * 60)
    verify_result = loader.verify_data()

    if verify_result["valid"]:
        print("\n✅ Data initialization completed successfully!")
        print(f"   - Business data loaded")
        print(f"   - Entity mappings loaded")
        print(f"   - Fallback templates loaded")
        print(f"   - Agent config loaded")
        print(f"   - SOP documents: {sop_count} chunks")
        sys.exit(0)
    else:
        print("\n⚠️ Data initialization completed with issues:")
        for issue in verify_result["issues"]:
            print(f"  - {issue}")
        sys.exit(1)


if __name__ == "__main__":
    main()
