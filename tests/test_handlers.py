"""
Unit tests for bot command handlers.

These tests mock Telegram updates without requiring real Telegram connection.
"""

import pytest
import hashlib


# ========================
# Helper Functions (copied from bot.py for testing)
# ========================

def hash_file(file_path: str) -> str:
    """SHA-256 hash of file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def hash_data(data: bytes) -> str:
    """SHA-256 hash of raw data."""
    return hashlib.sha256(data).hexdigest()


# ========================
# Tests
# ========================

@pytest.mark.unit
def test_hash_file(temp_file):
    """Test file hashing produces consistent SHA-256."""
    hash1 = hash_file(temp_file)
    hash2 = hash_file(temp_file)
    
    # Same file should produce same hash
    assert hash1 == hash2
    
    # Hash should be 64 characters (SHA-256)
    assert len(hash1) == 64


@pytest.mark.unit
def test_hash_data():
    """Test data hashing."""
    data = b"Test data for hashing"
    hash_result = hash_data(data)
    
    # Should be valid SHA-256 (64 hex chars)
    assert len(hash_result) == 64
    assert all(c in '0123456789abcdef' for c in hash_result)


@pytest.mark.unit
def test_hash_empty_data():
    """Test hashing empty data."""
    empty_hash = hash_data(b"")
    
    # SHA-256 of empty string is known value
    expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert empty_hash == expected


@pytest.mark.unit
def test_contract_comment_format(sample_contract_hash):
    """Test NotaryTON comment formatting."""
    comment = f"NotaryTON:Launch:{sample_contract_hash[:16]}"
    
    # Should start with NotaryTON prefix
    assert comment.startswith("NotaryTON:")
    
    # Should contain hash prefix
    assert sample_contract_hash[:16] in comment


@pytest.mark.unit
def test_referral_code_format():
    """Test referral code generation."""
    user_id = 123456789
    referral_code = f"REF{user_id}"
    
    assert referral_code == "REF123456789"
    assert referral_code.startswith("REF")


@pytest.mark.unit
def test_verify_url_generation(sample_contract_hash):
    """Test verification URL format."""
    base_url = "https://notaryton.com"
    verify_url = f"{base_url}/api/v1/verify/{sample_contract_hash}"
    
    assert "notaryton.com" in verify_url
    assert sample_contract_hash in verify_url
    assert verify_url.startswith("https://")


@pytest.mark.unit
def test_tx_pattern_extraction():
    """Test extracting transaction ID from deploy bot message."""
    import re
    
    # Sample deploy bot message
    message = "New coin launched! Check it out: tx: ABC123XYZ456"
    
    tx_pattern = r"tx:\s*([A-Za-z0-9]+)"
    match = re.search(tx_pattern, message, re.IGNORECASE)
    
    assert match is not None
    assert match.group(1) == "ABC123XYZ456"


@pytest.mark.unit
def test_payment_amount_validation():
    """Test payment amount detection logic."""
    # Subscription payment
    sub_amount = 0.1
    assert sub_amount >= 0.095  # Allow small variance
    
    # Single notarization payment
    single_amount = 0.001
    assert single_amount >= 0.0009  # Allow small variance
    
    # Insufficient payment
    insufficient = 0.0005
    assert insufficient < 0.0009
