import hashlib
import hmac
import json
import os
import re
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Update, LabeledPrice, PreCheckoutQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent, WebAppInfo
from dotenv import load_dotenv
from pytoniq import LiteBalancer, WalletV5R1, Address
import uvicorn

# Database layer (PostgreSQL with Neon)
from database import db

# Social media auto-poster (X + Telegram channel)
from social import social_poster, announce_seal

# MemeScan - Meme coin terminal
from memescan.bot import router as memescan_router, get_client as get_memescan_client
from memescan.twitter import memescan_twitter

# Token crawler - THE DATA MOAT
from crawler import crawler, start_crawler, stop_crawler

# Load .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

# Load config
BOT_TOKEN = os.getenv("BOT_TOKEN")
MEMESEAL_BOT_TOKEN = os.getenv("MEMESEAL_BOT_TOKEN")
MEMESCAN_BOT_TOKEN = os.getenv("MEMESCAN_BOT_TOKEN")
TON_CENTER_API_KEY = os.getenv("TON_CENTER_API_KEY")
TON_WALLET_SECRET = os.getenv("TON_WALLET_SECRET")
SERVICE_TON_WALLET = os.getenv("SERVICE_TON_WALLET")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://notaryton.com")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
MEMESEAL_WEBHOOK_PATH = f"/webhook/{MEMESEAL_BOT_TOKEN}" if MEMESEAL_BOT_TOKEN else None
MEMESCAN_WEBHOOK_PATH = f"/webhook/{MEMESCAN_BOT_TOKEN}" if MEMESCAN_BOT_TOKEN else None
GROUP_IDS = os.getenv("GROUP_IDS", "").split(",")  # Comma-separated chat IDs

# TonAPI for real-time webhooks (replaces 30s polling!)
TONAPI_KEY = os.getenv("TONAPI_KEY", "")
TONAPI_WEBHOOK_SECRET = os.getenv("TONAPI_WEBHOOK_SECRET", "")

# Known deploy bots (add more as needed)
DEPLOY_BOTS = ["@tondeployer", "@memelaunchbot", "@toncoinbot"]

# Telegram Stars pricing (XTR currency)
# 1 Star ≈ $0.02-0.05 depending on purchase method
STARS_SINGLE_NOTARIZATION = 3   # 3 Stars for single notarization (~$0.10)
STARS_MONTHLY_SUBSCRIPTION = 50  # 50 Stars for monthly unlimited (~$2.50)

# TON pricing
TON_SINGLE_SEAL = 0.15   # 0.15 TON per seal (~$0.75) - still 20x cheaper than DeDust
TON_MONTHLY_SUB = 1.0    # 1.0 TON for monthly unlimited (~$5.00)

# Initialize bot and dispatcher (NotaryTON - professional)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Initialize MemeSeal bot (degen branding) - shares same database/wallet
memeseal_bot = Bot(token=MEMESEAL_BOT_TOKEN) if MEMESEAL_BOT_TOKEN else None
memeseal_dp = Dispatcher() if MEMESEAL_BOT_TOKEN else None

# Initialize MemeScan bot (meme coin terminal)
memescan_bot = Bot(token=MEMESCAN_BOT_TOKEN) if MEMESCAN_BOT_TOKEN else None
memescan_dp = Dispatcher() if MEMESCAN_BOT_TOKEN else None
if memescan_dp:
    memescan_dp.include_router(memescan_router)

app = FastAPI()

# CORS middleware for casino frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global bot usernames (fetched on startup)
BOT_USERNAME = "NotaryTON_bot"
MEMESEAL_USERNAME = "MemeSealTON_bot"

# Mount static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 templates
os.makedirs("templates/memescan", exist_ok=True)
templates = Jinja2Templates(directory="templates")

# ========================
# MULTI-LANGUAGE SUPPORT (i18n)
# ========================

TRANSLATIONS = {
    "en": {
        "welcome": "🔐 **NotaryTON** - Blockchain Notarization\n\nSeal contracts, files, and screenshots on TON forever.\n\n**Commands:**\n/notarize - Seal a contract\n/status - Check your subscription\n/subscribe - Get unlimited seals\n/referral - Earn 5% commission\n/withdraw - Withdraw referral earnings\n/lang - Change language",
        "no_sub": "⚠️ **Payment Required**\n\n3 Stars or 0.15 TON to seal this.",
        "sealed": "✅ **SEALED ON TON!**\n\nHash: `{hash}`\n\n🔗 Verify: {url}\n\nProof secured forever! 🔒",
        "withdraw_success": "✅ **Withdrawal Sent!**\n\n{amount} TON sent to your wallet.\nTX will appear in ~30 seconds.",
        "withdraw_min": "⚠️ Minimum withdrawal: 0.05 TON\n\nYour balance: {balance} TON",
        "withdraw_no_wallet": "⚠️ Please send your TON wallet address first.\n\nExample: `EQB...` or `UQA...`",
        "lang_changed": "✅ Language changed to English",
        "referral_stats": "🎁 **Referral Program**\n\n**Your Link:**\n`{url}`\n\n**Commission:** 5%\n**Referrals:** {count}\n**Earnings:** {earnings} TON\n**Withdrawn:** {withdrawn} TON\n**Available:** {available} TON\n\n💡 Use /withdraw to cash out!",
        "status_active": "✅ **Subscription Active**\n\nExpires: {expiry}\n\nUnlimited seals enabled!",
        "status_inactive": "❌ **No Active Subscription**\n\nCredits: {credits} TON\n\nUse /subscribe for unlimited!",
        "photo_prompt": "📸 **Nice screenshot!**\n\n3 Stars to seal it on TON forever.",
        "file_prompt": "📄 **Got your file!**\n\n3 Stars to seal it on TON forever.",
        # Agent 10: New strings for enhanced UX
        "sealing_progress": "⏳ **SEALING TO BLOCKCHAIN...**\n\nYour file is being timestamped on TON.\nThis takes 5-15 seconds.",
        "network_busy": "⚠️ **TON Network Busy**\n\nWe're retrying automatically. Please wait.",
        "retry_prompt": "🔄 **Try Again**\n\nTap the button below to retry.",
        "lottery_tickets": "🎫 Lottery tickets: {count}",
        "pot_grew": "💰 Pot grew +{amount} TON",
        "good_luck": "🍀 Good luck on Sunday!",
    },
    "ru": {
        "welcome": "🔐 **NotaryTON** - Блокчейн Нотаризация\n\nПечать контрактов, файлов и скриншотов на TON навсегда.\n\n**Команды:**\n/notarize - Запечатать контракт\n/status - Проверить подписку\n/subscribe - Безлимит\n/referral - Заработай 5%\n/withdraw - Вывести заработок\n/lang - Сменить язык",
        "no_sub": "⚠️ **Требуется оплата**\n\n3 Звезды или 0.15 TON для печати.",
        "sealed": "✅ **ЗАПЕЧАТАНО НА TON!**\n\nХеш: `{hash}`\n\n🔗 Проверить: {url}\n\nДоказательство сохранено навсегда! 🔒",
        "withdraw_success": "✅ **Вывод отправлен!**\n\n{amount} TON отправлено на ваш кошелек.\nTX появится через ~30 секунд.",
        "withdraw_min": "⚠️ Минимальный вывод: 0.05 TON\n\nВаш баланс: {balance} TON",
        "withdraw_no_wallet": "⚠️ Сначала отправьте адрес вашего TON кошелька.\n\nПример: `EQB...` или `UQA...`",
        "lang_changed": "✅ Язык изменен на Русский",
        "referral_stats": "🎁 **Реферальная Программа**\n\n**Ваша ссылка:**\n`{url}`\n\n**Комиссия:** 5%\n**Рефералы:** {count}\n**Заработано:** {earnings} TON\n**Выведено:** {withdrawn} TON\n**Доступно:** {available} TON\n\n💡 Используйте /withdraw для вывода!",
        "status_active": "✅ **Подписка Активна**\n\nИстекает: {expiry}\n\nБезлимитные печати включены!",
        "status_inactive": "❌ **Нет Активной Подписки**\n\nКредиты: {credits} TON\n\nИспользуйте /subscribe для безлимита!",
        "photo_prompt": "📸 **Отличный скриншот!**\n\n3 Звезды чтобы запечатать на TON навсегда.",
        "file_prompt": "📄 **Файл получен!**\n\n3 Звезды чтобы запечатать на TON навсегда.",
        # Agent 10: New strings for enhanced UX
        "sealing_progress": "⏳ **ЗАПЕЧАТЫВАНИЕ В БЛОКЧЕЙН...**\n\nВаш файл получает временную метку на TON.\nЭто занимает 5-15 секунд.",
        "network_busy": "⚠️ **Сеть TON занята**\n\nМы автоматически повторяем. Пожалуйста, подождите.",
        "retry_prompt": "🔄 **Попробовать снова**\n\nНажмите кнопку ниже для повтора.",
        "lottery_tickets": "🎫 Лотерейные билеты: {count}",
        "pot_grew": "💰 Банк вырос на +{amount} TON",
        "good_luck": "🍀 Удачи в воскресенье!",
    },
    "zh": {
        "welcome": "🔐 **NotaryTON** - 区块链公证\n\n在TON上永久封存合约、文件和截图。\n\n**命令:**\n/notarize - 封存合约\n/status - 查看订阅\n/subscribe - 无限封存\n/referral - 赚取5%佣金\n/withdraw - 提取收益\n/lang - 更改语言",
        "no_sub": "⚠️ **需要付款**\n\n3星或0.15 TON来封存。",
        "sealed": "✅ **已封存到TON!**\n\n哈希: `{hash}`\n\n🔗 验证: {url}\n\n证明已永久保存! 🔒",
        "withdraw_success": "✅ **提款已发送!**\n\n{amount} TON已发送到您的钱包。\n交易将在~30秒后显示。",
        "withdraw_min": "⚠️ 最低提款: 0.05 TON\n\n您的余额: {balance} TON",
        "withdraw_no_wallet": "⚠️ 请先发送您的TON钱包地址。\n\n例如: `EQB...` 或 `UQA...`",
        "lang_changed": "✅ 语言已更改为中文",
        "referral_stats": "🎁 **推荐计划**\n\n**您的链接:**\n`{url}`\n\n**佣金:** 5%\n**推荐人数:** {count}\n**收益:** {earnings} TON\n**已提取:** {withdrawn} TON\n**可用:** {available} TON\n\n💡 使用 /withdraw 提现!",
        "status_active": "✅ **订阅有效**\n\n到期: {expiry}\n\n无限封存已启用!",
        "status_inactive": "❌ **无有效订阅**\n\n余额: {credits} TON\n\n使用 /subscribe 获取无限!",
        "photo_prompt": "📸 **不错的截图!**\n\n1星即可永久封存到TON。",
        "file_prompt": "📄 **文件已收到!**\n\n1星即可永久封存到TON。",
        # Agent 10: New strings for enhanced UX
        "sealing_progress": "⏳ **正在封存到区块链...**\n\n您的文件正在TON上获取时间戳。\n这需要5-15秒。",
        "network_busy": "⚠️ **TON网络繁忙**\n\n我们正在自动重试。请稍候。",
        "retry_prompt": "🔄 **重试**\n\n点击下方按钮重试。",
        "lottery_tickets": "🎫 彩票: {count}张",
        "pot_grew": "💰 奖池增加 +{amount} TON",
        "good_luck": "🍀 祝周日好运!",
    }
}

# User language cache (user_id -> lang_code)
user_languages = {}

# 🐸 PENDING TON PAYMENTS - tracks files waiting for TON payment
# When user sends file → clicks "Pay with TON" → sends file again, auto-seal
pending_files = {}  # key: user_id, value: {"file_id": "...", "file_type": "document"|"photo", "timestamp": ...}
pending_ton_payments = {}  # key: user_id, value: {"memo": "123", "file_id": "...", "file_type": "...", "timestamp": ...}
import time
import random
import string

# Agent 5: Unique memo generator for TON payments
def generate_payment_memo(user_id: int) -> str:
    """Generate a unique, short memo for TON payments like SEAL-A7B3"""
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(chars, k=4))
    return f"SEAL-{suffix}"

# Reverse lookup: memo -> user_id
payment_memo_lookup = {}  # key: memo, value: {"user_id": int, "timestamp": float}

def get_text(user_id: int, key: str, **kwargs) -> str:
    """Get translated text for user"""
    lang = user_languages.get(user_id, "en")
    text = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, TRANSLATIONS["en"].get(key, key))
    if kwargs:
        text = text.format(**kwargs)
    return text

async def detect_user_language(user: types.User) -> str:
    """Detect language from Telegram user settings"""
    lang_code = getattr(user, 'language_code', 'en') or 'en'
    # Map Telegram language codes to our supported languages
    if lang_code.startswith('ru'):
        return 'ru'
    elif lang_code.startswith('zh'):
        return 'zh'
    return 'en'

async def get_user_language(user_id: int) -> str:
    """Get user's language preference from DB or cache"""
    if user_id in user_languages:
        return user_languages[user_id]

    lang = await db.users.get_language(user_id)
    user_languages[user_id] = lang
    return lang

async def set_user_language(user_id: int, lang: str):
    """Set user's language preference"""
    user_languages[user_id] = lang
    await db.users.set_language(user_id, lang)


# 🐸 CLEANUP TASK - remove expired pending payments every 5 minutes
async def cleanup_pending_payments():
    """Clean up old pending files and TON payments every 5 minutes"""
    while True:
        try:
            now = time.time()
            # Clean pending_files (expire after 10 min)
            expired_files = [uid for uid, data in pending_files.items() if now - data["timestamp"] > 600]
            for uid in expired_files:
                del pending_files[uid]
            # Clean pending_ton_payments (expire after 10 min)
            expired_payments = [uid for uid, data in pending_ton_payments.items() if now - data["timestamp"] > 600]
            for uid in expired_payments:
                del pending_ton_payments[uid]
            # Clean payment_memo_lookup (expire after 10 min)
            expired_memos = [memo for memo, data in payment_memo_lookup.items() if now - data["timestamp"] > 600]
            for memo in expired_memos:
                del payment_memo_lookup[memo]
            if expired_files or expired_payments or expired_memos:
                print(f"🧹 Cleaned {len(expired_files)} files, {len(expired_payments)} payments, {len(expired_memos)} memos")
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")
        await asyncio.sleep(300)  # Every 5 minutes


# 🎰 LOTTERY DRAW TASK - picks winner every Sunday at 00:00 UTC (midnight)
async def run_sunday_lottery_draw():
    """Background task: Run lottery draw every Sunday at 00:00 UTC (midnight)"""
    from datetime import timezone

    while True:
        try:
            # Calculate time until next Sunday 00:00 UTC (midnight)
            now = datetime.now(timezone.utc)
            days_until_sunday = (6 - now.weekday()) % 7
            if days_until_sunday == 0 and now.hour > 0:
                # It's already past midnight Sunday, wait until next week
                days_until_sunday = 7

            next_draw = now + timedelta(days=days_until_sunday)
            next_draw = next_draw.replace(hour=0, minute=0, second=0, microsecond=0)

            sleep_seconds = (next_draw - now).total_seconds()
            hours_until = sleep_seconds / 3600
            print(f"🎰 Lottery draw scheduled for {next_draw.strftime('%Y-%m-%d %H:%M UTC')} ({hours_until:.1f}h from now)")

            # Sleep until draw time
            await asyncio.sleep(sleep_seconds)

            # === DRAW TIME ===
            print("🎰 LOTTERY DRAW STARTING...")

            # Get pot size before draw
            pot_stars = await db.lottery.get_pot_size_stars()
            pot_ton = await db.lottery.get_pot_size_ton()
            total_entries = await db.lottery.get_total_entries()

            if total_entries == 0:
                print("⚠️ No lottery entries - skipping draw")
                continue

            # Generate draw ID from timestamp
            draw_id = int(datetime.now(timezone.utc).timestamp())

            # Pick the winner!
            winner_id = await db.lottery.pick_winner(draw_id)

            if winner_id:
                print(f"🏆 LOTTERY WINNER: User {winner_id} wins {pot_stars} ⭐ ({pot_ton:.4f} TON)!")

                # Notify winner via DM
                winner_msg = (
                    f"🏆🎰 **YOU WON THE LOTTERY!** 🎰🏆\n\n"
                    f"Prize: **{pot_stars} ⭐** ({pot_ton:.4f} TON)\n"
                    f"Entries: {total_entries} tickets in this draw\n\n"
                    f"Congratulations, degen! 🐸\n\n"
                    f"Prize will be credited to your account."
                )

                # Try both bots to reach the winner
                for send_bot in [memeseal_bot, bot]:
                    if send_bot:
                        try:
                            await send_bot.send_message(winner_id, winner_msg, parse_mode="Markdown")
                            break
                        except Exception as e:
                            print(f"⚠️ Could not DM winner via {send_bot}: {e}")

                # Announce on socials
                try:
                    await social_poster.post_lottery_winner(winner_id, pot_ton, pot_stars)
                except Exception as e:
                    print(f"⚠️ Could not post winner to socials: {e}")

                # Try auto-payout if winner has withdrawal wallet set
                try:
                    winner = await db.users.get(winner_id)
                    if winner and winner.withdrawal_wallet and pot_ton >= MIN_WITHDRAWAL_TON:
                        # Auto-payout to winner's wallet
                        try:
                            await send_payout_transaction(
                                winner.withdrawal_wallet,
                                pot_ton,
                                f"MemeSeal Lottery Win! {pot_stars} Stars"
                            )
                            print(f"✅ Auto-payout {pot_ton:.4f} TON to {winner.withdrawal_wallet[:20]}...")
                            # Notify winner about auto-payout
                            payout_msg = f"💸 **{pot_ton:.4f} TON** sent to your wallet!\nCheck: tonscan.org/address/{winner.withdrawal_wallet}"
                            for send_bot in [memeseal_bot, bot]:
                                if send_bot:
                                    try:
                                        await send_bot.send_message(winner_id, payout_msg, parse_mode="Markdown")
                                        break
                                    except Exception:
                                        pass
                        except Exception as payout_err:
                            print(f"⚠️ Auto-payout failed, crediting account instead: {payout_err}")
                            await db.users.add_referral_earnings(winner_id, pot_ton)
                    else:
                        # No wallet or pot too small - credit to account
                        await db.users.add_referral_earnings(winner_id, pot_ton)
                        print(f"✅ Credited {pot_ton:.4f} TON to winner's account (use /withdraw to claim)")
                except Exception as e:
                    print(f"⚠️ Could not process winner payout: {e}")
            else:
                print(f"❌ Lottery draw failed - no winner selected")

        except Exception as e:
            print(f"❌ Lottery draw error: {e}")
            # Don't crash - sleep 1 hour and retry
            await asyncio.sleep(3600)


