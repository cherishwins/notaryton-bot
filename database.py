"""
Database Layer for NotaryTON
============================
PostgreSQL database connection and operations using asyncpg.

Usage:
    from database import db

    # Initialize on startup
    await db.connect()

    # Use in handlers
    user = await db.users.get(user_id)
    await db.notarizations.create(...)

    # Cleanup on shutdown
    await db.disconnect()
"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

import asyncpg
from asyncpg import Pool, Connection

# ========================
# MODELS (Dataclasses)
# ========================

@dataclass
class User:
    user_id: int
    subscription_expiry: Optional[datetime] = None
    total_paid: float = 0.0
    referral_code: Optional[str] = None
    referred_by: Optional[int] = None
    referral_earnings: float = 0.0
    total_withdrawn: float = 0.0
    withdrawal_wallet: Optional[str] = None
    language: str = "en"
    created_at: Optional[datetime] = None

    @property
    def has_active_subscription(self) -> bool:
        if self.subscription_expiry is None:
            return False
        return self.subscription_expiry > datetime.now()

    @property
    def available_balance(self) -> float:
        return max(0, self.referral_earnings - self.total_withdrawn)


@dataclass
class Notarization:
    id: Optional[int] = None
    user_id: int = 0
    tx_hash: Optional[str] = None
    contract_hash: str = ""
    timestamp: Optional[datetime] = None
    paid: bool = False
    via_api: bool = False


@dataclass
class PendingPayment:
    id: Optional[int] = None
    user_id: int = 0
    amount: float = 0.0
    memo: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class ApiKey:
    key: str
    user_id: int
    created_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    requests_count: int = 0


@dataclass
class BotState:
    key: str
    value: str


@dataclass
class LotteryEntry:
    id: Optional[int] = None
    user_id: int = 0
    amount_stars: int = 0  # Stars paid that generated this entry
    created_at: Optional[datetime] = None
    draw_id: Optional[int] = None  # Which draw this entry is for (null = current)
    won: bool = False


@dataclass
class TrackedToken:
    """Token tracked for rug detection and scoring."""
    address: str
    symbol: Optional[str] = None
    name: Optional[str] = None
    decimals: int = 9
    deployer: Optional[str] = None
    total_supply: float = 0

    # Snapshot at first detection
    first_seen: Optional[datetime] = None
    initial_holder_count: int = 0
    initial_top_holder_pct: float = 0
    initial_liquidity_usd: float = 0

    # Safety analysis
    safety_score: int = 50
    lp_locked: bool = False
    ownership_renounced: bool = False

    # Rug detection
    first_dev_sell_at: Optional[datetime] = None
    first_dev_sell_pct: float = 0
    rugged: bool = False
    rugged_at: Optional[datetime] = None

    # Current state
    current_holder_count: int = 0
    current_top_holder_pct: float = 0
    current_price_usd: float = 0
    last_updated: Optional[datetime] = None


@dataclass
class TokenEvent:
    """Significant event for a tracked token."""
    id: Optional[int] = None
    token_address: str = ""
    event_type: str = ""  # 'deploy', 'first_sell', 'whale_dump', 'rug', 'moon'
    event_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None


@dataclass
class HolderSnapshot:
    """Snapshot of a token holder at a point in time."""
    id: Optional[int] = None
    token_address: str = ""
    wallet_address: str = ""
    balance: float = 0
    pct_of_supply: float = 0
    rank: int = 0  # 1 = top holder
    snapshot_at: Optional[datetime] = None


@dataclass
class KnownWallet:
    """Known wallet with label (whale, exchange, dev, etc)."""
    address: str = ""
    label: str = ""  # 'whale', 'exchange', 'dev', 'influencer'
    owner_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


# ========================
# REPOSITORY CLASSES
# ========================

class UserRepository:
    """Repository for user operations"""

    def __init__(self, pool: Pool):
        self._pool = pool

    async def get(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1",
                user_id
            )
            if row:
                return User(**dict(row))
            return None

    async def create(self, user_id: int, **kwargs) -> User:
        """Create a new user"""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, referral_code, referred_by, language)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO NOTHING
            """, user_id,
                kwargs.get('referral_code'),
                kwargs.get('referred_by'),
                kwargs.get('language', 'en')
            )
        return await self.get(user_id) or User(user_id=user_id)

    async def ensure_exists(self, user_id: int) -> None:
        """Ensure user exists in database"""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
                user_id
            )

    async def get_subscription_expiry(self, user_id: int) -> Optional[datetime]:
        """Get user's subscription expiry"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT subscription_expiry FROM users WHERE user_id = $1",
                user_id
            )
            if row and row['subscription_expiry']:
                return row['subscription_expiry']
            return None

    async def has_active_subscription(self, user_id: int) -> bool:
        """Check if user has active subscription"""
        expiry = await self.get_subscription_expiry(user_id)
        if expiry:
            return expiry > datetime.now()
        return False

    async def add_subscription(self, user_id: int, months: int = 1) -> datetime:
        """Add or extend subscription, returns new expiry"""
        expiry = datetime.now() + timedelta(days=30 * months)
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, subscription_expiry)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET subscription_expiry = $2
            """, user_id, expiry)
        return expiry

    async def get_language(self, user_id: int) -> str:
        """Get user's language preference"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT language FROM users WHERE user_id = $1",
                user_id
            )
            if row and row['language']:
                return row['language']
            return 'en'

    async def set_language(self, user_id: int, lang: str) -> None:
        """Set user's language preference"""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, language)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET language = $2
            """, user_id, lang)

    async def get_total_paid(self, user_id: int) -> float:
        """Get user's total paid amount"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT total_paid FROM users WHERE user_id = $1",
                user_id
            )
            if row and row['total_paid']:
                return float(row['total_paid'])
            return 0.0

    async def add_payment(self, user_id: int, amount: float) -> None:
        """Add to user's total paid"""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, total_paid)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET total_paid = users.total_paid + $2
            """, user_id, amount)

    async def deduct_payment(self, user_id: int, amount: float) -> None:
        """Deduct from user's total paid (for per-use payments)"""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET total_paid = total_paid - $2 WHERE user_id = $1",
                user_id, amount
            )

    async def get_referral_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user's referral stats"""
        async with self._pool.acquire() as conn:
            user_row = await conn.fetchrow("""
                SELECT referral_code, referral_earnings, total_withdrawn
                FROM users WHERE user_id = $1
            """, user_id)

            if not user_row:
                return {
                    'code': None,
                    'count': 0,
                    'earnings': 0.0,
                    'withdrawn': 0.0,
                    'available': 0.0
                }

            count_row = await conn.fetchrow(
                "SELECT COUNT(*) as count FROM users WHERE referred_by = $1",
                user_id
            )

            earnings = float(user_row['referral_earnings'] or 0)
            withdrawn = float(user_row['total_withdrawn'] or 0)

            return {
                'code': user_row['referral_code'],
                'count': count_row['count'] if count_row else 0,
                'earnings': earnings,
                'withdrawn': withdrawn,
                'available': max(0, earnings - withdrawn)
            }

    async def set_referral_code(self, user_id: int, code: str) -> None:
        """Set user's referral code"""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET referral_code = $2 WHERE user_id = $1
            """, user_id, code)

    async def add_referral_earnings(self, user_id: int, amount: float) -> None:
        """Add referral earnings to user"""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET referral_earnings = referral_earnings + $2
                WHERE user_id = $1
            """, user_id, amount)

    async def get_withdrawal_wallet(self, user_id: int) -> Optional[str]:
        """Get user's withdrawal wallet"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT withdrawal_wallet FROM users WHERE user_id = $1",
                user_id
            )
            if row:
                return row['withdrawal_wallet']
            return None

    async def set_withdrawal_wallet(self, user_id: int, wallet: str) -> None:
        """Set user's withdrawal wallet"""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET withdrawal_wallet = $2 WHERE user_id = $1
            """, user_id, wallet)

    async def record_withdrawal(self, user_id: int, amount: float) -> None:
        """Record a withdrawal"""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET total_withdrawn = total_withdrawn + $2
                WHERE user_id = $1
            """, user_id, amount)

    async def get_by_referral_code(self, code: str) -> Optional[User]:
        """Get user by referral code"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE referral_code = $1",
                code
            )
            if row:
                return User(**dict(row))
            return None

    async def count(self) -> int:
        """Get total user count"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) as count FROM users")
            return row['count'] if row else 0


