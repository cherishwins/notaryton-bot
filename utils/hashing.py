"""
MemeSeal TON - Hashing Utilities
SHA-256 hashing for files and data
"""
import hashlib


def hash_file(file_path: str) -> str:
    """SHA-256 hash of file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def hash_data(data: bytes) -> str:
    """SHA-256 hash of raw data"""
    return hashlib.sha256(data).hexdigest()
