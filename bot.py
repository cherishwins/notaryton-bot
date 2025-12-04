import hashlib
import os
import re
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Update, LabeledPrice, PreCheckoutQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from dotenv import load_dotenv
from pytoniq import LiteBalancer, WalletV4R2, Address
import uvicorn

# Database layer (PostgreSQL with Neon)
from database import db

# Load .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

# Load config
BOT_TOKEN = os.getenv("BOT_TOKEN")
MEMESEAL_BOT_TOKEN = os.getenv("MEMESEAL_BOT_TOKEN")
TON_CENTER_API_KEY = os.getenv("TON_CENTER_API_KEY")
TON_WALLET_SECRET = os.getenv("TON_WALLET_SECRET")
SERVICE_TON_WALLET = os.getenv("SERVICE_TON_WALLET")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://notaryton.com")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
MEMESEAL_WEBHOOK_PATH = f"/webhook/{MEMESEAL_BOT_TOKEN}" if MEMESEAL_BOT_TOKEN else None
GROUP_IDS = os.getenv("GROUP_IDS", "").split(",")  # Comma-separated chat IDs

# Known deploy bots (add more as needed)
DEPLOY_BOTS = ["@tondeployer", "@memelaunchbot", "@toncoinbot"]

# Telegram Stars pricing (XTR currency)
# 1 Star ≈ $0.02-0.05 depending on purchase method
STARS_SINGLE_NOTARIZATION = 1   # 1 Star for single notarization
STARS_MONTHLY_SUBSCRIPTION = 20  # 20 Stars for monthly unlimited (~$1.00)

# TON pricing
TON_SINGLE_SEAL = 0.015  # 0.015 TON per seal (~$0.05)
TON_MONTHLY_SUB = 0.3    # 0.3 TON for monthly unlimited (~$1.00)

# Initialize bot and dispatcher (NotaryTON - professional)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Initialize MemeSeal bot (degen branding) - shares same database/wallet
memeseal_bot = Bot(token=MEMESEAL_BOT_TOKEN) if MEMESEAL_BOT_TOKEN else None
memeseal_dp = Dispatcher() if MEMESEAL_BOT_TOKEN else None

app = FastAPI()

# Global bot usernames (fetched on startup)
BOT_USERNAME = "NotaryTON_bot"
MEMESEAL_USERNAME = "MemeSealTON_bot"

# Mount static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ========================
# MULTI-LANGUAGE SUPPORT (i18n)
# ========================

TRANSLATIONS = {
    "en": {
        "welcome": "🔐 **NotaryTON** - Blockchain Notarization\n\nSeal contracts, files, and screenshots on TON forever.\n\n**Commands:**\n/notarize - Seal a contract\n/status - Check your subscription\n/subscribe - Get unlimited seals\n/referral - Earn 5% commission\n/withdraw - Withdraw referral earnings\n/lang - Change language",
        "no_sub": "⚠️ **Payment Required**\n\n1 Star or 0.015 TON to seal this.",
        "sealed": "✅ **SEALED ON TON!**\n\nHash: `{hash}`\n\n🔗 Verify: {url}\n\nProof secured forever! 🔒",
        "withdraw_success": "✅ **Withdrawal Sent!**\n\n{amount} TON sent to your wallet.\nTX will appear in ~30 seconds.",
        "withdraw_min": "⚠️ Minimum withdrawal: 0.05 TON\n\nYour balance: {balance} TON",
        "withdraw_no_wallet": "⚠️ Please send your TON wallet address first.\n\nExample: `EQB...` or `UQA...`",
        "lang_changed": "✅ Language changed to English",
        "referral_stats": "🎁 **Referral Program**\n\n**Your Link:**\n`{url}`\n\n**Commission:** 5%\n**Referrals:** {count}\n**Earnings:** {earnings} TON\n**Withdrawn:** {withdrawn} TON\n**Available:** {available} TON\n\n💡 Use /withdraw to cash out!",
        "status_active": "✅ **Subscription Active**\n\nExpires: {expiry}\n\nUnlimited seals enabled!",
        "status_inactive": "❌ **No Active Subscription**\n\nCredits: {credits} TON\n\nUse /subscribe for unlimited!",
        "photo_prompt": "📸 **Nice screenshot!**\n\n1 Star to seal it on TON forever.",
        "file_prompt": "📄 **Got your file!**\n\n1 Star to seal it on TON forever.",
    },
    "ru": {
        "welcome": "🔐 **NotaryTON** - Блокчейн Нотаризация\n\nПечать контрактов, файлов и скриншотов на TON навсегда.\n\n**Команды:**\n/notarize - Запечатать контракт\n/status - Проверить подписку\n/subscribe - Безлимит\n/referral - Заработай 5%\n/withdraw - Вывести заработок\n/lang - Сменить язык",
        "no_sub": "⚠️ **Требуется оплата**\n\n1 Звезда или 0.015 TON для печати.",
        "sealed": "✅ **ЗАПЕЧАТАНО НА TON!**\n\nХеш: `{hash}`\n\n🔗 Проверить: {url}\n\nДоказательство сохранено навсегда! 🔒",
        "withdraw_success": "✅ **Вывод отправлен!**\n\n{amount} TON отправлено на ваш кошелек.\nTX появится через ~30 секунд.",
        "withdraw_min": "⚠️ Минимальный вывод: 0.05 TON\n\nВаш баланс: {balance} TON",
        "withdraw_no_wallet": "⚠️ Сначала отправьте адрес вашего TON кошелька.\n\nПример: `EQB...` или `UQA...`",
        "lang_changed": "✅ Язык изменен на Русский",
        "referral_stats": "🎁 **Реферальная Программа**\n\n**Ваша ссылка:**\n`{url}`\n\n**Комиссия:** 5%\n**Рефералы:** {count}\n**Заработано:** {earnings} TON\n**Выведено:** {withdrawn} TON\n**Доступно:** {available} TON\n\n💡 Используйте /withdraw для вывода!",
        "status_active": "✅ **Подписка Активна**\n\nИстекает: {expiry}\n\nБезлимитные печати включены!",
        "status_inactive": "❌ **Нет Активной Подписки**\n\nКредиты: {credits} TON\n\nИспользуйте /subscribe для безлимита!",
        "photo_prompt": "📸 **Отличный скриншот!**\n\n1 Звезда чтобы запечатать на TON навсегда.",
        "file_prompt": "📄 **Файл получен!**\n\n1 Звезда чтобы запечатать на TON навсегда.",
    },
    "zh": {
        "welcome": "🔐 **NotaryTON** - 区块链公证\n\n在TON上永久封存合约、文件和截图。\n\n**命令:**\n/notarize - 封存合约\n/status - 查看订阅\n/subscribe - 无限封存\n/referral - 赚取5%佣金\n/withdraw - 提取收益\n/lang - 更改语言",
        "no_sub": "⚠️ **需要付款**\n\n1星或0.015 TON来封存。",
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
    }
}

# User language cache (user_id -> lang_code)
user_languages = {}

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

async def send_ton_transaction(comment: str, amount_ton: float = 0.005):
    """Send TON transaction with comment (notarization proof)"""
    client = None
    try:
        client = LiteBalancer.from_mainnet_config(trust_level=1)
        await client.start_up()

        mnemonics = TON_WALLET_SECRET.split()
        wallet = await WalletV4R2.from_mnemonic(provider=client, mnemonics=mnemonics)

        # Send transaction to self with comment (proof stored on-chain)
        result = await wallet.transfer(
            destination=SERVICE_TON_WALLET,
            amount=int(amount_ton * 1e9),  # Convert to nanotons
            body=comment
        )

        print(f"✅ Notarization transaction sent with comment: {comment}")
        return result
    except Exception as e:
        print(f"❌ Error sending transaction: {e}")
        print(f"   Make sure wallet has sufficient TON balance")
        raise
    finally:
        if client:
            await client.close_all()

