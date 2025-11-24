"""
Unit tests for database operations.

Tests all database functions without requiring Telegram or TON blockchain.
"""

import pytest
import aiosqlite
from datetime import datetime, timedelta


# ========================
# Database Helper Functions (copied from bot.py for testing)
# ========================

async def get_user_subscription(db_path: str, user_id: int):
    """Check if user has active subscription."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT subscription_expiry FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                expiry = datetime.fromisoformat(row[0])
                if expiry > datetime.now():
                    return True
            return False


async def add_subscription(db_path: str, user_id: int, months: int = 1):
    """Add or extend subscription."""
    expiry = datetime.now() + timedelta(days=30 * months)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT INTO users (user_id, subscription_expiry)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET subscription_expiry = ?
        """, (user_id, expiry, expiry))
        await db.commit()


async def log_notarization(db_path: str, user_id: int, tx_hash: str, contract_hash: str, paid: bool = False):
    """Log a notarization event."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT INTO notarizations (user_id, tx_hash, contract_hash, paid)
            VALUES (?, ?, ?, ?)
        """, (user_id, tx_hash, contract_hash, paid))
        await db.commit()


# ========================
# Tests
# ========================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_subscription_check_no_user(test_db, sample_user_id):
    """Test subscription check for non-existent user."""
    has_sub = await get_user_subscription(test_db, sample_user_id)
    assert has_sub == False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_and_check_subscription(test_db, sample_user_id):
    """Test adding subscription and checking it."""
    # Add subscription
    await add_subscription(test_db, sample_user_id, months=1)
    
    # Check it exists
    has_sub = await get_user_subscription(test_db, sample_user_id)
    assert has_sub == True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_expired_subscription(test_db, sample_user_id):
    """Test that expired subscriptions return False."""
    # Add expired subscription (past date)
    expiry = datetime.now() - timedelta(days=1)
    async with aiosqlite.connect(test_db) as db:
        await db.execute("""
            INSERT INTO users (user_id, subscription_expiry)
            VALUES (?, ?)
        """, (sample_user_id, expiry))
        await db.commit()
    
    # Should return False
    has_sub = await get_user_subscription(test_db, sample_user_id)
    assert has_sub == False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_log_notarization(test_db, sample_user_id, sample_contract_hash):
    """Test logging a notarization."""
    tx_hash = "test_tx_12345"
    
    # Log notarization
    await log_notarization(test_db, sample_user_id, tx_hash, sample_contract_hash, paid=True)
    
    # Verify it was logged
    async with aiosqlite.connect(test_db) as db:
        async with db.execute(
            "SELECT user_id, tx_hash, contract_hash, paid FROM notarizations WHERE user_id = ?",
            (sample_user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == sample_user_id
            assert row[1] == tx_hash
            assert row[2] == sample_contract_hash
            assert row[3] == 1  # paid=True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_referral_tracking(test_db):
    """Test referral system tracking."""
    referrer_id = 111111111
    referred_id = 222222222
    
    # Create referrer with code
    async with aiosqlite.connect(test_db) as db:
        await db.execute("""
            INSERT INTO users (user_id, referral_code)
            VALUES (?, ?)
        """, (referrer_id, f"REF{referrer_id}"))
        
        # Create referred user
        await db.execute("""
            INSERT INTO users (user_id, referred_by)
            VALUES (?, ?)
        """, (referred_id, referrer_id))
        
        await db.commit()
        
        # Verify referral link
        async with db.execute(
            "SELECT referred_by FROM users WHERE user_id = ?",
            (referred_id,)
        ) as cursor:
            row = await cursor.fetchone()
            assert row[0] == referrer_id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multiple_notarizations(test_db, sample_user_id):
    """Test logging multiple notarizations for same user."""
    hashes = ["hash1", "hash2", "hash3"]
    
    for i, h in enumerate(hashes):
        await log_notarization(test_db, sample_user_id, f"tx_{i}", h, paid=True)
    
    # Count notarizations
    async with aiosqlite.connect(test_db) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM notarizations WHERE user_id = ?",
            (sample_user_id,)
        ) as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 3
