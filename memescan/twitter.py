"""
MemeScan Twitter Auto-Poster
Posts trending meme coins and new launches automatically.
The utility-first growth strategy.
"""
import os
import asyncio
import time
from datetime import datetime
from typing import Optional
import tweepy

from .api import MemeScanClient
from .models import Token, SafetyLevel


# Rate limits - conservative to avoid bans
TWEET_INTERVAL = 1800  # 30 minutes between tweets (48 tweets/day max)
MAX_TWEETS_PER_DAY = 48


class MemeScanTwitter:
    """
    Auto-posts meme coin data to Twitter.
    Utility-first content that people want to see daily.
    """

    def __init__(self):
        self.client: Optional[tweepy.Client] = None
        self.memescan: Optional[MemeScanClient] = None
        self.last_tweet_time: float = 0
        self.daily_tweets: int = 0
        self.day_start: float = 0
        self._running = False

    def initialize(self):
        """Initialize Twitter client from env vars."""
        api_key = os.getenv("MEMESCAN_TWITTER_API_KEY") or os.getenv("TWITTER_API_KEY")
        api_secret = os.getenv("MEMESCAN_TWITTER_API_SECRET") or os.getenv("TWITTER_API_SECRET")
        access_token = os.getenv("MEMESCAN_TWITTER_ACCESS_TOKEN") or os.getenv("TWITTER_ACCESS_TOKEN")
        access_secret = os.getenv("MEMESCAN_TWITTER_ACCESS_SECRET") or os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

        if all([api_key, api_secret, access_token, access_secret]):
            try:
                self.client = tweepy.Client(
                    consumer_key=api_key,
                    consumer_secret=api_secret,
                    access_token=access_token,
                    access_token_secret=access_secret
                )
                print("MemeScan Twitter client initialized")
            except Exception as e:
                print(f"MemeScan Twitter init failed: {e}")

        self.memescan = MemeScanClient(tonapi_key=os.getenv("TONAPI_KEY", ""))

    def _can_tweet(self) -> bool:
        """Check rate limits."""
        now = time.time()

        # Reset daily counter
        if now - self.day_start > 86400:
            self.daily_tweets = 0
            self.day_start = now

        if self.daily_tweets >= MAX_TWEETS_PER_DAY:
            return False

        return (now - self.last_tweet_time) >= TWEET_INTERVAL

    def _record_tweet(self):
        """Record tweet for rate limiting."""
        self.last_tweet_time = time.time()
        self.daily_tweets += 1

    async def post_trending_update(self):
        """Post trending meme coins update."""
        if not self.client or not self._can_tweet():
            return

        try:
            tokens = await self.memescan.get_trending(limit=5)
            if not tokens:
                return

            # Format the tweet
            lines = ["TON Meme Coins Trending Now", ""]

            for i, token in enumerate(tokens[:5], 1):
                change = f"+{token.price_change_24h:.0f}%" if token.price_change_24h >= 0 else f"{token.price_change_24h:.0f}%"
                emoji = "" if token.price_change_24h >= 0 else ""
                lines.append(f"{i}. ${token.symbol} {emoji} {change}")

            lines.append("")
            lines.append(f"Updated: {datetime.utcnow().strftime('%H:%M UTC')}")
            lines.append("")
            lines.append("#TON #MemeCoin #Crypto")

            tweet = "\n".join(lines)

            response = self.client.create_tweet(text=tweet)
            self._record_tweet()
            print(f"Posted trending update: {response.data['id']}")

        except tweepy.TooManyRequests:
            print("Twitter rate limit hit")
        except Exception as e:
            print(f"Trending tweet failed: {e}")

    async def post_new_launch_alert(self, token: Token):
        """Post alert for a promising new launch."""
        if not self.client or not self._can_tweet():
            return

        try:
            # Only post if looks somewhat safe
            if token.safety_level == SafetyLevel.DANGER:
                return

            safety_emoji = token.safety_emoji()
            liq = token.liquidity_usd

            if liq >= 1_000_000:
                liq_str = f"${liq / 1_000_000:.1f}M"
            elif liq >= 1_000:
                liq_str = f"${liq / 1_000:.1f}K"
            else:
                liq_str = f"${liq:.0f}"

            tweet = (
                f" NEW LAUNCH on TON\n\n"
                f"${token.symbol}\n"
                f" Liquidity: {liq_str}\n"
                f"{safety_emoji} Safety: {token.safety_level.value.upper()}\n\n"
                f"DYOR - Not financial advice\n\n"
                f"#TON #NewListing #MemeCoin"
            )

            response = self.client.create_tweet(text=tweet)
            self._record_tweet()
            print(f"Posted new launch: ${token.symbol}")

        except Exception as e:
            print(f"New launch tweet failed: {e}")

    async def post_whale_alert(self, symbol: str, action: str, amount_usd: float):
        """Post whale movement alert."""
        if not self.client or not self._can_tweet():
            return

        try:
            emoji = "" if action == "buy" else ""
            action_text = "bought" if action == "buy" else "sold"

            if amount_usd >= 1_000_000:
                amount_str = f"${amount_usd / 1_000_000:.1f}M"
            else:
                amount_str = f"${amount_usd / 1_000:.0f}K"

            tweet = (
                f" WHALE ALERT\n\n"
                f"{emoji} Whale {action_text} {amount_str} of ${symbol}\n\n"
                f"#TON #WhaleAlert #MemeCoin"
            )

            response = self.client.create_tweet(text=tweet)
            self._record_tweet()
            print(f"Posted whale alert: ${symbol}")

        except Exception as e:
            print(f"Whale tweet failed: {e}")

    async def run_auto_poster(self, interval_seconds: int = 1800):
        """
        Run automated posting loop.
        Posts trending update every 30 minutes.
        """
        if not self.client:
            self.initialize()

        self._running = True
        print(f"MemeScan auto-poster started (every {interval_seconds}s)")

        while self._running:
            try:
                await self.post_trending_update()
            except Exception as e:
                print(f"Auto-post error: {e}")

            await asyncio.sleep(interval_seconds)

    def stop(self):
        """Stop the auto-poster."""
        self._running = False


# Global instance
memescan_twitter = MemeScanTwitter()


async def start_twitter_auto_poster():
    """Start the Twitter auto-poster in background."""
    await memescan_twitter.run_auto_poster()
