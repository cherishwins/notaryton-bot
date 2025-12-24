"""
KOL Intelligence Models
========================
Track influencer calls and performance for the proprietary trader database.

This is the DATA MOAT that compounds value over time.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class KOL:
    """Key Opinion Leader / Influencer profile."""
    id: Optional[int] = None
    name: str = ""
    x_handle: Optional[str] = None
    telegram_handle: Optional[str] = None
    telegram_channel: Optional[str] = None

    # Classification
    chain_focus: str = "multi"  # 'ton', 'sol', 'eth', 'multi'
    category: str = "caller"  # 'caller', 'researcher', 'whale', 'dev', 'scammer'
    tier: str = "unknown"  # 'whale', 'alpha', 'mid', 'micro', 'unknown'

    # Engagement metrics
    x_followers: int = 0
    avg_likes: int = 0
    avg_views: int = 0

    # Performance (calculated from calls)
    total_calls: int = 0
    winning_calls: int = 0
    rug_calls: int = 0
    avg_return_pct: float = 0
    best_call_return: float = 0

    # Trust
    verified_wallet: bool = False
    reputation_score: int = 50  # 0-100

    # Metadata
    notes: Optional[str] = None
    source: str = "manual"  # 'manual', 'grok', 'crawler'
    first_seen: Optional[datetime] = None
    last_active: Optional[datetime] = None
    created_at: Optional[datetime] = None

    @property
    def win_rate(self) -> float:
        return round(self.winning_calls / max(self.total_calls, 1) * 100, 1)

    @property
    def rug_rate(self) -> float:
        return round(self.rug_calls / max(self.total_calls, 1) * 100, 1)


@dataclass
class KOLCall:
    """A token call/shill made by a KOL."""
    id: Optional[int] = None
    kol_id: int = 0
    token_address: Optional[str] = None
    token_symbol: str = ""
    chain: str = "ton"

    # Call details
    call_type: str = "buy"  # 'buy', 'sell', 'warning', 'shill'
    call_price_usd: float = 0
    call_mcap: float = 0

    # Source
    source_platform: str = "x"  # 'x', 'telegram', 'discord'
    source_url: Optional[str] = None
    source_text: Optional[str] = None

    # Outcome tracking
    peak_price_usd: float = 0
    peak_mcap: float = 0
    final_price_usd: float = 0
    return_pct: float = 0

    # Status
    outcome: str = "pending"  # 'pending', 'win', 'loss', 'rug'
    rugged: bool = False

    # Timing
    called_at: Optional[datetime] = None
    peak_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


@dataclass
class KOLWallet:
    """Known wallet associated with a KOL."""
    id: Optional[int] = None
    kol_id: int = 0
    wallet_address: str = ""
    chain: str = "ton"

    verified: bool = False
    verification_method: Optional[str] = None  # 'signature', 'bio', 'inference'

    total_trades: int = 0
    profitable_trades: int = 0
    total_pnl_usd: float = 0

    notes: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_active: Optional[datetime] = None


# ========================
# SQL SCHEMA
# ========================

KOL_SCHEMA = """
-- KOL Profiles
CREATE TABLE IF NOT EXISTS kols (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    x_handle VARCHAR(50),
    telegram_handle VARCHAR(50),
    telegram_channel VARCHAR(100),

    -- Classification
    chain_focus VARCHAR(20) DEFAULT 'multi',
    category VARCHAR(20) DEFAULT 'caller',
    tier VARCHAR(20) DEFAULT 'unknown',

    -- Engagement
    x_followers INTEGER DEFAULT 0,
    avg_likes INTEGER DEFAULT 0,
    avg_views INTEGER DEFAULT 0,

    -- Performance
    total_calls INTEGER DEFAULT 0,
    winning_calls INTEGER DEFAULT 0,
    rug_calls INTEGER DEFAULT 0,
    avg_return_pct DECIMAL(10, 2) DEFAULT 0,
    best_call_return DECIMAL(10, 2) DEFAULT 0,

    -- Trust
    verified_wallet BOOLEAN DEFAULT FALSE,
    reputation_score INTEGER DEFAULT 50,

    -- Metadata
    notes TEXT,
    source VARCHAR(20) DEFAULT 'manual',
    first_seen TIMESTAMP,
    last_active TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),

    -- Unique constraint on handles
    UNIQUE(x_handle),
    UNIQUE(telegram_handle)
);