# Minimum withdrawal amount
MIN_WITHDRAWAL_TON = 0.05

# ========================
# DATABASE FUNCTIONS (using PostgreSQL via database.py)
# ========================

async def get_user_subscription(user_id: int):
    """Check if user has active subscription"""
    return await db.users.has_active_subscription(user_id)

async def add_subscription(user_id: int, months: int = 1):
    """Add or extend subscription"""
    await db.users.add_subscription(user_id, months)

async def log_notarization(user_id: int, tx_hash: str, contract_hash: str, paid: bool = False):
    """Log a notarization event"""
    await db.notarizations.create(
        user_id=user_id,
        tx_hash=tx_hash,
        contract_hash=contract_hash,
        paid=paid
    )

# ========================
# TON FUNCTIONS
# ========================

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


# ========================
# ERROR HANDLING HELPERS (Agent 3: Humanized Errors)
# ========================

class ErrorType:
    USER_INPUT = "user_input"      # Invalid input from user
    NETWORK = "network"            # TON network issues
    PAYMENT = "payment"            # Payment problems
    FILE = "file"                  # File handling errors
    UNKNOWN = "unknown"            # Catch-all

def classify_error(error: Exception) -> str:
    """Classify an error into a user-friendly category"""
    error_str = str(error).lower()

    if "invalid" in error_str or "address" in error_str:
        return ErrorType.USER_INPUT
    elif "timeout" in error_str or "liteserver" in error_str or "network" in error_str or "crashed" in error_str:
        return ErrorType.NETWORK
    elif "not initialized" in error_str or "-256" in error_str:
        return ErrorType.NETWORK
    elif "payment" in error_str or "balance" in error_str:
        return ErrorType.PAYMENT
    elif "file" in error_str or "download" in error_str:
        return ErrorType.FILE
    else:
        return ErrorType.UNKNOWN

def get_user_friendly_error(error: Exception, context: str = "") -> str:
    """Convert technical errors into user-friendly messages with guidance"""
    error_type = classify_error(error)

    if error_type == ErrorType.USER_INPUT:
        return (
            "⚠️ **Invalid Input**\n\n"
            f"{context}\n\n"
            "**Examples of valid input:**\n"
            "• Contract: `EQB...` or `UQ...`\n"
            "• Hash: 64 character hex string\n"
            "• File: Any document or screenshot"
        )

    elif error_type == ErrorType.NETWORK:
        return (
            "⚠️ **TON Network Busy**\n\n"
            "The blockchain is experiencing high load.\n\n"
            "**What to do:**\n"
            "• Wait 30 seconds and try again\n"
            "• Or use ⭐ Stars for faster processing\n\n"
            "_We're automatically retrying..._"
        )

    elif error_type == ErrorType.PAYMENT:
        return (
            "⚠️ **Payment Issue**\n\n"
            "We couldn't process your payment.\n\n"
            "**Try:**\n"
            "• Check your wallet balance\n"
            "• Ensure the memo is correct\n"
            "• Use /subscribe for subscription status"
        )

    elif error_type == ErrorType.FILE:
        return (
            "⚠️ **File Error**\n\n"
            "We couldn't process your file.\n\n"
            "**Try:**\n"
            "• Re-send the file\n"
            "• Check file isn't corrupted\n"
            "• Max size: 20MB"
        )

    else:
        return (
            "⚠️ **Something Went Wrong**\n\n"
            "We hit an unexpected error.\n\n"
            "**What to do:**\n"
            "• Try again in a few seconds\n"
            "• If it persists, contact @NotaryTON_support\n\n"
            f"_Error ref: {str(error)[:50]}_"
        )


async def get_contract_code_from_tx(tx_id: str) -> bytes:
    """Fetch contract bytecode from transaction"""
    client = None
    try:
        client = LiteBalancer.from_mainnet_config(trust_level=1)
        await client.start_up()

        # Try to parse the tx_id as a contract address
        try:
            address = Address(tx_id)
            # Get account state
            account_state = await client.run_get_method(
                address=address.to_str(),
                method="get_public_key",
                stack=[]
            )

            # Get the actual contract code
            account = await client.get_account_state(address.to_str())
            if account and hasattr(account, 'code') and account.code:
                code = account.code
                return code if isinstance(code, bytes) else str(code).encode()
            else:
                print(f"No code found for address: {tx_id}")
                return b""

        except Exception as addr_error:
            # If not an address, check if it's a valid hex hash (64 chars)
            if re.match(r'^[A-Fa-f0-9]{64}$', tx_id):
                 # It's a hash, but we can't easily fetch the code without an indexer or knowing the account.
                 # For now, we'll just notarize the hash itself as requested.
                 return tx_id.encode()
            else:
                 print(f"Invalid contract identifier: {tx_id}")
                 return b""

    except Exception as e:
        print(f"Error fetching contract code: {e}")
        return b""
    finally:
        if client:
            await client.close_all()

async def send_ton_transaction(comment: str, amount_ton: float = 0.005, retries: int = 3):
    """Send TON transaction with comment (notarization proof)"""
    last_error = None

    for attempt in range(retries):
        client = None
        try:
            client = LiteBalancer.from_mainnet_config(trust_level=1)
            await client.start_up()

            mnemonics = TON_WALLET_SECRET.split()
            wallet = await WalletV5R1.from_mnemonic(provider=client, mnemonics=mnemonics, network_global_id=-239)

            # Send transaction to self with comment (proof stored on-chain)
            result = await wallet.transfer(
                destination=SERVICE_TON_WALLET,
                amount=int(amount_ton * 1e9),  # Convert to nanotons
                body=comment
            )

            print(f"✅ Notarization transaction sent with comment: {comment}")
            return result
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            print(f"⚠️ Attempt {attempt + 1}/{retries} failed: {e}")

            # If contract not initialized, need to deploy wallet first
            if "not initialized" in error_str or "-256" in error_str:
                print("💡 Wallet contract not deployed. Attempting deploy...")
                try:
                    # Try to deploy wallet by sending minimal amount
                    await wallet.transfer(
                        destination=SERVICE_TON_WALLET,
                        amount=1,  # 1 nanoton to deploy
                        body="MemeSeal:WalletDeploy"
                    )
                    await asyncio.sleep(5)  # Wait for deploy
                    continue  # Retry main transaction
                except Exception as deploy_err:
                    print(f"❌ Deploy attempt failed: {deploy_err}")

            # Liteserver crash - wait and retry
            if "liteserver" in error_str or "crashed" in error_str:
                await asyncio.sleep(2)
                continue

        finally:
            if client:
                try:
                    await client.close_all()
                except:
                    pass

    print(f"❌ All {retries} attempts failed. Last error: {last_error}")
    raise last_error

async def send_payout_transaction(destination: str, amount_ton: float, memo: str = "NotaryTON Payout"):
    """Send TON payout to user wallet"""
    client = None
    try:
        client = LiteBalancer.from_mainnet_config(trust_level=1)
        await client.start_up()

        mnemonics = TON_WALLET_SECRET.split()
        wallet = await WalletV5R1.from_mnemonic(provider=client, mnemonics=mnemonics, network_global_id=-239)

        # Send to user's wallet
        result = await wallet.transfer(
            destination=destination,
            amount=int(amount_ton * 1e9),  # Convert to nanotons
            body=memo
        )

        print(f"✅ Payout sent: {amount_ton} TON to {destination}")
        return result
    except Exception as e:
        print(f"❌ Error sending payout: {e}")
        raise
    finally:
        if client:
            await client.close_all()


async def seal_file_from_webhook(user_id: int, file_id: str, file_type: str, progress_msg):
    """
    Seal file triggered by TonAPI webhook payment detection.
    Module-level function that can be called from webhook handler.
    """
    file_path = None
    try:
        # Determine which bot to use (prefer memeseal_bot)
        active_bot = memeseal_bot if memeseal_bot else bot

        # Download file
        if file_type == "photo":
            file = await active_bot.get_file(file_id)
            file_path = f"downloads/{file_id}.jpg"
        else:
            file = await active_bot.get_file(file_id)
            file_path = f"downloads/{file_id}"

        os.makedirs("downloads", exist_ok=True)
        await active_bot.download_file(file.file_path, file_path)
        file_hash = hash_file(file_path)

        # Seal to blockchain with retries
        comment = f"MemeSeal:{file_hash[:16]}"
        sealed = False

        for attempt in range(5):
            try:
                await send_ton_transaction(comment)
                sealed = True
                break
            except Exception as e:
                print(f"⚠️ Webhook seal attempt {attempt+1}/5 failed: {e}")
                await asyncio.sleep(5)

        if sealed:
            # Log and announce
            await log_notarization(user_id, "webhook_ton_instant", file_hash, paid=True)

            # Update progress message with success
            if progress_msg:
                try:
                    await progress_msg.edit_text(
                        f"✅ **SEALED TO BLOCKCHAIN!** 🐸\n\n"
                        f"**Hash:** `{file_hash[:16]}...`\n\n"
                        f"[View on TONScan](https://tonscan.org/) | "
                        f"[Verify](https://notaryton.com/verify?hash={file_hash})\n\n"
                        f"On TON forever. Receipts secured.",
                        parse_mode="Markdown"
                    )
                except:
                    pass

            # Announce to socials
            asyncio.create_task(announce_seal_to_socials(file_hash))
            print(f"✅ Webhook seal success for user {user_id}: {file_hash[:16]}")
        else:
            if progress_msg:
                try:
                    await progress_msg.edit_text(
                        f"⚠️ **Network Busy**\n\n"
                        f"Seal failed after 5 attempts.\n"
                        f"Your payment is credited - send the file again to retry!",
                        parse_mode="Markdown"
                    )
                except:
                    pass
            print(f"❌ Webhook seal failed for user {user_id}")

    except Exception as e:
        print(f"❌ Webhook seal error: {e}")
        if progress_msg:
            try:
                await progress_msg.edit_text(
                    f"⚠️ **Error sealing**\n\n{str(e)[:100]}\n\nPlease try again.",
                    parse_mode="Markdown"
                )
            except:
                pass
    finally:
        if file_path:
            try:
                os.remove(file_path)
            except:
                pass


async def resolve_ton_dns(domain: str) -> str:
    """Resolve .ton domain to TON address"""
    client = None
    try:
        # Clean up domain
        domain = domain.lower().strip()
        if not domain.endswith('.ton'):
            return None

        client = LiteBalancer.from_mainnet_config(trust_level=1)
        await client.start_up()

        # TON DNS root contract address
        DNS_ROOT = "EQC3dNlesgVD8YbAazcauIrXBPfiVhMMr5YYk2in0Mtsz0Bz"

        # Resolve domain
        domain_parts = domain[:-4].split('.')  # Remove .ton and split
        domain_parts.reverse()  # TON DNS resolves from right to left

        current_address = DNS_ROOT
        for part in domain_parts:
            # Hash the domain part
            part_hash = hashlib.sha256(part.encode()).digest()

            # Call get_next_resolver on current address
            try:
                result = await client.run_get_method(
                    address=current_address,
                    method="dnsresolve",
                    stack=[{"type": "slice", "value": part_hash}, {"type": "int", "value": 256}]
                )
                if result and len(result) > 1:
                    # Extract wallet address from result
                    current_address = result[1]
            except Exception:
                return None

        # Validate it's a proper address
        try:
            Address(current_address)
            print(f"✅ Resolved {domain} -> {current_address}")
            return current_address
        except Exception:
            return None

    except Exception as e:
        print(f"⚠️ DNS resolution failed for {domain}: {e}")
        return None
    finally:
        if client:
            await client.close_all()

async def poll_wallet_for_payments():
    """Background task to poll wallet for incoming payments with retry logic"""
    last_processed_lt = 0

    # Load last processed LT from DB
    try:
        lt_value = await db.bot_state.get('last_processed_lt')
        if lt_value:
            last_processed_lt = int(lt_value)
            print(f"🔄 Resuming payment polling from LT: {last_processed_lt}")
    except Exception as e:
        print(f"⚠️ Failed to load last_processed_lt: {e}")

    consecutive_errors = 0
    max_backoff = 300  # Max 5 minutes between retries

    while True:
        client = None
        try:
            client = LiteBalancer.from_mainnet_config(trust_level=1)
            await asyncio.wait_for(client.start_up(), timeout=30)  # 30s timeout

            # Get wallet address
            wallet_address = Address(SERVICE_TON_WALLET)

            # Get recent transactions with timeout
            transactions = await asyncio.wait_for(
                client.get_transactions(address=wallet_address.to_str(), count=10),
                timeout=30
            )

            # Sort transactions by LT ascending (oldest first) to process in order
            transactions.sort(key=lambda x: x.lt)

            new_max_lt = last_processed_lt

            for tx in transactions:
                # Skip if we've already processed this transaction
                if tx.lt <= last_processed_lt:
                    continue

                # Check if this is an incoming transaction
                if hasattr(tx, 'in_msg') and tx.in_msg:
                    in_msg = tx.in_msg

                    # Extract amount (in nanotons)
                    amount_nano = getattr(in_msg, 'value', 0) if hasattr(in_msg, 'value') else 0
                    amount_ton = amount_nano / 1e9

                    # Extract memo/comment
                    memo = ""
                    if hasattr(in_msg, 'body') and in_msg.body:
                        try:
                            memo = in_msg.body.decode('utf-8', errors='ignore')
                        except Exception:
                            memo = str(in_msg.body)

                    print(f"📥 Incoming payment: {amount_ton} TON, memo: {memo}")

                    # Try to extract user_id from memo
                    user_id = None
                    try:
                        match = re.search(r'\d+', memo)
                        if match:
                            user_id = int(match.group())
                    except Exception:
                        pass

                    if user_id:
                        # Credit referrer with 5% commission
                        user = await db.users.get(user_id)
                        if user and user.referred_by:
                            referrer_id = user.referred_by
                            commission = amount_ton * 0.05
                            await db.users.add_referral_earnings(referrer_id, commission)
                            print(f"💰 Credited {commission:.4f} TON to referrer {referrer_id}")

                        # Check if it's a subscription payment (0.3 TON)
                        if amount_ton >= 0.28:  # Allow small variance
                            await add_subscription(user_id, months=1)
                            print(f"✅ Activated subscription for user {user_id}")

                            # Notify user via both bots
                            for b in [bot, memeseal_bot]:
                                if b:
                                    try:
                                        await b.send_message(
                                            user_id,
                                            "✅ **Subscription Activated!**\n\n"
                                            "You now have unlimited notarizations for 30 days!\n\n"
                                            "Send me a file or contract address to seal it! 🔒",
                                            parse_mode="Markdown"
                                        )
                                        break  # Only send once
                                    except Exception:
                                        pass

                        # Check if it's a single notarization payment (0.15 TON)
                        elif amount_ton >= 0.014:  # Allow small variance
                            # Add to database as paid credit
                            await db.users.ensure_exists(user_id)
                            await db.users.add_payment(user_id, amount_ton)

                            print(f"✅ Credited {amount_ton} TON to user {user_id}")

                            # Notify user via both bots
                            for b in [bot, memeseal_bot]:
                                if b:
                                    try:
                                        await b.send_message(
                                            user_id,
                                            "✅ **Payment Received!**\n\n"
                                            f"You can now notarize one contract.\n\n"
                                            "Send me a file or contract address! 🔒",
                                            parse_mode="Markdown"
                                        )
                                        break  # Only send once
                                    except Exception:
                                        pass

                # Update max LT seen
                if tx.lt > new_max_lt:
                    new_max_lt = tx.lt

            # Update DB if we processed new transactions
            if new_max_lt > last_processed_lt:
                last_processed_lt = new_max_lt
                await db.bot_state.set('last_processed_lt', str(last_processed_lt))

            # Success - reset error counter
            consecutive_errors = 0

        except asyncio.TimeoutError:
            consecutive_errors += 1
            print(f"⚠️ Wallet polling timeout (attempt {consecutive_errors})")
        except Exception as e:
            consecutive_errors += 1
            error_msg = str(e)
            # Don't spam logs with the same Liteserver error
            if "651" in error_msg:
                print(f"⚠️ Liteserver sync issue (attempt {consecutive_errors}) - will retry")
            elif "lt not in db" in error_msg or "cannot find block" in error_msg:
                # Stale block reference - reset to start fresh
                print(f"⚠️ Stale block reference detected - resetting transaction tracking")
                last_processed_lt = 0
                await db.bot_state.delete('last_processed_lt')
                consecutive_errors = 0  # Reset since we fixed the issue
            else:
                print(f"❌ Error polling wallet (attempt {consecutive_errors}): {error_msg}")
        finally:
            if client:
                try:
                    await client.close_all()
                except Exception:
                    pass

        # Exponential backoff on errors (30s -> 60s -> 120s -> 240s -> 300s max)
        if consecutive_errors > 0:
            backoff = min(30 * (2 ** (consecutive_errors - 1)), max_backoff)
            print(f"🔄 Retrying in {backoff}s...")
            await asyncio.sleep(backoff)
        else:
            await asyncio.sleep(30)  # Normal poll interval

