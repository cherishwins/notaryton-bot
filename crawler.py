"""
Token Crawler - THE DATA MOAT
==============================
Continuously discovers and analyzes TON tokens for rug detection.
Runs as a background task alongside the bot.

Usage:
    # Start crawler as background task
    asyncio.create_task(start_crawler())

    # Or run standalone for testing
    python crawler.py
"""

import asyncio
import os
from datetime import datetime
from typing import Optional

from database import db, TrackedToken
from memescan.api import MemeScanClient, TonAPI, GeckoTerminalAPI
from memescan.models import SafetyLevel


class TokenCrawler:
    """
    Crawls TON blockchain for new tokens and analyzes their safety.
    Builds the data moat by tracking every token from launch.
    """

    def __init__(self, tonapi_key: str = ""):
        self.client = MemeScanClient(tonapi_key=tonapi_key)
        self.running = False
        self._crawl_interval = 60  # seconds between crawl cycles
        self._analyze_interval = 5  # seconds between token analyses (rate limit)

    async def start(self):
        """Start the crawler loop."""
        self.running = True
        print("🕷️ Token crawler started")

        while self.running:
            try:
                await self._crawl_cycle()
            except Exception as e:
                print(f"❌ Crawler error: {e}")

            await asyncio.sleep(self._crawl_interval)

    async def stop(self):
        """Stop the crawler."""
        self.running = False
        await self.client.close()
        print("🛑 Token crawler stopped")

    async def _crawl_cycle(self):
        """Single crawl cycle - discover and analyze tokens."""
        # 1. Get new token launches from GeckoTerminal
        new_tokens = await self.client.get_new_launches(limit=20)
        print(f"📡 Found {len(new_tokens)} new tokens")

        for token in new_tokens:
            if not token.address:
                continue

            # Check if we already track this token
            existing = await db.tokens.get(token.address)
            if existing:
                # Update current state if > 1 hour since last update
                if existing.last_updated:
                    hours_ago = (datetime.now() - existing.last_updated).total_seconds() / 3600
                    if hours_ago < 1:
                        continue  # Skip, recently updated

            # Analyze token safety
            try:
                await self._analyze_and_store(token.address)
                await asyncio.sleep(self._analyze_interval)  # Rate limit
            except Exception as e:
                print(f"⚠️ Failed to analyze {token.symbol}: {e}")

        # 2. Get trending tokens (these may be older but worth tracking)
        trending = await self.client.get_trending(limit=10)
        for token in trending:
            if not token.address:
                continue

            existing = await db.tokens.get(token.address)
            if not existing:
                try:
                    await self._analyze_and_store(token.address)
                    await asyncio.sleep(self._analyze_interval)
                except Exception as e:
                    print(f"⚠️ Failed to analyze trending {token.symbol}: {e}")

    async def _analyze_and_store(self, address: str) -> Optional[TrackedToken]:
        """Analyze a token and store results with holder snapshots."""
        # Get detailed analysis
        analysis = await self.client.analyze_token_safety(address)

        # Get holder data for snapshots
        holders = await self.client.tonapi.get_jetton_holders(address, limit=20)
        jetton_info = await self.client.tonapi.get_jetton_info(address)
        total_supply = float(jetton_info.get("total_supply", 0) or 0) if jetton_info else 0

        # Convert safety level to score
        safety_score = 50  # Default
        if analysis.safety_level == SafetyLevel.SAFE:
            safety_score = 90
        elif analysis.safety_level == SafetyLevel.WARNING:
            safety_score = 50
        elif analysis.safety_level == SafetyLevel.DANGER:
            safety_score = 20
        elif analysis.safety_level == SafetyLevel.UNKNOWN:
            safety_score = 30

        # Adjust score based on holder metrics
        if analysis.holder_count >= 100:
            safety_score = min(100, safety_score + 10)
        elif analysis.holder_count < 10:
            safety_score = max(0, safety_score - 20)

        if analysis.dev_wallet_percent > 50:
            safety_score = max(0, safety_score - 30)
        elif analysis.dev_wallet_percent > 20:
            safety_score = max(0, safety_score - 15)

        # Build tracked token
        tracked = TrackedToken(
            address=address,
            symbol=analysis.symbol,
            name=analysis.name,
            decimals=analysis.decimals or 9,
            total_supply=analysis.total_supply or 0,
            first_seen=datetime.now(),
            initial_holder_count=analysis.holder_count or 0,
            initial_top_holder_pct=analysis.dev_wallet_percent or 0,
            initial_liquidity_usd=analysis.liquidity_usd or 0,
            safety_score=safety_score,
            current_holder_count=analysis.holder_count or 0,
            current_top_holder_pct=analysis.dev_wallet_percent or 0,
            current_price_usd=analysis.price_usd or 0,
        )

        # Store in database
        await db.tokens.upsert(tracked)

        # Log event for new token
        existing = await db.tokens.get(address)
        is_new = not existing or not existing.last_updated

        if is_new:
            await db.tokens.add_event(
                address,
                "deploy",
                {
                    "symbol": analysis.symbol,
                    "holder_count": analysis.holder_count,
                    "top_holder_pct": analysis.dev_wallet_percent,
                    "safety_score": safety_score,
                }
            )
            print(f"✅ New token tracked: {analysis.symbol} (score: {safety_score})")

            # Snapshot initial holders for new tokens
            if holders and total_supply > 0:
                count = await db.wallets.snapshot_holders(address, holders, total_supply)
                print(f"   📸 Snapshotted {count} initial holders")
        else:
            # For existing tokens, detect whale changes before snapshotting
            if holders and total_supply > 0:
                changes = await db.wallets.detect_whale_changes(
                    address, holders, total_supply, threshold_pct=5.0
                )

                for change in changes:
                    if change["type"] == "whale_entry":
                        await db.tokens.add_event(address, "whale_entry", change)
                        print(f"   🐋 Whale entry: {change['wallet'][:12]}... ({change['pct']:.1f}%)")
                    elif change["type"] == "whale_exit":
                        await db.tokens.add_event(address, "whale_exit", change)
                        print(f"   🏃 Whale exit: {change['wallet'][:12]}... (sold {change['pct_sold']:.1f}%)")

                # Snapshot current holders
                await db.wallets.snapshot_holders(address, holders, total_supply)

            print(f"🔄 Updated: {analysis.symbol} (score: {safety_score})")

        return tracked

    async def analyze_single(self, address: str) -> Optional[TrackedToken]:
        """Analyze a single token on-demand."""
        return await self._analyze_and_store(address)

    async def refresh_rugged_detection(self):
        """
        Check tracked tokens for rug indicators.
        Run periodically to detect rugs as they happen.
        """
        # Get tokens tracked in last 7 days that aren't already marked rugged
        recent_tokens = await db.tokens.get_recent(limit=500)

        for token in recent_tokens:
            if token.rugged:
                continue  # Already marked

            # Re-analyze
            try:
                analysis = await self.client.analyze_token_safety(token.address)

                # Rug indicators:
                # 1. Dev sold > 90% of their holdings
                if analysis.dev_wallet_percent < 5 and token.initial_top_holder_pct > 30:
                    await db.tokens.mark_rugged(token.address)
                    await db.tokens.add_event(
                        token.address,
                        "rug",
                        {
                            "initial_dev_pct": token.initial_top_holder_pct,
                            "current_dev_pct": analysis.dev_wallet_percent,
                            "detection_method": "dev_exit",
                        }
                    )
                    print(f"🚨 RUG DETECTED: {token.symbol}")

                # 2. Holders dropped by 80%+
                if analysis.holder_count and token.initial_holder_count:
                    holder_drop = 1 - (analysis.holder_count / token.initial_holder_count)
                    if holder_drop > 0.8:
                        await db.tokens.mark_rugged(token.address)
                        await db.tokens.add_event(
                            token.address,
                            "rug",
                            {
                                "initial_holders": token.initial_holder_count,
                                "current_holders": analysis.holder_count,
                                "detection_method": "holder_exodus",
                            }
                        )
                        print(f"🚨 RUG DETECTED (holder exodus): {token.symbol}")

                await asyncio.sleep(self._analyze_interval)

            except Exception as e:
                print(f"⚠️ Failed to check {token.symbol}: {e}")


# Global crawler instance
crawler = TokenCrawler(tonapi_key=os.getenv("TONAPI_KEY", ""))


async def start_crawler():
    """Start the crawler (call from bot startup)."""
    await crawler.start()


async def stop_crawler():
    """Stop the crawler (call from bot shutdown)."""
    await crawler.stop()


# ========================
# STANDALONE MODE
# ========================

async def main():
    """Run crawler standalone for testing."""
    print("🕷️ Starting Token Crawler (standalone mode)")

    # Connect to database
    await db.connect()

    try:
        # Run a single crawl cycle
        await crawler._crawl_cycle()

        # Show stats
        stats = await db.tokens.get_stats()
        print(f"\n📊 Token Database Stats:")
        print(f"   Total tracked: {stats['total_tracked']}")
        print(f"   Rugged: {stats['rugged_count']}")
        print(f"   Safe (80+): {stats['safe_count']}")
        print(f"   Tracked today: {stats['tracked_today']}")
        print(f"   Rug rate: {stats['rug_rate']}%")

    finally:
        await crawler.client.close()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
