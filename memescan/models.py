"""
Data models for MemeScan.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class SafetyLevel(Enum):
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    UNKNOWN = "unknown"


@dataclass
class Token:
    """Meme coin token data."""
    address: str
    symbol: str
    name: str
    decimals: int = 9

    # Supply info
    total_supply: float = 0
    holder_count: int = 0

    # Price data
    price_usd: float = 0
    price_ton: float = 0
    price_change_24h: float = 0

    # Liquidity
    liquidity_usd: float = 0
    liquidity_ton: float = 0

    # Volume
    volume_24h_usd: float = 0

    # Metadata
    image_url: Optional[str] = None
    verified: bool = False
    created_at: Optional[datetime] = None

    # Safety analysis
    safety_level: SafetyLevel = SafetyLevel.UNKNOWN
    safety_warnings: list = field(default_factory=list)
    dev_wallet_percent: float = 0
    liquidity_locked: bool = False

    def format_price(self) -> str:
        if self.price_usd < 0.00001:
            return f"${self.price_usd:.10f}"
        elif self.price_usd < 0.01:
            return f"${self.price_usd:.6f}"
        else:
            return f"${self.price_usd:.4f}"

    def format_change(self) -> str:
        sign = "+" if self.price_change_24h >= 0 else ""
        return f"{sign}{self.price_change_24h:.1f}%"

    def safety_emoji(self) -> str:
        return {
            SafetyLevel.SAFE: "✅",
            SafetyLevel.WARNING: "⚠️",
            SafetyLevel.DANGER: "🚨",
            SafetyLevel.UNKNOWN: "❓"
        }.get(self.safety_level, "❓")


@dataclass
class Pool:
    """DEX liquidity pool."""
    address: str
    dex: str  # "stonfi" or "dedust"

    token0_address: str
    token0_symbol: str
    token1_address: str
    token1_symbol: str

    liquidity_usd: float = 0
    volume_24h: float = 0

    # Price
    token0_price_usd: float = 0
    token1_price_usd: float = 0

    # APR for LPs
    apr: float = 0

    created_at: Optional[datetime] = None


@dataclass
class WhaleMovement:
    """Large wallet transaction."""
    wallet_address: str
    token_address: str
    token_symbol: str

    action: str  # "buy" or "sell"
    amount: float
    amount_usd: float

    tx_hash: str
    timestamp: datetime

    def format_amount(self) -> str:
        if self.amount >= 1_000_000_000:
            return f"{self.amount / 1_000_000_000:.1f}B"
        elif self.amount >= 1_000_000:
            return f"{self.amount / 1_000_000:.1f}M"
        elif self.amount >= 1_000:
            return f"{self.amount / 1_000:.1f}K"
        return f"{self.amount:.0f}"


@dataclass
class NewLaunch:
    """Newly deployed token."""
    token: Token
    pool: Optional[Pool] = None

    launched_at: datetime = field(default_factory=datetime.utcnow)
    initial_liquidity: float = 0

    def age_str(self) -> str:
        delta = datetime.utcnow() - self.launched_at
        if delta.total_seconds() < 60:
            return f"{int(delta.total_seconds())}s ago"
        elif delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() / 60)}m ago"
        elif delta.total_seconds() < 86400:
            return f"{int(delta.total_seconds() / 3600)}h ago"
        return f"{delta.days}d ago"
