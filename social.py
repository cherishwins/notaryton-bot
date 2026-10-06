"""
Social Media Auto-Poster for MemeSeal
=====================================
Posts to X (Twitter) and Telegram channel on every seal.
Rate-limited to avoid bans.
"""

import os
import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
import tweepy
from aiogram import Bot

# Rate limiting config
TWITTER_MIN_INTERVAL = 60  # Minimum 60 seconds between tweets
TELEGRAM_MIN_INTERVAL = 10  # Minimum 10 seconds between TG posts
MAX_POSTS_PER_HOUR = 30  # Max posts to either platform per hour

@dataclass
class RateLimiter:
    """Simple rate limiter to avoid API bans"""
    last_twitter_post: float = 0
    last_telegram_post: float = 0
    hourly_posts: int = 0
    hour_start: float = 0

    def can_post_twitter(self) -> bool:
        now = time.time()
        self._reset_hourly_if_needed(now)
        if self.hourly_posts >= MAX_POSTS_PER_HOUR:
            return False
        return (now - self.last_twitter_post) >= TWITTER_MIN_INTERVAL

    def can_post_telegram(self) -> bool:
        now = time.time()
        self._reset_hourly_if_needed(now)
        if self.hourly_posts >= MAX_POSTS_PER_HOUR:
            return False
        return (now - self.last_telegram_post) >= TELEGRAM_MIN_INTERVAL

    def record_twitter_post(self):
        self.last_twitter_post = time.time()
        self.hourly_posts += 1

    def record_telegram_post(self):
        self.last_telegram_post = time.time()
        self.hourly_posts += 1

    def _reset_hourly_if_needed(self, now: float):
        if now - self.hour_start > 3600:
            self.hourly_posts = 0
            self.hour_start = now


# Global rate limiter
rate_limiter = RateLimiter()


