"""
MemeSeal TON - Payment Memo Utilities
Generate unique memos for TON payments
"""
import random
import string
import time


# Reverse lookup: memo -> user_id
payment_memo_lookup = {}  # key: memo, value: {"user_id": int, "timestamp": float}


def generate_payment_memo(user_id: int) -> str:
    """Generate a unique, short memo for TON payments like SEAL-A7B3"""
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(chars, k=4))
    return f"SEAL-{suffix}"


def register_memo(memo: str, user_id: int) -> None:
    """Register a memo for reverse lookup"""
    payment_memo_lookup[memo] = {
        "user_id": user_id,
        "timestamp": time.time()
    }


def get_user_from_memo(memo: str) -> int | None:
    """Get user_id from memo, or None if not found/expired"""
    data = payment_memo_lookup.get(memo)
    if data:
        return data["user_id"]
    return None


def cleanup_expired_memos(max_age_seconds: int = 600) -> int:
    """Remove expired memo entries. Returns count of removed entries."""
    now = time.time()
    expired_memos = [memo for memo, data in payment_memo_lookup.items()
                     if now - data["timestamp"] > max_age_seconds]
    for memo in expired_memos:
        del payment_memo_lookup[memo]
    return len(expired_memos)
