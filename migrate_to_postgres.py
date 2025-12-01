#!/usr/bin/env python3
"""
Migration Script: SQLite to PostgreSQL (Neon)
==============================================

This script migrates all data from the existing SQLite database
to the new PostgreSQL database on Neon.

Usage:
    1. Set DATABASE_URL environment variable with your Neon connection string
    2. Run: python migrate_to_postgres.py

The script will:
    - Connect to both databases
    - Create the PostgreSQL schema (if not exists)
    - Migrate all data from SQLite tables
    - Report progress and any errors
"""

import asyncio
import os
import sys
from datetime import datetime

import aiosqlite
import asyncpg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
SQLITE_PATH = "notaryton.db"
DATABASE_URL = os.getenv("DATABASE_URL")

# Table migration order (respects foreign key constraints)
TABLES = ["users", "notarizations", "pending_payments", "api_keys", "bot_state"]


async def migrate():
    """Main migration function"""
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL environment variable not set!")
        print("Please set it to your Neon PostgreSQL connection string.")
        print("Example: postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require")
        sys.exit(1)

    if not os.path.exists(SQLITE_PATH):
        print(f"ERROR: SQLite database not found at {SQLITE_PATH}")
        print("Nothing to migrate.")
        sys.exit(1)

    print("=" * 60)
    print("NotaryTON Database Migration: SQLite -> PostgreSQL (Neon)")
    print("=" * 60)
    print()

    # Connect to PostgreSQL
    print("Connecting to PostgreSQL...")
    try:
        pg_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            ssl='require' if 'neon' in DATABASE_URL.lower() else 'prefer'
        )
        print("  PostgreSQL connected!")
    except Exception as e:
        print(f"  ERROR: Failed to connect to PostgreSQL: {e}")
        sys.exit(1)

    # Connect to SQLite
    print("Connecting to SQLite...")
    try:
        sqlite_db = await aiosqlite.connect(SQLITE_PATH)
        sqlite_db.row_factory = aiosqlite.Row
        print("  SQLite connected!")
    except Exception as e:
        print(f"  ERROR: Failed to connect to SQLite: {e}")
        sys.exit(1)

    print()
    print("Creating PostgreSQL schema...")

    async with pg_pool.acquire() as conn:
        # Create tables
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                subscription_expiry TIMESTAMP,
                total_paid DECIMAL(20, 8) DEFAULT 0,
                referral_code VARCHAR(20) UNIQUE,
                referred_by BIGINT,
                referral_earnings DECIMAL(20, 8) DEFAULT 0,
                total_withdrawn DECIMAL(20, 8) DEFAULT 0,
                withdrawal_wallet VARCHAR(100),
                language VARCHAR(10) DEFAULT 'en',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS notarizations (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                tx_hash VARCHAR(100),
                contract_hash VARCHAR(64) NOT NULL,
                timestamp TIMESTAMP DEFAULT NOW(),
                paid BOOLEAN DEFAULT FALSE,
                via_api BOOLEAN DEFAULT FALSE
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_payments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                amount DECIMAL(20, 8),
                memo VARCHAR(200),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key VARCHAR(64) PRIMARY KEY,
                user_id BIGINT,
                created_at TIMESTAMP DEFAULT NOW(),
                last_used TIMESTAMP,
                requests_count INTEGER DEFAULT 0
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_state (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT
            )
        """)

        # Create indexes
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notarizations_user_id
            ON notarizations(user_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notarizations_contract_hash
            ON notarizations(contract_hash)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notarizations_timestamp
            ON notarizations(timestamp DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_referral_code
            ON users(referral_code)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_referred_by
            ON users(referred_by)
        """)

    print("  Schema created!")
    print()

    # Migrate each table
    total_migrated = 0
    errors = []

    for table in TABLES:
        print(f"Migrating table: {table}")

        try:
            # Get row count from SQLite
            async with sqlite_db.execute(f"SELECT COUNT(*) FROM {table}") as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0

            if count == 0:
                print(f"  No data to migrate (0 rows)")
                continue

            print(f"  Found {count} rows")

            # Fetch all data from SQLite
            async with sqlite_db.execute(f"SELECT * FROM {table}") as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]

            # Insert into PostgreSQL
            migrated = 0
            async with pg_pool.acquire() as conn:
                for row in rows:
                    try:
                        # Build INSERT statement
                        placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
                        insert_sql = f"""
                            INSERT INTO {table} ({", ".join(columns)})
                            VALUES ({placeholders})
                            ON CONFLICT DO NOTHING
                        """

                        # Convert row to list and handle None values
                        values = []
                        for i, val in enumerate(row):
                            col = columns[i]
                            if val is None:
                                values.append(None)
                            elif col in ['subscription_expiry', 'created_at', 'timestamp', 'last_used']:
                                # Convert datetime strings
                                if isinstance(val, str):
                                    try:
                                        values.append(datetime.fromisoformat(val))
                                    except ValueError:
                                        values.append(None)
                                else:
                                    values.append(val)
                            elif col in ['paid', 'via_api']:
                                # Convert boolean
                                values.append(bool(val))
                            else:
                                values.append(val)

                        await conn.execute(insert_sql, *values)
                        migrated += 1
                    except Exception as e:
                        errors.append(f"  Error inserting row in {table}: {e}")

            print(f"  Migrated {migrated}/{count} rows")
            total_migrated += migrated

        except Exception as e:
            errors.append(f"Error migrating table {table}: {e}")
            print(f"  ERROR: {e}")

    # Close connections
    await sqlite_db.close()
    await pg_pool.close()

    # Summary
    print()
    print("=" * 60)
    print("Migration Complete!")
    print("=" * 60)
    print(f"Total rows migrated: {total_migrated}")

    if errors:
        print()
        print("Errors encountered:")
        for error in errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")
    else:
        print("No errors!")

    print()
    print("Next steps:")
    print("  1. Verify the migration by checking your Neon dashboard")
    print("  2. Update your bot to use DATABASE_URL")
    print("  3. Test the bot to ensure everything works")
    print("  4. (Optional) Backup and remove the SQLite file")
    print()


if __name__ == "__main__":
    asyncio.run(migrate())