class NotarizationRepository:
    """Repository for notarization operations"""

    def __init__(self, pool: Pool):
        self._pool = pool

    async def create(
        self,
        user_id: int,
        contract_hash: str,
        tx_hash: Optional[str] = None,
        paid: bool = False,
        via_api: bool = False
    ) -> Notarization:
        """Create a new notarization record"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO notarizations (user_id, tx_hash, contract_hash, paid, via_api)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
            """, user_id, tx_hash, contract_hash, paid, via_api)
            return Notarization(**dict(row))

    async def get_by_hash(self, contract_hash: str) -> Optional[Notarization]:
        """Get notarization by contract hash"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM notarizations WHERE contract_hash = $1 ORDER BY timestamp DESC LIMIT 1",
                contract_hash
            )
            if row:
                return Notarization(**dict(row))
            return None

    async def find_by_hash(self, contract_hash: str) -> List[Notarization]:
        """Find all notarizations for a hash"""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM notarizations WHERE contract_hash = $1 ORDER BY timestamp DESC",
                contract_hash
            )
            return [Notarization(**dict(row)) for row in rows]

    async def get_user_notarizations(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Notarization]:
        """Get user's notarizations"""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM notarizations
                WHERE user_id = $1
                ORDER BY timestamp DESC
                LIMIT $2
            """, user_id, limit)
            return [Notarization(**dict(row)) for row in rows]

    async def get_recent(self, limit: int = 10) -> List[Notarization]:
        """Get recent notarizations"""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM notarizations
                ORDER BY timestamp DESC
                LIMIT $1
            """, limit)
            return [Notarization(**dict(row)) for row in rows]

    async def count(self) -> int:
        """Get total notarization count"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) as count FROM notarizations")
            return row['count'] if row else 0

    async def count_by_user(self, user_id: int) -> int:
        """Get user's notarization count"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) as count FROM notarizations WHERE user_id = $1",
                user_id
            )
            return row['count'] if row else 0