-- KOL Calls (token shills/recommendations)
CREATE TABLE IF NOT EXISTS kol_calls (
    id SERIAL PRIMARY KEY,
    kol_id INTEGER REFERENCES kols(id),
    token_address VARCHAR(100),
    token_symbol VARCHAR(50) NOT NULL,
    chain VARCHAR(20) DEFAULT 'ton',

    -- Call details
    call_type VARCHAR(20) DEFAULT 'buy',
    call_price_usd DECIMAL(30, 18) DEFAULT 0,
    call_mcap DECIMAL(20, 2) DEFAULT 0,

    -- Source
    source_platform VARCHAR(20) DEFAULT 'x',
    source_url TEXT,
    source_text TEXT,

    -- Outcome
    peak_price_usd DECIMAL(30, 18) DEFAULT 0,
    peak_mcap DECIMAL(20, 2) DEFAULT 0,
    final_price_usd DECIMAL(30, 18) DEFAULT 0,
    return_pct DECIMAL(10, 2) DEFAULT 0,

    -- Status
    outcome VARCHAR(20) DEFAULT 'pending',
    rugged BOOLEAN DEFAULT FALSE,

    -- Timing
    called_at TIMESTAMP DEFAULT NOW(),
    peak_at TIMESTAMP,
    resolved_at TIMESTAMP
);