async def send_payout_transaction(destination: str, amount_ton: float, memo: str = "NotaryTON Payout"):
    """Send TON payout to user wallet"""
    client = None
    try:
        client = LiteBalancer.from_mainnet_config(trust_level=1)
        await client.start_up()

        mnemonics = TON_WALLET_SECRET.split()
        wallet = await WalletV4R2.from_mnemonic(provider=client, mnemonics=mnemonics)

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

                        # Check if it's a single notarization payment (0.015 TON)
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
        "💰 ⭐ 1 Star per seal | 20 Stars/mo unlimited"
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
    """Show TON payment instructions"""
    user_id = callback.from_user.id
    await callback.answer()

    await callback.message.answer(
        f"💎 **Pay with TON**\n\n"
        f"Send **0.3 TON** to:\n"
        f"`{SERVICE_TON_WALLET}`\n\n"
        f"**IMPORTANT:** Include this memo:\n"
        f"`{user_id}`\n\n"
        f"Your subscription activates automatically within 1 minute!",
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
    """Show TON payment instructions for single notarization"""
    user_id = callback.from_user.id
    await callback.answer()

    await callback.message.answer(
        f"💎 **Pay with TON**\n\n"
        f"Send **0.015 TON** to:\n"
        f"`{SERVICE_TON_WALLET}`\n\n"
        f"**IMPORTANT:** Include this memo:\n"
        f"`{user_id}`\n\n"
        f"Your credit will be added automatically within 1 minute!\n"
        f"Then use /notarize again.",
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

        await message.answer(
            "✅ **Subscription Activated!**\n\n"
            "You now have **unlimited notarizations** for 30 days!\n\n"
            "Use /notarize to seal your first contract.\n"
            "Use /api to get API access for integrations.\n\n"
            "🔒 Thank you for supporting NotaryTON!",
            parse_mode="Markdown"
        )

    elif payload.startswith("single_"):
        # Add single notarization credit
        await db.users.ensure_exists(user_id)
        await db.users.add_payment(user_id, TON_SINGLE_SEAL)

        await message.answer(
            "✅ **Payment Received!**\n\n"
            "You can now notarize **one contract or file**.\n\n"
            "Send me:\n"
            "• A contract address (EQ...)\n"
            "• Or upload a file\n\n"
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

    stats = {
        "total_paid": user.total_paid if user else 0,
        "referral_earnings": user.referral_earnings if user else 0,
        "notarizations": notarization_count
    }

    status_msg = "✅ **Active Subscription**\n\n" if has_sub else "❌ **No Active Subscription**\n\n"
    status_msg += f"📊 **Your Stats:**\n"
    status_msg += f"• Notarizations: {stats['notarizations']}\n"
    status_msg += f"• Total Spent: {stats['total_paid']:.4f} TON\n"

    if stats['referral_earnings'] > 0:
        status_msg += f"• Referral Earnings: {stats['referral_earnings']:.4f} TON\n"

    if not has_sub:
        status_msg += "\nUse /subscribe to get unlimited access!"
    
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

    await message.answer(
        f"🎁 **Referral Program**\n\n"
        f"**Your Referral Link:**\n"
        f"`{referral_url}`\n\n"
        f"**Commission:** 5% of referrals' payments\n"
        f"**Your Stats:**\n"
        f"• Referrals: {referral_stats['count']}\n"
        f"• Total Earnings: {referral_stats['earnings']:.4f} TON\n"
        f"• Withdrawn: {referral_stats['withdrawn']:.4f} TON\n"
        f"• Available: {referral_stats['available']:.4f} TON\n\n"
        f"💡 Use /withdraw to cash out!",
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
            [types.InlineKeyboardButton(text="⭐ Pay 1 Star", callback_data="pay_stars_single")],
            [types.InlineKeyboardButton(text="💎 Pay 0.015 TON", callback_data="pay_ton_single")],
            [types.InlineKeyboardButton(text="🚀 Unlimited (20 Stars/mo)", callback_data="pay_stars_sub")]
        ])

        await message.answer(
            "⚠️ **Payment Required**\n\n"
            "Choose how to pay for this notarization:\n\n"
            "⭐ **1 Star** - Quick & easy\n"
            "💎 **0.015 TON** - Native crypto\n"
            "🚀 **20 Stars/mo** - Unlimited access\n",
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
        [types.InlineKeyboardButton(text="⭐ Pay 1 Star", callback_data="pay_stars_single")],
        [types.InlineKeyboardButton(text="💎 Pay 0.015 TON", callback_data="pay_ton_single")],
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
                f"⚠️ Send 0.015 TON to `{SERVICE_TON_WALLET}` (memo: `{user_id}`) to notarize!\n"
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
            "⭐ **1 Star** - Quick & easy\n"
            "💎 **0.015 TON** - Native crypto\n"
            "🚀 **20 Stars/mo** - Unlimited access\n",
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
            "1 Star to seal it on TON forever.\n"
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
            "**3.** Get on-chain seal + verification link\n\n"
            "👇 **Send something to seal it forever**"
            f"{free_seal_msg}"
        )

        # Add helpful buttons
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🚀 Go Unlimited (15 ⭐/mo)", callback_data="ms_pay_stars_sub")]
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
        await callback.message.answer(
            f"💎 **Pay with TON**\n\n"
            f"Send **0.015 TON** to:\n"
            f"`{SERVICE_TON_WALLET}`\n\n"
            f"**Memo:** `{user_id}`\n\n"
            f"Then send your file again. We'll seal it. 🐸",
            parse_mode="Markdown"
        )

    @memeseal_dp.pre_checkout_query()
    async def memeseal_pre_checkout(pre_checkout_query: PreCheckoutQuery):
        await pre_checkout_query.answer(ok=True)

    @memeseal_dp.message(F.successful_payment)
    async def memeseal_payment_success(message: types.Message):
        user_id = message.from_user.id
        payment = message.successful_payment
        payload = payment.invoice_payload

        if "sub" in payload:
            await add_subscription(user_id, months=1)
            await message.answer(
                "⚡ **YOU'RE UNLIMITED NOW** ⚡\n\n"
                "30 days of infinite seals.\n"
                "Send me anything - files, screenshots, contracts.\n"
                "I'll seal them all.\n\n"
                "LFG 🐸🚀",
                parse_mode="Markdown"
            )
        else:
            await db.users.ensure_exists(user_id)
            await db.users.add_payment(user_id, TON_SINGLE_SEAL)
            await message.answer(
                "✅ **PAID**\n\n"
                "Now send me what you want sealed.\n"
                "File, screenshot, whatever.\n\n"
                "🐸",
                parse_mode="Markdown"
            )

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

    @memeseal_dp.message(F.document)
    async def memeseal_handle_document(message: types.Message):
        user_id = message.from_user.id
        has_sub = await get_user_subscription(user_id)

        has_credit = False
        if not has_sub:
            total_paid = await db.users.get_total_paid(user_id)
            if total_paid >= TON_SINGLE_SEAL:
                has_credit = True

        if not has_sub and not has_credit:
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="⭐ Pay 1 Star & Seal Now", callback_data="ms_pay_stars_single")],
                [types.InlineKeyboardButton(text="💎 Pay 0.015 TON instead", callback_data="ms_pay_ton_single")],
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
        has_sub = await get_user_subscription(user_id)

        has_credit = False
        if not has_sub:
            total_paid = await db.users.get_total_paid(user_id)
            if total_paid >= TON_SINGLE_SEAL:
                has_credit = True

        if not has_sub and not has_credit:
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="⭐ Pay 1 Star & Seal Now", callback_data="ms_pay_stars_single")],
                [types.InlineKeyboardButton(text="💎 Pay 0.015 TON instead", callback_data="ms_pay_ton_single")],
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

@app.get("/health")
@app.head("/health")
async def health_check():
    """Health check endpoint - supports both GET and HEAD"""
    return {"status": "running", "bot": "NotaryTON", "version": "2.0-memecoin"}