# ========================
# BOT HANDLERS
# ========================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Check for referral code in /start command
    referral_code = None
    if message.text and len(message.text.split()) > 1:
        referral_code = message.text.split()[1]
    
    # Create user if doesn't exist
    if referral_code and referral_code.startswith("REF"):
        # Extract referrer's user_id from referral code
        try:
            referrer_id = int(referral_code.replace("REF", ""))
            await db.users.create(user_id, referred_by=referrer_id)

            # Notify referrer
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎉 New referral! User {user_id} joined via your link.\n"
                    f"You'll earn 5% of their payments!"
                )
            except Exception:
                pass
        except Exception:
            await db.users.ensure_exists(user_id)
    else:
        # Just create user entry
        await db.users.ensure_exists(user_id)
    
    welcome_msg = (
        "🔐 **NotaryTON** → Now **MemeSeal** 🐸\n\n"
        "We rebranded! Same powerful blockchain notarization, fresh degen vibe.\n\n"
        "👉 **Check out @MemeSealTON_bot** for the full experience!\n\n"
        "This bot still works - your subscription & seals carry over.\n\n"
        "**Commands:**\n"
        "• /subscribe - Unlimited seals\n"
        "• /status - Your stats\n"
        "• /notarize - Seal a file\n"
        "• /referral - Earn 5%\n\n"
        "💰 ⭐ 3 Stars per seal | 50 Stars/mo unlimited"
    )
    
    await message.answer(welcome_msg, parse_mode="Markdown")

@dp.message(Command("subscribe"))
async def cmd_subscribe(message: types.Message):
    user_id = message.from_user.id

    # Create inline keyboard with payment options
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⭐ Pay with Stars (20 Stars)", callback_data="pay_stars_sub")],
        [types.InlineKeyboardButton(text="💎 Pay with TON (0.3 TON)", callback_data="pay_ton_sub")]
    ])

    await message.answer(
        f"💎 **Unlimited Monthly Subscription**\n\n"
        f"**Benefits:** Unlimited notarizations for 30 days\n\n"
        f"**Choose Payment Method:**\n"
        f"⭐ **Telegram Stars:** 20 Stars (~$1.00)\n"
        f"💎 **TON:** 0.3 TON (~$1.00)\n\n"
        f"Tap a button below to pay:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "pay_stars_sub")
async def process_stars_subscription(callback: types.CallbackQuery):
    """Send Stars invoice for subscription"""
    await callback.answer()

    prices = [LabeledPrice(label="Monthly Unlimited", amount=STARS_MONTHLY_SUBSCRIPTION)]

    await callback.message.answer_invoice(
        title="NotaryTON Monthly Subscription",
        description="Unlimited notarizations for 30 days. Seal contracts, files, and more on TON blockchain.",
        payload=f"subscription_{callback.from_user.id}",
        currency="XTR",  # Telegram Stars
        prices=prices,
        provider_token="",  # Empty for Stars
    )


@dp.callback_query(F.data == "pay_ton_sub")
async def process_ton_subscription(callback: types.CallbackQuery):
    """Show TON payment instructions (Agent 5: Simplified)"""
    user_id = callback.from_user.id
    await callback.answer()

    # Generate unique memo for this payment
    memo = generate_payment_memo(user_id)
    payment_memo_lookup[memo] = {"user_id": user_id, "timestamp": time.time(), "type": "subscription"}

    await callback.message.answer(
        f"💎 **PAY WITH TON**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"**Step 1:** Copy this address\n"
        f"`{SERVICE_TON_WALLET}`\n\n"
        f"**Step 2:** Send exactly **0.3 TON**\n\n"
        f"**Step 3:** Add this memo:\n"
        f"`{user_id}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏱️ Activates in ~1 minute after sending\n"
        f"✅ We'll notify you when confirmed!",
        parse_mode="Markdown"
    )


@dp.callback_query(F.data == "pay_stars_single")
async def process_stars_single(callback: types.CallbackQuery):
    """Send Stars invoice for single notarization"""
    await callback.answer()

    prices = [LabeledPrice(label="Single Notarization", amount=STARS_SINGLE_NOTARIZATION)]

    await callback.message.answer_invoice(
        title="Single Notarization",
        description="Notarize one contract or file on TON blockchain forever.",
        payload=f"single_{callback.from_user.id}",
        currency="XTR",  # Telegram Stars
        prices=prices,
        provider_token="",  # Empty for Stars
    )


@dp.callback_query(F.data == "pay_ton_single")
async def process_ton_single(callback: types.CallbackQuery):
    """Show TON payment instructions for single notarization (Agent 5: Simplified)"""
    user_id = callback.from_user.id
    await callback.answer()

    # Generate unique memo for this payment
    memo = generate_payment_memo(user_id)
    payment_memo_lookup[memo] = {"user_id": user_id, "timestamp": time.time(), "type": "single"}

    await callback.message.answer(
        f"💎 **PAY WITH TON**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"**Step 1:** Copy this address\n"
        f"`{SERVICE_TON_WALLET}`\n\n"
        f"**Step 2:** Send exactly **0.15 TON**\n\n"
        f"**Step 3:** Add this memo:\n"
        f"`{user_id}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏱️ Credit added in ~1 minute\n"
        f"📤 Then send your file to seal it!",
        parse_mode="Markdown"
    )


# ========================
# INLINE QUERY HANDLER (for @NotaryTON_bot <hash> in any chat)
# ========================

@dp.inline_query()
async def process_inline_query(inline_query: InlineQuery):
    """Handle inline queries - users type @NotaryTON_bot <hash> to verify"""
    query_text = inline_query.query.strip()

    results = []

    if not query_text:
        # No query - show instructions
        results.append(
            InlineQueryResultArticle(
                id="help",
                title="🔍 Verify a Notarization",
                description="Enter a contract hash to verify its notarization status",
                input_message_content=InputTextMessageContent(
                    message_text="🔐 **NotaryTON Verification**\n\nTo verify a notarization, type:\n`@NotaryTON_bot <contract_hash>`\n\n🌐 Or visit: https://notaryton.com",
                    parse_mode="Markdown"
                )
            )
        )
    else:
        # Query provided - look up the hash
        try:
            notarizations = await db.notarizations.find_by_hash(query_text)

            if notarizations:
                for i, n in enumerate(notarizations[:5]):
                    results.append(
                        InlineQueryResultArticle(
                            id=f"result_{i}",
                            title=f"✅ Verified: {n.contract_hash[:16]}...",
                            description=f"Notarized on {n.timestamp}",
                            input_message_content=InputTextMessageContent(
                                message_text=f"✅ **VERIFIED NOTARIZATION**\n\n"
                                             f"🔐 Hash: `{n.contract_hash}`\n"
                                             f"📅 Timestamp: {n.timestamp}\n"
                                             f"⛓️ Blockchain: TON\n\n"
                                             f"🔗 Verify: https://notaryton.com/api/v1/verify/{n.contract_hash}",
                                parse_mode="Markdown"
                            )
                        )
                    )
            else:
                results.append(
                    InlineQueryResultArticle(
                        id="not_found",
                        title=f"❌ Not Found: {query_text[:16]}...",
                        description="No notarization found for this hash",
                        input_message_content=InputTextMessageContent(
                            message_text=f"❌ **NOT FOUND**\n\n"
                                         f"No notarization found for:\n`{query_text}`\n\n"
                                         f"🔐 Want to notarize? Use @NotaryTON_bot",
                            parse_mode="Markdown"
                        )
                    )
                )
        except Exception as e:
            print(f"Inline query error: {e}")
            results.append(
                InlineQueryResultArticle(
                    id="error",
                    title="⚠️ Error",
                    description="Could not process query",
                    input_message_content=InputTextMessageContent(
                        message_text="⚠️ Error processing verification. Try again or visit https://notaryton.com"
                    )
                )
            )

    await inline_query.answer(results, cache_time=60)


# ========================
# TELEGRAM STARS PAYMENT HANDLERS
# ========================

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """Handle pre-checkout query - must respond within 10 seconds"""
    # Always approve - Stars payments are instant and reliable
    await pre_checkout_query.answer(ok=True)


@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    """Handle successful Stars payment"""
    user_id = message.from_user.id
    payment = message.successful_payment
    payload = payment.invoice_payload

    # Log the payment
    print(f"✅ Stars payment received: {payment.total_amount} XTR from user {user_id}, payload: {payload}")

    if payload.startswith("subscription_"):
        # Activate subscription
        await add_subscription(user_id, months=1)

        # Update total paid (convert Stars to approximate TON value)
        stars_value_ton = payment.total_amount * 0.001  # Rough conversion
        await db.users.add_payment(user_id, stars_value_ton)

        # 🎰 LOTTERY: Subscriptions get tickets too! 1 ticket per Star
        await db.lottery.add_entry(user_id, amount_stars=payment.total_amount)
        ticket_count = await db.lottery.count_user_entries(user_id)

        await message.answer(
            "✅ **Subscription Activated!**\n\n"
            "You now have **unlimited notarizations** for 30 days!\n\n"
            "Use /notarize to seal your first contract.\n"
            "Use /api to get API access for integrations.\n\n"
            f"🎰 **+{payment.total_amount} LOTTERY TICKETS!** (Total: {ticket_count})\n"
            "🔒 Thank you for supporting NotaryTON!",
            parse_mode="Markdown"
        )

    elif payload.startswith("single_"):
        # Add single notarization credit
        await db.users.ensure_exists(user_id)
        await db.users.add_payment(user_id, TON_SINGLE_SEAL)

        # 🎰 LOTTERY: Add entry (1 Star = 1 ticket, 20% goes to pot)
        await db.lottery.add_entry(user_id, amount_stars=payment.total_amount)
        ticket_count = await db.lottery.count_user_entries(user_id)

        await message.answer(
            "✅ **Payment Received!**\n\n"
            "You can now notarize **one contract or file**.\n\n"
            "Send me:\n"
            "• A contract address (EQ...)\n"
            "• Or upload a file\n\n"
            f"🎰 **+1 LOTTERY TICKET!** (Total: {ticket_count})\n"
            "🔒 I'll seal it on TON blockchain forever!",
            parse_mode="Markdown"
        )


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    user_id = message.from_user.id
    has_sub = await get_user_subscription(user_id)

    # Get user stats
    user = await db.users.get(user_id)
    notarization_count = await db.notarizations.count_by_user(user_id)
    ticket_count = await db.lottery.count_user_entries(user_id)

    stats = {
        "total_paid": user.total_paid if user else 0,
        "referral_earnings": user.referral_earnings if user else 0,
        "notarizations": notarization_count
    }

    status_msg = "✅ **Active Subscription**\n\n" if has_sub else "❌ **No Active Subscription**\n\n"
    status_msg += f"📊 **Your Stats:**\n"
    status_msg += f"• Notarizations: {stats['notarizations']}\n"
    status_msg += f"• Lottery Tickets: {ticket_count} 🎰\n"
    status_msg += f"• Total Spent: {stats['total_paid']:.4f} TON\n"

    if stats['referral_earnings'] > 0:
        status_msg += f"• Referral Earnings: {stats['referral_earnings']:.4f} TON\n"

    # Agent 6: Subscription Value Calculator
    if not has_sub and notarization_count > 0:
        # Calculate if subscription would save money
        pay_as_you_go_cost = notarization_count * STARS_SINGLE_NOTARIZATION  # Stars
        subscription_cost = STARS_MONTHLY_SUBSCRIPTION  # 20 Stars

        if notarization_count >= 20:
            savings = pay_as_you_go_cost - subscription_cost
            status_msg += f"\n💡 **You've sealed {notarization_count} times!**\n"
            status_msg += f"With a subscription, you'd save {savings} ⭐!\n"
        elif notarization_count >= 10:
            seals_to_breakeven = subscription_cost - notarization_count
            status_msg += f"\n💡 **Tip:** {seals_to_breakeven} more seals and subscription pays off!\n"
        else:
            status_msg += f"\n💡 Subscribe at 20 ⭐ for unlimited seals!"
    elif not has_sub:
        status_msg += "\n💡 Use /subscribe for unlimited seals!"

    await message.answer(status_msg, parse_mode="Markdown")

@dp.message(Command("referral"))
async def cmd_referral(message: types.Message):
    user_id = message.from_user.id

    # Get or generate referral code
    referral_stats = await db.users.get_referral_stats(user_id)
    referral_code = referral_stats['code']

    if not referral_code:
        # Generate unique referral code
        referral_code = f"REF{user_id}"
        await db.users.ensure_exists(user_id)
        await db.users.set_referral_code(user_id, referral_code)
        referral_stats = await db.users.get_referral_stats(user_id)

    referral_url = f"https://t.me/NotaryTON_bot?start={referral_code}"

    # Agent 7: Clear referral explanation
    referral_msg = (
        f"🎁 **Referral Program**\n\n"
        f"**Your Link:**\n"
        f"`{referral_url}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"**How it works:**\n"
        f"• Share your link with friends\n"
        f"• You earn **5% of EVERY seal** they make\n"
        f"• Not just first purchase - **lifetime!**\n"
        f"• Withdraw when you hit 0.05 TON\n\n"
    )

    # Show earnings breakdown
    if referral_stats['count'] > 0:
        avg_per_referral = referral_stats['earnings'] / referral_stats['count'] if referral_stats['count'] > 0 else 0
        referral_msg += (
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"**Your Stats:**\n"
            f"👥 Referrals: **{referral_stats['count']}**\n"
            f"💰 Total Earned: **{referral_stats['earnings']:.4f} TON**\n"
            f"📊 Avg per referral: {avg_per_referral:.4f} TON\n\n"
            f"💵 Withdrawn: {referral_stats['withdrawn']:.4f} TON\n"
            f"✅ Available: **{referral_stats['available']:.4f} TON**\n\n"
        )

        # Progress bar to withdrawal
        min_withdrawal = 0.05
        if referral_stats['available'] < min_withdrawal:
            progress = (referral_stats['available'] / min_withdrawal) * 100
            needed = min_withdrawal - referral_stats['available']
            referral_msg += (
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"**Withdrawal Progress:**\n"
                f"{'█' * int(progress / 10)}{'░' * (10 - int(progress / 10))} {progress:.0f}%\n"
                f"Need {needed:.4f} more TON to withdraw\n"
            )
        else:
            referral_msg += f"✅ **Ready to withdraw!** Use /withdraw <wallet>\n"
    else:
        referral_msg += (
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"**No referrals yet!**\n\n"
            f"Share your link in:\n"
            f"• TON trading groups\n"
            f"• Memecoin communities\n"
            f"• With deployer friends\n"
        )

    await message.answer(referral_msg, parse_mode="Markdown")


def get_next_draw_date() -> str:
    """Get next Sunday at 20:00 UTC (8pm - US prime time) as draw date"""
    from datetime import timezone
    now = datetime.now(timezone.utc)
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0 and now.hour >= 20:
        days_until_sunday = 7
    next_draw = now + timedelta(days=days_until_sunday)
    next_draw = next_draw.replace(hour=20, minute=0, second=0, microsecond=0)
    return next_draw.strftime("%Y-%m-%d %H:%M UTC")


async def announce_seal_to_socials(file_hash: str):
    """Post seal announcement to X and Telegram channel (rate-limited)"""
    try:
        pot_stars = await db.lottery.get_pot_size_stars()
        pot_ton = await db.lottery.get_pot_size_ton()
        next_draw = get_next_draw_date()
        await announce_seal(file_hash, pot_stars, pot_ton, next_draw)
    except Exception as e:
        print(f"⚠️ Social announcement failed: {e}")


def get_countdown_to_draw() -> str:
    """Get human-readable countdown to next draw"""
    now = datetime.now()
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0 and now.hour >= 12:
        days_until_sunday = 7
    next_draw = now + timedelta(days=days_until_sunday)
    next_draw = next_draw.replace(hour=12, minute=0, second=0, microsecond=0)

    delta = next_draw - now
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


@dp.message(Command("pot"))
async def cmd_pot(message: types.Message):
    """Show current lottery pot - DEGEN MODE 🎰 (Agent 8: Enhanced)"""
    user_id = message.from_user.id
    pot_stars = await db.lottery.get_pot_size_stars()
    pot_ton = await db.lottery.get_pot_size_ton()
    total_entries = await db.lottery.get_total_entries()
    unique_players = await db.lottery.get_unique_participants()
    user_tickets = await db.lottery.count_user_entries(user_id)
    next_draw = get_next_draw_date()
    countdown = get_countdown_to_draw()

    # Calculate user's odds
    if total_entries > 0 and user_tickets > 0:
        win_chance = (user_tickets / total_entries) * 100
        odds_msg = f"🎯 **Your odds:** {win_chance:.2f}% ({user_tickets} tickets)"
    elif user_tickets == 0:
        odds_msg = "🎯 **Your odds:** 0% (no tickets yet!)"
    else:
        odds_msg = ""

    # Build exciting message
    pot_msg = (
        f"🎰 **MEMESEAL LOTTERY** 🎰\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 **JACKPOT**\n"
        f"⭐ **{pot_stars} Stars**\n"
        f"≈ {pot_ton:.4f} TON (~${pot_ton * 3.5:.2f})\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏰ **Next Draw:** {countdown}\n"
        f"📅 {next_draw}\n\n"
        f"📊 **Stats:**\n"
        f"• Total Tickets: {total_entries}\n"
        f"• Players: {unique_players}\n\n"
        f"{odds_msg}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"**How to Play:**\n"
        f"• Every seal = 1 lottery ticket\n"
        f"• 20% of each fee → jackpot\n"
        f"• Winner takes all on Sunday!\n"
    )

    # Add CTA based on user's tickets
    if user_tickets == 0:
        pot_msg += f"\n🚀 **Seal something to enter!**"
    elif user_tickets < 5:
        pot_msg += f"\n🚀 **Seal more to improve your odds!**"
    else:
        pot_msg += f"\n🍀 **Good luck on Sunday!**"

    await message.answer(pot_msg, parse_mode="Markdown")


@dp.message(Command("mytickets"))
async def cmd_mytickets(message: types.Message):
    """Show user's lottery tickets (Agent 8: Enhanced)"""
    user_id = message.from_user.id
    ticket_count = await db.lottery.count_user_entries(user_id)
    total_entries = await db.lottery.get_total_entries()
    pot_stars = await db.lottery.get_pot_size_stars()
    pot_ton = await db.lottery.get_pot_size_ton()
    unique_players = await db.lottery.get_unique_participants()
    countdown = get_countdown_to_draw()

    if total_entries > 0:
        win_chance = (ticket_count / total_entries) * 100
    else:
        win_chance = 0

    next_draw = get_next_draw_date()

    if ticket_count == 0:
        await message.answer(
            f"🎫 **YOUR LOTTERY TICKETS**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"**Tickets:** 0\n"
            f"**Win Chance:** 0%\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 **Current Pot:** {pot_stars} ⭐ ({pot_ton:.4f} TON)\n"
            f"⏰ **Draw in:** {countdown}\n\n"
            f"**How to get tickets:**\n"
            f"• Seal a file or screenshot\n"
            f"• Every seal = 1 ticket\n"
            f"• 20% of fees → jackpot\n\n"
            f"🚀 **Start sealing to enter!**",
            parse_mode="Markdown"
        )
    else:
        # Calculate rank (simplified - just show if top player)
        rank_msg = ""
        if ticket_count > 0 and unique_players > 1:
            avg_tickets = total_entries / unique_players
            if ticket_count > avg_tickets * 2:
                rank_msg = "🏆 **You're a TOP player!**\n"
            elif ticket_count > avg_tickets:
                rank_msg = "📈 **Above average odds!**\n"

        # Visual ticket representation
        ticket_visual = "🎫" * min(ticket_count, 10)
        if ticket_count > 10:
            ticket_visual += f" +{ticket_count - 10} more"

        await message.answer(
            f"🎫 **YOUR LOTTERY TICKETS**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"{ticket_visual}\n\n"
            f"**Tickets:** {ticket_count}\n"
            f"**Win Chance:** {win_chance:.2f}%\n"
            f"{rank_msg}"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 **Pot:** {pot_stars} ⭐ (~{pot_ton:.4f} TON)\n"
            f"👥 **Players:** {unique_players}\n"
            f"⏰ **Draw in:** {countdown}\n\n"
            f"🚀 **Seal more = better odds!**",
            parse_mode="Markdown"
        )


@dp.message(Command("withdraw"))
async def cmd_withdraw(message: types.Message):
    """Withdraw referral earnings"""
    user_id = message.from_user.id
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []

    # Get user's available balance
    user = await db.users.get(user_id)
    if not user:
        await message.answer("⚠️ No earnings yet. Share your /referral link to start earning!")
        return

    available = user.available_balance
    saved_wallet = user.withdrawal_wallet

    # Check if wallet address was provided
    wallet_address = None
    if args:
        potential_wallet = args[0]
        # Validate TON address format
        if potential_wallet.startswith(('EQ', 'UQ', 'kQ', '0Q')):
            try:
                Address(potential_wallet)
                wallet_address = potential_wallet
                # Save wallet for future
                await db.users.set_withdrawal_wallet(user_id, wallet_address)
            except Exception:
                await message.answer("⚠️ Invalid wallet address format.")
                return
    else:
        wallet_address = saved_wallet

    if not wallet_address:
        await message.answer(
            "💳 **Withdraw Referral Earnings**\n\n"
            f"Available: **{available:.4f} TON**\n\n"
            "To withdraw, send:\n"
            "`/withdraw EQYourWalletAddress...`\n\n"
            "Example:\n"
            "`/withdraw EQB4s8q3ysQxY2gTT14xWUJzBu2g...`",
            parse_mode="Markdown"
        )
        return

    # Check minimum
    if available < MIN_WITHDRAWAL_TON:
        await message.answer(
            f"⚠️ **Minimum Withdrawal: {MIN_WITHDRAWAL_TON} TON**\n\n"
            f"Your balance: {available:.4f} TON\n\n"
            f"Keep sharing your /referral link to earn more!",
            parse_mode="Markdown"
        )
        return

    # Process withdrawal
    try:
        await send_payout_transaction(
            destination=wallet_address,
            amount_ton=available,
            memo=f"NotaryTON Referral Payout"
        )

        # Update DB
        await db.users.record_withdrawal(user_id, available)

        await message.answer(
            f"✅ **Withdrawal Sent!**\n\n"
            f"**Amount:** {available:.4f} TON\n"
            f"**To:** `{wallet_address[:20]}...`\n\n"
            f"TX will appear in ~30 seconds.\n"
            f"Check: tonscan.org/address/{wallet_address}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(
            f"❌ **Withdrawal Failed**\n\n"
            f"Error: {str(e)}\n\n"
            f"Please try again later or contact support.",
            parse_mode="Markdown"
        )

@dp.message(Command("lang"))
async def cmd_lang(message: types.Message):
    """Change language"""
    user_id = message.from_user.id

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en"),
            types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
        ],
        [
            types.InlineKeyboardButton(text="🇨🇳 中文", callback_data="lang_zh"),
        ]
    ])

    await message.answer(
        "🌍 **Choose Your Language**\n\n"
        "Select your preferred language:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("lang_"))
async def process_lang_change(callback: types.CallbackQuery):
    """Handle language change callback"""
    user_id = callback.from_user.id
    lang = callback.data.replace("lang_", "")

    await set_user_language(user_id, lang)
    await callback.answer()

    lang_names = {"en": "English", "ru": "Русский", "zh": "中文"}
    await callback.message.edit_text(
        f"✅ Language changed to **{lang_names.get(lang, 'English')}**",
        parse_mode="Markdown"
    )

@dp.message(Command("api"))
async def cmd_api(message: types.Message):
    user_id = message.from_user.id
    has_sub = await get_user_subscription(user_id)
    
    if not has_sub:
        await message.answer(
            "⚠️ **API Access Requires Subscription**\n\n"
            "Subscribe first with /subscribe to get API access!",
            parse_mode="Markdown"
        )
        return
    
    await message.answer(
        f"🔌 **NotaryTON API**\n\n"
        f"**Your API Key:** `{user_id}`\n\n"
        f"**Endpoints:**\n"
        f"• POST {WEBHOOK_URL}/api/v1/notarize\n"
        f"• POST {WEBHOOK_URL}/api/v1/batch\n"
        f"• GET {WEBHOOK_URL}/api/v1/verify/{{hash}}\n\n"
        f"**Example:**\n"
        f"```bash\n"
        f"curl -X POST {WEBHOOK_URL}/api/v1/notarize \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -d '{{\n"
        f"    \"api_key\": \"{user_id}\",\n"
        f"    \"contract_address\": \"EQ...\",\n"
        f"    \"metadata\": {{\"project_name\": \"MyCoin\"}}\n"
        f"  }}'\n"
        f"```\n\n"
        f"📚 Full docs: {WEBHOOK_URL}/docs",
        parse_mode="Markdown"
    )

@dp.message(Command("notarize"))
async def cmd_notarize(message: types.Message):
    user_id = message.from_user.id
    has_sub = await get_user_subscription(user_id)

    # Check if user has paid credits
    has_credit = False
    if not has_sub:
        total_paid = await db.users.get_total_paid(user_id)
        if total_paid >= TON_SINGLE_SEAL:
            has_credit = True

    if not has_sub and not has_credit:
        # Offer payment options
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⭐ Pay 3 Stars", callback_data="pay_stars_single")],
            [types.InlineKeyboardButton(text="💎 Pay 0.15 TON", callback_data="pay_ton_single")],
            [types.InlineKeyboardButton(text="🚀 Unlimited (20 Stars/mo)", callback_data="pay_stars_sub")]
        ])

        await message.answer(
            "⚠️ **Payment Required**\n\n"
            "Choose how to pay for this notarization:\n\n"
            "⭐ **3 Stars** - Quick & easy\n"
            "💎 **0.15 TON** - Native crypto\n"
            "🚀 **50 Stars/mo** - Unlimited access\n",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return

    await message.answer(
        "📄 **Manual Notarization Ready**\n\n"
        "Send me:\n"
        "• A contract address (EQ...)\n"
        "• A file to notarize\n\n"
        "I'll seal it on TON blockchain forever! 🔒",
        parse_mode="Markdown"
    )

async def check_user_can_notarize(user_id: int):
    """Check if user has subscription or credits. Returns (can_notarize, has_subscription)"""
    has_sub = await get_user_subscription(user_id)
    if has_sub:
        return True, True

    total_paid = await db.users.get_total_paid(user_id)
    if total_paid >= TON_SINGLE_SEAL:
        return True, False
    return False, False


async def deduct_credit(user_id: int):
    """Deduct one notarization credit from user"""
    await db.users.deduct_payment(user_id, TON_SINGLE_SEAL)


def get_payment_keyboard():
    """Return standard payment keyboard"""
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⭐ Pay 3 Stars", callback_data="pay_stars_single")],
        [types.InlineKeyboardButton(text="💎 Pay 0.15 TON", callback_data="pay_ton_single")],
        [types.InlineKeyboardButton(text="🚀 Unlimited (20 Stars/mo)", callback_data="pay_stars_sub")]
    ])


