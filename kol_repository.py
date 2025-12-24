"""
KOL Repository
==============
Database operations for KOL intelligence tracking.
82 KOLs across 19 languages, 6 categories.
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from asyncpg import Pool

from kol_models import KOL, KOLCall, KOLWallet, KOL_SCHEMA, GROK_KOL_SEED


class KOLRepository:
    """Repository for KOL intelligence operations."""

    def __init__(self, pool: Pool):
        self._pool = pool

    async def init_schema(self) -> None:
        """Initialize KOL tables."""
        async with self._pool.acquire() as conn:
            await conn.execute(KOL_SCHEMA)
        print("KOL schema initialized")

    async def seed_from_grok(self) -> int:
        """Seed database with Grok's 82 KOL intel. Returns count inserted."""
        count = 0
        for kol_data in GROK_KOL_SEED:
            try:
                existing = await self.get_by_x_handle(kol_data.get("x_handle"))
                if not existing:
                    await self.create(**kol_data)
                    count += 1
            except Exception as e:
                print(f"Failed to seed {kol_data.get('x_handle')}: {e}")
        return count

    # ========================
    # CRUD Operations
    # ========================

    async def create(self, **kwargs) -> KOL:
        """Create a new KOL profile."""
        # Convert chain_focus list to JSON
        chain_focus = kwargs.get('chain_focus', ['multi'])
        if isinstance(chain_focus, list):
            chain_focus = json.dumps(chain_focus)

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO kols (
                    name, x_handle, telegram, telegram_note,
                    chain_focus, category, tier, language,
                    x_followers, avg_likes, avg_views, engagement,
                    total_calls, winning_calls, rug_calls,
                    avg_return_pct, best_call_return,
                    verified, verified_wallet, reputation_score,
                    edge, win_play, notes, source
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                    $21, $22, $23, $24
                )
                ON CONFLICT (x_handle) DO UPDATE SET
                    telegram = COALESCE(EXCLUDED.telegram, kols.telegram),
                    telegram_note = COALESCE(EXCLUDED.telegram_note, kols.telegram_note),
                    edge = COALESCE(EXCLUDED.edge, kols.edge),
                    win_play = COALESCE(EXCLUDED.win_play, kols.win_play),
                    last_active = NOW()
                RETURNING *
            """,
                kwargs.get('x_handle', ''),  # Use x_handle as name if not provided
                kwargs.get('x_handle'),
                kwargs.get('telegram'),
                kwargs.get('telegram_note'),
                chain_focus,
                kwargs.get('category', 'general'),
                kwargs.get('tier', 'unknown'),
                kwargs.get('language', 'en'),
                kwargs.get('x_followers', 0),
                kwargs.get('avg_likes', 0),
                kwargs.get('avg_views', 0),
                kwargs.get('engagement'),
                kwargs.get('total_calls', 0),
                kwargs.get('winning_calls', 0),
                kwargs.get('rug_calls', 0),
                kwargs.get('avg_return_pct', 0),
                kwargs.get('best_call_return', 0),
                kwargs.get('verified', False),
                kwargs.get('verified_wallet', False),
                kwargs.get('reputation_score', 50),
                kwargs.get('edge'),
                kwargs.get('win_play'),
                kwargs.get('notes'),
                kwargs.get('source', 'grok')
            )
            return self._row_to_kol(row)

    async def get(self, kol_id: int) -> Optional[KOL]:
        """Get KOL by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM kols WHERE id = $1", kol_id
            )
            return self._row_to_kol(row) if row else None

    async def get_by_x_handle(self, x_handle: str) -> Optional[KOL]:
        """Get KOL by X handle."""
        if not x_handle:
            return None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM kols WHERE x_handle = $1", x_handle
            )
            return self._row_to_kol(row) if row else None

    async def list_all(
        self,
        chain_focus: Optional[str] = None,
        category: Optional[str] = None,
        language: Optional[str] = None,
        min_reputation: int = 0,
        verified_only: bool = False,
        limit: int = 100
    ) -> List[KOL]:
        """List KOLs with optional filters."""
        async with self._pool.acquire() as conn:
            query = "SELECT * FROM kols WHERE reputation_score >= $1"
            params = [min_reputation]
            idx = 2

            if chain_focus:
                query += f" AND chain_focus ? ${idx}"
                params.append(chain_focus)
                idx += 1

            if category:
                query += f" AND category = ${idx}"
                params.append(category)
                idx += 1

            if language:
                query += f" AND language = ${idx}"
                params.append(language)
                idx += 1

            if verified_only:
                query += " AND verified = TRUE"

            query += f" ORDER BY reputation_score DESC, avg_views DESC LIMIT ${idx}"
            params.append(limit)

            rows = await conn.fetch(query, *params)
            return [self._row_to_kol(row) for row in rows]

    async def get_by_language(self, language: str, limit: int = 50) -> List[KOL]:
        """Get KOLs by primary language."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM kols
                WHERE language = $1
                ORDER BY reputation_score DESC, avg_views DESC
                LIMIT $2
            """, language, limit)
            return [self._row_to_kol(row) for row in rows]

    async def get_by_category(self, category: str, limit: int = 50) -> List[KOL]:
        """Get KOLs by category."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM kols
                WHERE category = $1
                ORDER BY reputation_score DESC, avg_views DESC
                LIMIT $2
            """, category, limit)
            return [self._row_to_kol(row) for row in rows]

    async def get_by_chain(self, chain: str, limit: int = 50) -> List[KOL]:
        """Get KOLs that focus on a specific chain."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM kols
                WHERE chain_focus ? $1
                ORDER BY reputation_score DESC, avg_views DESC
                LIMIT $2
            """, chain, limit)
            return [self._row_to_kol(row) for row in rows]

    async def get_leaderboard(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get top KOLs by win rate and return."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    id, x_handle, telegram, category, chain_focus,
                    language, tier, verified,
                    total_calls, winning_calls, rug_calls,
                    avg_return_pct, best_call_return, reputation_score,
                    edge,
                    CASE WHEN total_calls > 0
                        THEN ROUND(winning_calls::numeric / total_calls * 100, 1)
                        ELSE 0
                    END as win_rate,
                    CASE WHEN total_calls > 0
                        THEN ROUND(rug_calls::numeric / total_calls * 100, 1)
                        ELSE 0
                    END as rug_rate
                FROM kols
                WHERE total_calls >= 3
                ORDER BY win_rate DESC, avg_return_pct DESC
                LIMIT $1
            """, limit)
            return [self._row_to_dict(row) for row in rows]

    async def update_stats(self, kol_id: int) -> None:
        """Recalculate KOL stats from their calls."""
        async with self._pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_calls,
                    COUNT(*) FILTER (WHERE outcome = 'win') as winning_calls,
                    COUNT(*) FILTER (WHERE outcome = 'rug' OR rugged = TRUE) as rug_calls,
                    COALESCE(AVG(return_pct), 0) as avg_return_pct,
                    COALESCE(MAX(return_pct), 0) as best_call_return
                FROM kol_calls
                WHERE kol_id = $1
            """, kol_id)

            if stats:
                total = stats['total_calls'] or 0
                wins = stats['winning_calls'] or 0
                rugs = stats['rug_calls'] or 0

                if total > 0:
                    win_rate = wins / total
                    rug_rate = rugs / total
                    reputation = int(50 + (win_rate * 30) - (rug_rate * 40))
                    reputation = max(0, min(100, reputation))
                else:
                    reputation = 50

                await conn.execute("""
                    UPDATE kols SET
                        total_calls = $2,
                        winning_calls = $3,
                        rug_calls = $4,
                        avg_return_pct = $5,
                        best_call_return = $6,
                        reputation_score = $7,
                        last_active = NOW()
                    WHERE id = $1
                """,
                    kol_id,
                    stats['total_calls'],
                    stats['winning_calls'],
                    stats['rug_calls'],
                    float(stats['avg_return_pct']),
                    float(stats['best_call_return']),
                    reputation
                )

    # ========================
    # Call Tracking
    # ========================

    async def record_call(
        self,
        kol_id: int,
        token_symbol: str,
        token_address: Optional[str] = None,
        chain: str = "ton",
        call_type: str = "buy",
        call_price_usd: float = 0,
        call_mcap: float = 0,
        source_platform: str = "x",
        source_url: Optional[str] = None,
        source_text: Optional[str] = None
    ) -> KOLCall:
        """Record a new call from a KOL."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO kol_calls (
                    kol_id, token_address, token_symbol, chain,
                    call_type, call_price_usd, call_mcap,
                    source_platform, source_url, source_text
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING *
            """,
                kol_id, token_address, token_symbol, chain,
                call_type, call_price_usd, call_mcap,
                source_platform, source_url, source_text
            )
            return self._row_to_call(row)

    async def update_call_outcome(
        self,
        call_id: int,
        peak_price_usd: float = 0,
        peak_mcap: float = 0,
        final_price_usd: float = 0,
        rugged: bool = False
    ) -> None:
        """Update a call's outcome."""
        async with self._pool.acquire() as conn:
            call = await conn.fetchrow(
                "SELECT call_price_usd, kol_id FROM kol_calls WHERE id = $1", call_id
            )
            if not call:
                return

            call_price = float(call['call_price_usd']) or 1

            if final_price_usd > 0:
                return_pct = ((final_price_usd - call_price) / call_price) * 100
            elif peak_price_usd > 0:
                return_pct = ((peak_price_usd - call_price) / call_price) * 100
            else:
                return_pct = 0

            if rugged:
                outcome = "rug"
            elif return_pct >= 100:
                outcome = "win"
            elif return_pct <= -50:
                outcome = "loss"
            else:
                outcome = "pending"

            await conn.execute("""
                UPDATE kol_calls SET
                    peak_price_usd = $2,
                    peak_mcap = $3,
                    final_price_usd = $4,
                    return_pct = $5,
                    outcome = $6,
                    rugged = $7,
                    resolved_at = CASE WHEN $6 != 'pending' THEN NOW() ELSE NULL END,
                    peak_at = CASE WHEN $2 > 0 THEN NOW() ELSE peak_at END
                WHERE id = $1
            """, call_id, peak_price_usd, peak_mcap, final_price_usd,
                return_pct, outcome, rugged
            )

            if call['kol_id']:
                await self.update_stats(call['kol_id'])

    async def get_calls_for_token(
        self,
        token_address: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get all KOL calls for a specific token."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    c.*,
                    k.x_handle,
                    k.telegram,
                    k.category,
                    k.reputation_score,
                    k.verified
                FROM kol_calls c
                JOIN kols k ON c.kol_id = k.id
                WHERE c.token_address = $1
                ORDER BY c.called_at DESC
                LIMIT $2
            """, token_address, limit)
            return [self._row_to_dict(row) for row in rows]

    async def get_recent_calls(
        self,
        chain: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent KOL calls."""
        async with self._pool.acquire() as conn:
            if chain:
                rows = await conn.fetch("""
                    SELECT
                        c.*,
                        k.x_handle,
                        k.telegram,
                        k.category,
                        k.reputation_score
                    FROM kol_calls c
                    JOIN kols k ON c.kol_id = k.id
                    WHERE c.chain = $1
                    ORDER BY c.called_at DESC
                    LIMIT $2
                """, chain, limit)
            else:
                rows = await conn.fetch("""
                    SELECT
                        c.*,
                        k.x_handle,
                        k.telegram,
                        k.category,
                        k.reputation_score
                    FROM kol_calls c
                    JOIN kols k ON c.kol_id = k.id
                    ORDER BY c.called_at DESC
                    LIMIT $1
                """, limit)
            return [self._row_to_dict(row) for row in rows]

    # ========================
    # Wallet Tracking
    # ========================

    async def link_wallet(
        self,
        kol_id: int,
        wallet_address: str,
        chain: str = "ton",
        verified: bool = False,
        verification_method: Optional[str] = None,
        notes: Optional[str] = None
    ) -> KOLWallet:
        """Link a wallet to a KOL."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO kol_wallets (
                    kol_id, wallet_address, chain, verified,
                    verification_method, notes, first_seen
                ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
                ON CONFLICT (wallet_address, chain) DO UPDATE SET
                    verified = COALESCE($4, kol_wallets.verified),
                    notes = COALESCE($6, kol_wallets.notes)
                RETURNING *
            """, kol_id, wallet_address, chain, verified,
                verification_method, notes
            )
            return self._row_to_wallet(row)

    async def get_kol_wallets(self, kol_id: int) -> List[KOLWallet]:
        """Get all wallets linked to a KOL."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM kol_wallets WHERE kol_id = $1", kol_id
            )
            return [self._row_to_wallet(row) for row in rows]

    async def find_kol_by_wallet(
        self,
        wallet_address: str
    ) -> Optional[Dict[str, Any]]:
        """Find KOL associated with a wallet."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    k.*,
                    w.verified as wallet_verified,
                    w.verification_method
                FROM kol_wallets w
                JOIN kols k ON w.kol_id = k.id
                WHERE w.wallet_address = $1
            """, wallet_address)
            return self._row_to_dict(row) if row else None

    # ========================
    # Analytics
    # ========================

    async def get_stats(self) -> Dict[str, Any]:
        """Get overall KOL tracking stats."""
        async with self._pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_kols,
                    COUNT(*) FILTER (WHERE category = 'ton') as ton_kols,
                    COUNT(*) FILTER (WHERE category = 'solana') as sol_kols,
                    COUNT(*) FILTER (WHERE category = 'watchdog') as watchdog_kols,
                    COUNT(*) FILTER (WHERE category = 'regional') as regional_kols,
                    COUNT(*) FILTER (WHERE verified = TRUE) as verified_kols,
                    COUNT(DISTINCT language) as languages,
                    AVG(reputation_score) as avg_reputation
                FROM kols
            """)

            call_stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_calls,
                    COUNT(*) FILTER (WHERE outcome = 'win') as winning_calls,
                    COUNT(*) FILTER (WHERE outcome = 'rug') as rug_calls,
                    AVG(return_pct) FILTER (WHERE outcome != 'pending') as avg_return
                FROM kol_calls
            """)

            # Get language distribution
            lang_dist = await conn.fetch("""
                SELECT language, COUNT(*) as count
                FROM kols
                GROUP BY language
                ORDER BY count DESC
            """)

            return {
                "total_kols": stats['total_kols'] or 0,
                "ton_kols": stats['ton_kols'] or 0,
                "sol_kols": stats['sol_kols'] or 0,
                "watchdog_kols": stats['watchdog_kols'] or 0,
                "regional_kols": stats['regional_kols'] or 0,
                "verified_kols": stats['verified_kols'] or 0,
                "languages_covered": stats['languages'] or 0,
                "avg_reputation": float(stats['avg_reputation'] or 50),
                "total_calls": call_stats['total_calls'] or 0,
                "winning_calls": call_stats['winning_calls'] or 0,
                "rug_calls": call_stats['rug_calls'] or 0,
                "avg_return": float(call_stats['avg_return'] or 0),
                "language_distribution": {r['language']: r['count'] for r in lang_dist}
            }

    async def get_available_languages(self) -> List[str]:
        """Get list of languages we have KOLs for."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT language FROM kols ORDER BY language
            """)
            return [r['language'] for r in rows]

    async def get_available_categories(self) -> List[str]:
        """Get list of KOL categories."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT category FROM kols ORDER BY category
            """)
            return [r['category'] for r in rows]

    async def get_available_chains(self) -> List[str]:
        """Get list of chains KOLs focus on."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT jsonb_array_elements_text(chain_focus) as chain
                FROM kols
                ORDER BY chain
            """)
            return [r['chain'] for r in rows]

    # ========================
    # Helpers
    # ========================

    def _row_to_kol(self, row) -> Optional[KOL]:
        """Convert database row to KOL object."""
        if not row:
            return None
        d = dict(row)
        # Convert Decimal to float
        for k in ['avg_return_pct', 'best_call_return']:
            if k in d and d[k] is not None:
                d[k] = float(d[k])
        # chain_focus is JSONB, already parsed
        return KOL(**d)

    def _row_to_call(self, row) -> Optional[KOLCall]:
        """Convert database row to KOLCall object."""
        if not row:
            return None
        d = dict(row)
        for k in ['call_price_usd', 'call_mcap', 'peak_price_usd',
                  'peak_mcap', 'final_price_usd', 'return_pct']:
            if k in d and d[k] is not None:
                d[k] = float(d[k])
        return KOLCall(**d)

    def _row_to_wallet(self, row) -> Optional[KOLWallet]:
        """Convert database row to KOLWallet object."""
        if not row:
            return None
        d = dict(row)
        for k in ['total_pnl_usd']:
            if k in d and d[k] is not None:
                d[k] = float(d[k])
        return KOLWallet(**d)

    def _row_to_dict(self, row) -> Optional[Dict[str, Any]]:
        """Convert database row to dict with proper type conversion."""
        if not row:
            return None
        d = dict(row)
        # Convert Decimal types
        for k, v in d.items():
            if hasattr(v, 'is_nan'):  # Decimal check
                d[k] = float(v)
        return d