@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    favicon_path = "static/favicon.ico"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    # Fallback to logo.png
    return FileResponse("static/logo.png", media_type="image/png")


@app.get("/verify", response_class=HTMLResponse)
async def verify_page():
    """Public verification page - check any seal"""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verify a Seal - MemeSeal TON</title>
    <meta name="description" content="Verify any seal on TON blockchain. Paste a hash to check if it's been sealed.">

    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://notaryton.com/verify">
    <meta property="og:title" content="Verify a Seal - MemeSeal TON">
    <meta property="og:description" content="Verify any seal on TON blockchain. Paste a hash to check if it's been sealed.">
    <meta property="og:image" content="https://notaryton.com/static/memeseal_icon.png">
    <meta property="og:site_name" content="MemeSeal TON">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="Verify a Seal - MemeSeal TON">
    <meta name="twitter:description" content="Check if any hash has been sealed on TON blockchain.">

    <!-- Favicon -->
    <link rel="icon" type="image/png" href="/static/memeseal_icon.png">
    <link rel="apple-touch-icon" href="/static/memeseal_icon.png">

    <!-- Analytics -->
    <script defer src="https://cloud.umami.is/script.js" data-website-id="5d783ccd-fca7-4957-ad7e-06cc2814da83"></script>

    <style>
        @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Space+Mono:wght@400;700&display=swap');
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Space Mono', monospace;
            background: #0a0a0f;
            color: #00ff88;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 600px;
            width: 100%;
            text-align: center;
        }}
        h1 {{
            font-family: 'Press Start 2P', cursive;
            font-size: 1.5rem;
            color: #00ff88;
            text-shadow: 0 0 20px #00ff88;
            margin-bottom: 10px;
        }}
        .subtitle {{
            color: #666;
            margin-bottom: 40px;
        }}
        .search-box {{
            background: #111;
            border: 2px solid #00ff8844;
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 30px;
        }}
        input[type="text"] {{
            width: 100%;
            background: #000;
            border: 1px solid #00ff8844;
            border-radius: 8px;
            padding: 15px;
            font-family: 'Space Mono', monospace;
            font-size: 0.9rem;
            color: #00ff88;
            margin-bottom: 15px;
        }}
        input[type="text"]:focus {{
            outline: none;
            border-color: #00ff88;
            box-shadow: 0 0 20px rgba(0,255,136,0.3);
        }}
        input[type="text"]::placeholder {{
            color: #444;
        }}
        button {{
            background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
            color: #000;
            border: none;
            padding: 15px 40px;
            border-radius: 8px;
            font-family: 'Press Start 2P', cursive;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.3s;
        }}
        button:hover {{
            transform: scale(1.05);
            box-shadow: 0 0 30px rgba(0,255,136,0.5);
        }}
        #result {{
            background: #111;
            border: 2px solid #222;
            border-radius: 16px;
            padding: 30px;
            text-align: left;
            display: none;
        }}
        #result.show {{ display: block; }}
        #result.verified {{ border-color: #00ff88; }}
        #result.not-found {{ border-color: #ff4444; }}
        .result-header {{
            font-family: 'Press Start 2P', cursive;
            font-size: 1rem;
            margin-bottom: 20px;
        }}
        .verified .result-header {{ color: #00ff88; }}
        .not-found .result-header {{ color: #ff4444; }}
        .result-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #222;
        }}
        .result-row:last-child {{ border-bottom: none; }}
        .result-label {{ color: #666; }}
        .result-value {{
            color: #00ff88;
            word-break: break-all;
            text-align: right;
            max-width: 60%;
        }}
        .cta-link {{
            display: inline-block;
            margin-top: 30px;
            color: #00ff88;
            text-decoration: none;
            border: 1px solid #00ff88;
            padding: 10px 20px;
            border-radius: 8px;
            transition: all 0.3s;
        }}
        .cta-link:hover {{
            background: #00ff8822;
        }}
        .logo {{
            width: 80px;
            margin-bottom: 20px;
        }}
        .loading {{
            color: #666;
            animation: pulse 1s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <img src="/static/memeseal_icon.png" alt="MemeSeal" class="logo">
        <h1>🔍 VERIFY A SEAL</h1>
        <p class="subtitle">Paste any hash to check if it's been sealed on TON</p>

        <div class="search-box">
            <input type="text" id="hashInput" placeholder="Paste hash here (e.g., a1b2c3d4e5f6...)" />
            <button onclick="verifyHash()">VERIFY</button>
        </div>

        <div id="result"></div>

        <a href="https://t.me/{MEMESEAL_USERNAME}" class="cta-link">🐸 Seal something yourself</a>
    </div>

    <script>
        async function verifyHash() {{
            const hash = document.getElementById('hashInput').value.trim();
            const resultDiv = document.getElementById('result');

            if (!hash) {{
                alert('Please enter a hash to verify');
                return;
            }}

            resultDiv.className = 'show';
            resultDiv.innerHTML = '<p class="loading">Checking blockchain...</p>';

            try {{
                const response = await fetch('/api/v1/verify/' + encodeURIComponent(hash));
                const data = await response.json();

                if (data.verified) {{
                    resultDiv.className = 'show verified';
                    resultDiv.innerHTML = `
                        <div class="result-header">✅ VERIFIED SEAL</div>
                        <div class="result-row">
                            <span class="result-label">Hash</span>
                            <span class="result-value">${{data.hash}}</span>
                        </div>
                        <div class="result-row">
                            <span class="result-label">Timestamp</span>
                            <span class="result-value">${{data.timestamp}}</span>
                        </div>
                        <div class="result-row">
                            <span class="result-label">Blockchain</span>
                            <span class="result-value">${{data.blockchain}}</span>
                        </div>
                        <div class="result-row">
                            <span class="result-label">Status</span>
                            <span class="result-value">Sealed Forever 🔒</span>
                        </div>
                    `;
                }} else {{
                    resultDiv.className = 'show not-found';
                    resultDiv.innerHTML = `
                        <div class="result-header">❌ NOT FOUND</div>
                        <p style="color: #888; margin-top: 10px;">
                            This hash hasn't been sealed yet.<br><br>
                            Want to seal it? <a href="https://t.me/{MEMESEAL_USERNAME}" style="color: #00ff88;">Use @{MEMESEAL_USERNAME}</a>
                        </p>
                    `;
                }}
            }} catch (error) {{
                resultDiv.className = 'show not-found';
                resultDiv.innerHTML = `
                    <div class="result-header">⚠️ ERROR</div>
                    <p style="color: #888;">Could not verify. Try again.</p>
                `;
            }}
        }}

        // Allow Enter key to verify
        document.getElementById('hashInput').addEventListener('keypress', function(e) {{
            if (e.key === 'Enter') verifyHash();
        }});
    </script>
</body>
</html>
"""

@app.get("/memeseal")
async def memeseal_redirect():
    """Redirect /memeseal to root for backwards compatibility"""
    return RedirectResponse(url="/", status_code=301)


@app.get("/whitepaper", response_class=HTMLResponse)
async def whitepaper():
    """FROGS FOREVER - The Vision"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FROGS FOREVER - MemeSeal Whitepaper</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Space Mono', monospace;
            background: #0a0a0f;
            color: #ccc;
            line-height: 1.8;
            padding: 40px 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        h1 {
            color: #00ff88;
            font-size: 2rem;
            margin-bottom: 10px;
            text-shadow: 0 0 20px #00ff88;
        }
        h2 {
            color: #00ff88;
            font-size: 1.3rem;
            margin: 40px 0 20px;
            border-bottom: 1px solid #00ff8844;
            padding-bottom: 10px;
        }
        h3 {
            color: #88ffbb;
            font-size: 1.1rem;
            margin: 25px 0 15px;
        }
        p {
            margin-bottom: 15px;
        }
        .tagline {
            color: #888;
            font-size: 1.1rem;
            margin-bottom: 30px;
        }
        ul, ol {
            margin-left: 25px;
            margin-bottom: 20px;
        }
        li {
            margin-bottom: 10px;
        }
        strong {
            color: #00ff88;
        }
        .highlight {
            background: #00ff8822;
            padding: 20px;
            border-radius: 10px;
            border-left: 4px solid #00ff88;
            margin: 20px 0;
        }
        a {
            color: #00ff88;
        }
        .footer {
            margin-top: 60px;
            text-align: center;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>MemeSeal TON ⚡🐸</h1>
        <p class="tagline"><strong>Proof or it didn't happen. Gamble or it didn't matter.</strong></p>

        <p>The on-chain notary that turns every screenshot, wallet flex, and political meltdown into a slot machine you actually want to feed.</p>

        <h2>1. Vision</h2>
        <p>MemeSeal is already stamping thousands of bags forever for 1 Star.</p>
        <p>But that's the trojan frog.</p>

        <div class="highlight">
            <p>The real game: every seal, every meme coin launch, every headline becomes fuel for a weekly lottery where someone gets a giant check delivered by a guy in a Pepe turtle suit while Robert Barnes announces it live.</p>
        </div>

        <p>Politics, NBA finals, Oscars—whatever real-world events drive live odds, frog puppets roast the candidates in a 7-minute cartoon, holders win life-changing TON, rake funds the next moonshot.</p>
        <p><strong>This isn't another meme coin. This is reality television you own—and sometimes the frog kisses you back.</strong></p>

        <h2>2. Problem</h2>
        <ul>
            <li>36,000 meme coins launch daily and die in 12 days because retention = zero</li>
            <li>Prediction markets are for boomers with Excel</li>
            <li>Telegram casinos feel like 2018 exit liquidity scams—no recurring dopamine, no reason to wake up</li>
            <li>Real gamblers (BC Lotto cards, Vegas whales, DraftKings addicts) stare at "TON" and think it's sushi</li>
        </ul>
        <p><strong>Nobody is giving them micro-hits every five minutes while the world burns.</strong></p>

        <h2>3. Solution – The Slot Machine Flywheel</h2>

        <h3>Phase 1 – LIVE RIGHT NOW</h3>
        <p>Send file/screenshot → pay 1 Star (~$0.02) → permanent TON hash + verification link</p>
        <p>Used for bags, launches, receipts, GTFO screenshots, everything.</p>

        <h3>Phase 2 – Post-grant (30-60 days)</h3>
        <ul>
            <li>Every single seal auto-enters the weekly lottery pool</li>
            <li>We mint event coins: $FROGTRUMP, $KAMALATOAD, $SUPERBOWLPEPE</li>
            <li>Price tracks Polymarket/Kalshi odds via oracle in real time</li>
            <li>5% rake on trades → 2% treasury, 3% burned forever</li>
            <li>Weekly live cartoon show (7 min): turtle host + frog puppets roast the week's scandals</li>
            <li>End of show → random wallet wins $5k–$250k+ in TON + physical giant check + Barnes calls them on stream</li>
        </ul>

        <h3>Phase 3 – Casino Mini-App</h3>
        <ul>
            <li>Slots, roulette, crash—but the symbols are the politicians you're already betting on</li>
            <li>Pay with Stars (credit card, zero KYC) or Bitcoin via Moonpay embed</li>
            <li>One ecosystem. One growing jackpot. One cult.</li>
        </ul>

        <h2>4. Tokenomics</h2>
        <p><strong>Fair launch, no presale, no VC bags:</strong></p>
        <ul>
            <li>Total supply: 1 billion $SEAL</li>
            <li>50% lottery + burn vault</li>
            <li>20% liquidity</li>
            <li>15% treasury (dev + marketing + turtle costumes)</li>
            <li>10% airdrops to early sealers</li>
            <li>5% Robert Barnes "Free Speech Defense Fund"</li>
        </ul>
        <p>Every transaction takes 2-5% rake → buys back $SEAL → half burned, half to lottery.</p>
        <p><strong>Deflation + infinite jackpot = price up only + stay forever.</strong></p>

        <h2>5. Roadmap</h2>
        <ul>
            <li><strong>Dec 2025</strong> → Grant submitted. Notary already printing.</li>
            <li><strong>Jan 2026</strong> → Lottery engine live. First test coin: Super Bowl. Casino MVP.</li>
            <li><strong>Feb 2026</strong> → Robert Barnes on-boarded. First political coins. Weekly cartoon show drops.</li>
            <li><strong>Q2 2026</strong> → 400+ midterm frog coins. Full casino suite. 100k DAU.</li>
            <li><strong>2027</strong> → Oscars frogs, Eurovision frogs, Olympic frogs. Physical checks delivered globally.</li>
        </ul>

        <h2>6. Why TON</h2>
        <ul>
            <li>Stars = credit card on-ramp, zero KYC, Apple/Google already did the dirty work</li>
            <li>Telegram native = viral coefficient on steroids</li>
            <li>Actually fast & cheap when Solana is choking</li>
            <li>We will onboard tens of thousands of real-world gamblers who think Bitcoin is the only crypto</li>
        </ul>
        <p><strong>Expected impact: 50k+ new TON wallets in 90 days, all addicted to frogs.</strong></p>

        <div class="highlight">
            <p>We're not asking for a grant to "build in public."</p>
            <p>We're asking for rocket fuel to turn the entire gambling world into frogs—and let the frogs pay us forever.</p>
        </div>

        <p>P.S. First lottery winner gets a real giant check signed by Robert Barnes and a 24k gold Pepe chain. We're not kidding.</p>

        <h2 style="text-align: center; margin-top: 60px;">Frogs Forever. 🐸</h2>
        <h2 style="text-align: center; color: #888;">Turtles Never Rug. 🐢</h2>
        <h2 style="text-align: center; color: #ff006e;">Let's fucking win. ⚡</h2>

        <div class="footer">
            <p><a href="/">← Back to MemeSeal</a></p>
            <p style="margin-top: 20px;">© 2025 MemeSeal TON</p>
        </div>
    </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def landing_page_memeseal():
    """MemeSeal TON - Main landing page - NUCLEAR VERSION"""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MemeSeal TON ⚡🐸 - Proof or it didn't happen</title>
    <meta name="description" content="Seal your bags before the rug. Instant on-chain proof on TON. Every seal feeds the weekly lottery pot.">

    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://notaryton.com/">
    <meta property="og:title" content="MemeSeal TON ⚡🐸 - Proof or it didn't happen">
    <meta property="og:description" content="Seal your bags. Feed the lottery. Win big. On-chain proof on TON.">
    <meta property="og:image" content="https://notaryton.com/static/memeseal_banner.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:site_name" content="MemeSeal TON">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:url" content="https://notaryton.com/">
    <meta name="twitter:title" content="MemeSeal TON ⚡🐸 - Proof or it didn't happen">
    <meta name="twitter:description" content="Seal your bags. Feed the lottery. Win big. Receipts or GTFO 🐸">
    <meta name="twitter:image" content="https://notaryton.com/static/memeseal_banner.png">

    <!-- Favicon -->
    <link rel="icon" type="image/png" href="/static/memeseal_icon.png">
    <link rel="apple-touch-icon" href="/static/memeseal_icon.png">

    <!-- Analytics -->
    <script defer src="https://cloud.umami.is/script.js" data-website-id="5d783ccd-fca7-4957-ad7e-06cc2814da83"></script>

    <style>
        @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Space+Mono:wght@400;700&display=swap');
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Space Mono', monospace;
            background: #0a0a0f;
            color: #00ff88;
            min-height: 100vh;
            overflow-x: hidden;
        }}

        /* HERO */
        .hero {{
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 40px 20px;
            text-align: center;
            background: radial-gradient(ellipse at center, #0d1f1a 0%, #0a0a0f 70%);
        }}
        .banner {{
            max-width: 800px;
            width: 100%;
            border-radius: 20px;
            margin-bottom: 30px;
            box-shadow: 0 0 60px rgba(0,255,136,0.3);
            border: 2px solid #00ff88;
        }}
        h1 {{
            font-family: 'Press Start 2P', cursive;
            font-size: 1.8rem;
            color: #00ff88;
            text-shadow: 0 0 20px #00ff88, 0 0 40px #00ff88;
            margin-bottom: 15px;
        }}
        .tagline {{
            font-size: 1.4rem;
            color: #88ffbb;
            margin-bottom: 10px;
            font-weight: bold;
        }}
        .subtagline {{
            font-size: 1rem;
            color: #666;
            margin-bottom: 30px;
            max-width: 500px;
        }}
        .cta {{
            display: inline-block;
            background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
            color: #000;
            padding: 20px 50px;
            border-radius: 50px;
            text-decoration: none;
            font-size: 1.1rem;
            font-weight: 700;
            font-family: 'Press Start 2P', cursive;
            transition: all 0.3s;
            box-shadow: 0 0 30px rgba(0,255,136,0.5);
            border: none;
            cursor: pointer;
        }}
        .cta:hover {{
            transform: scale(1.05);
            box-shadow: 0 0 50px rgba(0,255,136,0.8);
        }}
        .badge {{
            display: inline-block;
            background: #00ff8822;
            color: #00ff88;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.85rem;
            margin-top: 15px;
            border: 1px solid #00ff8844;
        }}

        /* LOTTERY BANNER */
        .lottery-banner {{
            background: linear-gradient(90deg, #ff006e, #8338ec, #3a86ff, #ff006e);
            background-size: 300% 100%;
            animation: gradient-shift 3s ease infinite;
            padding: 20px;
            margin-top: 30px;
            border-radius: 15px;
            max-width: 700px;
            width: 100%;
            border: 2px solid #fff;
            box-shadow: 0 0 40px rgba(255,0,110,0.5);
        }}
        @keyframes gradient-shift {{
            0% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
            100% {{ background-position: 0% 50%; }}
        }}
        .lottery-banner h3 {{
            font-family: 'Press Start 2P', cursive;
            font-size: 0.8rem;
            color: #fff;
            margin-bottom: 10px;
            animation: flash 1s infinite;
        }}
        @keyframes flash {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.7; }}
        }}
        .lottery-banner .pot {{
            font-family: 'Press Start 2P', cursive;
            font-size: 1.5rem;
            color: #ffff00;
            text-shadow: 0 0 20px #ffff00;
        }}
        .lottery-banner .sub {{
            color: #fff;
            font-size: 0.85rem;
            margin-top: 10px;
            opacity: 0.9;
        }}

        /* LOTTERY SCENE */
        .lottery-scene {{
            padding: 40px 20px;
            text-align: center;
            background: linear-gradient(180deg, #0a0a0f 0%, #0d0d15 100%);
        }}
        .scene-img {{
            max-width: 900px;
            width: 100%;
            border-radius: 20px;
            box-shadow: 0 0 60px rgba(0,255,136,0.3);
            border: 2px solid #00ff8844;
        }}
        .scene-caption {{
            color: #888;
            margin-top: 20px;
            font-size: 1.1rem;
            font-style: italic;
        }}

        /* FEATURES */
        .features {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 25px;
            max-width: 1000px;
            margin: 50px auto;
            padding: 0 20px;
        }}
        .feature {{
            background: linear-gradient(180deg, #111 0%, #0a0a0f 100%);
            border: 1px solid #00ff8833;
            padding: 30px;
            border-radius: 16px;
            text-align: left;
            transition: all 0.3s;
        }}
        .feature:hover {{
            border-color: #00ff88;
            box-shadow: 0 0 30px rgba(0,255,136,0.2);
            transform: translateY(-5px);
        }}
        .feature h3 {{
            font-size: 1.1rem;
            margin-bottom: 15px;
            color: #00ff88;
        }}
        .feature p {{
            color: #888;
            line-height: 1.6;
        }}

        /* PRICING */
        .pricing {{
            padding: 60px 20px;
            text-align: center;
            background: #080810;
        }}
        .pricing h2 {{
            font-family: 'Press Start 2P', cursive;
            font-size: 1.1rem;
            margin-bottom: 10px;
            color: #00ff88;
        }}
        .pricing-sub {{
            color: #666;
            margin-bottom: 40px;
            font-size: 0.9rem;
        }}
        .price-cards {{
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
        }}
        .price-card {{
            background: #111;
            border: 2px solid #222;
            border-radius: 20px;
            padding: 35px;
            width: 300px;
            transition: all 0.3s;
        }}
        .price-card:hover {{
            border-color: #00ff88;
            transform: translateY(-5px);
        }}
        .price-card.featured {{
            border-color: #00ff88;
            box-shadow: 0 0 40px rgba(0,255,136,0.3);
            position: relative;
        }}
        .price-card.featured::before {{
            content: "🔥 MOST POPULAR";
            position: absolute;
            top: -12px;
            left: 50%;
            transform: translateX(-50%);
            background: #00ff88;
            color: #000;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.7rem;
            font-weight: bold;
        }}
        .price-card h3 {{
            font-size: 1.2rem;
            margin-bottom: 15px;
            color: #fff;
        }}
        .price-card .price {{
            font-family: 'Press Start 2P', cursive;
            font-size: 1.4rem;
            color: #00ff88;
            margin-bottom: 10px;
        }}
        .price-card .price-alt {{
            color: #666;
            font-size: 0.9rem;
            margin-bottom: 20px;
        }}
        .price-card ul {{
            list-style: none;
            text-align: left;
        }}
        .price-card li {{
            padding: 10px 0;
            color: #888;
            border-bottom: 1px solid #222;
        }}
        .price-card li:before {{
            content: "✓ ";
            color: #00ff88;
        }}
        .price-card li:last-child {{
            border-bottom: none;
        }}

        /* CASINO SECTION */
        .casino-section {{
            padding: 80px 20px;
            text-align: center;
            background: linear-gradient(180deg, #0a0510 0%, #150520 50%, #0a0510 100%);
            border-top: 2px solid #ff006e33;
            border-bottom: 2px solid #ff006e33;
        }}
        .casino-section h2 {{
            font-family: 'Press Start 2P', cursive;
            font-size: 1rem;
            color: #ff006e;
            margin-bottom: 10px;
            text-shadow: 0 0 30px #ff006e;
        }}
        .casino-section .subtitle {{
            color: #8338ec;
            font-size: 1.1rem;
            margin-bottom: 40px;
        }}
        .casino-cards {{
            display: flex;
            justify-content: center;
            gap: 25px;
            flex-wrap: wrap;
            max-width: 1000px;
            margin: 0 auto 40px;
        }}
        .casino-card {{
            background: linear-gradient(180deg, #1a0a20 0%, #0d0510 100%);
            border: 2px solid #8338ec44;
            border-radius: 20px;
            padding: 30px;
            width: 300px;
            transition: all 0.3s;
        }}
        .casino-card:hover {{
            border-color: #ff006e;
            box-shadow: 0 0 40px rgba(255,0,110,0.3);
            transform: translateY(-5px);
        }}
        .casino-card h3 {{
            font-size: 1.1rem;
            color: #ff006e;
            margin-bottom: 15px;
        }}
        .casino-card p {{
            color: #999;
            line-height: 1.6;
            font-size: 0.9rem;
        }}
        .casino-card .emoji {{
            font-size: 2.5rem;
            margin-bottom: 15px;
        }}
        .casino-card .card-img {{
            width: 100%;
            border-radius: 12px;
            margin-bottom: 15px;
        }}
        .casino-hero-img {{
            max-width: 900px;
            width: 100%;
            border-radius: 20px;
            margin-bottom: 40px;
            box-shadow: 0 0 60px rgba(255,0,110,0.4);
            border: 2px solid #ff006e44;
        }}
        .launch-date {{
            display: inline-block;
            background: linear-gradient(90deg, #ff006e, #8338ec);
            color: #fff;
            padding: 12px 30px;
            border-radius: 30px;
            font-weight: bold;
            font-size: 0.9rem;
            margin-top: 20px;
        }}

        /* TESTIMONIALS */
        .testimonials {{
            padding: 60px 20px;
            background: #050508;
            text-align: center;
        }}
        .testimonials h2 {{
            font-family: 'Press Start 2P', cursive;
            font-size: 0.9rem;
            color: #00ff88;
            margin-bottom: 30px;
        }}
        .testimonial-strip {{
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
            max-width: 1000px;
            margin: 0 auto;
        }}
        .testimonial {{
            background: #0a0a0f;
            border: 1px solid #222;
            border-radius: 15px;
            padding: 25px;
            max-width: 320px;
            text-align: left;
        }}
        .testimonial p {{
            color: #888;
            font-style: italic;
            margin-bottom: 15px;
            line-height: 1.5;
        }}
        .testimonial .author {{
            color: #00ff88;
            font-size: 0.85rem;
        }}
        .testimonial .stars {{
            color: #ffcc00;
            margin-bottom: 10px;
        }}

        /* BARNES SECTION */
        .barnes-section {{
            padding: 50px 20px;
            text-align: center;
            background: linear-gradient(180deg, #0a0a0f 0%, #0a1010 100%);
        }}
        .barnes-section h3 {{
            font-size: 1rem;
            color: #666;
            margin-bottom: 10px;
        }}
        .barnes-section p {{
            color: #888;
            max-width: 500px;
            margin: 0 auto;
            font-size: 0.9rem;
        }}
        .barnes-section .coming {{
            color: #00ff88;
            margin-top: 15px;
            font-size: 0.85rem;
        }}
        .barnes-img {{
            max-width: 300px;
            width: 100%;
            border-radius: 50%;
            margin-bottom: 20px;
            box-shadow: 0 0 40px rgba(0,255,136,0.3);
            border: 3px solid #00ff8844;
        }}

        /* DEV SECTION */
        .dev-section {{
            padding: 60px 20px;
            text-align: center;
            background: linear-gradient(180deg, #0a0a0f 0%, #0d1510 100%);
        }}
        .dev-section h2 {{
            font-family: 'Press Start 2P', cursive;
            font-size: 1rem;
            color: #00ff88;
            margin-bottom: 20px;
        }}
        .dev-section p {{
            color: #888;
            max-width: 600px;
            margin: 0 auto 30px;
            line-height: 1.6;
        }}
        .code-block {{
            background: #000;
            border: 1px solid #00ff8833;
            border-radius: 10px;
            padding: 20px;
            max-width: 600px;
            margin: 0 auto;
            text-align: left;
            overflow-x: auto;
        }}
        .code-block code {{
            color: #00ff88;
            font-size: 0.85rem;
        }}

        /* FOOTER */
        footer {{
            background: #000;
            color: #444;
            padding: 50px 20px;
            text-align: center;
            border-top: 1px solid #111;
        }}
        footer a {{
            color: #00ff88;
            text-decoration: none;
            transition: color 0.3s;
        }}
        footer a:hover {{
            color: #88ffbb;
        }}
        .social-links {{
            display: flex;
            justify-content: center;
            gap: 20px;
            margin: 20px 0;
        }}
        .social-links a {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: #111;
            padding: 10px 20px;
            border-radius: 25px;
            border: 1px solid #222;
            transition: all 0.3s;
        }}
        .social-links a:hover {{
            border-color: #00ff88;
            background: #0a0a0f;
        }}

        /* ANIMATIONS */
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.7; }}
        }}
        .pulse {{ animation: pulse 2s infinite; }}

        /* MOBILE */
        @media (max-width: 768px) {{
            h1 {{ font-size: 1.3rem; }}
            .tagline {{ font-size: 1.1rem; }}
            .cta {{ padding: 15px 30px; font-size: 0.9rem; }}
            .lottery-banner h3 {{ font-size: 0.7rem; }}
            .lottery-banner .pot {{ font-size: 1.2rem; }}
            .banner {{ border-radius: 10px; }}
            .price-card {{ width: 100%; max-width: 350px; }}
            .casino-card {{ width: 100%; max-width: 350px; }}
            .testimonial {{ max-width: 100%; }}
        }}
    </style>
</head>
<body>
    <!-- HERO -->
    <div class="hero">
        <img src="/static/memeseal_banner.png" alt="MemeSeal TON - Master Stampway & The Frog" class="banner">
        <h1>MEMESEAL TON ⚡🐸</h1>
        <p class="tagline">Proof or it didn't happen.</p>
        <p class="subtagline">One tap = on-chain proof you were early. No more "bro trust me" screenshots. Every seal feeds the pot.</p>
        <a href="https://t.me/{MEMESEAL_USERNAME}" class="cta">START SEALING</a>
        <span class="badge">🔥 Cheaper than gas on ETH → 0.015 TON</span>

        <!-- LOTTERY BANNER -->
        <div class="lottery-banner">
            <h3>🎰 EVERY SEAL FEEDS THE WEEKLY LOTTERY POT 🎰</h3>
            <div class="pot">CURRENT POT: 0 TON</div>
            <p class="sub">Someone's getting a giant check delivered by a guy in a turtle suit. Might be you. 🐢</p>
        </div>
    </div>

    <!-- LOTTERY WIN SCENE -->
    <div class="lottery-scene">
        <img src="/static/lottery_win.png" alt="Frog Jackpot Winner" class="scene-img">
        <p class="scene-caption">This could be you. $420,069 TON. Giant check. Turtle suit guy. Confetti.</p>
    </div>

    <!-- FEATURES -->
    <div class="features">
        <div class="feature">
            <h3>⚡ Instant Hash on TON</h3>
            <p>Under 1 second. Your screenshot, wallet connect, voice note - whatever - gets sealed on-chain forever. Master Stampway approves.</p>
        </div>
        <div class="feature">
            <h3>🔗 Permanent Verification</h3>
            <p>Anyone can check. No login, no KYC, no cope. Just paste the hash and see the proof. Even your ex can verify you weren't lying.</p>
        </div>
        <div class="feature">
            <h3>🤖 Auto-Seal in Groups</h3>
            <p>Add @{MEMESEAL_USERNAME} to your raid channel. Every coin drop = auto-sealed with timestamp. Dev can't deny fair launch.</p>
        </div>
        <div class="feature">
            <h3>💰 5% Referral Forever</h3>
            <p>Plug it into your pump clone, DEX, sniper bot. When your users seal through your link → you eat forever. Passive income szn.</p>
        </div>
    </div>

    <!-- PRICING -->
    <div class="pricing">
        <h2>DEGEN PRICING</h2>
        <p class="pricing-sub">no subscription bullshit unless you want it | every payment feeds the lottery</p>
        <div class="price-cards">
            <div class="price-card">
                <h3>Pay As You Go</h3>
                <div class="price">1 ⭐ STAR</div>
                <div class="price-alt">or 0.015 TON (~$0.05)</div>
                <ul>
                    <li>Single seal</li>
                    <li>Instant on-chain proof</li>
                    <li>Permanent verify link</li>
                    <li>1 lottery ticket per seal</li>
                    <li>Perfect for 47 coins before breakfast</li>
                </ul>
            </div>
            <div class="price-card featured">
                <h3>Unlimited Monthly</h3>
                <div class="price">20 ⭐ STARS</div>
                <div class="price-alt">or 0.3 TON (~$1.00)</div>
                <ul>
                    <li>Unlimited seals</li>
                    <li>API access included</li>
                    <li>Batch operations</li>
                    <li>20 lottery tickets/month</li>
                    <li>For real cookers who launch daily</li>
                </ul>
            </div>
        </div>
    </div>

    <!-- CASINO SECTION -->
    <div class="casino-section">
        <h2>🎰 COMING NEXT: THE FROG CASINO YOU'LL NEVER LEAVE 🎰</h2>
        <p class="subtitle">Master Stampway's grand vision. The frog gambles. You win.</p>

        <img src="/static/casino_interior.png" alt="Frog Casino Interior" class="casino-hero-img">

        <div class="casino-cards">
            <div class="casino-card">
                <div class="emoji">📈</div>
                <h3>Event Coins</h3>
                <p>$FROGTRUMP price tracks real election odds. $FROGWEATHER tracks tomorrow's temp. Rake feeds the pot. Bet on reality.</p>
            </div>
            <div class="casino-card">
                <img src="/static/weekly_show.png" alt="Weekly Live Show" class="card-img">
                <h3>Weekly Live Show</h3>
                <p>Puppet frogs roast the news, then we draw the lottery winner on stream. Degen entertainment meets real money.</p>
            </div>
            <div class="casino-card">
                <div class="emoji">🎰</div>
                <h3>Politician Slots</h3>
                <p>Slots where politicians are the reels. Trump hair = 100x wild. Biden stumble = free spin. Nancy = insider multiplier.</p>
            </div>
        </div>

        <div class="launch-date">🚀 LAUNCHING Q1 2026 | EARLY SEALERS GET PRIORITY ACCESS + FREE SPINS</div>
    </div>

    <!-- TESTIMONIALS -->
    <div class="testimonials">
        <h2>WHAT SEALERS ARE SAYING</h2>
        <div class="testimonial-strip">
            <div class="testimonial">
                <div class="stars">⭐⭐⭐⭐⭐</div>
                <p>"Sealed my bag at 4k MC. Won the lottery at 69M MC. Master Stampway called me personally. Life changing."</p>
                <span class="author">— @whale_anon</span>
            </div>
            <div class="testimonial">
                <div class="stars">⭐⭐⭐⭐⭐</div>
                <p>"Finally proof I was early. My wife's boyfriend is impressed."</p>
                <span class="author">— @degen_dad_42</span>
            </div>
            <div class="testimonial">
                <div class="stars">⭐⭐⭐⭐⭐</div>
                <p>"Integrated the API into my pump.fun clone. 5% kickback is printing. The turtle knows."</p>
                <span class="author">— @cooker_supreme</span>
            </div>
        </div>
    </div>

    <!-- BARNES SECTION -->
    <div class="barnes-section">
        <img src="/static/barnes_frog.png" alt="Robert Barnes Frog" class="barnes-img">
        <h3>⚖️ LEGAL GODFATHER INCOMING</h3>
        <p>Robert Barnes joining soon. Political event coins vetted by the man who bets on elections for fun. The lawyer the establishment fears.</p>
        <p class="coming">Gavel + lottery ticket + TON blockchain = inevitable</p>
    </div>

    <!-- DEV SECTION -->
    <div class="dev-section">
        <h2>DEVELOPERS / COOKERS</h2>
        <p>Public REST API + 5% referral kickback. Use this to auto-seal every launch on your Pump.fun clone → feed our lottery → we all win.</p>
        <div class="code-block">
            <code>
POST /api/v1/notarize<br>
{{<br>
&nbsp;&nbsp;"api_key": "your_telegram_id",<br>
&nbsp;&nbsp;"contract_address": "EQ...",<br>
&nbsp;&nbsp;"metadata": {{"coin": "FROG420"}}<br>
}}<br><br>
// Every API seal = lottery ticket for your users<br>
// 5% of their payment = yours forever
            </code>
        </div>
        <a href="/docs" class="badge" style="margin-top: 30px; text-decoration: none;">📚 Full API Docs</a>
    </div>

    <!-- FOOTER -->
    <footer>
        <p style="font-size: 1rem; color: #666; margin-bottom: 20px;">Powered by TON | Built for degens | Master Stampway never rugs 🐢</p>

        <div class="social-links">
            <a href="https://t.me/{MEMESEAL_USERNAME}">🤖 Bot</a>
            <a href="https://t.me/MemeSealTON">📢 Channel</a>
            <a href="https://x.com/MemeSealTON">𝕏 Twitter</a>
            <a href="/whitepaper">📄 Whitepaper</a>
        </div>

        <p style="margin-top: 20px;">
            <a href="https://t.me/{MEMESEAL_USERNAME}">Start Sealing</a> |
            <a href="https://t.me/JPandaJamez">Support</a> |
            <a href="/verify">Verify a Seal</a>
        </p>

        <p style="margin-top: 25px; font-size: 0.75rem; color: #333;">
            © 2025 MemeSeal TON – receipts or GTFO 🐸<br>
            <span style="color: #222;">NFA. DYOR. Turtles all the way down.</span>
        </p>
    </footer>
</body>
</html>
"""

@app.get("/notaryton", response_class=HTMLResponse)
async def landing_page_legacy():
    """Legacy NotaryTON landing page"""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NotaryTON - Blockchain Notarization on TON</title>
    <meta name="description" content="Seal any file on TON blockchain. Instant. Immutable. Forever. Starting at 1 Star or 0.015 TON.">

    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://notaryton.com/">
    <meta property="og:title" content="NotaryTON - Blockchain Notarization on TON">
    <meta property="og:description" content="Seal any file on TON blockchain. Instant. Immutable. Forever. Starting at 1 Star or 0.015 TON.">
    <meta property="og:image" content="https://notaryton.com/static/logo.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:site_name" content="NotaryTON">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:url" content="https://notaryton.com/">
    <meta name="twitter:title" content="NotaryTON - Blockchain Notarization on TON">
    <meta name="twitter:description" content="Seal any file on TON blockchain. Instant. Immutable. Forever.">
    <meta name="twitter:image" content="https://notaryton.com/static/logo.png">

    <!-- Favicon -->
    <link rel="icon" type="image/png" href="/static/logo.png">
    <link rel="apple-touch-icon" href="/static/logo.png">

    <!-- Analytics -->
    <script defer src="https://cloud.umami.is/script.js" data-website-id="5d783ccd-fca7-4957-ad7e-06cc2814da83"></script>
    <!-- End Analytics -->

    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(180deg, #f0f4f8 0%, #d9e2ec 100%);
            color: #1a1a2e;
            min-height: 100vh;
        }}
        .hero {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 60px 20px;
            text-align: center;
        }}
        .logo-img {{
            width: 280px;
            height: auto;
            margin-bottom: 20px;
            filter: drop-shadow(0 10px 30px rgba(0,100,200,0.2));
        }}
        h1 {{
            font-size: 2.8rem;
            margin-bottom: 15px;
            color: #0a4d8c;
        }}
        .tagline {{
            font-size: 1.4rem;
            color: #555;
            margin-bottom: 40px;
            max-width: 500px;
        }}
        .features {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 25px;
            max-width: 900px;
            margin: 0 auto 50px;
            padding: 0 20px;
        }}
        .feature {{
            background: white;
            padding: 25px;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            text-align: left;
        }}
        .feature h3 {{
            font-size: 1.2rem;
            margin-bottom: 10px;
            color: #0a4d8c;
        }}
        .feature p {{
            color: #666;
            line-height: 1.5;
        }}
        .cta-section {{
            background: linear-gradient(135deg, #0a4d8c 0%, #1a7fd4 100%);
            padding: 60px 20px;
            text-align: center;
        }}
        .cta-section h2 {{
            color: white;
            font-size: 2rem;
            margin-bottom: 20px;
        }}
        .cta-section p {{
            color: rgba(255,255,255,0.9);
            font-size: 1.2rem;
            margin-bottom: 30px;
        }}
        .cta {{
            display: inline-block;
            background: white;
            color: #0a4d8c;
            padding: 18px 50px;
            border-radius: 50px;
            text-decoration: none;
            font-size: 1.2rem;
            font-weight: 700;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .cta:hover {{
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.2);
        }}
        .pricing {{
            padding: 60px 20px;
            text-align: center;
            background: white;
        }}
        .pricing h2 {{
            font-size: 2rem;
            margin-bottom: 40px;
            color: #0a4d8c;
        }}
        .price-cards {{
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
        }}
        .price-card {{
            background: #f8fafc;
            border: 2px solid #e2e8f0;
            border-radius: 20px;
            padding: 35px;
            width: 280px;
            transition: transform 0.2s, border-color 0.2s;
        }}
        .price-card:hover {{
            transform: translateY(-5px);
            border-color: #0a4d8c;
        }}
        .price-card h3 {{
            font-size: 1.3rem;
            margin-bottom: 15px;
            color: #333;
        }}
        .price-card .price {{
            font-size: 2.5rem;
            font-weight: 700;
            color: #0a4d8c;
            margin-bottom: 15px;
        }}
        .price-card .price small {{
            font-size: 1rem;
            color: #888;
        }}
        .price-card ul {{
            list-style: none;
            text-align: left;
            margin-top: 20px;
        }}
        .price-card li {{
            padding: 8px 0;
            color: #555;
        }}
        .price-card li:before {{
            content: "✓ ";
            color: #22c55e;
            font-weight: bold;
        }}
        footer {{
            background: #1a1a2e;
            color: #888;
            padding: 40px 20px;
            text-align: center;
        }}
        footer a {{
            color: #00d4ff;
            text-decoration: none;
        }}
        .api-badge {{
            display: inline-block;
            background: #e0f2fe;
            color: #0369a1;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9rem;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="hero">
        <img src="/static/logo.png" alt="NotaryTON Logo" class="logo-img">
        <h1>NotaryTON</h1>
        <p class="tagline">Seal any file on TON blockchain. Instant. Immutable. Forever.</p>
        <a href="https://t.me/{BOT_USERNAME}" class="cta">Start Notarizing</a>
        <span class="api-badge">Public API Available</span>
    </div>

    <div class="features">
        <div class="feature">
            <h3>Instant Blockchain Proof</h3>
            <p>Get immutable on-chain proof in seconds. Your files are hashed and sealed on TON forever.</p>
        </div>
        <div class="feature">
            <h3>Auto-Notarize in Groups</h3>
            <p>Add the bot to your Telegram group. Every memecoin launch gets automatically notarized.</p>
        </div>
        <div class="feature">
            <h3>Public Verification</h3>
            <p>Anyone can verify a notarization. No account needed. Just paste the hash.</p>
        </div>
        <div class="feature">
            <h3>Developer API</h3>
            <p>Integrate notarization into your dApp, DEX, or deploy bot with our simple REST API.</p>
        </div>
    </div>

    <div class="pricing">
        <h2>Simple Pricing</h2>
        <div class="price-cards">
            <div class="price-card">
                <h3>Pay As You Go</h3>
                <div class="price">1 Star <small>or 0.015 TON</small></div>
                <ul>
                    <li>Single notarization</li>
                    <li>Instant on-chain proof</li>
                    <li>Permanent verification URL</li>
                    <li>Works with any file</li>
                </ul>
            </div>
            <div class="price-card" style="border-color: #0a4d8c;">
                <h3>Monthly Unlimited</h3>
                <div class="price">20 Stars <small>or 0.3 TON</small></div>
                <ul>
                    <li>Unlimited notarizations</li>
                    <li>API access included</li>
                    <li>Batch operations</li>
                    <li>Priority support</li>
                </ul>
            </div>
        </div>
    </div>

    <div class="cta-section">
        <h2>Ready to Seal Your First File?</h2>
        <p>Join thousands of projects using NotaryTON for blockchain-verified proof.</p>
        <a href="https://t.me/{BOT_USERNAME}" class="cta">Open in Telegram</a>
    </div>

    <footer>
        <p>Powered by TON Blockchain | <a href="https://t.me/JPandaJamez">Support</a> | <a href="/verify">Verify a Hash</a></p>
        <p style="margin-top: 15px; font-size: 0.85rem;">© 2025 NotaryTON. All rights reserved.</p>
    </footer>
</body>
</html>
"""

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

@app.get("/stats")
async def stats():
    """Get bot statistics (JSON API)"""
    total_users = await db.users.count()
    total_notarizations = await db.notarizations.count()

    return {
        "total_users": total_users,
        "total_notarizations": total_notarizations
    }

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
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

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NotaryTON Dashboard</title>
    <script src="https://cloud.umami.is/script.js" data-website-id="b0430a5c-a5f9-4b36-9498-5cd9eb662403" defer></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{
            text-align: center;
            font-size: 2.5rem;
            margin-bottom: 30px;
            background: linear-gradient(90deg, #00d4ff, #0099ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 24px;
            text-align: center;
            backdrop-filter: blur(10px);
            transition: transform 0.3s, box-shadow 0.3s;
        }}
        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 40px rgba(0,212,255,0.2);
        }}
        .stat-value {{
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .stat-label {{
            color: #888;
            font-size: 0.9rem;
            margin-top: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .section {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
        }}
        .section h2 {{
            font-size: 1.3rem;
            margin-bottom: 16px;
            color: #00d4ff;
        }}
        .table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .table th, .table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .table th {{ color: #888; font-weight: 500; }}
        .hash {{ font-family: monospace; color: #00ff88; font-size: 0.85rem; }}
        .badge {{
            background: linear-gradient(90deg, #00d4ff, #0099ff);
            color: #000;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            color: #666;
            margin-top: 40px;
            padding: 20px;
        }}
        .footer a {{ color: #00d4ff; text-decoration: none; }}
        @media (max-width: 600px) {{
            .stat-value {{ font-size: 1.8rem; }}
            h1 {{ font-size: 1.8rem; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔐 NotaryTON Dashboard</h1>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{total_users:,}</div>
                <div class="stat-label">Total Users</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_notarizations:,}</div>
                <div class="stat-label">Total Seals</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{notarizations_24h:,}</div>
                <div class="stat-label">Seals (24h)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{users_24h:,}</div>
                <div class="stat-label">New Users (24h)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_revenue:.2f}</div>
                <div class="stat-label">Revenue (TON)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_referrals:,}</div>
                <div class="stat-label">Referrals</div>
            </div>
        </div>

        <div class="section">
            <h2>🏆 Top Referrers</h2>
            <table class="table">
                <tr><th>User ID</th><th>Referrals</th><th>Earnings</th></tr>
                {"".join(f'<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]:.4f} TON</td></tr>' for r in top_referrers) if top_referrers else '<tr><td colspan="3" style="color:#666">No referrers yet</td></tr>'}
            </table>
        </div>

        <div class="section">
            <h2>⚡ Recent Seals</h2>
            <table class="table">
                <tr><th>Hash</th><th>Time</th></tr>
                {"".join(f'<tr><td class="hash">{s[0][:16]}...</td><td>{s[1]}</td></tr>' for s in recent_seals) if recent_seals else '<tr><td colspan="2" style="color:#666">No seals yet</td></tr>'}
            </table>
        </div>

        <div class="footer">
            <p>Powered by <a href="https://t.me/NotaryTON_bot">@NotaryTON_bot</a> | <a href="/">Home</a> | <a href="/stats">API</a></p>
        </div>
    </div>
</body>
</html>
"""

@app.on_event("startup")
async def on_startup():
    """Set webhooks for both bots on startup"""
    global BOT_USERNAME, MEMESEAL_USERNAME

    # Initialize database (PostgreSQL via Neon)
    await db.connect()

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

    os.makedirs("downloads", exist_ok=True)

@app.on_event("shutdown")
async def on_shutdown():
    """Cleanup on shutdown - DO NOT delete webhook (causes issues with Render restarts)"""
    await bot.session.close()
    if memeseal_bot:
        await memeseal_bot.session.close()
    await db.disconnect()
    print("🛑 Bot sessions and database closed (webhooks preserved)")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