@dp.message(F.text)
async def handle_text_message(message: types.Message):
    """Handle text messages - contract addresses, tx hashes, and deploy bot patterns"""
    text = message.text.strip()
    user_id = message.from_user.id

    # Skip if it's a command
    if text.startswith('/'):
        return

    # Check if message is from a known deploy bot (auto-notarization in groups)
    sender_username = f"@{message.from_user.username}" if message.from_user.username else None
    is_deploy_bot = sender_username in DEPLOY_BOTS

    # Pattern matching for TON addresses and transactions
    ton_address_pattern = r'^(EQ|UQ|0:)[A-Za-z0-9_-]{46,48}$'
    tx_pattern = r'tx:\s*([A-Za-z0-9]+)'
    hash_pattern = r'^[A-Fa-f0-9]{64}$'

    contract_id = None

    # Check for TON address
    if re.match(ton_address_pattern, text):
        contract_id = text
    # Check for tx: pattern (from deploy bots)
    elif match := re.search(tx_pattern, text, re.IGNORECASE):
        contract_id = match.group(1)
    # Check for hash verification request
    elif re.match(hash_pattern, text):
        # User is trying to verify a hash
        try:
            notarization = await db.notarizations.get_by_hash(text)
            if notarization:
                await message.reply(
                    f"✅ **VERIFIED**\n\n"
                    f"Hash: `{text}`\n"
                    f"Timestamp: {notarization.timestamp}\n"
                    f"Status: Sealed on TON 🔒\n\n"
                    f"🔗 {WEBHOOK_URL}/api/v1/verify/{text}",
                    parse_mode="Markdown"
                )
            else:
                await message.reply(
                    f"❌ **Not Found**\n\n"
                    f"Hash `{text[:16]}...` has not been notarized yet.\n\n"
                    f"Want to seal something? Send me a file or contract address!",
                    parse_mode="Markdown"
                )
        except Exception as e:
            await message.reply(f"⚠️ Error checking hash: {str(e)}")
        return
    else:
        # Not a recognized pattern - ignore silently in groups, help in DMs
        if message.chat.type == "private":
            await message.reply(
                "🔐 **NotaryTON**\n\n"
                "Send me:\n"
                "• A TON contract address (EQ... or UQ...)\n"
                "• A file or screenshot to notarize\n"
                "• A hash to verify\n\n"
                "Or use /notarize to get started!",
                parse_mode="Markdown"
            )
        return

    # We have a contract to notarize
    can_notarize, has_sub = await check_user_can_notarize(user_id)

    if not can_notarize:
        if is_deploy_bot:
            await message.reply(
                f"🔍 **New Launch Detected!**\n\n"
                f"Contract: `{contract_id[:20]}...`\n\n"
                f"⚠️ Send 0.15 TON to `{SERVICE_TON_WALLET}` (memo: `{user_id}`) to notarize!\n"
                f"Or /subscribe for unlimited access.",
                parse_mode="Markdown"
            )
        else:
            await message.reply(
                "⚠️ **Payment Required**\n\n"
                f"Contract detected: `{contract_id[:20]}...`\n\n"
                "Choose how to pay:",
                parse_mode="Markdown",
                reply_markup=get_payment_keyboard()
            )
        return

    # Notarize the contract
    try:
        await message.reply("⏳ Fetching contract and sealing on TON...")

        contract_code = await get_contract_code_from_tx(contract_id)
        if not contract_code:
            await message.reply(
                "❌ **Could not fetch contract**\n\n"
                "Make sure the address is valid and the contract is deployed.",
                parse_mode="Markdown"
            )
            return

        contract_hash = hash_data(contract_code)
        comment = f"NotaryTON:Contract:{contract_hash[:16]}"
        await send_ton_transaction(comment, amount_ton=TON_SINGLE_SEAL)
        await log_notarization(user_id, contract_id, contract_hash, paid=True)

        # Deduct credit if not subscription
        if not has_sub:
            await deduct_credit(user_id)

        await message.reply(
            f"✅ **SEALED!**\n\n"
            f"Contract: `{contract_id[:30]}...`\n"
            f"Hash: `{contract_hash}`\n\n"
            f"🔗 Verify: {WEBHOOK_URL}/api/v1/verify/{contract_hash}\n\n"
            f"Sealed on TON blockchain forever! 🔒",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.reply(f"❌ Error notarizing: {str(e)}")

@dp.message(F.document)
async def handle_document(message: types.Message):
    """Handle file uploads for manual notarization"""
    user_id = message.from_user.id
    can_notarize, has_sub = await check_user_can_notarize(user_id)

    if not can_notarize:
        await message.answer(
            "⚠️ **Payment Required to Notarize**\n\n"
            "Choose how to pay:\n\n"
            "⭐ **3 Stars** - Quick & easy\n"
            "💎 **0.15 TON** - Native crypto\n"
            "🚀 **50 Stars/mo** - Unlimited access\n",
            parse_mode="Markdown",
            reply_markup=get_payment_keyboard()
        )
        return

    # Download file
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_path = f"downloads/{file_id}"
    os.makedirs("downloads", exist_ok=True)
    await bot.download_file(file.file_path, file_path)

    # Hash it
    file_hash = hash_file(file_path)
    comment = f"NotaryTON:File:{file_hash[:16]}"

    try:
        await send_ton_transaction(comment)
        await log_notarization(user_id, "manual_file", file_hash, paid=True)

        # Deduct credit if not subscription
        if not has_sub:
            await deduct_credit(user_id)

        await message.answer(
            f"✅ **SEALED!**\n\n"
            f"File: `{message.document.file_name}`\n"
            f"Hash: `{file_hash}`\n\n"
            f"🔗 Verify: {WEBHOOK_URL}/api/v1/verify/{file_hash}\n\n"
            f"Proof stored on TON blockchain forever! 🔒",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

    # Clean up
    try:
        os.remove(file_path)
    except Exception:
        pass


@dp.message(F.photo)
async def handle_photo(message: types.Message):
    """Handle photo/screenshot uploads for notarization"""
    user_id = message.from_user.id
    can_notarize, has_sub = await check_user_can_notarize(user_id)

    if not can_notarize:
        await message.answer(
            "📸 **Nice screenshot!**\n\n"
            "3 Stars to seal it on TON forever.\n"
            "Proof you were there. 🔐",
            parse_mode="Markdown",
            reply_markup=get_payment_keyboard()
        )
        return

    # Download largest photo
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_path = f"downloads/{photo.file_id}.jpg"
    os.makedirs("downloads", exist_ok=True)
    await bot.download_file(file.file_path, file_path)

    file_hash = hash_file(file_path)
    comment = f"NotaryTON:Screenshot:{file_hash[:12]}"

    try:
        await send_ton_transaction(comment)
        await log_notarization(user_id, "screenshot", file_hash, paid=True)

        if not has_sub:
            await deduct_credit(user_id)

        await message.answer(
            f"✅ **SCREENSHOT SEALED!**\n\n"
            f"Hash: `{file_hash}`\n\n"
            f"🔗 Verify: {WEBHOOK_URL}/api/v1/verify/{file_hash}\n\n"
            f"Proof secured on TON forever! 🔒",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

    try:
        os.remove(file_path)
    except Exception:
        pass


# ========================
# MEMESEAL TON HANDLERS (Degen branding)
# ========================

if memeseal_dp:
    @memeseal_dp.message(Command("start"))
    async def memeseal_start(message: types.Message):
        user_id = message.from_user.id

        # Check for promo code
        promo_code = None
        if message.text and len(message.text.split()) > 1:
            promo_code = message.text.split()[1].upper()

        # Create user if doesn't exist
        await db.users.ensure_exists(user_id)

        # Check for CHIMPWIN promo (first 500 free seals)
        free_seal_msg = ""
        if promo_code == "CHIMPWIN":
            await db.users.add_payment(user_id, TON_SINGLE_SEAL)
            free_seal_msg = "\n\n🎁 **PROMO ACTIVATED!** You got 1 free seal. LFG!"

        welcome_msg = (
            "⚡🐸 **MEMESEAL TON**\n\n"
            "Proof or it didn't happen.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "**WHAT PEOPLE SEAL:**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "• Wallet balances & trades\n"
            "• Token contracts & launches\n"
            "• Agreements & receipts\n"
            "• Anything you need timestamped proof of\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "**HOW IT WORKS:**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "**1.** Send any file or image\n"
            "**2.** Pay 1 ⭐ Star (~$0.02)\n"
            "**3.** Get on-chain seal + verification link\n"
            "**4.** 🎰 Get lottery ticket (20% feeds pot!)\n\n"
            "👇 **Send something to seal it forever**"
            f"{free_seal_msg}"
        )

        # Add helpful buttons
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(
                text="🎰 PLAY CASINO",
                web_app=WebAppInfo(url="https://memeseal-casino.vercel.app")
            )],
            [types.InlineKeyboardButton(text="💰 Check Lottery Pot", callback_data="ms_check_pot")],
            [types.InlineKeyboardButton(text="🚀 Go Unlimited (20 ⭐/mo)", callback_data="ms_pay_stars_sub")]
        ])

        await message.answer(welcome_msg, parse_mode="Markdown", reply_markup=keyboard)

    @memeseal_dp.message(Command("unlimited"))
    async def memeseal_subscribe(message: types.Message):
        user_id = message.from_user.id

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⭐ 20 Stars - Go Unlimited", callback_data="ms_pay_stars_sub")],
            [types.InlineKeyboardButton(text="💎 0.3 TON - Same thing", callback_data="ms_pay_ton_sub")]
        ])

        await message.answer(
            "🚀 **UNLIMITED SEALS**\n\n"
            "Stop counting. Start sealing everything.\n\n"
            "**What you get:**\n"
            "• Unlimited seals for 30 days\n"
            "• API access included\n"
            "• Batch operations\n"
            "• Priority support (lol jk we respond to everyone)\n\n"
            "**Price:** 20 Stars OR 0.3 TON\n\n"
            "That's like... 2 failed txs on Solana.\n"
            "Except this one actually works. 🐸",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    @memeseal_dp.callback_query(F.data == "ms_check_pot")
    async def memeseal_check_pot(callback: types.CallbackQuery):
        """Show lottery pot from button"""
        await callback.answer()
        pot_stars = await db.lottery.get_pot_size_stars()
        pot_ton = await db.lottery.get_pot_size_ton()
        total_entries = await db.lottery.get_total_entries()
        unique_players = await db.lottery.get_unique_participants()
        next_draw = get_next_draw_date()
        user_tickets = await db.lottery.count_user_entries(callback.from_user.id)

        await callback.message.answer(
            f"🎰🐸 **THE FROG POT**\n\n"
            f"**JACKPOT:**\n"
            f"⭐ {pot_stars} Stars (~{pot_ton:.4f} TON)\n\n"
            f"📊 **STATS:**\n"
            f"• Total Entries: {total_entries}\n"
            f"• Degens Playing: {unique_players}\n"
            f"• Your Tickets: {user_tickets}\n\n"
            f"⏰ **NEXT DRAW:** {next_draw}\n\n"
            f"Every seal = 1 ticket\n"
            f"20% of fees feed the pot\n\n"
            f"Seal something to enter! 🚀",
            parse_mode="Markdown"
        )

    @memeseal_dp.callback_query(F.data == "ms_pay_stars_sub")
    async def memeseal_stars_sub(callback: types.CallbackQuery):
        await callback.answer()
        prices = [LabeledPrice(label="Unlimited Seals (30 days)", amount=STARS_MONTHLY_SUBSCRIPTION)]
        await callback.message.answer_invoice(
            title="MemeSeal Unlimited",
            description="Seal everything. Forever. No limits for 30 days.",
            payload=f"memeseal_sub_{callback.from_user.id}",
            currency="XTR",
            prices=prices,
            provider_token="",
        )

    @memeseal_dp.callback_query(F.data == "ms_pay_ton_sub")
    async def memeseal_ton_sub(callback: types.CallbackQuery):
        user_id = callback.from_user.id
        await callback.answer()
        await callback.message.answer(
            f"💎 **Pay with TON**\n\n"
            f"Send **0.3 TON** to:\n"
            f"`{SERVICE_TON_WALLET}`\n\n"
            f"**Memo:** `{user_id}`\n\n"
            f"Auto-activates in ~1 min. Then go seal everything. 🐸",
            parse_mode="Markdown"
        )

    @memeseal_dp.callback_query(F.data == "ms_pay_stars_single")
    async def memeseal_stars_single(callback: types.CallbackQuery):
        await callback.answer()
        prices = [LabeledPrice(label="Single Seal", amount=STARS_SINGLE_NOTARIZATION)]
        await callback.message.answer_invoice(
            title="Single Seal",
            description="One seal. On-chain forever. Proof you were there.",
            payload=f"memeseal_single_{callback.from_user.id}",
            currency="XTR",
            prices=prices,
            provider_token="",
        )

    @memeseal_dp.callback_query(F.data == "ms_pay_ton_single")
    async def memeseal_ton_single(callback: types.CallbackQuery):
        user_id = callback.from_user.id
        await callback.answer()

        # 🐸 INSTANT DOPAMINE - show success immediately, seal in background
        if user_id not in pending_files:
            await callback.message.answer(
                f"💎 **Pay with TON**\n\n"
                f"Send **0.15 TON** to:\n"
                f"`{SERVICE_TON_WALLET}`\n\n"
                f"**Memo:** `{user_id}`\n\n"
                f"Then send your file - I'll seal it instantly! 🐸⚡",
                parse_mode="Markdown"
            )
            return

        file_info = pending_files[user_id]
        del pending_files[user_id]

        # ✅ HONEST PROGRESS - show real status, no fake success
        progress_msg = await callback.message.answer(
            f"⏳ **SEALING TO BLOCKCHAIN...**\n\n"
            f"Your file is being timestamped on TON.\n"
            f"This takes 5-15 seconds.\n\n"
            f"_Please wait..._",
            parse_mode="Markdown"
        )

        # 🔥 BACKGROUND SEAL - do the actual work
        asyncio.create_task(background_seal_ton(
            user_id=user_id,
            file_info=file_info,
            message_to_edit=progress_msg
        ))


    async def background_seal_ton(user_id: int, file_info: dict, message_to_edit):
        """Background task to seal file and update message with real link"""
        file_hash = None
        file_path = None

        try:
            # Download file
            file_id = file_info["file_id"]
            file_type = file_info["file_type"]

            if file_type == "photo":
                file = await memeseal_bot.get_file(file_id)
                file_path = f"downloads/{file_id}.jpg"
            else:
                file = await memeseal_bot.get_file(file_id)
                file_path = f"downloads/{file_id}"

            os.makedirs("downloads", exist_ok=True)
            await memeseal_bot.download_file(file.file_path, file_path)
            file_hash = hash_file(file_path)

            # Try to seal with retries
            comment = f"MemeSeal:{file_hash[:16]}"
            sealed = False

            for attempt in range(5):
                try:
                    await send_ton_transaction(comment)
                    sealed = True
                    break
                except Exception as e:
                    error_str = str(e).lower()
                    print(f"⚠️ Seal attempt {attempt+1}/5 failed: {e}")

                    # Contract not initialized - try self-deploy
                    if "not initialized" in error_str or "-256" in error_str:
                        if attempt == 2:  # After 3rd fail, try deploy
                            print("🔧 Attempting wallet self-deploy...")
                            try:
                                await send_ton_transaction("MemeSeal:Deploy", amount_ton=0.01)
                                await asyncio.sleep(10)
                            except:
                                pass

                    await asyncio.sleep(10)

            if sealed:
                await log_notarization(user_id, "memeseal_ton_instant", file_hash, paid=True)
                await db.lottery.add_entry(user_id, amount_stars=1)
                ticket_count = await db.lottery.count_user_entries(user_id)

                # ✅ UPDATE MESSAGE WITH REAL LINK
                await message_to_edit.edit_text(
                    f"🚨 **TON PAYMENT CONFIRMED** 🟢\n\n"
                    f"✅ **SEALED FOREVER!** 🐸⚡\n\n"
                    f"Hash: `{file_hash}`\n"
                    f"🔗 Verify: notaryton.com/api/v1/verify/{file_hash}\n\n"
                    f"🎰 Lottery tickets: {ticket_count}\n"
                    f"💰 Pot grew +0.003 TON\n\n"
                    f"**Screenshot this. Post it. Become legend.**",
                    parse_mode="Markdown"
                )
                asyncio.create_task(announce_seal_to_socials(file_hash))
            else:
                # ❌ All retries failed - show retry button
                retry_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="🔄 Try Again", callback_data="ms_retry_seal")],
                    [types.InlineKeyboardButton(text="⭐ Use Stars Instead", callback_data="ms_pay_stars_single")]
                ])
                await message_to_edit.edit_text(
                    f"⚠️ **TON Network Busy**\n\n"
                    f"We tried 5 times but the network is congested.\n\n"
                    f"**Your options:**\n"
                    f"• Tap 'Try Again' in 30 seconds\n"
                    f"• Use Stars for guaranteed instant seal\n\n"
                    f"_Your file is safe - just try again!_",
                    parse_mode="Markdown",
                    reply_markup=retry_keyboard
                )
                # Store file for retry
                pending_files[user_id] = file_info

        except Exception as e:
            print(f"❌ Background seal error: {e}")
            # Agent 9: ALWAYS notify user of failures
            retry_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔄 Try Again", callback_data="ms_retry_seal")],
                [types.InlineKeyboardButton(text="⭐ Use Stars Instead", callback_data="ms_pay_stars_single")]
            ])
            try:
                error_msg = get_user_friendly_error(e, "Sealing your file")
                await message_to_edit.edit_text(
                    error_msg,
                    parse_mode="Markdown",
                    reply_markup=retry_keyboard
                )
                # Store file for retry
                pending_files[user_id] = file_info
            except:
                pass

        finally:
            if file_path:
                try:
                    os.remove(file_path)
                except:
                    pass

    @memeseal_dp.pre_checkout_query()
    async def memeseal_pre_checkout(pre_checkout_query: PreCheckoutQuery):
        await pre_checkout_query.answer(ok=True)

    @memeseal_dp.message(F.successful_payment)
    async def memeseal_payment_success(message: types.Message):
        user_id = message.from_user.id
        payment = message.successful_payment
        payload = payment.invoice_payload

        # 🎰 LOTTERY: Add entry for EVERY payment
        await db.users.ensure_exists(user_id)
        await db.lottery.add_entry(user_id, amount_stars=payment.total_amount)
        ticket_count = await db.lottery.count_user_entries(user_id)

        if "sub" in payload:
            await add_subscription(user_id, months=1)
            await message.answer(
                "🚨 **UNLIMITED MODE ACTIVATED** 🟢\n\n"
                "⚡ 30 days of infinite seals unlocked!\n\n"
                f"🎰 **+{payment.total_amount} LOTTERY TICKETS!**\n"
                f"Total tickets: {ticket_count}\n\n"
                "Send me ANYTHING - I'll seal it all.\n"
                "Files, screenshots, contracts, memes.\n\n"
                "**You're in the club now.** 🐸🚀",
                parse_mode="Markdown"
            )
        else:
            # ✅ HONEST PROGRESS - check if we have pending file to seal
            if user_id in pending_files:
                file_info = pending_files[user_id]
                del pending_files[user_id]

                # Show honest progress message
                progress_msg = await message.answer(
                    f"✅ **PAYMENT RECEIVED!** 🟢\n\n"
                    f"1 ⭐ confirmed — now sealing to blockchain...\n\n"
                    f"⏳ This takes 5-15 seconds.\n"
                    f"🎰 Lottery tickets: {ticket_count}\n\n"
                    f"_Please wait..._",
                    parse_mode="Markdown"
                )

                # Seal in background
                asyncio.create_task(background_seal_stars(
                    user_id=user_id,
                    file_info=file_info,
                    message_to_edit=progress_msg,
                    ticket_count=ticket_count
                ))
            else:
                await db.users.add_payment(user_id, TON_SINGLE_SEAL)
                await message.answer(
                    "🚨 **PAYMENT CONFIRMED** 🟢\n\n"
                    "1 ⭐ Star received!\n\n"
                    "Now send me what you want sealed.\n"
                    "File, screenshot, whatever.\n\n"
                    f"🎰 **+1 LOTTERY TICKET!** ({ticket_count} total)\n"
                    "🐸⚡",
                    parse_mode="Markdown"
                )


    async def background_seal_stars(user_id: int, file_info: dict, message_to_edit, ticket_count: int):
        """Background task to seal file paid with Stars"""
        file_hash = None
        file_path = None

        try:
            file_id = file_info["file_id"]
            file_type = file_info["file_type"]

            if file_type == "photo":
                file = await memeseal_bot.get_file(file_id)
                file_path = f"downloads/{file_id}.jpg"
            else:
                file = await memeseal_bot.get_file(file_id)
                file_path = f"downloads/{file_id}"

            os.makedirs("downloads", exist_ok=True)
            await memeseal_bot.download_file(file.file_path, file_path)
            file_hash = hash_file(file_path)

            comment = f"MemeSeal:{file_hash[:16]}"
            await send_ton_transaction(comment)
            await log_notarization(user_id, "memeseal_stars_instant", file_hash, paid=True)

            # ✅ UPDATE WITH REAL LINK
            await message_to_edit.edit_text(
                f"🚨 **STAR PAYMENT CONFIRMED** 🟢\n\n"
                f"✅ **SEALED FOREVER!** 🐸⚡\n\n"
                f"Hash: `{file_hash}`\n"
                f"🔗 Verify: notaryton.com/api/v1/verify/{file_hash}\n\n"
                f"🎰 Lottery tickets: {ticket_count}\n"
                f"💰 Pot grew +0.002 TON\n\n"
                f"**Screenshot this. Post it. Become legend.**",
                parse_mode="Markdown"
            )
            asyncio.create_task(announce_seal_to_socials(file_hash))

        except Exception as e:
            print(f"❌ Stars seal error: {e}")
            # Agent 9: Notify user with retry option (they paid, we owe them!)
            retry_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔄 Retry Seal", callback_data="ms_retry_seal")]
            ])
            if file_hash:
                try:
                    await message_to_edit.edit_text(
                        f"⚠️ **Network Delay**\n\n"
                        f"Payment received but seal pending.\n\n"
                        f"Hash: `{file_hash}`\n\n"
                        f"**Your seal is queued** - tap Retry or wait 30s.\n"
                        f"🎰 Lottery tickets: {ticket_count}\n\n"
                        f"_We'll keep trying automatically!_",
                        parse_mode="Markdown",
                        reply_markup=retry_keyboard
                    )
                    # Store for retry
                    pending_files[user_id] = file_info
                except:
                    pass
            else:
                try:
                    error_msg = get_user_friendly_error(e, "Processing your file")
                    await message_to_edit.edit_text(
                        error_msg,
                        parse_mode="Markdown",
                        reply_markup=retry_keyboard
                    )
                    pending_files[user_id] = file_info
                except:
                    pass

        finally:
            if file_path:
                try:
                    os.remove(file_path)
                except:
                    pass

    # Agent 9: Retry handler for failed seals
    @memeseal_dp.callback_query(F.data == "ms_retry_seal")
    async def memeseal_retry_seal(callback: types.CallbackQuery):
        """Handle retry button for failed seals"""
        user_id = callback.from_user.id
        await callback.answer("🔄 Retrying...")

        if user_id not in pending_files:
            await callback.message.edit_text(
                "⚠️ **Session Expired**\n\n"
                "Please send your file again to seal it.",
                parse_mode="Markdown"
            )
            return

        file_info = pending_files[user_id]
        del pending_files[user_id]

        # Show progress
        progress_msg = await callback.message.edit_text(
            f"⏳ **RETRYING...**\n\n"
            f"Sealing to blockchain.\n"
            f"This takes 5-15 seconds.\n\n"
            f"_Please wait..._",
            parse_mode="Markdown"
        )

        # Retry in background
        ticket_count = await db.lottery.count_user_entries(user_id)
        asyncio.create_task(background_seal_stars(
            user_id=user_id,
            file_info=file_info,
            message_to_edit=progress_msg,
            ticket_count=ticket_count
        ))

    @memeseal_dp.message(Command("api"))
    async def memeseal_api(message: types.Message):
        user_id = message.from_user.id
        await message.answer(
            f"🔧 **MEMESEAL API**\n\n"
            f"**Your API Key:** `{user_id}`\n"
            f"**Your Referral:** `https://t.me/MemeSealTON_bot?start=REF{user_id}`\n\n"
            f"**Endpoints:**\n"
            f"```\n"
            f"POST /api/v1/notarize\n"
            f"POST /api/v1/batch\n"
            f"GET /api/v1/verify/{{hash}}\n"
            f"```\n\n"
            f"**5% referral** on all seals from your link. Forever.\n\n"
            f"Docs: notaryton.com/memeseal",
            parse_mode="Markdown"
        )

    @memeseal_dp.message(Command("verify"))
    async def memeseal_verify(message: types.Message):
        await message.answer(
            "🔍 **VERIFY A SEAL**\n\n"
            "Send me a hash to check if it's been sealed.\n\n"
            "Or use inline mode:\n"
            "`@MemeSealTON_bot <hash>`\n\n"
            "in any chat to flex your receipts. 🐸",
            parse_mode="Markdown"
        )

    @memeseal_dp.message(Command("pot"))
    async def memeseal_pot(message: types.Message):
        """Show current lottery pot - FULL DEGEN MODE 🎰🐸"""
        pot_stars = await db.lottery.get_pot_size_stars()
        pot_ton = await db.lottery.get_pot_size_ton()
        total_entries = await db.lottery.get_total_entries()
        unique_players = await db.lottery.get_unique_participants()
        next_draw = get_next_draw_date()

        await message.answer(
            f"🎰🐸 **THE FROG POT**\n\n"
            f"**JACKPOT:**\n"
            f"⭐ {pot_stars} Stars (~{pot_ton:.4f} TON)\n\n"
            f"📊 **STATS:**\n"
            f"• Entries: {total_entries}\n"
            f"• Degens: {unique_players}\n\n"
            f"⏰ **NEXT DRAW:** {next_draw}\n\n"
            f"Every seal = 1 ticket\n"
            f"20% of fees feed the pot\n\n"
            f"/mytickets to check your odds 🎫",
            parse_mode="Markdown"
        )

    @memeseal_dp.message(Command("casino"))
    async def memeseal_casino(message: types.Message):
        """Open the casino mini app"""
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(
                text="🎰 OPEN CASINO",
                web_app=WebAppInfo(url="https://memeseal-casino.vercel.app")
            )]
        ])

        await message.answer(
            "🎰🐸 **MEMESEAL CASINO**\n\n"
            "**GAMES:**\n"
            "• 🎰 Politician Slots (100x jackpot)\n"
            "• 🚀 Frog Rocket (crash game)\n"
            "• 🎯 Election Roulette\n\n"
            "**THE DEAL:**\n"
            "• 20% of ALL bets feed the lottery pot\n"
            "• Connect TON wallet to play\n"
            "• Win big or feed the frogs\n\n"
            "Tap below to enter the casino 👇",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    @memeseal_dp.message(Command("mytickets"))
    async def memeseal_mytickets(message: types.Message):
        """Show user's lottery tickets - DEGEN STYLE"""
        user_id = message.from_user.id
        ticket_count = await db.lottery.count_user_entries(user_id)
        total_entries = await db.lottery.get_total_entries()

        if total_entries > 0:
            win_chance = (ticket_count / total_entries) * 100
        else:
            win_chance = 0

        next_draw = get_next_draw_date()

        if ticket_count == 0:
            await message.answer(
                f"🎫 **YOUR TICKETS: 0**\n\n"
                f"no tickets = no moon\n\n"
                f"**GET TICKETS:**\n"
                f"• Seal anything = 1 ticket\n"
                f"• More seals = more chances\n\n"
                f"Start sealing, degen. 🐸",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"🎫 **YOUR TICKETS**\n\n"
                f"**Count:** {ticket_count}\n"
                f"**Win Odds:** {win_chance:.2f}%\n\n"
                f"**Next Draw:** {next_draw}\n\n"
                f"more seals = more tickets = more moon 🚀🐸",
                parse_mode="Markdown"
            )

    @memeseal_dp.message(F.document)
    async def memeseal_handle_document(message: types.Message):
        user_id = message.from_user.id

        # 🐸 CHECK FOR PENDING TON PAYMENT - auto-seal if user paid via TON
        if user_id in pending_ton_payments:
            pending = pending_ton_payments[user_id]
            if time.time() - pending["timestamp"] < 600:  # 10 min window
                # AUTO-SEAL: User clicked "Pay with TON" and is now sending the file
                file_id = message.document.file_id
                file = await memeseal_bot.get_file(file_id)
                file_path = f"downloads/{file_id}"
                os.makedirs("downloads", exist_ok=True)
                await memeseal_bot.download_file(file.file_path, file_path)

                file_hash = hash_file(file_path)
                comment = f"MemeSeal:{file_hash[:16]}"

                try:
                    await send_ton_transaction(comment)
                    await log_notarization(user_id, "memeseal_file_ton", file_hash, paid=True)
                    del pending_ton_payments[user_id]

                    await message.answer(
                        f"⚡ **TON PAYMENT DETECTED** ⚡\n\n"
                        f"File: `{message.document.file_name}`\n"
                        f"Hash: `{file_hash}`\n\n"
                        f"🔗 Verify: notaryton.com/api/v1/verify/{file_hash}\n\n"
                        f"Sealed forever. Memo matched. 🐸🎰",
                        parse_mode="Markdown"
                    )
                    asyncio.create_task(announce_seal_to_socials(file_hash))
                except Exception as e:
                    await message.answer(f"❌ Seal failed: {str(e)}")

                try:
                    os.remove(file_path)
                except:
                    pass
                return
            else:
                del pending_ton_payments[user_id]  # Expired

        has_sub = await get_user_subscription(user_id)

        has_credit = False
        if not has_sub:
            total_paid = await db.users.get_total_paid(user_id)
            if total_paid >= TON_SINGLE_SEAL:
                has_credit = True

        if not has_sub and not has_credit:
            # 🐸 Store file info for pending TON payment flow
            pending_files[user_id] = {
                "file_id": message.document.file_id,
                "file_type": "document",
                "file_name": message.document.file_name,
                "timestamp": time.time()
            }

            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="⭐ Pay 3 Stars & Seal Now", callback_data="ms_pay_stars_single")],
                [types.InlineKeyboardButton(text="💎 Pay 0.15 TON instead", callback_data="ms_pay_ton_single")],
                [types.InlineKeyboardButton(text="🚀 Unlimited (15 ⭐/mo)", callback_data="ms_pay_stars_sub")]
            ])
            await message.answer(
                "✅ **Ready to seal!**\n\n"
                "**Cost:** 1 ⭐ Star (~$0.02)\n"
                "**You get:** On-chain timestamp + verification link\n\n"
                "👇 Tap to seal it on TON forever:",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            return

        # Download and seal
        file_id = message.document.file_id
        file = await memeseal_bot.get_file(file_id)
        file_path = f"downloads/{file_id}"
        os.makedirs("downloads", exist_ok=True)
        await memeseal_bot.download_file(file.file_path, file_path)

        file_hash = hash_file(file_path)
        comment = f"MemeSeal:{file_hash[:16]}"

        try:
            await send_ton_transaction(comment)
            await log_notarization(user_id, "memeseal_file", file_hash, paid=True)

            if not has_sub:
                await db.users.deduct_payment(user_id, TON_SINGLE_SEAL)

            await message.answer(
                f"⚡ **SEALED** ⚡\n\n"
                f"File: `{message.document.file_name}`\n"
                f"Hash: `{file_hash}`\n\n"
                f"🔗 Verify: notaryton.com/api/v1/verify/{file_hash}\n\n"
                f"On TON forever. Receipts secured. 🐸",
                parse_mode="Markdown"
            )

            # 📣 ANNOUNCE TO X + TELEGRAM CHANNEL
            asyncio.create_task(announce_seal_to_socials(file_hash))

        except Exception as e:
            await message.answer(f"❌ Seal failed: {str(e)}")

        try:
            os.remove(file_path)
        except Exception:
            pass

    @memeseal_dp.message(F.photo)
    async def memeseal_handle_photo(message: types.Message):
        """Handle screenshots/photos"""
        user_id = message.from_user.id

        # 🐸 CHECK FOR PENDING TON PAYMENT - auto-seal if user paid via TON
        if user_id in pending_ton_payments:
            pending = pending_ton_payments[user_id]
            if time.time() - pending["timestamp"] < 600:  # 10 min window
                # AUTO-SEAL: User clicked "Pay with TON" and is now sending the photo
                photo = message.photo[-1]
                file = await memeseal_bot.get_file(photo.file_id)
                file_path = f"downloads/{photo.file_id}.jpg"
                os.makedirs("downloads", exist_ok=True)
                await memeseal_bot.download_file(file.file_path, file_path)

                file_hash = hash_file(file_path)
                comment = f"MemeSeal:Screenshot:{file_hash[:12]}"

                try:
                    await send_ton_transaction(comment)
                    await log_notarization(user_id, "memeseal_photo_ton", file_hash, paid=True)
                    del pending_ton_payments[user_id]

                    await message.answer(
                        f"⚡ **TON PAYMENT DETECTED** ⚡\n\n"
                        f"Hash: `{file_hash}`\n\n"
                        f"🔗 Verify: notaryton.com/api/v1/verify/{file_hash}\n\n"
                        f"Screenshot sealed. Memo matched. 🐸🎰",
                        parse_mode="Markdown"
                    )
                    asyncio.create_task(announce_seal_to_socials(file_hash))
                except Exception as e:
                    await message.answer(f"❌ Seal failed: {str(e)}")

                try:
                    os.remove(file_path)
                except:
                    pass
                return
            else:
                del pending_ton_payments[user_id]  # Expired

        has_sub = await get_user_subscription(user_id)

        has_credit = False
        if not has_sub:
            total_paid = await db.users.get_total_paid(user_id)
            if total_paid >= TON_SINGLE_SEAL:
                has_credit = True

        if not has_sub and not has_credit:
            # 🐸 Store photo info for pending TON payment flow
            pending_files[user_id] = {
                "file_id": message.photo[-1].file_id,
                "file_type": "photo",
                "timestamp": time.time()
            }

            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="⭐ Pay 3 Stars & Seal Now", callback_data="ms_pay_stars_single")],
                [types.InlineKeyboardButton(text="💎 Pay 0.15 TON instead", callback_data="ms_pay_ton_single")],
                [types.InlineKeyboardButton(text="🚀 Unlimited (15 ⭐/mo)", callback_data="ms_pay_stars_sub")]
            ])
            await message.answer(
                "✅ **Ready to seal!**\n\n"
                "**Cost:** 1 ⭐ Star (~$0.02)\n"
                "**You get:** On-chain timestamp + verification link\n\n"
                "👇 Tap to seal it on TON forever:",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            return

        # Download largest photo
        photo = message.photo[-1]
        file = await memeseal_bot.get_file(photo.file_id)
        file_path = f"downloads/{photo.file_id}.jpg"
        os.makedirs("downloads", exist_ok=True)
        await memeseal_bot.download_file(file.file_path, file_path)

        file_hash = hash_file(file_path)
        comment = f"MemeSeal:Screenshot:{file_hash[:12]}"

        try:
            await send_ton_transaction(comment)
            await log_notarization(user_id, "memeseal_photo", file_hash, paid=True)

            if not has_sub:
                await db.users.deduct_payment(user_id, TON_SINGLE_SEAL)

            await message.answer(
                f"⚡ **SCREENSHOT SEALED** ⚡\n\n"
                f"Hash: `{file_hash}`\n\n"
                f"🔗 Verify: notaryton.com/api/v1/verify/{file_hash}\n\n"
                f"Proof secured. Now flex it. 🐸",
                parse_mode="Markdown"
            )

            # 📣 ANNOUNCE TO X + TELEGRAM CHANNEL
            asyncio.create_task(announce_seal_to_socials(file_hash))

        except Exception as e:
            await message.answer(f"❌ Seal failed: {str(e)}")

        try:
            os.remove(file_path)
        except Exception:
            pass

# ========================
# FASTAPI ENDPOINTS
# ========================

@app.post(WEBHOOK_PATH)
async def webhook_handler(request: Request):
    """Handle incoming webhook updates from Telegram (NotaryTON)"""
    update = Update(**(await request.json()))
    await dp.feed_update(bot, update)
    return {"ok": True}

# MemeSeal webhook endpoint
if MEMESEAL_WEBHOOK_PATH:
    @app.post(MEMESEAL_WEBHOOK_PATH)
    async def memeseal_webhook_handler(request: Request):
        """Handle incoming webhook updates from Telegram (MemeSeal)"""
        update = Update(**(await request.json()))
        await memeseal_dp.feed_update(memeseal_bot, update)
        return {"ok": True}

# MemeScan webhook endpoint (meme coin terminal)
if MEMESCAN_WEBHOOK_PATH:
    @app.post(MEMESCAN_WEBHOOK_PATH)
    async def memescan_webhook_handler(request: Request):
        """Handle incoming webhook updates from Telegram (MemeScan)"""
        update = Update(**(await request.json()))
        await memescan_dp.feed_update(memescan_bot, update)
        return {"ok": True}

# ========================
# TONAPI WEBHOOK - Real-time payment detection (no more 30s polling!)
# ========================
# Set this webhook URL in TonAPI console: https://notaryton.com/webhook/tonapi
# Docs: https://docs.tonconsole.com/tonapi/webhooks

@app.post("/webhook/tonapi")
async def tonapi_webhook(request: Request):
    """
    Handle real-time transaction webhooks from TonAPI.
    This replaces the 30-second polling with instant detection!
    """
    try:
        # Verify webhook signature if secret is configured
        if TONAPI_WEBHOOK_SECRET:
            body = await request.body()
            signature = request.headers.get("X-TonAPI-Signature", "")
            expected = hmac.new(
                TONAPI_WEBHOOK_SECRET.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                print(f"⚠️ TonAPI webhook: Invalid signature")
                return {"ok": False, "error": "Invalid signature"}
            data = json.loads(body)
        else:
            data = await request.json()

        print(f"📡 TonAPI webhook received: {data.get('event_type', 'unknown')}")

        # TonAPI sends transaction events when our wallet receives payments
        # Event types: "transaction" for incoming transactions
        event_type = data.get("event_type", "")

        if event_type == "transaction" or "transactions" in data:
            # Handle transaction event
            transactions = data.get("transactions", [data.get("transaction", {})])

            for tx in transactions:
                # Check if it's incoming to our wallet
                account = tx.get("account", {})
                account_address = account.get("address", "")

                # Normalize addresses for comparison
                our_wallet = SERVICE_TON_WALLET.replace("UQ", "").replace("EQ", "").lower()
                tx_wallet = account_address.replace("0:", "").lower()

                # Extract incoming message
                in_msg = tx.get("in_msg", {})
                if not in_msg:
                    continue

                # Get amount (in nanotons)
                amount_nano = int(in_msg.get("value", 0))
                amount_ton = amount_nano / 1e9

                if amount_ton < 0.001:  # Ignore dust
                    continue

                # Extract memo/comment from message
                memo = ""
                msg_data = in_msg.get("msg_data", {})
                if msg_data.get("@type") == "msg.dataText":
                    memo = msg_data.get("text", "")
                elif in_msg.get("decoded_body"):
                    decoded = in_msg.get("decoded_body", {})
                    memo = decoded.get("text", "") or decoded.get("comment", "")

                # Also check raw body for memo
                if not memo and in_msg.get("raw_body"):
                    try:
                        import base64
                        raw = base64.b64decode(in_msg.get("raw_body", ""))
                        # Skip first 4 bytes (comment op code)
                        if len(raw) > 4:
                            memo = raw[4:].decode('utf-8', errors='ignore').strip()
                    except:
                        pass

                print(f"💰 TonAPI Payment: {amount_ton:.4f} TON, memo: '{memo}'")

                # Try to find user_id from memo using our SEAL-XXXX format
                user_id = None

                # Check payment_memo_lookup first (SEAL-A7B3 format)
                if memo in payment_memo_lookup:
                    lookup = payment_memo_lookup[memo]
                    if time.time() - lookup["timestamp"] < 600:  # 10 min validity
                        user_id = lookup["user_id"]
                        payment_type = lookup.get("type", "single")
                        print(f"✅ Matched memo {memo} to user {user_id} ({payment_type})")

                # Fallback: extract numeric user_id from memo
                if not user_id:
                    try:
                        match = re.search(r'\d+', memo)
                        if match:
                            user_id = int(match.group())
                    except:
                        pass

                if user_id:
                    # Credit referrer with 5% commission
                    user = await db.users.get(user_id)
                    if user and user.referred_by:
                        referrer_id = user.referred_by
                        commission = amount_ton * 0.05
                        await db.users.add_referral_earnings(referrer_id, commission)
                        print(f"💰 Credited {commission:.4f} TON to referrer {referrer_id}")

                    # Check payment type (subscription vs single)
                    if amount_ton >= 0.28:  # Subscription (0.3 TON)
                        await add_subscription(user_id, months=1)

                        # 🎰 LOTTERY: Subscriptions get tickets
                        await db.lottery.add_entry(user_id, amount_stars=20)  # Equivalent to 20 stars
                        ticket_count = await db.lottery.count_user_entries(user_id)

                        # Notify user instantly!
                        for b in [bot, memeseal_bot]:
                            if b:
                                try:
                                    await b.send_message(
                                        user_id,
                                        f"🚨 **INSTANT PAYMENT DETECTED!** 🟢\n\n"
                                        f"✅ {amount_ton:.3f} TON received\n"
                                        f"✅ Subscription activated (30 days)\n\n"
                                        f"🎰 **+20 LOTTERY TICKETS!** (Total: {ticket_count})\n\n"
                                        f"Send me anything to seal! 🐸⚡",
                                        parse_mode="Markdown"
                                    )
                                except:
                                    pass

                        print(f"⚡ INSTANT: Activated subscription for user {user_id}")

                    elif amount_ton >= TON_SINGLE_SEAL * 0.9:  # Single seal (with small variance)
                        await db.users.ensure_exists(user_id)
                        await db.users.add_payment(user_id, amount_ton)

                        # 🎰 LOTTERY: Add entry
                        await db.lottery.add_entry(user_id, amount_stars=1)
                        ticket_count = await db.lottery.count_user_entries(user_id)

                        # Check if user has pending file to auto-seal
                        if user_id in pending_ton_payments:
                            pending = pending_ton_payments[user_id]

                            if pending.get("file_id"):
                                # AUTO-SEAL: User already sent file, now payment received
                                file_id = pending["file_id"]
                                file_type = pending.get("file_type", "document")
                                del pending_ton_payments[user_id]

                                # Send progress message and trigger seal
                                progress_msg = None
                                for b in [memeseal_bot, bot]:
                                    if b:
                                        try:
                                            progress_msg = await b.send_message(
                                                user_id,
                                                f"🚨 **PAYMENT DETECTED!** 🟢\n\n"
                                                f"✅ {amount_ton:.4f} TON received\n"
                                                f"⏳ Sealing your file now...",
                                                parse_mode="Markdown"
                                            )
                                            break
                                        except:
                                            pass

                                # Trigger seal using module-level function
                                asyncio.create_task(seal_file_from_webhook(user_id, file_id, file_type, progress_msg))
                                print(f"⚡ INSTANT: Auto-sealing file for user {user_id}")
                            else:
                                # Payment received but no file - just notify
                                for b in [bot, memeseal_bot]:
                                    if b:
                                        try:
                                            await b.send_message(
                                                user_id,
                                                f"🚨 **INSTANT PAYMENT DETECTED!** 🟢\n\n"
                                                f"✅ {amount_ton:.4f} TON received\n"
                                                f"✅ Credit added to your account\n\n"
                                                f"🎰 **+1 LOTTERY TICKET!** (Total: {ticket_count})\n\n"
                                                f"Now send me what you want sealed! 🐸",
                                                parse_mode="Markdown"
                                            )
                                        except:
                                            pass
                        else:
                            # Generic credit notification
                            for b in [bot, memeseal_bot]:
                                if b:
                                    try:
                                        await b.send_message(
                                            user_id,
                                            f"✅ **Payment Received!**\n\n"
                                            f"{amount_ton:.4f} TON credited\n"
                                            f"🎰 +1 lottery ticket (Total: {ticket_count})\n\n"
                                            f"Send me a file to seal it! 🐸",
                                            parse_mode="Markdown"
                                        )
                                    except:
                                        pass

                        print(f"⚡ INSTANT: Credited {amount_ton:.4f} TON to user {user_id}")

        return {"ok": True, "processed": True}

    except Exception as e:
        print(f"⚠️ TonAPI webhook error: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


# ========================
# SEAL CASINO WEBHOOK - Game results & bets
# ========================
# Set up at TonConsole for address: EQA-LMcVJpo9UlOq55YfZ7fFyQttu64cq6FpuMiLjBOgVGHY

SEAL_CASINO_ADDRESS = os.getenv("SEAL_CASINO_ADDRESS", "EQA-LMcVJpo9UlOq55YfZ7fFyQttu64cq6FpuMiLjBOgVGHY")
TONCONSOLE_CASINO_SECRET = os.getenv("TONCONSOLE_CASINO_SECRET", "")

@app.post("/webhook/casino")
async def casino_webhook(request: Request):
    """
    Handle SealCasino smart contract events.
    Receives bet placements, wins, losses, liquidity events.
    """
    try:
        body = await request.body()

        # Verify webhook signature if secret is configured
        if TONCONSOLE_CASINO_SECRET:
            signature = request.headers.get("X-Signature", "")
            expected = hmac.new(
                TONCONSOLE_CASINO_SECRET.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                print(f"⚠️ Casino webhook: Invalid signature")
                return {"ok": False, "error": "Invalid signature"}

        data = json.loads(body)
        print(f"🎰 Casino webhook: {json.dumps(data, indent=2)[:500]}")

        # TODO: Process casino events
        # - PlaceBet: User placed a bet
        # - BetResult: Win/lose outcome
        # - AddLiquidity: LP added funds
        # - Withdraw: LP withdrew funds

        return {"ok": True, "processed": True}

    except Exception as e:
        print(f"⚠️ Casino webhook error: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


# ========================
# SEAL TOKENS WEBHOOK - Token launches & trades
# ========================
# Set up at TonConsole for address: EQBju5vqGVsqfpjEpcNCFhn2CSKlVeQMG3f7kMz11Tw0A-ME

SEAL_TOKENS_ADDRESS = os.getenv("SEAL_TOKENS_ADDRESS", "EQBju5vqGVsqfpjEpcNCFhn2CSKlVeQMG3f7kMz11Tw0A-ME")
TONCONSOLE_TOKENS_SECRET = os.getenv("TONCONSOLE_TOKENS_SECRET", "")

@app.post("/webhook/tokens")
async def tokens_webhook(request: Request):
    """
    Handle SealTokenFactory smart contract events.
    Receives token creations, buys, sells, graduations.
    """
    try:
        body = await request.body()

        # Verify webhook signature if secret is configured
        if TONCONSOLE_TOKENS_SECRET:
            signature = request.headers.get("X-Signature", "")
            expected = hmac.new(
                TONCONSOLE_TOKENS_SECRET.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                print(f"⚠️ Tokens webhook: Invalid signature")
                return {"ok": False, "error": "Invalid signature"}

        data = json.loads(body)
        print(f"🪙 Tokens webhook: {json.dumps(data, indent=2)[:500]}")

        # TODO: Process token events
        # - CreateToken: New token launched
        # - BuyTokens: Someone bought on bonding curve
        # - SellTokens: Someone sold back to curve
        # - GraduateToken: Token hit 69 TON, moving to DEX

        return {"ok": True, "processed": True}

    except Exception as e:
        print(f"⚠️ Tokens webhook error: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


@app.get("/health")
@app.head("/health")
async def health_check():
    """Health check endpoint - supports both GET and HEAD"""
    return {"status": "running", "bot": "NotaryTON", "version": "2.0-memecoin"}


@app.get("/callback")
async def twitter_callback(oauth_token: str = None, oauth_verifier: str = None):
    """Twitter OAuth callback"""
    return HTMLResponse(content="<html><body style='background:#0d0d0d;color:#00ff41;font-family:monospace;display:flex;justify-content:center;align-items:center;height:100vh'><h1>Connected! You can close this window.</h1></body></html>")


@app.get("/terms", response_class=HTMLResponse)
async def terms_of_service():
    """Terms of Service"""
    return "<html><head><title>MemeSeal Terms</title><style>body{background:#0d0d0d;color:#00ff41;font-family:monospace;padding:40px;max-width:800px;margin:0 auto}h1{color:#39ff14}h2{color:#00ffff;margin-top:30px}a{color:#ff00ff}</style></head><body><h1>MemeSeal Terms of Service</h1><p>Last updated: December 2024</p><h2>1. Acceptance</h2><p>By using MemeSeal, you agree to these terms.</p><h2>2. Service</h2><p>MemeSeal provides blockchain timestamping on TON. 20% of fees go to lottery pot.</p><h2>3. Payments</h2><p>Payments via Telegram Stars or TON are final.</p><h2>4. No Guarantees</h2><p>Service provided as-is. DYOR. NFA.</p><h2>5. Contact</h2><p><a href='https://t.me/MemeSealTON'>Telegram</a></p></body></html>"


@app.get("/memescan", response_class=HTMLResponse)
async def memescan_landing(request: Request):
    """MemeScan - TON Meme Terminal Landing Page"""
    return templates.TemplateResponse("memescan/landing.html", {"request": request})


@app.get("/memescan/litepaper", response_class=HTMLResponse)
async def memescan_litepaper(request: Request):
    """MemeScan Litepaper - readable whitepaper"""
    return templates.TemplateResponse("memescan/litepaper.html", {"request": request})


# ========================
# MEMESCAN REST API - For Mini App
# ========================

@app.get("/api/v1/memescan/trending")
async def api_memescan_trending(limit: int = 10):
    """Get trending meme coins."""
    try:
        client = get_memescan_client()
        tokens = await client.get_trending(limit=min(limit, 20))
        return {
            "success": True,
            "tokens": [
                {
                    "address": t.address,
                    "symbol": t.symbol,
                    "name": t.name,
                    "price_usd": t.price_usd,
                    "price_change_24h": t.price_change_24h,
                    "volume_24h_usd": t.volume_24h_usd,
                    "liquidity_usd": t.liquidity_usd,
                }
                for t in tokens
            ],
        }
    except Exception as e:
        print(f"❌ MemeScan trending error: {e}")
        return {"success": False, "error": str(e), "tokens": []}


@app.get("/api/v1/memescan/new")
async def api_memescan_new(limit: int = 10):
    """Get newly launched tokens."""
    try:
        client = get_memescan_client()
        tokens = await client.get_new_launches(limit=min(limit, 20))
        return {
            "success": True,
            "tokens": [
                {
                    "address": t.address,
                    "symbol": t.symbol,
                    "name": t.name,
                    "price_usd": t.price_usd,
                    "liquidity_usd": t.liquidity_usd,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in tokens
            ],
        }
    except Exception as e:
        print(f"❌ MemeScan new error: {e}")
        return {"success": False, "error": str(e), "tokens": []}


@app.get("/api/v1/memescan/check/{address}")
async def api_memescan_check(address: str):
    """Analyze token safety."""
    try:
        # Validate address format
        if not (address.startswith("EQ") or address.startswith("UQ") or address.startswith("0:")):
            return {"success": False, "error": "Invalid TON address format"}

        client = get_memescan_client()
        token = await client.analyze_token_safety(address)
        return {
            "success": True,
            "token": {
                "address": token.address,
                "symbol": token.symbol,
                "name": token.name,
                "holder_count": token.holder_count,
                "dev_wallet_percent": token.dev_wallet_percent,
                "safety_level": token.safety_level.value,
                "safety_warnings": token.safety_warnings,
            },
        }
    except Exception as e:
        print(f"❌ MemeScan check error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/score/{address}")
@app.get("/api/v1/rugscore/{address}")
async def api_rugscore(address: str):
    """
    RUG SCORE API - Returns 0-100 safety score for any TON token.

    Score breakdown:
    - 90-100: SAFE (green badge) - Low holder concentration, many holders
    - 60-89: WARNING (yellow badge) - Some concentration or few holders
    - 0-59: DANGER (red badge) - High concentration, likely rug risk

    Free to use. Powered by notaryton.com
    """
    try:
        # Validate address format
        if not (address.startswith("EQ") or address.startswith("UQ") or address.startswith("0:")):
            return {"success": False, "error": "Invalid TON address format", "score": 0}

        client = get_memescan_client()
        token = await client.analyze_token_safety(address)

        # Calculate 0-100 score based on safety factors
        score = 100

        # Deduct for holder concentration (biggest factor)
        if token.dev_wallet_percent > 50:
            score -= 50  # Massive red flag
        elif token.dev_wallet_percent > 30:
            score -= 35
        elif token.dev_wallet_percent > 20:
            score -= 20
        elif token.dev_wallet_percent > 10:
            score -= 10

        # Deduct for low holder count
        if token.holder_count < 5:
            score -= 30
        elif token.holder_count < 10:
            score -= 20
        elif token.holder_count < 50:
            score -= 10
        elif token.holder_count < 100:
            score -= 5

        # Determine badge color
        if score >= 90:
            badge = "green"
            verdict = "SAFE"
        elif score >= 60:
            badge = "yellow"
            verdict = "WARNING"
        else:
            badge = "red"
            verdict = "DANGER"

        return {
            "success": True,
            "score": max(0, score),
            "badge": badge,
            "verdict": verdict,
            "token": {
                "address": token.address,
                "symbol": token.symbol,
                "name": token.name,
                "holder_count": token.holder_count,
                "top_wallet_percent": round(token.dev_wallet_percent, 1),
            },
            "warnings": token.safety_warnings,
            "powered_by": "notaryton.com"
        }
    except Exception as e:
        print(f"❌ Rug score error: {e}")
        return {"success": False, "error": str(e), "score": 0}


@app.get("/api/v1/tokens/stats")
async def api_token_stats():
    """
    TOKEN TRACKING STATS - Data moat analytics.

    Returns statistics about tracked tokens including:
    - Total tokens tracked
    - Rugged tokens count
    - Safe tokens count (score >= 80)
    - Tokens tracked today
    - Overall rug rate percentage
    """
    try:
        stats = await db.tokens.get_stats()
        return {
            "success": True,
            "stats": stats,
            "powered_by": "notaryton.com"
        }
    except Exception as e:
        print(f"❌ Token stats error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/v1/tokens/recent")
async def api_recent_tokens(limit: int = 20):
    """Get recently tracked tokens."""
    try:
        tokens = await db.tokens.get_recent(limit=min(limit, 100))
        return {
            "success": True,
            "tokens": [
                {
                    "address": t.address,
                    "symbol": t.symbol,
                    "name": t.name,
                    "safety_score": t.safety_score,
                    "holder_count": t.current_holder_count,
                    "top_holder_pct": t.current_top_holder_pct,
                    "rugged": t.rugged,
                    "first_seen": t.first_seen.isoformat() if t.first_seen else None,
                }
                for t in tokens
            ],
            "powered_by": "notaryton.com"
        }
    except Exception as e:
        print(f"❌ Recent tokens error: {e}")
        return {"success": False, "error": str(e), "tokens": []}


@app.get("/api/v1/tokens/rugged")
async def api_rugged_tokens(limit: int = 20):
    """Get tokens that have been detected as rugs."""
    try:
        tokens = await db.tokens.get_rugged(limit=min(limit, 100))
        return {
            "success": True,
            "count": len(tokens),
            "tokens": [
                {
                    "address": t.address,
                    "symbol": t.symbol,
                    "name": t.name,
                    "initial_holders": t.initial_holder_count,
                    "initial_dev_pct": t.initial_top_holder_pct,
                    "rugged_at": t.rugged_at.isoformat() if t.rugged_at else None,
                }
                for t in tokens
            ],
            "powered_by": "notaryton.com"
        }
    except Exception as e:
        print(f"❌ Rugged tokens error: {e}")
        return {"success": False, "error": str(e), "tokens": []}


@app.get("/api/v1/memescan/pools")
async def api_memescan_pools(limit: int = 10):
    """Get top liquidity pools."""
    try:
        client = get_memescan_client()
        pools = await client.stonfi.get_trending_pools(limit=min(limit, 20))
        return {
            "success": True,
            "pools": [
                {
                    "address": p.address,
                    "dex": p.dex,
                    "pair": f"{p.token0_symbol}/{p.token1_symbol}",
                    "token0_symbol": p.token0_symbol,
                    "token1_symbol": p.token1_symbol,
                    "liquidity_usd": p.liquidity_usd,
                    "volume_24h": p.volume_24h,
                }
                for p in pools
            ],
        }
    except Exception as e:
        print(f"❌ MemeScan pools error: {e}")
        return {"success": False, "error": str(e), "pools": []}


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    """Privacy Policy"""
    return "<html><head><title>MemeSeal Privacy</title><style>body{background:#0d0d0d;color:#00ff41;font-family:monospace;padding:40px;max-width:800px;margin:0 auto}h1{color:#39ff14}h2{color:#00ffff;margin-top:30px}a{color:#ff00ff}</style></head><body><h1>MemeSeal Privacy Policy</h1><p>Last updated: December 2024</p><h2>1. What We Collect</h2><p>Telegram user ID, file hashes (not files), payment records, wallet addresses.</p><h2>2. What We Don't</h2><p>Your actual files, personal info beyond Telegram ID.</p><h2>3. Blockchain = Public</h2><p>Seals on TON are permanent and public.</p><h2>4. Contact</h2><p><a href='https://t.me/MemeSealTON'>Telegram</a></p></body></html>"


@app.get("/pot")
async def get_lottery_pot():
    """Get current lottery pot value - polled by landing page"""
    try:
        # Use real DB values instead of simulation
        pot_stars = await db.lottery.get_pot_size_stars()
        pot_ton = await db.lottery.get_pot_size_ton()
        total_entries = await db.lottery.get_total_entries()
        unique_players = await db.lottery.get_unique_participants()
        next_draw = get_next_draw_date()
        return {
            "stars": pot_stars,
            "ton": round(pot_ton, 4),
            "entries": total_entries,
            "players": unique_players,
            "next_draw": next_draw
        }
    except Exception as e:
        print(f"❌ Error getting pot: {e}")
        return {"stars": 0, "ton": 0.0, "entries": 0, "players": 0, "next_draw": "Sunday 20:00 UTC"}


@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    favicon_path = "static/favicon.ico"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    # Fallback to logo.png
    return FileResponse("static/logo.png", media_type="image/png")


@app.get("/verify", response_class=HTMLResponse)
async def verify_page(request: Request):
    """Public verification page - check any seal"""
    return templates.TemplateResponse("verify.html", {"request": request, "memeseal_username": MEMESEAL_USERNAME})


@app.get("/memeseal")
async def memeseal_redirect():
    """Redirect /memeseal to root for backwards compatibility"""
    return RedirectResponse(url="/", status_code=301)


@app.get("/whitepaper", response_class=HTMLResponse)
async def whitepaper(request: Request):
    """FROGS FOREVER - The Vision"""
    return templates.TemplateResponse("whitepaper.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
async def landing_page_memeseal(request: Request):
    """MemeSeal TON - Main landing page"""
    return templates.TemplateResponse("landing.html", {
        "request": request,
        "memeseal_username": MEMESEAL_USERNAME
    })

@app.get("/notaryton", response_class=HTMLResponse)
async def landing_page_legacy(request: Request):
    """Legacy NotaryTON landing page"""
    return templates.TemplateResponse("notaryton.html", {
        "request": request,
        "bot_username": BOT_USERNAME
    })

@app.get("/score", response_class=HTMLResponse)
async def rugscore_page(request: Request):
    """Rug Score landing page - marketing hook for token safety checks"""
    return templates.TemplateResponse("score.html", {"request": request})

# ========================
# PUBLIC API ENDPOINTS (Make NotaryTON essential infrastructure)
# ========================

@app.post("/api/v1/notarize")
async def api_notarize(request: Request):
    """
    Public API for third-party services to notarize contracts
    
    POST /api/v1/notarize
    {
        "api_key": "user_telegram_id",  // For now, use Telegram user ID
        "contract_address": "EQ...",     // TON address or tx hash
        "metadata": {                    // Optional
            "project_name": "MyCoin",
            "launch_date": "2025-11-24"
        }
    }
    
    Returns: {"success": true, "hash": "...", "tx_url": "https://tonscan.org/..."}
    """
    try:
        data = await request.json()
        user_id = int(data.get("api_key", 0))
        contract_id = data.get("contract_address", "")
        metadata = data.get("metadata", {})
        
        if not user_id or not contract_id:
            return {"success": False, "error": "Missing api_key or contract_address"}
        
        # Check if user has subscription or credits
        has_sub = await get_user_subscription(user_id)
        if not has_sub:
            return {
                "success": False, 
                "error": "No active subscription",
                "subscribe_url": f"https://t.me/NotaryTON_bot?start=subscribe"
            }
        
        # Fetch and notarize contract
        contract_code = await get_contract_code_from_tx(contract_id)
        if not contract_code:
            return {"success": False, "error": "Failed to fetch contract"}
        
        contract_hash = hash_data(contract_code)
        comment = f"NotaryTON:API:{contract_hash[:16]}"
        
        # Add metadata to comment if provided
        if metadata.get("project_name"):
            comment = f"NotaryTON:{metadata['project_name'][:20]}:{contract_hash[:12]}"
        
        await send_ton_transaction(comment, amount_ton=TON_SINGLE_SEAL)
        await log_notarization(user_id, contract_id, contract_hash, paid=True)
        
        return {
            "success": True,
            "hash": contract_hash,
            "contract": contract_id,
            "timestamp": datetime.now().isoformat(),
            "tx_url": "https://tonscan.org/",
            "verify_url": f"{WEBHOOK_URL}/api/v1/verify/{contract_hash}"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/v1/verify/{contract_hash}")
async def api_verify(contract_hash: str):
    """
    Public verification endpoint - anyone can verify a notarization

    GET /api/v1/verify/{hash}

    Returns: Notarization details including timestamp, tx_hash, etc.
    """
    try:
        notarization = await db.notarizations.get_by_hash(contract_hash)

        if notarization:
            return {
                "verified": True,
                "hash": contract_hash,
                "tx_hash": notarization.tx_hash,
                "timestamp": str(notarization.timestamp) if notarization.timestamp else None,
                "notarized_by": "NotaryTON",
                "blockchain": "TON",
                "explorer_url": f"https://tonscan.org/tx/{notarization.tx_hash}"
            }
        else:
            return {
                "verified": False,
                "hash": contract_hash,
                "message": "No notarization found for this hash"
            }
    except Exception as e:
        return {"verified": False, "error": str(e)}

@app.post("/api/v1/batch")
async def api_batch_notarize(request: Request):
    """
    Batch notarization for high-volume users
    
    POST /api/v1/batch
    {
        "api_key": "user_id",
        "contracts": [
            {"address": "EQ...", "name": "Coin1"},
            {"address": "EQ...", "name": "Coin2"}
        ]
    }
    
    Returns: Array of results
    """
    try:
        data = await request.json()
        user_id = int(data.get("api_key", 0))
        contracts = data.get("contracts", [])
        
        if not user_id or not contracts:
            return {"success": False, "error": "Missing api_key or contracts"}
        
        # Must have subscription for batch operations
        has_sub = await get_user_subscription(user_id)
        if not has_sub:
            return {
                "success": False,
                "error": "Subscription required for batch operations",
                "subscribe_url": f"https://t.me/NotaryTON_bot?start=subscribe"
            }
        
        results = []
        for contract in contracts[:50]:  # Limit to 50 per batch
            try:
                address = contract.get("address", "")
                name = contract.get("name", "")
                
                contract_code = await get_contract_code_from_tx(address)
                contract_hash = hash_data(contract_code)
                
                comment = f"NotaryTON:{name[:20]}:{contract_hash[:12]}" if name else f"NotaryTON:Batch:{contract_hash[:16]}"
                await send_ton_transaction(comment, amount_ton=TON_SINGLE_SEAL)
                await log_notarization(user_id, address, contract_hash, paid=True)
                
                results.append({
                    "success": True,
                    "address": address,
                    "hash": contract_hash,
                    "verify_url": f"{WEBHOOK_URL}/api/v1/verify/{contract_hash}"
                })
            except Exception as e:
                results.append({
                    "success": False,
                    "address": contract.get("address", ""),
                    "error": str(e)
                })
        
        return {
            "success": True,
            "processed": len(results),
            "results": results
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


# ========================
# LOTTERY API ENDPOINTS
# ========================

@app.get("/api/v1/lottery/pot")
async def api_lottery_pot():
    """
    Get current lottery pot info for casino integration

    Returns:
        pot_stars: Total stars in pot (20% of fees)
        pot_ton: Estimated TON value
        total_entries: Number of lottery tickets
        unique_players: Number of unique participants
        next_draw: Next draw timestamp (Sunday 12:00 UTC)
    """
    try:
        pot_stars = await db.lottery.get_pot_size_stars()
        pot_ton = await db.lottery.get_pot_size_ton()
        total_entries = await db.lottery.get_total_entries()
        unique_players = await db.lottery.get_unique_participants()
        next_draw = get_next_draw_date()

        return {
            "success": True,
            "pot_stars": pot_stars,
            "pot_ton": pot_ton,
            "total_entries": total_entries,
            "unique_players": unique_players,
            "next_draw": next_draw
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/v1/lottery/tickets/{user_id}")
async def api_user_tickets(user_id: int):
    """Get user's lottery ticket count"""
    try:
        ticket_count = await db.lottery.count_user_entries(user_id)
        total_entries = await db.lottery.get_total_entries()
        win_chance = (ticket_count / total_entries * 100) if total_entries > 0 else 0

        return {
            "success": True,
            "user_id": user_id,
            "tickets": ticket_count,
            "win_chance_percent": round(win_chance, 2),
            "total_entries": total_entries
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/v1/casino/bet")
async def api_casino_bet(request: Request):
    """
    Record a casino bet and add lottery entry

    POST /api/v1/casino/bet
    {
        "user_id": "wallet_address_or_tg_id",
        "amount": 0.1,
        "game": "slots|roulette|crash"
    }
    """
    try:
        data = await request.json()
        user_id_str = str(data.get("user_id", "guest"))
        amount = float(data.get("amount", 0))
        game = data.get("game", "casino")

        # Convert wallet address to numeric ID if needed
        if user_id_str.startswith("EQ") or user_id_str.startswith("UQ"):
            # Hash wallet to get consistent user_id
            user_id = abs(hash(user_id_str)) % (10**9)
        else:
            try:
                user_id = int(user_id_str)
            except:
                user_id = abs(hash(user_id_str)) % (10**9)

        # Ensure user exists
        await db.users.ensure_exists(user_id)

        # Add lottery entry (equivalent to 1 star per 0.001 TON bet)
        stars_equivalent = max(1, int(amount * 1000))
        await db.lottery.add_entry(user_id, amount_stars=stars_equivalent)

        ticket_count = await db.lottery.count_user_entries(user_id)

        return {
            "success": True,
            "lottery_entry": True,
            "tickets_added": 1,
            "total_tickets": ticket_count,
            "game": game,
            "message": f"Bet recorded. +1 lottery ticket!"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/stats")
async def stats():
    """Get bot statistics (JSON API)"""
    total_users = await db.users.count()
    total_notarizations = await db.notarizations.count()

    return {
        "total_users": total_users,
        "total_notarizations": total_notarizations
    }


# Admin endpoint to seed lottery pot (protected by secret)
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "memeseal-admin-2024")

@app.post("/admin/seed-lottery")
async def seed_lottery(amount_stars: int = 2500, secret: str = ""):
    """Seed the lottery pot with fake entries (admin only)"""
    if secret != ADMIN_SECRET:
        return {"error": "Unauthorized"}

    # Add entries to lottery (creates a "house" user if needed)
    house_user_id = 1  # System/house user

    try:
        # Ensure house user exists (create has ON CONFLICT DO NOTHING)
        await db.users.create(house_user_id, referral_code=f"REF{house_user_id}")

        # Add lottery entry with specified amount
        await db.lottery.add_entry(house_user_id, amount_stars)

        # Get new pot size
        pot_stars = await db.lottery.get_pot_size_stars()
        pot_ton = await db.lottery.get_pot_size_ton()

        return {
            "success": True,
            "added_stars": amount_stars,
            "pot_stars": pot_stars,
            "pot_ton": pot_ton
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Visual dashboard for NotaryTON stats"""
    # Total stats
    total_users = await db.users.count()
    total_notarizations = await db.notarizations.count()

    # 24h stats and other complex queries using raw SQL
    async with db.pool.acquire() as conn:
        notarizations_24h = await conn.fetchval("""
            SELECT COUNT(*) FROM notarizations
            WHERE timestamp > NOW() - INTERVAL '1 day'
        """)

        users_24h = await conn.fetchval("""
            SELECT COUNT(*) FROM users
            WHERE created_at > NOW() - INTERVAL '1 day'
        """)

        # Revenue stats
        total_revenue = await conn.fetchval(
            "SELECT COALESCE(SUM(total_paid), 0) FROM users"
        )

        # Referral stats
        total_referrals = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL"
        )

        total_referral_earnings = await conn.fetchval(
            "SELECT COALESCE(SUM(referral_earnings), 0) FROM users"
        )

        # Top referrers
        top_referrers = await conn.fetch("""
            SELECT u.user_id, COUNT(r.user_id) as ref_count, COALESCE(u.referral_earnings, 0) as earnings
            FROM users u
            LEFT JOIN users r ON r.referred_by = u.user_id
            WHERE u.referral_code IS NOT NULL
            GROUP BY u.user_id, u.referral_earnings
            ORDER BY ref_count DESC
            LIMIT 5
        """)

        # Recent notarizations
        recent_seals = await conn.fetch("""
            SELECT contract_hash, timestamp FROM notarizations
            ORDER BY timestamp DESC LIMIT 10
        """)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_users": total_users,
        "total_notarizations": total_notarizations,
        "notarizations_24h": notarizations_24h or 0,
        "users_24h": users_24h or 0,
        "total_revenue": total_revenue or 0,
        "total_referrals": total_referrals or 0,
        "top_referrers": top_referrers,
        "recent_seals": recent_seals
    })

@app.on_event("startup")
async def on_startup():
    """Set webhooks for both bots on startup"""
    global BOT_USERNAME, MEMESEAL_USERNAME

    # Initialize database (PostgreSQL via Neon)
    await db.connect()

    # Initialize social media poster (X + Telegram channel)
    social_poster.initialize()

    # Get bot info
    try:
        bot_info = await bot.get_me()
        BOT_USERNAME = bot_info.username
        print(f"✅ NotaryTON username: @{BOT_USERNAME}")
    except Exception as e:
        print(f"⚠️ Could not fetch NotaryTON info: {e}")

    if memeseal_bot:
        try:
            ms_info = await memeseal_bot.get_me()
            MEMESEAL_USERNAME = ms_info.username
            print(f"✅ MemeSeal username: @{MEMESEAL_USERNAME}")
        except Exception as e:
            print(f"⚠️ Could not fetch MemeSeal info: {e}")

    # Set NotaryTON webhook
    webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(webhook_url, drop_pending_updates=True)
    print(f"✅ NotaryTON webhook set to: {webhook_url}")

    # Set MemeSeal webhook (if configured)
    if memeseal_bot and MEMESEAL_WEBHOOK_PATH:
        memeseal_webhook_url = f"{WEBHOOK_URL}{MEMESEAL_WEBHOOK_PATH}"
        await memeseal_bot.set_webhook(memeseal_webhook_url, drop_pending_updates=True)
        print(f"✅ MemeSeal webhook set to: {memeseal_webhook_url}")

    # Set MemeScan webhook (if configured)
    if memescan_bot and MEMESCAN_WEBHOOK_PATH:
        memescan_webhook_url = f"{WEBHOOK_URL}{MEMESCAN_WEBHOOK_PATH}"
        await memescan_bot.set_webhook(memescan_webhook_url, drop_pending_updates=True)
        print(f"✅ MemeScan webhook set to: {memescan_webhook_url}")

    # Start MemeScan Twitter auto-poster (if enabled)
    if os.getenv("MEMESCAN_TWITTER_ENABLED", "").lower() == "true":
        memescan_twitter.initialize()
        asyncio.create_task(memescan_twitter.run_auto_poster(interval_seconds=1800))
        print("✅ MemeScan Twitter auto-poster started (every 30 min)")

    # Join groups
    for group_id in GROUP_IDS:
        if group_id.strip():
            try:
                await bot.send_message(group_id, "🔐 NotaryTON is now monitoring this group for auto-notarization!")
                print(f"✅ Joined group: {group_id}")
            except Exception as e:
                print(f"❌ Failed to join group {group_id}: {e}")

    # Start payment polling task
    asyncio.create_task(poll_wallet_for_payments())

    # 🐸 Start pending payment cleanup task
    asyncio.create_task(cleanup_pending_payments())

    # 🎰 Start lottery draw task (Sunday 20:00 UTC)
    asyncio.create_task(run_sunday_lottery_draw())

    # 🕷️ Start token crawler (data moat)
    if os.getenv("CRAWLER_ENABLED", "").lower() == "true":
        asyncio.create_task(start_crawler())
        print("✅ Token crawler started (building data moat)")

    os.makedirs("downloads", exist_ok=True)

@app.on_event("shutdown")
async def on_shutdown():
    """Cleanup on shutdown - DO NOT delete webhook (causes issues with Render restarts)"""
    await bot.session.close()
    if memeseal_bot:
        await memeseal_bot.session.close()
    if memescan_bot:
        await memescan_bot.session.close()
        # Also close memescan API clients
        client = get_memescan_client()
        await client.close()
    # Stop crawler if running
    await stop_crawler()
    await db.disconnect()
    print("🛑 Bot sessions and database closed (webhooks preserved)")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