class SocialPoster:
    """
    Handles posting to X (Twitter) and Telegram channel.
    Thread-safe and rate-limited.
    """

    def __init__(self):
        self.twitter_client: Optional[tweepy.Client] = None
        self.telegram_bot: Optional[Bot] = None
        self.telegram_channel: Optional[str] = None
        self._initialized = False

    def initialize(self):
        """Initialize API clients from environment variables"""
        if self._initialized:
            return

        # Twitter/X API v2 setup
        twitter_api_key = os.getenv("TWITTER_API_KEY")
        twitter_api_secret = os.getenv("TWITTER_API_SECRET")
        twitter_access_token = os.getenv("TWITTER_ACCESS_TOKEN")
        twitter_access_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

        if all([twitter_api_key, twitter_api_secret, twitter_access_token, twitter_access_secret]):
            try:
                self.twitter_client = tweepy.Client(
                    consumer_key=twitter_api_key,
                    consumer_secret=twitter_api_secret,
                    access_token=twitter_access_token,
                    access_token_secret=twitter_access_secret
                )
                print("✅ Twitter/X client initialized")
            except Exception as e:
                print(f"⚠️ Twitter init failed: {e}")
        else:
            print("⚠️ Twitter credentials not set, skipping X posting")

        # Telegram channel setup
        telegram_token = os.getenv("MEMESEAL_BOT_TOKEN")
        self.telegram_channel = os.getenv("TELEGRAM_CHANNEL_ID", "@MemeSealTON")

        if telegram_token:
            try:
                self.telegram_bot = Bot(token=telegram_token)
                print(f"✅ Telegram bot initialized for channel {self.telegram_channel}")
            except Exception as e:
                print(f"⚠️ Telegram init failed: {e}")

        self._initialized = True

    async def post_seal_announcement(
        self,
        file_hash: str,
        pot_stars: Optional[int] = None,
        pot_ton: Optional[float] = None,
        next_draw: Optional[str] = None,
        seal_type: str = "file"
    ):
        """
        Post seal announcement to all platforms.
        Rate-limited to avoid bans. The lottery lines are left out when
        pot_stars is None (the lottery is off: see LOTTERY_ENABLED in bot.py).
        """
        if not self._initialized:
            self.initialize()

        # Build the message
        verify_url = f"https://notaryton.com/api/v1/verify/{file_hash}"
        short_hash = file_hash[:12]

        lottery = pot_stars is not None
        pot_line = (f"🎰 Lottery pot: {pot_stars} ⭐ (~{pot_ton:.4f} TON)\n"
                    f"⏰ Next draw: {next_draw}\n") if lottery else ""
        twitter_pot_line = (f"🎰 Pot: {pot_stars}⭐ (~{pot_ton:.4f} TON)\n"
                            f"⏰ Draw: {next_draw}\n") if lottery else ""

        message = (
            f"🐸 New bag sealed forever!\n\n"
            f"🔗 Hash: {short_hash}...\n"
            f"{pot_line}\n"
            f"Seal yours or stay poor.\n"
            f"👉 t.me/MemeSealTON_bot"
        )

        twitter_message = (
            f"🐸 New bag sealed forever!\n\n"
            f"🔗 {verify_url}\n"
            f"{twitter_pot_line}\n"
            f"Seal yours 👉 t.me/MemeSealTON_bot\n\n"
            f"#TON #MemeSeal #Crypto #Web3"
        )

        # Post to Twitter (with rate limiting)
        asyncio.create_task(self._post_to_twitter(twitter_message))

        # Post to Telegram channel (with rate limiting)
        asyncio.create_task(self._post_to_telegram(message, verify_url))

    async def _post_to_twitter(self, message: str):
        """Post to Twitter/X with rate limiting"""
        if not self.twitter_client:
            return

        if not rate_limiter.can_post_twitter():
            print("⏳ Twitter rate limited, skipping")
            return

        try:
            response = self.twitter_client.create_tweet(text=message)
            rate_limiter.record_twitter_post()
            print(f"✅ Posted to X: {response.data['id']}")
        except tweepy.TooManyRequests:
            print("⚠️ Twitter rate limit hit (API side)")
        except tweepy.Forbidden as e:
            print(f"⚠️ Twitter forbidden (check permissions): {e}")
        except Exception as e:
            print(f"❌ Twitter post failed: {e}")

    async def _post_to_telegram(self, message: str, verify_url: str):
        """Post to Telegram channel with rate limiting"""
        if not self.telegram_bot or not self.telegram_channel:
            return

        if not rate_limiter.can_post_telegram():
            print("⏳ Telegram rate limited, skipping")
            return

        try:
            # Send with inline button
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Verify Seal", url=verify_url)],
                [InlineKeyboardButton(text="🐸 Start Sealing", url="https://t.me/MemeSealTON_bot")]
            ])

            await self.telegram_bot.send_message(
                chat_id=self.telegram_channel,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            rate_limiter.record_telegram_post()
            print(f"✅ Posted to Telegram channel {self.telegram_channel}")
        except Exception as e:
            print(f"❌ Telegram post failed: {e}")

    async def post_lottery_winner(self, winner_id: int, prize_amount: float, prize_stars: int):
        """Announce lottery winner"""
        if not self._initialized:
            self.initialize()

        message = (
            f"🎉🐸 LOTTERY WINNER! 🐸🎉\n\n"
            f"Someone just won the pot!\n"
            f"💰 Prize: {prize_stars} ⭐ (~{prize_amount:.4f} TON)\n\n"
            f"New round starting NOW.\n"
            f"Seal anything = lottery ticket.\n\n"
            f"👉 t.me/MemeSealTON_bot"
        )

        twitter_msg = (
            f"🎉🐸 LOTTERY WINNER!\n\n"
            f"💰 {prize_stars}⭐ (~{prize_amount:.4f} TON) WON!\n\n"
            f"New round starting. Every seal = ticket.\n\n"
            f"👉 t.me/MemeSealTON_bot\n\n"
            f"#TON #MemeSeal #Lottery #Winner"
        )

        asyncio.create_task(self._post_to_twitter(twitter_msg))
        asyncio.create_task(self._post_to_telegram(message, "https://t.me/MemeSealTON_bot"))


# Global singleton
social_poster = SocialPoster()


async def announce_seal(file_hash: str, pot_stars: Optional[int] = None,
                        pot_ton: Optional[float] = None, next_draw: Optional[str] = None):
    """Convenience function to announce a seal (no lottery lines without a pot)"""
    await social_poster.post_seal_announcement(file_hash, pot_stars, pot_ton, next_draw)


# =============================================================================
# TOKEN INTELLIGENCE AUTO-POSTING
# =============================================================================

class TokenPoster:
    """
    Auto-posts token intelligence to X and Telegram.
    - Rug detections (high priority - always post)
    - Low safety scores (warnings)
    - Whale movements (optional)
    """

    def __init__(self):
        self.twitter_client: Optional[tweepy.Client] = None
        self.telegram_bot: Optional[Bot] = None
        self.telegram_channel: Optional[str] = None
        self._initialized = False

    def initialize(self):
        """Initialize from environment (shares creds with SocialPoster)"""
        if self._initialized:
            return

        twitter_api_key = os.getenv("TWITTER_API_KEY")
        twitter_api_secret = os.getenv("TWITTER_API_SECRET")
        twitter_access_token = os.getenv("TWITTER_ACCESS_TOKEN")
        twitter_access_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

        if all([twitter_api_key, twitter_api_secret, twitter_access_token, twitter_access_secret]):
            try:
                self.twitter_client = tweepy.Client(
                    consumer_key=twitter_api_key,
                    consumer_secret=twitter_api_secret,
                    access_token=twitter_access_token,
                    access_token_secret=twitter_access_secret
                )
            except Exception as e:
                print(f"⚠️ TokenPoster Twitter init failed: {e}")

        telegram_token = os.getenv("MEMESEAL_BOT_TOKEN")
        self.telegram_channel = os.getenv("TELEGRAM_CHANNEL_ID", "@MemeSealTON")

        if telegram_token:
            try:
                self.telegram_bot = Bot(token=telegram_token)
            except Exception as e:
                print(f"⚠️ TokenPoster Telegram init failed: {e}")

        self._initialized = True

    async def post_rug_detected(
        self,
        symbol: str,
        address: str,
        detection_method: str,
        initial_holders: int = 0,
        current_holders: int = 0,
        dev_exit_pct: float = 0
    ):
        """
        🚨 RUG DETECTED - Always post, high priority
        """
        if not self._initialized:
            self.initialize()

        short_addr = address[:8] + "..." + address[-4:] if len(address) > 16 else address
        score_url = f"https://notaryton.com/score/{address}"

        # Build reason based on detection method
        if detection_method == "dev_exit":
            reason = f"Dev sold {dev_exit_pct:.0f}% of holdings"
        elif detection_method == "holder_exodus":
            drop_pct = ((initial_holders - current_holders) / initial_holders * 100) if initial_holders else 0
            reason = f"Holders crashed {drop_pct:.0f}% ({initial_holders} → {current_holders})"
        else:
            reason = detection_method

        telegram_msg = (
            f"🚨 <b>RUG DETECTED</b> 🚨\n\n"
            f"<b>${symbol}</b>\n"
            f"📍 {short_addr}\n"
            f"⚠️ {reason}\n\n"
            f"<a href='{score_url}'>View Full Analysis →</a>\n\n"
            f"#RugPull #TON #MemeScan"
        )

        twitter_msg = (
            f"🚨 RUG DETECTED: ${symbol}\n\n"
            f"⚠️ {reason}\n\n"
            f"Check score: {score_url}\n\n"
            f"#TON #RugPull #CryptoScam #MemeScan"
        )

        # Post immediately (rugs are high priority)
        await self._post_twitter(twitter_msg)
        await self._post_telegram(telegram_msg, score_url)

    async def post_danger_score(
        self,
        symbol: str,
        address: str,
        safety_score: int,
        holder_count: int,
        top_holder_pct: float
    ):
        """
        ⚠️ LOW SAFETY SCORE WARNING - Post for scores < 40
        """
        if not self._initialized:
            self.initialize()

        if safety_score >= 40:
            return  # Only post danger warnings

        short_addr = address[:8] + "..." + address[-4:] if len(address) > 16 else address
        score_url = f"https://notaryton.com/score/{address}"

        telegram_msg = (
            f"⚠️ <b>HIGH RISK TOKEN</b>\n\n"
            f"<b>${symbol}</b> - Score: {safety_score}/100\n"
            f"📍 {short_addr}\n"
            f"👥 {holder_count} holders\n"
            f"🐋 Top holder: {top_holder_pct:.1f}%\n\n"
            f"<a href='{score_url}'>Full Analysis →</a>\n\n"
            f"DYOR 🔍 #TON #MemeScan"
        )

        twitter_msg = (
            f"⚠️ HIGH RISK: ${symbol}\n\n"
            f"Score: {safety_score}/100 🔴\n"
            f"Top holder owns {top_holder_pct:.1f}%\n\n"
            f"{score_url}\n\n"
            f"#TON #CryptoRisk #DYOR"
        )

        await self._post_twitter(twitter_msg)
        await self._post_telegram(telegram_msg, score_url)

    async def post_whale_alert(
        self,
        symbol: str,
        address: str,
        whale_wallet: str,
        event_type: str,  # 'entry' or 'exit'
        pct: float
    ):
        """
        🐋 WHALE MOVEMENT - Post for significant moves (>10%)
        """
        if not self._initialized:
            self.initialize()

        if pct < 10:
            return  # Only post big moves

        short_addr = address[:8] + "..." + address[-4:] if len(address) > 16 else address
        short_whale = whale_wallet[:8] + "..." if len(whale_wallet) > 12 else whale_wallet
        score_url = f"https://notaryton.com/score/{address}"

        if event_type == "entry":
            emoji = "🐋"
            action = f"bought {pct:.1f}%"
        else:
            emoji = "🏃"
            action = f"dumped {pct:.1f}%"

        telegram_msg = (
            f"{emoji} <b>WHALE {event_type.upper()}</b>\n\n"
            f"<b>${symbol}</b>\n"
            f"Wallet {short_whale} {action}\n\n"
            f"<a href='{score_url}'>Check Score →</a>"
        )

        twitter_msg = (
            f"{emoji} WHALE {event_type.upper()}: ${symbol}\n\n"
            f"Wallet {action}\n\n"
            f"{score_url}\n\n"
            f"#TON #WhaleAlert"
        )

        await self._post_twitter(twitter_msg)
        await self._post_telegram(telegram_msg, score_url)

    async def _post_twitter(self, message: str):
        """Post to Twitter with rate limiting"""
        if not self.twitter_client:
            return

        if not rate_limiter.can_post_twitter():
            print("⏳ Token Twitter rate limited, skipping")
            return

        try:
            response = self.twitter_client.create_tweet(text=message)
            rate_limiter.record_twitter_post()
            print(f"✅ Token alert posted to X: {response.data['id']}")
        except tweepy.TooManyRequests:
            print("⚠️ Twitter rate limit (API)")
        except tweepy.Forbidden as e:
            print(f"⚠️ Twitter forbidden: {e}")
        except Exception as e:
            print(f"❌ Twitter post failed: {e}")

    async def _post_telegram(self, message: str, url: str):
        """Post to Telegram channel"""
        if not self.telegram_bot or not self.telegram_channel:
            return

        if not rate_limiter.can_post_telegram():
            print("⏳ Token Telegram rate limited, skipping")
            return

        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 View Analysis", url=url)],
                [InlineKeyboardButton(text="🐸 MemeScan Bot", url="https://t.me/MemeSealTON_bot")]
            ])

            await self.telegram_bot.send_message(
                chat_id=self.telegram_channel,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            rate_limiter.record_telegram_post()
            print(f"✅ Token alert posted to Telegram")
        except Exception as e:
            print(f"❌ Telegram post failed: {e}")


# Global token poster singleton
token_poster = TokenPoster()


# Convenience functions for crawler integration
async def announce_rug(symbol: str, address: str, detection_method: str, **kwargs):
    """Call from crawler when rug is detected"""
    await token_poster.post_rug_detected(symbol, address, detection_method, **kwargs)


async def announce_danger_score(symbol: str, address: str, safety_score: int, holder_count: int, top_holder_pct: float):
    """Call from crawler for dangerous tokens"""
    await token_poster.post_danger_score(symbol, address, safety_score, holder_count, top_holder_pct)


async def announce_whale(symbol: str, address: str, whale_wallet: str, event_type: str, pct: float):
    """Call from crawler for whale movements"""
    await token_poster.post_whale_alert(symbol, address, whale_wallet, event_type, pct)