class BotStateRepository:
    """Repository for bot state key-value store"""

    def __init__(self, pool: Pool):
        self._pool = pool

    async def get(self, key: str) -> Optional[str]:
        """Get state value by key"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM bot_state WHERE key = $1",
                key
            )
            if row:
                return row['value']
            return None

    async def set(self, key: str, value: str) -> None:
        """Set state value"""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO bot_state (key, value)
                VALUES ($1, $2)
                ON CONFLICT (key) DO UPDATE SET value = $2
            """, key, value)

    async def delete(self, key: str) -> None:
        """Delete state key"""
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM bot_state WHERE key = $1", key)


class LotteryRepository:
    """Repository for lottery operations - DEGEN MODE 🎰"""

    def __init__(self, pool: Pool):
        self._pool = pool

    async def add_entry(self, user_id: int, amount_stars: int = 1) -> LotteryEntry:
        """Add lottery entry for user (20% of each seal payment)"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO lottery_entries (user_id, amount_stars)
                VALUES ($1, $2)
                RETURNING *
            """, user_id, amount_stars)
            return LotteryEntry(**dict(row))

    async def get_user_entries(self, user_id: int, current_only: bool = True) -> List[LotteryEntry]:
        """Get user's lottery entries"""
        async with self._pool.acquire() as conn:
            if current_only:
                rows = await conn.fetch("""
                    SELECT * FROM lottery_entries
                    WHERE user_id = $1 AND draw_id IS NULL
                    ORDER BY created_at DESC
                """, user_id)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM lottery_entries
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                """, user_id)
            return [LotteryEntry(**dict(row)) for row in rows]

    async def count_user_entries(self, user_id: int, current_only: bool = True) -> int:
        """Count user's lottery entries for current draw"""
        async with self._pool.acquire() as conn:
            if current_only:
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as count FROM lottery_entries
                    WHERE user_id = $1 AND draw_id IS NULL
                """, user_id)
            else:
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as count FROM lottery_entries
                    WHERE user_id = $1
                """, user_id)
            return row['count'] if row else 0

    async def get_total_entries(self, current_only: bool = True) -> int:
        """Get total entries in current lottery"""
        async with self._pool.acquire() as conn:
            if current_only:
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as count FROM lottery_entries
                    WHERE draw_id IS NULL
                """)
            else:
                row = await conn.fetchrow("SELECT COUNT(*) as count FROM lottery_entries")
            return row['count'] if row else 0

    async def get_pot_size_stars(self) -> int:
        """Get current pot size in Stars (20% of all entries)"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT COALESCE(SUM(amount_stars), 0) as total FROM lottery_entries
                WHERE draw_id IS NULL
            """)
            # 20% of each star payment goes to pot
            total_stars = row['total'] if row else 0
            return int(total_stars * 0.2)

    async def get_pot_size_ton(self) -> float:
        """Get pot size converted to TON (rough estimate)"""
        stars = await self.get_pot_size_stars()
        # 1 Star ≈ 0.001 TON (rough conversion)
        return stars * 0.001

    async def get_unique_participants(self) -> int:
        """Get number of unique participants in current draw"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT COUNT(DISTINCT user_id) as count FROM lottery_entries
                WHERE draw_id IS NULL
            """)
            return row['count'] if row else 0

    async def pick_winner(self, draw_id: int) -> Optional[int]:
        """Randomly pick a winner from current entries (weighted by entry count - more entries = more chances)"""
        async with self._pool.acquire() as conn:
            # Pick random entry (each entry = equal chance, so more entries = better odds)
            row = await conn.fetchrow("""
                SELECT user_id FROM lottery_entries
                WHERE draw_id IS NULL
                ORDER BY RANDOM()
                LIMIT 1
            """)
            if row:
                winner_id = row['user_id']
                # Mark all current entries with this draw_id
                await conn.execute("""
                    UPDATE lottery_entries SET draw_id = $1 WHERE draw_id IS NULL
                """, draw_id)
                # Mark ONE winner entry using subquery (PostgreSQL compatible)
                await conn.execute("""
                    UPDATE lottery_entries SET won = TRUE
                    WHERE id = (
                        SELECT id FROM lottery_entries
                        WHERE user_id = $1 AND draw_id = $2
                        LIMIT 1
                    )
                """, winner_id, draw_id)
                return winner_id
            return None


class ApiKeyRepository:
    """Repository for API key operations"""

    def __init__(self, pool: Pool):
        self._pool = pool

    async def create(self, key: str, user_id: int) -> ApiKey:
        """Create a new API key"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO api_keys (key, user_id)
                VALUES ($1, $2)
                RETURNING *
            """, key, user_id)
            return ApiKey(**dict(row))

    async def get(self, key: str) -> Optional[ApiKey]:
        """Get API key"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM api_keys WHERE key = $1",
                key
            )
            if row:
                return ApiKey(**dict(row))
            return None

    async def get_by_user(self, user_id: int) -> List[ApiKey]:
        """Get all API keys for user"""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM api_keys WHERE user_id = $1",
                user_id
            )
            return [ApiKey(**dict(row)) for row in rows]

    async def record_usage(self, key: str) -> None:
        """Record API key usage"""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE api_keys
                SET last_used = NOW(), requests_count = requests_count + 1
                WHERE key = $1
            """, key)

    async def delete(self, key: str) -> None:
        """Delete API key"""
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM api_keys WHERE key = $1", key)


class WalletRepository:
    """Repository for wallet tracking - PHASE 1 of Trader Intelligence"""

    def __init__(self, pool: Pool):
        self._pool = pool

    async def snapshot_holders(
        self,
        token_address: str,
        holders: List[Dict[str, Any]],
        total_supply: float
    ) -> int:
        """Snapshot current top holders for a token. Returns count saved."""
        if not holders or total_supply <= 0:
            return 0

        async with self._pool.acquire() as conn:
            count = 0
            for rank, holder in enumerate(holders[:20], 1):  # Top 20
                wallet = holder.get("owner", {}).get("address", "") or holder.get("address", "")
                balance = float(holder.get("balance", 0) or 0)

                if not wallet or balance <= 0:
                    continue

                pct = (balance / total_supply) * 100

                await conn.execute("""
                    INSERT INTO holder_snapshots
                    (token_address, wallet_address, balance, pct_of_supply, rank)
                    VALUES ($1, $2, $3, $4, $5)
                """, token_address, wallet, balance, pct, rank)
                count += 1

            return count

    async def get_holder_history(
        self,
        token_address: str,
        limit: int = 5
    ) -> List[List[HolderSnapshot]]:
        """Get recent holder snapshots grouped by snapshot time."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT ON (snapshot_at::date, wallet_address)
                    id, token_address, wallet_address, balance, pct_of_supply, rank, snapshot_at
                FROM holder_snapshots
                WHERE token_address = $1
                ORDER BY snapshot_at DESC, wallet_address
                LIMIT $2
            """, token_address, limit * 20)

            return [HolderSnapshot(**dict(row)) for row in rows]

    async def get_wallet_tokens(self, wallet_address: str) -> List[Dict[str, Any]]:
        """Get all tokens a wallet has held."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT ON (token_address)
                    hs.token_address, hs.balance, hs.pct_of_supply, hs.snapshot_at,
                    t.symbol, t.name, t.safety_score, t.rugged
                FROM holder_snapshots hs
                JOIN tracked_tokens t ON hs.token_address = t.address
                WHERE hs.wallet_address = $1
                ORDER BY token_address, snapshot_at DESC
            """, wallet_address)

            return [dict(row) for row in rows]

    async def detect_whale_changes(
        self,
        token_address: str,
        current_holders: List[Dict[str, Any]],
        total_supply: float,
        threshold_pct: float = 5.0
    ) -> List[Dict[str, Any]]:
        """Detect significant holder changes (entries/exits)."""
        if not current_holders or total_supply <= 0:
            return []

        changes = []

        async with self._pool.acquire() as conn:
            # Get last snapshot
            last_snapshot = await conn.fetch("""
                SELECT wallet_address, pct_of_supply
                FROM holder_snapshots
                WHERE token_address = $1
                AND snapshot_at = (
                    SELECT MAX(snapshot_at) FROM holder_snapshots WHERE token_address = $1
                )
            """, token_address)

            old_holders = {row['wallet_address']: row['pct_of_supply'] for row in last_snapshot}

            # Current holders
            for holder in current_holders[:20]:
                wallet = holder.get("owner", {}).get("address", "") or holder.get("address", "")
                balance = float(holder.get("balance", 0) or 0)
                if not wallet or balance <= 0:
                    continue

                current_pct = (balance / total_supply) * 100
                old_pct = old_holders.get(wallet, 0)

                # New whale entry
                if wallet not in old_holders and current_pct >= threshold_pct:
                    changes.append({
                        "type": "whale_entry",
                        "wallet": wallet,
                        "pct": current_pct,
                    })

                # Significant increase
                elif current_pct - old_pct >= threshold_pct:
                    changes.append({
                        "type": "whale_increase",
                        "wallet": wallet,
                        "old_pct": old_pct,
                        "new_pct": current_pct,
                    })

            # Check for exits
            current_wallets = {
                holder.get("owner", {}).get("address", "") or holder.get("address", "")
                for holder in current_holders[:20]
            }

            for wallet, old_pct in old_holders.items():
                if wallet not in current_wallets and old_pct >= threshold_pct:
                    changes.append({
                        "type": "whale_exit",
                        "wallet": wallet,
                        "pct_sold": old_pct,
                    })

        return changes

    async def label_wallet(
        self,
        address: str,
        label: str,
        owner_name: Optional[str] = None,
        notes: Optional[str] = None
    ) -> None:
        """Label a known wallet."""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO known_wallets (address, label, owner_name, notes)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (address) DO UPDATE SET
                    label = $2, owner_name = COALESCE($3, known_wallets.owner_name),
                    notes = COALESCE($4, known_wallets.notes)
            """, address, label, owner_name, notes)

    async def get_wallet_label(self, address: str) -> Optional[KnownWallet]:
        """Get label for a wallet if known."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM known_wallets WHERE address = $1",
                address
            )
            if row:
                return KnownWallet(**dict(row))
            return None

    async def get_whales(self, min_appearances: int = 3) -> List[Dict[str, Any]]:
        """Get wallets that appear as top holders frequently."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    wallet_address,
                    COUNT(DISTINCT token_address) as token_count,
                    AVG(pct_of_supply) as avg_pct,
                    MAX(pct_of_supply) as max_pct
                FROM holder_snapshots
                WHERE rank <= 5
                GROUP BY wallet_address
                HAVING COUNT(DISTINCT token_address) >= $1
                ORDER BY token_count DESC
                LIMIT 100
            """, min_appearances)

            return [dict(row) for row in rows]


class TokenRepository:
    """Repository for token tracking - THE DATA MOAT 📊"""

    def __init__(self, pool: Pool):
        self._pool = pool

    async def get(self, address: str) -> Optional[TrackedToken]:
        """Get token by address"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM tracked_tokens WHERE address = $1",
                address
            )
            if row:
                return TrackedToken(**dict(row))
            return None

    async def upsert(self, token: TrackedToken) -> None:
        """Insert or update a token"""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO tracked_tokens (
                    address, symbol, name, decimals, deployer, total_supply,
                    first_seen, initial_holder_count, initial_top_holder_pct,
                    initial_liquidity_usd, safety_score, lp_locked,
                    ownership_renounced, current_holder_count,
                    current_top_holder_pct, current_price_usd, last_updated
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, NOW())
                ON CONFLICT (address) DO UPDATE SET
                    symbol = COALESCE($2, tracked_tokens.symbol),
                    name = COALESCE($3, tracked_tokens.name),
                    current_holder_count = $14,
                    current_top_holder_pct = $15,
                    current_price_usd = $16,
                    safety_score = $11,
                    last_updated = NOW()
            """,
                token.address, token.symbol, token.name, token.decimals,
                token.deployer, token.total_supply, token.first_seen,
                token.initial_holder_count, token.initial_top_holder_pct,
                token.initial_liquidity_usd, token.safety_score,
                token.lp_locked, token.ownership_renounced,
                token.current_holder_count, token.current_top_holder_pct,
                token.current_price_usd
            )

    async def mark_rugged(self, address: str) -> None:
        """Mark a token as rugged"""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE tracked_tokens
                SET rugged = TRUE, rugged_at = NOW()
                WHERE address = $1
            """, address)

    async def record_dev_sell(self, address: str, sell_pct: float) -> None:
        """Record first developer sell"""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE tracked_tokens
                SET first_dev_sell_at = NOW(), first_dev_sell_pct = $2
                WHERE address = $1 AND first_dev_sell_at IS NULL
            """, address, sell_pct)

    async def get_recent(self, limit: int = 100) -> List[TrackedToken]:
        """Get recently tracked tokens"""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM tracked_tokens
                ORDER BY first_seen DESC
                LIMIT $1
            """, limit)
            return [TrackedToken(**dict(row)) for row in rows]

    async def get_rugged(self, limit: int = 100) -> List[TrackedToken]:
        """Get tokens that rugged"""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM tracked_tokens
                WHERE rugged = TRUE
                ORDER BY rugged_at DESC
                LIMIT $1
            """, limit)
            return [TrackedToken(**dict(row)) for row in rows]

    async def get_safe(self, min_score: int = 80, limit: int = 100) -> List[TrackedToken]:
        """Get tokens with high safety scores"""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM tracked_tokens
                WHERE safety_score >= $1 AND rugged = FALSE
                ORDER BY safety_score DESC, first_seen DESC
                LIMIT $2
            """, min_score, limit)
            return [TrackedToken(**dict(row)) for row in rows]

    async def get_stats(self) -> Dict[str, Any]:
        """Get tracking statistics"""
        async with self._pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM tracked_tokens")
            rugged = await conn.fetchval("SELECT COUNT(*) FROM tracked_tokens WHERE rugged = TRUE")
            safe = await conn.fetchval("SELECT COUNT(*) FROM tracked_tokens WHERE safety_score >= 80")
            today = await conn.fetchval("""
                SELECT COUNT(*) FROM tracked_tokens
                WHERE first_seen >= NOW() - INTERVAL '24 hours'
            """)
            return {
                "total_tracked": total or 0,
                "rugged_count": rugged or 0,
                "safe_count": safe or 0,
                "tracked_today": today or 0,
                "rug_rate": round((rugged or 0) / max(total or 1, 1) * 100, 1)
            }

    async def add_event(self, token_address: str, event_type: str, event_data: Dict[str, Any] = None) -> None:
        """Log a token event"""
        import json
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO token_events (token_address, event_type, event_data)
                VALUES ($1, $2, $3)
            """, token_address, event_type, json.dumps(event_data or {}))

    async def get_events(self, token_address: str, limit: int = 50) -> List[TokenEvent]:
        """Get events for a token"""
        import json
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM token_events
                WHERE token_address = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, token_address, limit)
            events = []
            for row in rows:
                d = dict(row)
                if d.get('event_data'):
                    d['event_data'] = json.loads(d['event_data'])
                events.append(TokenEvent(**d))
            return events


# ========================
# DATABASE CLASS
# ========================

class Database:
    """
    Main database class with connection pooling.

    Usage:
        db = Database()
        await db.connect()

        # Access repositories
        user = await db.users.get(123)
        await db.notarizations.create(...)

        await db.disconnect()
    """

    def __init__(self):
        self._pool: Optional[Pool] = None
        self._users: Optional[UserRepository] = None
        self._notarizations: Optional[NotarizationRepository] = None
        self._bot_state: Optional[BotStateRepository] = None
        self._api_keys: Optional[ApiKeyRepository] = None
        self._lottery: Optional[LotteryRepository] = None
        self._tokens: Optional[TokenRepository] = None
        self._wallets: Optional[WalletRepository] = None

    @property
    def pool(self) -> Pool:
        if self._pool is None:
            raise RuntimeError("Database not connected. Call await db.connect() first.")
        return self._pool

    @property
    def users(self) -> UserRepository:
        if self._users is None:
            raise RuntimeError("Database not connected. Call await db.connect() first.")
        return self._users

    @property
    def notarizations(self) -> NotarizationRepository:
        if self._notarizations is None:
            raise RuntimeError("Database not connected. Call await db.connect() first.")
        return self._notarizations

    @property
    def bot_state(self) -> BotStateRepository:
        if self._bot_state is None:
            raise RuntimeError("Database not connected. Call await db.connect() first.")
        return self._bot_state

    @property
    def api_keys(self) -> ApiKeyRepository:
        if self._api_keys is None:
            raise RuntimeError("Database not connected. Call await db.connect() first.")
        return self._api_keys

    @property
    def lottery(self) -> LotteryRepository:
        if self._lottery is None:
            raise RuntimeError("Database not connected. Call await db.connect() first.")
        return self._lottery

    @property
    def tokens(self) -> TokenRepository:
        if self._tokens is None:
            raise RuntimeError("Database not connected. Call await db.connect() first.")
        return self._tokens

    @property
    def wallets(self) -> WalletRepository:
        if self._wallets is None:
            raise RuntimeError("Database not connected. Call await db.connect() first.")
        return self._wallets

    async def connect(self, database_url: Optional[str] = None) -> None:
        """
        Connect to the database and initialize connection pool.

        Args:
            database_url: PostgreSQL connection URL. If not provided,
                         reads from DATABASE_URL environment variable.
        """
        if self._pool is not None:
            return  # Already connected

        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError(
                "DATABASE_URL not set. Please set the DATABASE_URL environment variable "
                "or pass database_url to connect(). "
                "Example: postgresql://user:pass@host/dbname"
            )

        # Create connection pool
        # Render PostgreSQL requires SSL
        self._pool = await asyncpg.create_pool(
            url,
            min_size=2,
            max_size=10,
            command_timeout=30,
            ssl='require'
        )

        # Initialize repositories
        self._users = UserRepository(self._pool)
        self._notarizations = NotarizationRepository(self._pool)
        self._bot_state = BotStateRepository(self._pool)
        self._api_keys = ApiKeyRepository(self._pool)
        self._lottery = LotteryRepository(self._pool)
        self._tokens = TokenRepository(self._pool)
        self._wallets = WalletRepository(self._pool)

        # Initialize schema
        await self._init_schema()

        print("✅ Database connected (PostgreSQL)")

    async def disconnect(self) -> None:
        """Close database connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._users = None
            self._notarizations = None
            self._bot_state = None
            self._api_keys = None
            self._lottery = None
            self._tokens = None
            self._wallets = None
            print("Database disconnected")

    async def _init_schema(self) -> None:
        """Initialize database schema"""
        async with self._pool.acquire() as conn:
            # Users table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    subscription_expiry TIMESTAMP,
                    total_paid DECIMAL(20, 8) DEFAULT 0,
                    referral_code VARCHAR(20) UNIQUE,
                    referred_by BIGINT REFERENCES users(user_id),
                    referral_earnings DECIMAL(20, 8) DEFAULT 0,
                    total_withdrawn DECIMAL(20, 8) DEFAULT 0,
                    withdrawal_wallet VARCHAR(100),
                    language VARCHAR(10) DEFAULT 'en',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Notarizations table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS notarizations (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    tx_hash VARCHAR(100),
                    contract_hash VARCHAR(64) NOT NULL,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    paid BOOLEAN DEFAULT FALSE,
                    via_api BOOLEAN DEFAULT FALSE
                )
            """)

            # Pending payments table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_payments (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    amount DECIMAL(20, 8),
                    memo VARCHAR(200),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # API keys table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    key VARCHAR(64) PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_used TIMESTAMP,
                    requests_count INTEGER DEFAULT 0
                )
            """)

            # Bot state table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_state (
                    key VARCHAR(100) PRIMARY KEY,
                    value TEXT
                )
            """)

            # Lottery entries table - DEGEN MODE 🎰
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lottery_entries (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    amount_stars INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT NOW(),
                    draw_id INTEGER,
                    won BOOLEAN DEFAULT FALSE
                )
            """)

            # Token tracking table - THE DATA MOAT 📊
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tracked_tokens (
                    address VARCHAR(100) PRIMARY KEY,
                    symbol VARCHAR(50),
                    name VARCHAR(200),
                    decimals INTEGER DEFAULT 9,
                    deployer VARCHAR(100),
                    total_supply DECIMAL(40, 0),

                    -- Snapshot at first detection
                    first_seen TIMESTAMP DEFAULT NOW(),
                    initial_holder_count INTEGER DEFAULT 0,
                    initial_top_holder_pct DECIMAL(10, 2) DEFAULT 0,
                    initial_liquidity_usd DECIMAL(20, 2) DEFAULT 0,

                    -- Safety analysis
                    safety_score INTEGER DEFAULT 50,
                    lp_locked BOOLEAN DEFAULT FALSE,
                    ownership_renounced BOOLEAN DEFAULT FALSE,

                    -- Rug detection
                    first_dev_sell_at TIMESTAMP,
                    first_dev_sell_pct DECIMAL(10, 2),
                    rugged BOOLEAN DEFAULT FALSE,
                    rugged_at TIMESTAMP,

                    -- Current state (updated periodically)
                    current_holder_count INTEGER DEFAULT 0,
                    current_top_holder_pct DECIMAL(10, 2) DEFAULT 0,
                    current_price_usd DECIMAL(30, 18) DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT NOW()
                )
            """)

            # Token events log - Track significant events
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS token_events (
                    id SERIAL PRIMARY KEY,
                    token_address VARCHAR(100) REFERENCES tracked_tokens(address),
                    event_type VARCHAR(50),  -- 'deploy', 'first_sell', 'whale_dump', 'rug', 'moon'
                    event_data JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Holder snapshots - WALLET TRACKING (Phase 1)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS holder_snapshots (
                    id SERIAL PRIMARY KEY,
                    token_address VARCHAR(100) REFERENCES tracked_tokens(address),
                    wallet_address VARCHAR(100) NOT NULL,
                    balance DECIMAL(40, 0) DEFAULT 0,
                    pct_of_supply DECIMAL(10, 4) DEFAULT 0,
                    rank INTEGER DEFAULT 0,
                    snapshot_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Known wallets - Labeled whales, devs, exchanges
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS known_wallets (
                    address VARCHAR(100) PRIMARY KEY,
                    label VARCHAR(50),  -- 'whale', 'exchange', 'dev', 'influencer'
                    owner_name VARCHAR(200),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # KOL Profiles - Key Opinion Leaders tracking
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS kols (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100),
                    x_handle VARCHAR(50),
                    telegram VARCHAR(100),
                    telegram_note TEXT,
                    chain_focus JSONB DEFAULT '["multi"]',
                    category VARCHAR(30) DEFAULT 'general',
                    tier VARCHAR(20) DEFAULT 'unknown',
                    language VARCHAR(10) DEFAULT 'en',
                    x_followers INTEGER DEFAULT 0,
                    avg_likes INTEGER DEFAULT 0,
                    avg_views INTEGER DEFAULT 0,
                    engagement TEXT,
                    total_calls INTEGER DEFAULT 0,
                    winning_calls INTEGER DEFAULT 0,
                    rug_calls INTEGER DEFAULT 0,
                    avg_return_pct DECIMAL(10, 2) DEFAULT 0,
                    best_call_return DECIMAL(10, 2) DEFAULT 0,
                    verified BOOLEAN DEFAULT FALSE,
                    verified_wallet BOOLEAN DEFAULT FALSE,
                    reputation_score INTEGER DEFAULT 50,
                    edge TEXT,
                    win_play TEXT,
                    notes TEXT,
                    source VARCHAR(20) DEFAULT 'grok',
                    first_seen TIMESTAMP DEFAULT NOW(),
                    last_active TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(x_handle)
                )
            """)

            # KOL Calls - Token recommendations/shills
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS kol_calls (
                    id SERIAL PRIMARY KEY,
                    kol_id INTEGER REFERENCES kols(id),
                    token_address VARCHAR(100),
                    token_symbol VARCHAR(50) NOT NULL,
                    chain VARCHAR(20) DEFAULT 'ton',
                    call_type VARCHAR(20) DEFAULT 'buy',
                    call_price_usd DECIMAL(30, 18) DEFAULT 0,
                    call_mcap DECIMAL(20, 2) DEFAULT 0,
                    source_platform VARCHAR(20) DEFAULT 'x',
                    source_url TEXT,
                    source_text TEXT,
                    peak_price_usd DECIMAL(30, 18) DEFAULT 0,
                    peak_mcap DECIMAL(20, 2) DEFAULT 0,
                    final_price_usd DECIMAL(30, 18) DEFAULT 0,
                    return_pct DECIMAL(10, 2) DEFAULT 0,
                    outcome VARCHAR(20) DEFAULT 'pending',
                    rugged BOOLEAN DEFAULT FALSE,
                    called_at TIMESTAMP DEFAULT NOW(),
                    peak_at TIMESTAMP,
                    resolved_at TIMESTAMP
                )
            """)

            # KOL Wallets - Verified wallet addresses
            await conn.execute("""
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
                )
            """)

            # TON ID verified users - wallet-to-identity correlation
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS verified_users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    tonid_sub VARCHAR(100) UNIQUE,
                    wallet_address VARCHAR(100),
                    wallet_raw VARCHAR(150),
                    name VARCHAR(200),
                    picture_url TEXT,
                    twitter_verified BOOLEAN DEFAULT FALSE,
                    youtube_verified BOOLEAN DEFAULT FALSE,
                    is_kol BOOLEAN DEFAULT FALSE,
                    kol_id INTEGER REFERENCES kols(id),
                    access_token TEXT,
                    refresh_token TEXT,
                    token_expires_at TIMESTAMP,
                    verified_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Create indexes for performance
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
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_api_keys_user_id
                ON api_keys(user_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_lottery_entries_user_id
                ON lottery_entries(user_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_lottery_entries_draw_id
                ON lottery_entries(draw_id)
            """)

            # Token tracking indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tracked_tokens_first_seen
                ON tracked_tokens(first_seen DESC)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tracked_tokens_safety_score
                ON tracked_tokens(safety_score)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tracked_tokens_rugged
                ON tracked_tokens(rugged)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_events_address
                ON token_events(token_address)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_events_type
                ON token_events(event_type)
            """)

            # Holder snapshot indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_holder_snapshots_token
                ON holder_snapshots(token_address)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_holder_snapshots_wallet
                ON holder_snapshots(wallet_address)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_holder_snapshots_time
                ON holder_snapshots(snapshot_at DESC)
            """)

            # Known wallet indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_known_wallets_label
                ON known_wallets(label)
            """)

            # KOL indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kols_x_handle
                ON kols(x_handle)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kols_category
                ON kols(category)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kols_reputation
                ON kols(reputation_score DESC)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kol_calls_kol
                ON kol_calls(kol_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kol_calls_token
                ON kol_calls(token_address)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kol_calls_time
                ON kol_calls(called_at DESC)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kol_wallets_kol
                ON kol_wallets(kol_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kol_wallets_address
                ON kol_wallets(wallet_address)
            """)

            # Verified users indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_verified_users_wallet
                ON verified_users(wallet_address)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_verified_users_tonid
                ON verified_users(tonid_sub)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_verified_users_kol
                ON verified_users(kol_id) WHERE kol_id IS NOT NULL
            """)

    @asynccontextmanager
    async def transaction(self):
        """
        Context manager for database transactions.

        Usage:
            async with db.transaction() as conn:
                await conn.execute(...)
                await conn.execute(...)
                # Auto-commits on success, rolls back on exception
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def execute(self, query: str, *args) -> str:
        """Execute a raw query"""
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """Fetch multiple rows"""
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Fetch single row"""
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args) -> Any:
        """Fetch single value"""
        async with self._pool.acquire() as conn:
            return await conn.fetchval(query, *args)


# Global database instance
db = Database()
