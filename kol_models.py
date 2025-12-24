"""
KOL Intelligence Models
========================
Track influencer calls and performance for the proprietary trader database.

This is the DATA MOAT that compounds value over time.
82 KOLs seeded from Grok intel - multi-chain, multi-language coverage.
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
    telegram: Optional[str] = None  # Direct channel/group link
    telegram_note: Optional[str] = None  # Notes about TG access

    # Classification
    chain_focus: str = "multi"  # JSON array stored as string: '["ton","sol"]'
    category: str = "general"  # 'general', 'ton', 'solana', 'watchdog', 'regional', 'cross_chain'
    tier: str = "unknown"  # 'whale', 'alpha', 'mid', 'micro', 'unknown'
    language: str = "en"  # Primary language: en, ru, zh, hi, ar, es, fr, de, ko, pt, id, vi, th, fa, uk, pl, nl, it, sv

    # Engagement metrics
    x_followers: int = 0
    avg_likes: int = 0
    avg_views: int = 0
    engagement: Optional[str] = None  # Raw engagement description

    # Performance (calculated from calls)
    total_calls: int = 0
    winning_calls: int = 0
    rug_calls: int = 0
    avg_return_pct: float = 0
    best_call_return: float = 0

    # Trust
    verified: bool = False  # Official/verified account
    verified_wallet: bool = False
    reputation_score: int = 50  # 0-100

    # Intel
    edge: Optional[str] = None  # What makes them valuable
    win_play: Optional[str] = None  # How to leverage for notaryton

    # Metadata
    notes: Optional[str] = None
    source: str = "grok"  # 'manual', 'grok', 'crawler'
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
    name VARCHAR(100),
    x_handle VARCHAR(50),
    telegram VARCHAR(100),
    telegram_note TEXT,

    -- Classification
    chain_focus JSONB DEFAULT '["multi"]',
    category VARCHAR(30) DEFAULT 'general',
    tier VARCHAR(20) DEFAULT 'unknown',
    language VARCHAR(10) DEFAULT 'en',

    -- Engagement
    x_followers INTEGER DEFAULT 0,
    avg_likes INTEGER DEFAULT 0,
    avg_views INTEGER DEFAULT 0,
    engagement TEXT,

    -- Performance
    total_calls INTEGER DEFAULT 0,
    winning_calls INTEGER DEFAULT 0,
    rug_calls INTEGER DEFAULT 0,
    avg_return_pct DECIMAL(10, 2) DEFAULT 0,
    best_call_return DECIMAL(10, 2) DEFAULT 0,

    -- Trust
    verified BOOLEAN DEFAULT FALSE,
    verified_wallet BOOLEAN DEFAULT FALSE,
    reputation_score INTEGER DEFAULT 50,

    -- Intel
    edge TEXT,
    win_play TEXT,

    -- Metadata
    notes TEXT,
    source VARCHAR(20) DEFAULT 'grok',
    first_seen TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),

    -- Unique constraint on handles
    UNIQUE(x_handle)
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
CREATE INDEX IF NOT EXISTS idx_kols_category ON kols(category);
CREATE INDEX IF NOT EXISTS idx_kols_language ON kols(language);
CREATE INDEX IF NOT EXISTS idx_kols_chain_focus ON kols USING GIN(chain_focus);
CREATE INDEX IF NOT EXISTS idx_kols_reputation ON kols(reputation_score DESC);
CREATE INDEX IF NOT EXISTS idx_kols_verified ON kols(verified);

CREATE INDEX IF NOT EXISTS idx_kol_calls_kol ON kol_calls(kol_id);
CREATE INDEX IF NOT EXISTS idx_kol_calls_token ON kol_calls(token_address);
CREATE INDEX IF NOT EXISTS idx_kol_calls_outcome ON kol_calls(outcome);
CREATE INDEX IF NOT EXISTS idx_kol_calls_time ON kol_calls(called_at DESC);

CREATE INDEX IF NOT EXISTS idx_kol_wallets_kol ON kol_wallets(kol_id);
CREATE INDEX IF NOT EXISTS idx_kol_wallets_address ON kol_wallets(wallet_address);
"""


# ========================
# 82 KOLs FROM GROK INTEL
# ========================

