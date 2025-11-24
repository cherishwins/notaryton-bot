"""
Pytest fixtures and configuration for NotaryTON tests.

This file provides shared test fixtures used across all test files.
"""

import pytest
import asyncio
import os
import tempfile
import aiosqlite
from pathlib import Path


# ========================
# Database Fixtures
# ========================

@pytest.fixture
async def test_db():
    """Create a temporary test database."""
    # Create temp database file
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_notaryton.db")
    
    # Initialize test database schema
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                subscription_expiry TIMESTAMP,
                total_paid REAL DEFAULT 0,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                referral_earnings REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notarizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                tx_hash TEXT,
                contract_hash TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                paid BOOLEAN DEFAULT 0,
                via_api BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                memo TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key TEXT PRIMARY KEY,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                requests_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.commit()
    
    yield db_path
    
    # Cleanup
    try:
        os.remove(db_path)
        os.rmdir(temp_dir)
    except:
        pass


@pytest.fixture
def sample_user_id():
    """Sample Telegram user ID for testing."""
    return 123456789


@pytest.fixture
def sample_contract_address():
    """Sample TON contract address."""
    return "EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG"


@pytest.fixture
def sample_contract_hash():
    """Sample SHA-256 hash."""
    return "a3f8b92c1e4d5678901234567890abcdef123456789abcdef0123456789"


# ========================
# File Fixtures
# ========================

@pytest.fixture
def temp_file():
    """Create a temporary file for testing file notarization."""
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, "test_document.txt")
    
    # Write sample content
    with open(file_path, 'w') as f:
        f.write("This is a test document for NotaryTON\n")
        f.write("Second line of test data\n")
    
    yield file_path
    
    # Cleanup
    try:
        os.remove(file_path)
        os.rmdir(temp_dir)
    except:
        pass


# ========================
# Mock Environment Variables
# ========================

@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("BOT_TOKEN", "123456:TEST_TOKEN")
    monkeypatch.setenv("TON_CENTER_API_KEY", "test_api_key")
    monkeypatch.setenv("TON_WALLET_SECRET", "test test test test test test test test test test test test test test test test test test test test test test test test")
    monkeypatch.setenv("SERVICE_TON_WALLET", "UQtest_wallet_address")
    monkeypatch.setenv("WEBHOOK_URL", "https://test.notaryton.com")
    monkeypatch.setenv("GROUP_IDS", "")


# ========================
# Async Event Loop
# ========================

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
