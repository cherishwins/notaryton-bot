"""
MemeScan Telegram Bot
Meme coin terminal for degens.
"""
import os
import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

from .api import MemeScanClient
from .formatter import (
    format_trending,
    format_new_launches,
    format_token_analysis,
    format_top_pools,
    format_terminal_header,
)

load_dotenv()

# Router for all memescan commands
router = Router()

# Global client instance (initialized on startup)
_client: MemeScanClient = None


def get_client() -> MemeScanClient:
    global _client
    if _client is None:
        _client = MemeScanClient(tonapi_key=os.getenv("TONAPI_KEY", ""))
    return _client


# ============================================================
# COMMANDS
# ============================================================

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Welcome message."""
    text = f"""{format_terminal_header()}

**Welcome to MemeScan** - TON Meme Terminal

Your Bloomberg for meme coins.

**Commands:**
/trending - Hot meme coins right now
/new - Just launched tokens
/check <address> - Safety analysis
/pools - Top liquidity pools

_Free during beta. Premium features coming soon._
"""
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("trending", "hot", "t"))
async def cmd_trending(message: Message):
    """Show trending meme coins."""
    await message.answer("🔍 Scanning markets...")

    client = get_client()
    tokens = await client.get_trending(limit=10)

    response = format_trending(tokens)
    await message.answer(response, parse_mode="Markdown")


@router.message(Command("new", "launches", "n"))
async def cmd_new_launches(message: Message):
    """Show newly launched tokens."""
    await message.answer("🔍 Finding new launches...")

    client = get_client()
    tokens = await client.get_new_launches(limit=10)

    response = format_new_launches(tokens)
    await message.answer(response, parse_mode="Markdown")


@router.message(Command("check", "scan", "c"))
async def cmd_check_token(message: Message):
    """Analyze token safety."""
    # Extract address from command
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Usage: `/check <token_address>`\n\n"
            "Example: `/check EQB...`",
            parse_mode="Markdown"
        )
        return

    address = parts[1].strip()

    # Basic validation
    if not (address.startswith("EQ") or address.startswith("UQ") or address.startswith("0:")):
        await message.answer(
            "Invalid TON address format.\n"
            "Should start with `EQ`, `UQ`, or `0:`",
            parse_mode="Markdown"
        )
        return

    await message.answer(f"🔍 Analyzing `{address[:12]}...`", parse_mode="Markdown")

    client = get_client()
    token = await client.analyze_token_safety(address)

    response = format_token_analysis(token)
    await message.answer(response, parse_mode="Markdown")


@router.message(Command("pools", "liquidity", "p"))
async def cmd_pools(message: Message):
    """Show top liquidity pools."""
    await message.answer("🔍 Loading pools...")

    client = get_client()
    pools = await client.stonfi.get_trending_pools(limit=10)

    response = format_top_pools(pools)
    await message.answer(response, parse_mode="Markdown")


@router.message(Command("help", "h"))
async def cmd_help(message: Message):
    """Help message."""
    text = """**MemeScan Commands**

**Discovery:**
`/trending` - Hot meme coins right now
`/new` - Newly launched tokens
`/pools` - Top liquidity pools

**Analysis:**
`/check <address>` - Token safety scan
  • Holder distribution
  • Dev wallet %
  • Rug risk score

**Coming Soon:**
• Whale alerts
• Price alerts
• Portfolio tracking
• Premium features

_Questions? DM @memescan\\_support_
"""
    await message.answer(text, parse_mode="Markdown")


# ============================================================
# STANDALONE BOT RUNNER
# ============================================================

async def run_standalone():
    """Run as standalone bot (for testing or separate deployment)."""
    token = os.getenv("MEMESCAN_BOT_TOKEN")
    if not token:
        print("ERROR: MEMESCAN_BOT_TOKEN not set")
        return

    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)

    print("MemeScan bot starting...")

    try:
        await dp.start_polling(bot)
    finally:
        client = get_client()
        await client.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_standalone())