-- KOL Wallets
CREATE TABLE IF NOT EXISTS kol_wallets (
    id SERIAL PRIMARY KEY,
    kol_id INTEGER REFERENCES kols(id),
    wallet_address VARCHAR(128) NOT NULL,
    chain VARCHAR(20) DEFAULT 'ton',

    verified BOOLEAN DEFAULT FALSE,
    verification_method VARCHAR(50),

    total_trades INTEGER DEFAULT 0,
    profitable_trades INTEGER DEFAULT 0,
    total_pnl_usd DECIMAL(20, 2) DEFAULT 0,

    notes TEXT,
    first_seen TIMESTAMP,
    last_active TIMESTAMP,

    UNIQUE(wallet_address, chain)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_kols_x_handle ON kols(x_handle);
CREATE INDEX IF NOT EXISTS idx_kols_telegram ON kols(telegram_handle);
CREATE INDEX IF NOT EXISTS idx_kols_chain ON kols(chain_focus);
CREATE INDEX IF NOT EXISTS idx_kols_reputation ON kols(reputation_score DESC);

CREATE INDEX IF NOT EXISTS idx_kol_calls_kol ON kol_calls(kol_id);
CREATE INDEX IF NOT EXISTS idx_kol_calls_token ON kol_calls(token_address);
CREATE INDEX IF NOT EXISTS idx_kol_calls_outcome ON kol_calls(outcome);
CREATE INDEX IF NOT EXISTS idx_kol_calls_time ON kol_calls(called_at DESC);

CREATE INDEX IF NOT EXISTS idx_kol_wallets_kol ON kol_wallets(kol_id);
CREATE INDEX IF NOT EXISTS idx_kol_wallets_address ON kol_wallets(wallet_address);
"""


# ========================
# SEED DATA FROM GROK
# ========================

GROK_KOL_SEED = [
    # TON-focused KOLs
    {
        "name": "TON Blockchain Official",
        "x_handle": "ton_blockchain",
        "telegram_channel": "@TONmemelandia",
        "chain_focus": "ton",
        "category": "official",
        "tier": "whale",
        "notes": "Official TON voice, drops meme launchpad alphas",
        "source": "grok"
    },
    {
        "name": "WizCalls",
        "x_handle": "WizCalls",
        "telegram_channel": "@Wizzzzcalls",
        "chain_focus": "multi",
        "category": "caller",
        "tier": "alpha",
        "avg_likes": 152,
        "avg_views": 16000,
        "best_call_return": 112.0,  # $PNUT 112x
        "notes": "Full-time hunter, 112x on $PNUT",
        "source": "grok"
    },
    {
        "name": "Pump Research",
        "x_handle": "pumpresearch",
        "chain_focus": "ton",
        "category": "researcher",
        "tier": "alpha",
        "notes": "TON meme researcher, spots undiscovered gems",
        "source": "grok"
    },
    {
        "name": "ZenithTON",
        "x_handle": "ZenithTON",
        "telegram_channel": "@TONmemelandia",
        "chain_focus": "ton",
        "category": "caller",
        "tier": "alpha",
        "avg_likes": 2705,
        "avg_views": 91000,
        "notes": "TON NFT lead, audio tokens",
        "source": "grok"
    },
    {
        "name": "TON Fish",
        "x_handle": "tonfish_tg",
        "telegram_channel": "@tonfish_tg",
        "chain_focus": "ton",
        "category": "caller",
        "tier": "mid",
        "avg_likes": 686,
        "avg_views": 74000,
        "notes": "TON's first social meme token",
        "source": "grok"
    },
    {
        "name": "CryptoSanthoshK",
        "x_handle": "cryptosanthoshK",
        "telegram_channel": "Cks call & pumpfun cabal",
        "chain_focus": "ton",
        "category": "caller",
        "tier": "mid",
        "avg_views": 35000,
        "notes": "Crypto king, TON airdrops",
        "source": "grok"
    },
    {
        "name": "TON Insights",
        "x_handle": "ton_insi",
        "chain_focus": "ton",
        "category": "researcher",
        "tier": "mid",
        "avg_likes": 129,
        "avg_views": 6000,
        "notes": "Meme wave forecasts, launchpad intel",
        "source": "grok"
    },
    {
        "name": "Precursor KOLS",
        "x_handle": "precurkols",
        "telegram_channel": "@COCOONONTON",
        "chain_focus": "ton",
        "category": "caller",
        "tier": "mid",
        "notes": "TON ambassador, Cocoon AI",
        "source": "grok"
    },
    # Solana-focused KOLs
    {
        "name": "Wolf of Crypto",
        "x_handle": "W0LF0FCRYPT0",
        "chain_focus": "sol",
        "category": "researcher",
        "tier": "alpha",
        "avg_likes": 460,
        "avg_views": 45000,
        "notes": "Raw degen mastermind, calls out pumpfun rugs",
        "source": "grok"
    },
    {
        "name": "Kadense (Bonk)",
        "x_handle": "iamkadense",
        "telegram_channel": "@bonk_inu",
        "chain_focus": "sol",
        "category": "dev",
        "tier": "whale",
        "avg_likes": 307,
        "avg_views": 14000,
        "notes": "Bonk core contributor, exposes pump tanks",
        "source": "grok"
    },
    {
        "name": "MASTR",
        "x_handle": "MastrXYZ",
        "chain_focus": "sol",
        "category": "researcher",
        "tier": "alpha",
        "avg_likes": 452,
        "avg_views": 31000,
        "notes": "OG watchdog, 98% Sol rugs exposed",
        "source": "grok"
    },
    {
        "name": "Flocko (Trove CIO)",
        "x_handle": "flocko",
        "telegram_channel": "@trovemarkets",
        "chain_focus": "sol",
        "category": "researcher",
        "tier": "whale",
        "avg_likes": 322,
        "avg_views": 60000,
        "notes": "Roasts influencers, tracks batting averages",
        "source": "grok"
    },
    {
        "name": "Wizard of Soho",
        "x_handle": "wizardofsoho",
        "chain_focus": "sol",
        "category": "researcher",
        "tier": "whale",
        "avg_likes": 1000,
        "avg_views": 96000,
        "notes": "Weekly Wizdom founder, calls pump presales",
        "source": "grok"
    },
    # Multi-chain callers
    {
        "name": "True Gem Hunter",
        "x_handle": "TrueGemHunter",
        "telegram_channel": "GEM HUNTERS",
        "chain_focus": "multi",
        "category": "caller",
        "tier": "alpha",
        "avg_likes": 200,
        "notes": "$NOWAI 50K to 650K, spots 5-30x gems",
        "source": "grok"
    },
    {
        "name": "Self Success Saga",
        "x_handle": "SelfSuccessSaga",
        "chain_focus": "multi",
        "category": "caller",
        "tier": "alpha",
        "notes": "Turned $800 to $3.1M, 32x plays from 9K MC",
        "source": "grok"
    },
    {
        "name": "Dr Profit Crypto",
        "x_handle": "DrProfitCrypto",
        "chain_focus": "multi",
        "category": "caller",
        "tier": "alpha",
        "avg_likes": 653,
        "notes": "Elite x100 caller, premium signals",
        "source": "grok"
    },
    {
        "name": "Degen Meme Calls",
        "x_handle": "DegenMemeCalls",
        "chain_focus": "sol",
        "category": "caller",
        "tier": "mid",
        "avg_views": 50,
        "notes": "Hourly Sol pumps, copy trade wallets",
        "source": "grok"
    },
]