GROK_KOL_SEED = [
    # ==================== GENERAL MULTI-CHAIN ====================
    {
        "x_handle": "TrueGemHunter",
        "telegram": "@GEM_HUNTERS",
        "category": "general",
        "chain_focus": ["sol", "ton"],
        "language": "en",
        "edge": "Calls bottom entries like $NOWAI 50K→650K ATH, 5-30x gems",
        "engagement": "200+ likes per call, 10k+ subs",
        "win_play": "Free notary for their gems, tap subs for virality"
    },
    {
        "x_handle": "SelfSuccessSaga",
        "telegram": "@SelfSuccessSaga",
        "category": "general",
        "chain_focus": ["sol"],
        "language": "en",
        "edge": "$800→$3.1M, 32x plays from 9K MC",
        "engagement": "2k+ degens per thread",
        "win_play": "Cross-promote seals, remix broke-to-Lambo narrative"
    },
    {
        "x_handle": "DrProfitCrypto",
        "telegram_note": "Premium via Whop",
        "category": "general",
        "chain_focus": ["btc", "alts"],
        "language": "en",
        "edge": "Elite x100 caller, 4 traders, 653 likes/post",
        "win_play": "SealBet on their calls, correlate psych reads"
    },
    {
        "x_handle": "WizCalls",
        "telegram": "@Wizzzzcalls",
        "category": "general",
        "chain_focus": ["sol", "ton"],
        "language": "en",
        "edge": "Full-time hunter, 112x on $PNUT, 152 likes/16k views",
        "best_call_return": 112.0,
        "win_play": "Early seed their calls, atomic party on 51x"
    },
    {
        "x_handle": "FASHAKING3",
        "telegram": "@FASHAKING3",
        "category": "general",
        "chain_focus": ["sol", "ton"],
        "language": "en",
        "edge": "Unfiltered alpha, on-chain plays",
        "win_play": "Invite to test notary scores"
    },
    {
        "x_handle": "don3x_1",
        "telegram_note": "DM for access",
        "category": "general",
        "chain_focus": ["defi"],
        "language": "en",
        "edge": "Daily alpha, 344 likes, 48k+ views",
        "avg_likes": 344,
        "avg_views": 48000,
        "win_play": "DM collab, bio-mimicry insights"
    },
    {
        "x_handle": "Mr_insider0",
        "telegram_note": "DM to join alpha group",
        "category": "general",
        "chain_focus": ["memes"],
        "language": "en",
        "edge": "8-fig trader, early calls",
        "win_play": "Insurance integration"
    },
    {
        "x_handle": "n8333n",
        "telegram": "@MizzMiamiLounge",
        "category": "general",
        "chain_focus": ["sol"],
        "language": "en",
        "edge": "10x-50x calls, 389x returns tracked",
        "best_call_return": 389.0,
        "win_play": "Auto-notary badges for ranked gems"
    },
    {
        "x_handle": "moki_solanaa",
        "telegram_note": "Limited free channel",
        "category": "general",
        "chain_focus": ["sol", "ton"],
        "language": "en",
        "edge": "Degen caller, 210 likes, 19k views",
        "avg_likes": 210,
        "avg_views": 19000,
        "win_play": "Free seals for investments"
    },
    {
        "x_handle": "JeremyDowells",
        "telegram": "@JeremyDowells",
        "category": "general",
        "chain_focus": ["memes"],
        "language": "en",
        "edge": "TA charts, meme consultant, $GIGGLE calls",
        "win_play": "Trading comps use notary proofs"
    },
    {
        "x_handle": "Mr_Jay_Pee",
        "telegram": "@MrJayPee",
        "category": "general",
        "chain_focus": ["web3", "airdrops"],
        "language": "en",
        "edge": "Airdrop hunter, 237 likes, 43k views",
        "avg_likes": 237,
        "avg_views": 43000,
        "win_play": "Seal their airdrops"
    },
    {
        "x_handle": "ThePepeARMY",
        "telegram_note": "Early calls channel",
        "category": "general",
        "chain_focus": ["memes"],
        "language": "en",
        "edge": "Meme army, 10x-100x like $FWOG",
        "win_play": "Army tests SealBet"
    },
    {
        "x_handle": "CryptoExpert101",
        "telegram_note": "Monitors 7+ TG callers",
        "category": "general",
        "chain_focus": ["bnb"],
        "language": "en",
        "edge": "BNB maxi, tracks TG groups",
        "win_play": "Track their trackers"
    },
    {
        "x_handle": "bitcoin_gems1",
        "telegram_note": "60k community, DM for access",
        "category": "general",
        "chain_focus": ["multi"],
        "language": "en",
        "edge": "Gem influencer, promo DMs",
        "engagement": "60k community",
        "win_play": "DM collab"
    },
    {
        "x_handle": "blockheadd5",
        "telegram_note": "Promo DMs, @RapChainAi ties",
        "category": "general",
        "chain_focus": ["multi"],
        "language": "en",
        "edge": "100x calls like $MDOGS, army partnerships",
        "win_play": "Promo swap"
    },
    {
        "x_handle": "xTrigger_pro",
        "telegram": "@xTrigger_pro",
        "category": "general",
        "chain_focus": ["sol", "ton"],
        "language": "en",
        "edge": "Bot analytics, meme trading",
        "win_play": "Integrate snipers with crawler"
    },

    # ==================== TON ECOSYSTEM ====================
    {
        "x_handle": "ton_blockchain",
        "telegram": "@TONmemelandia",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "Official TON, $35M peak MCs, 100k+ views",
        "verified": True,
        "avg_views": 100000,
        "win_play": "Seed seals in launchpads, tap 900M TG users"
    },
    {
        "x_handle": "tonstakers",
        "telegram": "@tonstakers",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "Liquid staking, spotlights builders",
        "win_play": "Builders seal via notaryton"
    },
    {
        "x_handle": "s0meone_u_know",
        "telegram_note": "TON Ecosystem AMAs",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "TON marketing lead, Catizen/Hamster millions",
        "win_play": "SealBet for onboarded millions"
    },
    {
        "x_handle": "precursorkols",
        "telegram": "@COCOONONTON",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "TON ambassador, calls bottoms on Cocoon/TCAT",
        "win_play": "Notary badges on calls"
    },
    {
        "x_handle": "hotdao_",
        "telegram": "@hotdao_",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "TON wallet devs, TON PUMP launchpad",
        "win_play": "Auto-seal their pads"
    },
    {
        "x_handle": "pumpresearch",
        "telegram": "@pumpresearch",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "TON meme researcher, undiscovered tickers",
        "win_play": "Data fusion with crawler"
    },
    {
        "x_handle": "cryptosanthoshK",
        "telegram": "@CKScall",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "Crypto king, 350$+ airdrops, 35k views",
        "avg_views": 35000,
        "win_play": "Seal airdrops, atomic-snipe rewards"
    },
    {
        "x_handle": "AnonVee_",
        "telegram_note": "Contributor networks",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "Narrative shaper, 79k views on hype falls",
        "avg_views": 79000,
        "win_play": "Notary proofs on insights"
    },
    {
        "x_handle": "ton_insi",
        "telegram": "@ton_insi",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "TON insights, meme wave forecasts, 6k views",
        "avg_views": 6000,
        "win_play": "Forecasts seal via notaryton"
    },
    {
        "x_handle": "BalaiBB",
        "telegram_note": "TON brethren chats",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "TON tech advocate, 39k views",
        "avg_views": 39000,
        "win_play": "Followers grind notary tools"
    },
    {
        "x_handle": "jacobweb3club",
        "telegram_note": "NFT/meme club communities",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "TON NFT maestro, Plush Pepes seasons",
        "win_play": "Empires seal memes"
    },
    {
        "x_handle": "cryptogems555",
        "telegram": "@TONCOINMAINCHAT",
        "category": "ton",
        "chain_focus": ["ton", "sol"],
        "language": "en",
        "edge": "TON promo king, low MC bangers, doxxed devs",
        "win_play": "Cross-chain notary"
    },
    {
        "x_handle": "tomek1044",
        "telegram_note": "Meme communities",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "TON meme caller, Tonio vibes",
        "win_play": "Early seed their vibes"
    },
    {
        "x_handle": "zolozeth",
        "telegram": "@toga_coin",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "TON meme pumper, $TOGA retro gains",
        "win_play": "Insurance on their bosses"
    },
    {
        "x_handle": "evokein",
        "telegram_note": "TON Foundation ties",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "Founder vibes, @memeslabxyz backers, 142 likes",
        "avg_likes": 142,
        "win_play": "Seal their lab launches"
    },
    {
        "x_handle": "ZenithTON",
        "telegram": "@TONmemelandia",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "TON NFT lead, 2705 likes, 91k views",
        "avg_likes": 2705,
        "avg_views": 91000,
        "win_play": "Calls get notary badges"
    },
    {
        "x_handle": "tonfish_tg",
        "telegram": "@tonfish_tg",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "First social meme token, 686 likes, 74k views",
        "avg_likes": 686,
        "avg_views": 74000,
        "win_play": "Drops seal via notaryton"
    },
    {
        "x_handle": "tdmilky",
        "telegram_note": "Trench networks",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "Roasts KOLs, notes TG wallet, 197 likes",
        "avg_likes": 197,
        "win_play": "Roasts get notary proofs"
    },
    {
        "x_handle": "mbexbt",
        "telegram_note": "CLOWN communities",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "$CLOWN hype, 124 likes, 15k views",
        "avg_likes": 124,
        "avg_views": 15000,
        "win_play": "Takeovers seal risks"
    },
    {
        "x_handle": "iamalexthugart",
        "telegram": "@dictatorcrypt",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "TonDictatorCrypto, proclaims TON ownership",
        "win_play": "Visions get insurance"
    },
    {
        "x_handle": "3orovik",
        "telegram_note": "OG networks",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "Early TON meme caller, $REDO, 222 likes",
        "avg_likes": 222,
        "win_play": "Equivalents seal risks"
    },
    {
        "x_handle": "_zeldr1ss",
        "telegram_note": "Trench networks",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "Roasts TON KOLs, 191 likes, 46k views",
        "avg_likes": 191,
        "avg_views": 46000,
        "win_play": "Worths get notary badges"
    },
    {
        "x_handle": "Gbemicharles_",
        "telegram": "@_PEDROTON",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "Builds TON meme tools, scanners",
        "win_play": "Scanners integrate crawler"
    },
    {
        "x_handle": "alenka_on_x",
        "telegram_note": "TON blockchain hubs",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "$USDT on TON hype, 255 likes, 34k views",
        "avg_likes": 255,
        "avg_views": 34000,
        "win_play": "Stuffs seal via notaryton"
    },
    {
        "x_handle": "CryptoTeluguO",
        "telegram_note": "Free rewards channels",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "$TON rewards, 304 likes, 75k views",
        "avg_likes": 304,
        "avg_views": 75000,
        "win_play": "Revenues test insurance"
    },
    {
        "x_handle": "TacBuild",
        "telegram": "@TacBuild",
        "category": "ton",
        "chain_focus": ["ton", "evm"],
        "language": "en",
        "edge": "EVM-TON bridges, 1B users",
        "win_play": "LFGs get notary proofs"
    },
    {
        "x_handle": "CNainyas",
        "telegram": "@ston_fi",
        "category": "ton",
        "chain_focus": ["ton"],
        "language": "en",
        "edge": "STON.fi ambassador, liquidity primitives",
        "win_play": "Natives get insurance"
    },

    # ==================== WATCHDOGS / RUG HUNTERS ====================
    {
        "x_handle": "W0LF0FCRYPT0",
        "telegram_note": "Trench alpha groups",
        "category": "watchdog",
        "chain_focus": ["sol"],
        "language": "en",
        "edge": "Calls pumpfun rugs, 460 likes, 45k views",
        "avg_likes": 460,
        "avg_views": 45000,
        "win_play": "Rug calls seal via notaryton"
    },
    {
        "x_handle": "iamkadense",
        "telegram": "@bonk_inu",
        "category": "watchdog",
        "chain_focus": ["sol"],
        "language": "en",
        "edge": "Bonk contributor, exposes pump tanks, 307 likes",
        "avg_likes": 307,
        "win_play": "SealBet for their eco"
    },
    {
        "x_handle": "MastrXYZ",
        "telegram": "@MASTR",
        "category": "watchdog",
        "chain_focus": ["sol"],
        "language": "en",
        "edge": "OG watchdog, 98% Sol rugs documented, 452 likes",
        "avg_likes": 452,
        "win_play": "Stats feed crawler"
    },
    {
        "x_handle": "flocko",
        "telegram": "@trovemarkets",
        "category": "watchdog",
        "chain_focus": ["sol"],
        "language": "en",
        "edge": "Trove CIO, roasts .100 averages, 322 likes",
        "avg_likes": 322,
        "win_play": "Roasts get notary proofs"
    },
    {
        "x_handle": "wizardofsoho",
        "telegram_note": "Capital networks, newsletter",
        "category": "watchdog",
        "chain_focus": ["sol"],
        "language": "en",
        "edge": "Weekly Wizdom, 1k likes, 96k views",
        "avg_likes": 1000,
        "avg_views": 96000,
        "win_play": "Insights seal high-risks"
    },
    {
        "x_handle": "adhcrypto",
        "telegram": "@unruggable_io",
        "category": "watchdog",
        "chain_focus": ["sol"],
        "language": "en",
        "edge": "Unruggable partnerships, warns on influencers",
        "win_play": "Warnings test notary scores"
    },

    # ==================== SOLANA CALLERS ====================
    {
        "x_handle": "DegenMemeCalls",
        "telegram_note": "Copy trade wallets",
        "category": "solana",
        "chain_focus": ["sol"],
        "language": "en",
        "edge": "Snipe/gamble caller, hourly pumps",
        "win_play": "Calls auto-seal"
    },
    {
        "x_handle": "arha_13",
        "telegram_note": "Business DMs",
        "category": "solana",
        "chain_focus": ["sol"],
        "language": "en",
        "edge": "Researcher, shills $PUMP, 22k views",
        "avg_views": 22000,
        "win_play": "Researches feed crawler"
    },
    {
        "x_handle": "legolas_p3",
        "telegram": "@superteambr",
        "category": "solana",
        "chain_focus": ["sol"],
        "language": "en",
        "edge": "Superteam contributor, FUD-busts",
        "win_play": "Busts get notary badges"
    },

    # ==================== CROSS-CHAIN ====================
    {
        "x_handle": "mfckr_eth",
        "telegram_note": "TON research networks",
        "category": "cross_chain",
        "chain_focus": ["ton", "eth"],
        "language": "en",
        "edge": "Blockchain analyst, 100x account growth spotted",
        "win_play": "Insights feed crawler"
    },
    {
        "x_handle": "CallScanAlerts",
        "telegram_note": "ZKVProtocol networks",
        "category": "cross_chain",
        "chain_focus": ["multi"],
        "language": "en",
        "edge": "Real-time scanner, 5x alerts from 8k MC",
        "win_play": "Alerts auto-seal"
    },
    {
        "x_handle": "ZssBecker",
        "telegram_note": "Alpha groups",
        "category": "cross_chain",
        "chain_focus": ["alts"],
        "language": "en",
        "edge": "Crypto leader, 4324 likes, 288k views on alts",
        "avg_likes": 4324,
        "avg_views": 288000,
        "win_play": "Seasons seal via notaryton"
    },
    {
        "x_handle": "ChatKolz",
        "telegram": "@ChatKolz",
        "category": "cross_chain",
        "chain_focus": ["multi"],
        "language": "en",
        "edge": "KOL token with AI agents, 72 likes, 20k views",
        "avg_likes": 72,
        "avg_views": 20000,
        "win_play": "Agents integrate crawler"
    },
    {
        "x_handle": "AltCryptoGems",
        "telegram_note": "Gem networks",
        "category": "cross_chain",
        "chain_focus": ["ton", "multi"],
        "language": "en",
        "edge": "Sjuul, TON opportunities, 45 likes, 122k views",
        "avg_likes": 45,
        "avg_views": 122000,
        "win_play": "Golds seal via notaryton"
    },

    # ==================== REGIONAL: RUSSIAN ====================
    {
        "x_handle": "wojak_ton",
        "telegram": "@wojak_ton",
        "category": "regional",
        "chain_focus": ["ton"],
        "language": "ru",
        "edge": "Wojak meme on TON, Russian community",
        "win_play": "Make TON meme great again"
    },
    {
        "x_handle": "khasanov_gt",
        "telegram_note": "Crypto YT/chats",
        "category": "regional",
        "chain_focus": ["multi"],
        "language": "ru",
        "edge": "Top Russian crypto Instagram, 3.91% engagement",
        "engagement": "3.91% engagement",
        "win_play": "Faith wave adoptions"
    },
    {
        "x_handle": "ncuxAy",
        "telegram_note": "YT ties",
        "category": "regional",
        "chain_focus": ["ton"],
        "language": "ru",
        "edge": "Leading Russian crypto YouTuber, TON focus",
        "win_play": "Marathon grinds"
    },

    # ==================== REGIONAL: CHINESE ====================
    {
        "x_handle": "da_hongfei",
        "telegram_note": "Neo/ONT communities",
        "category": "regional",
        "chain_focus": ["multi"],
        "language": "zh",
        "edge": "Neo founder, influences Chinese meme metas",
        "win_play": "100x potential"
    },
    {
        "x_handle": "cz_binance",
        "telegram": "@binance",
        "category": "regional",
        "chain_focus": ["multi"],
        "language": "zh",
        "edge": "CZ Binance, shapes Chinese meme trends",
        "verified": True,
        "win_play": "Global 3x-100x calls"
    },

    # ==================== REGIONAL: HINDI/INDIAN ====================
    {
        "x_handle": "sujaljethwani",
        "telegram_note": "Meme coin YT/chats",
        "category": "regional",
        "chain_focus": ["ton"],
        "language": "hi",
        "edge": "Top Indian crypto influencer, bull run picks",
        "win_play": "Take profit waves"
    },
    {
        "x_handle": "balajis",
        "telegram_note": "Blockchain India groups",
        "category": "regional",
        "chain_focus": ["ton"],
        "language": "hi",
        "edge": "Balaji Srinivasan, TON rotations",
        "verified": True,
        "win_play": "Tech psych with meme adoptions"
    },

    # ==================== REGIONAL: ARABIC ====================
    {
        "x_handle": "andresmeneses",
        "telegram_note": "UAE crypto chats",
        "category": "regional",
        "chain_focus": ["multi"],
        "language": "ar",
        "edge": "Top UAE crypto influencer, 3.91% engagement",
        "engagement": "3.91% engagement",
        "win_play": "Faith waves beyond Western math"
    },
    {
        "x_handle": "grazlygeek",
        "telegram_note": "YT ties",
        "category": "regional",
        "chain_focus": ["ton"],
        "language": "ar",
        "edge": "Saudi crypto YT, TON trends",
        "win_play": "Scams vs resilience"
    },

    # ==================== REGIONAL: SPANISH ====================
    {
        "x_handle": "marioruiz",
        "telegram_note": "Spanish crypto groups",
        "category": "regional",
        "chain_focus": ["multi"],
        "language": "es",
        "edge": "Top Spanish crypto influencer, Durev calls",
        "win_play": "Latin boss spirits"
    },
    {
        "x_handle": "danielmuvdi",
        "telegram": "@danielmuvdicrypto",
        "category": "regional",
        "chain_focus": ["ton"],
        "language": "es",
        "edge": "Spanish crypto YT, safety trends",
        "win_play": "Rugs vs bio-chaos"
    },

    # ==================== REGIONAL: FRENCH ====================
    {
        "x_handle": "owensimonin",
        "telegram": "@hasheur",
        "category": "regional",
        "chain_focus": ["ton"],
        "language": "fr",
        "edge": "Hasheur, France top crypto influencer",
        "win_play": "Educational prints"
    },
    {
        "x_handle": "ton_france",
        "telegram": "@ton_france",
        "category": "regional",
        "chain_focus": ["ton"],
        "language": "fr",
        "edge": "TON France official, consumer solutions",
        "win_play": "Crypto-first onboarding"
    },

    # ==================== REGIONAL: GERMAN ====================
    {
        "x_handle": "lucarolle",
        "telegram_note": "German crypto chats",
        "category": "regional",
        "chain_focus": ["multi"],
        "language": "de",
        "edge": "Top German crypto influencer, safety trends",
        "win_play": "Final boss psych"
    },
    {
        "x_handle": "cryptoblaney",
        "telegram_note": "YT ties",
        "category": "regional",
        "chain_focus": ["ton"],
        "language": "de",
        "edge": "German crypto YT, market insights",
        "win_play": "Extracts vs resilience"
    },

    # ==================== REGIONAL: KOREAN ====================
    {
        "x_handle": "cryptofactsofficial",
        "telegram_note": "YT ties",
        "category": "regional",
        "chain_focus": ["ton"],
        "language": "ko",
        "edge": "Top Korean crypto influencer, TON rewards",
        "win_play": "Bear spirits"
    },
    {
        "x_handle": "younghoonkim",
        "telegram_note": "XRP promo groups",
        "category": "regional",
        "chain_focus": ["multi"],
        "language": "ko",
        "edge": "Korean influencer, TON-like alts",
        "win_play": "Psych vs bio-chaos"
    },

    # ==================== REGIONAL: PORTUGUESE ====================
    {
        "x_handle": "nicvonrupp",
        "telegram_note": "Portugal crypto chats",
        "category": "regional",
        "chain_focus": ["multi"],
        "language": "pt",
        "edge": "Top Portuguese crypto influencer, 3.91%",
        "engagement": "3.91% engagement",
        "win_play": "Final boss psych"
    },

    # ==================== REGIONAL: INDONESIAN ====================
    {
        "x_handle": "riccienick",
        "telegram_note": "Indonesia crypto groups",
        "category": "regional",
        "chain_focus": ["ton"],
        "language": "id",
        "edge": "Top Indonesian crypto influencer, TON vibes",
        "win_play": "Community prints"
    },
    {
        "x_handle": "yonathandinata",
        "category": "regional",
        "chain_focus": ["ton"],
        "language": "id",
        "edge": "Indonesian KOL, top 20 crypto influencers",
        "win_play": "Local psych with meme trends"
    },

    # ==================== REGIONAL: VIETNAMESE ====================
    {
        "x_handle": "leduycryptoman",
        "telegram_note": "Vietnamese KOL groups",
        "category": "regional",
        "chain_focus": ["ton"],
        "language": "vi",
        "edge": "Top Vietnamese crypto KOL, TON insights",
        "win_play": "Faith wave adoptions"
    },

    # ==================== REGIONAL: THAI ====================
    {
        "x_handle": "golf_ak9",
        "telegram_note": "Thailand crypto chats",
        "category": "regional",
        "chain_focus": ["multi"],
        "language": "th",
        "edge": "Top Thai crypto influencer",
        "win_play": "Final boss psych"
    },

    # ==================== REGIONAL: PERSIAN ====================
    {
        "x_handle": "butcher.call",
        "telegram_note": "Iran crypto groups",
        "category": "regional",
        "chain_focus": ["multi"],
        "language": "fa",
        "edge": "Top Iranian crypto influencer, viral prints",
        "win_play": "Rugs vs resilience"
    },

    # ==================== REGIONAL: UKRAINIAN ====================
    {
        "x_handle": "kostyakudo",
        "telegram_note": "Ukrainian crypto chats",
        "category": "regional",
        "chain_focus": ["ton"],
        "language": "uk",
        "edge": "Ukrainian influencer, TON meme vibes",
        "win_play": "Psych vs bio-chaos"
    },

    # ==================== REGIONAL: POLISH ====================
    {
        "x_handle": "monaanom",
        "telegram_note": "Polish TikTok groups",
        "category": "regional",
        "chain_focus": ["multi"],
        "language": "pl",
        "edge": "Top Polish crypto TikToker, humor + safety",
        "win_play": "Bear spirits"
    },

    # ==================== REGIONAL: DUTCH ====================
    {
        "x_handle": "sibel",
        "telegram_note": "Dutch memecoin chats",
        "category": "regional",
        "chain_focus": ["ton"],
        "language": "nl",
        "edge": "Dutch memecoin enthusiast, TON vibes",
        "win_play": "Swarm discussions"
    },

    # ==================== REGIONAL: ITALIAN ====================
    {
        "x_handle": "stefanocastiello",
        "telegram_note": "Italian crypto groups",
        "category": "regional",
        "chain_focus": ["multi"],
        "language": "it",
        "edge": "Top Italian crypto influencer, safety high",
        "win_play": "Extracts vs resilience"
    },

    # ==================== REGIONAL: SWEDISH ====================
    {
        "x_handle": "issyrodriguez_",
        "telegram_note": "Swedish crypto chats",
        "category": "regional",
        "chain_focus": ["multi"],
        "language": "sv",
        "edge": "Top Swedish crypto influencer, visual prints",
        "win_play": "Bear spirits"
    },
]

# Quick stats
SEED_STATS = {
    "total_kols": len(GROK_KOL_SEED),
    "categories": {
        "general": len([k for k in GROK_KOL_SEED if k.get("category") == "general"]),
        "ton": len([k for k in GROK_KOL_SEED if k.get("category") == "ton"]),
        "watchdog": len([k for k in GROK_KOL_SEED if k.get("category") == "watchdog"]),
        "solana": len([k for k in GROK_KOL_SEED if k.get("category") == "solana"]),
        "cross_chain": len([k for k in GROK_KOL_SEED if k.get("category") == "cross_chain"]),
        "regional": len([k for k in GROK_KOL_SEED if k.get("category") == "regional"]),
    },
    "languages": list(set(k.get("language", "en") for k in GROK_KOL_SEED)),
    "verified": len([k for k in GROK_KOL_SEED if k.get("verified")]),
}
