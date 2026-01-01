#!/usr/bin/env python3
"""
Import ton-labels data into notaryton's known_wallets table.

This script migrates 2,958 labeled addresses from the ton-labels dataset
into notaryton's PostgreSQL database for enhanced rug score detection.

Usage:
    python scripts/import_ton_labels.py

The script connects to the same PostgreSQL database used by notaryton-bot.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg

# Load from .env if dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


async def import_labels():
    """Import ton-labels into known_wallets table."""

    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Set it or create a .env file with DATABASE_URL=...")
        return

    # Load the ton-labels data
    labels_path = Path(__file__).parent / "ton-labels-compiled.json"
    if not labels_path.exists():
        print(f"ERROR: {labels_path} not found")
        print("Copy ton-labels-compiled.json from creative-hub/data/")
        return

    with open(labels_path) as f:
        data = json.load(f)

    print(f"Loaded {data['total']} addresses from ton-labels")
    print(f"Stats: {json.dumps(data['stats'], indent=2)}")

    # Connect to PostgreSQL
    print(f"\nConnecting to database...")
    conn = await asyncpg.connect(database_url, ssl='require')

    # Ensure table exists
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS known_wallets (
            address VARCHAR(66) PRIMARY KEY,
            label VARCHAR(50) NOT NULL,
            owner_name VARCHAR(200),
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_known_wallets_label
        ON known_wallets(label)
    """)

    # Import addresses
    imported = 0
    skipped = 0

    for address, info in data['addresses'].items():
        # Map ton-labels structure to notaryton structure
        label = info.get('category', 'unknown')
        owner_name = info.get('label') or info.get('organization', '')

        # Build notes from extra info
        notes_data = {
            'website': info.get('website'),
            'subcategory': info.get('subcategory'),
            'description': info.get('description'),
            'tags': info.get('tags', []),
            'source': 'ton-labels'
        }
        # Remove empty values
        notes_data = {k: v for k, v in notes_data.items() if v}
        notes = json.dumps(notes_data) if notes_data else None

        try:
            await conn.execute("""
                INSERT INTO known_wallets (address, label, owner_name, notes)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (address) DO UPDATE SET
                    label = $2,
                    owner_name = COALESCE($3, known_wallets.owner_name),
                    notes = COALESCE($4, known_wallets.notes)
            """, address, label, owner_name, notes)
            imported += 1
        except Exception as e:
            print(f"  Error importing {address}: {e}")
            skipped += 1

        # Progress indicator
        if imported % 500 == 0:
            print(f"  Imported {imported} addresses...")

    await conn.close()

    print(f"\n✅ Import complete!")
    print(f"   Imported: {imported}")
    print(f"   Skipped: {skipped}")
    print(f"   Total: {data['total']}")

    # Verification query suggestion
    print(f"\nTo verify, run:")
    print(f"  SELECT label, COUNT(*) FROM known_wallets GROUP BY label ORDER BY COUNT(*) DESC;")


if __name__ == "__main__":
    asyncio.run(import_labels())
