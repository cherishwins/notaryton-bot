import hashlib
import os
import re
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Update, LabeledPrice, PreCheckoutQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from dotenv import load_dotenv
from pytoniq import LiteBalancer, WalletV4R2, Address
import aiosqlite
import uvicorn

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
# 1 Star ≈ $0.013
STARS_SINGLE_NOTARIZATION = 1   # 1 Star for single notarization
STARS_MONTHLY_SUBSCRIPTION = 15  # 15 Stars for monthly unlimited (~$0.20)

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

# Database path
DB_PATH = "notaryton.db"

# ========================
# DATABASE FUNCTIONS
# ========================

async def init_db():
    """Initialize SQLite database"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                subscription_expiry TIMESTAMP,
                total_paid REAL DEFAULT 0,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                referral_earnings REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notarizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                tx_hash TEXT,
                contract_hash TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                paid BOOLEAN DEFAULT 0,
                via_api BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                memo TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key TEXT PRIMARY KEY,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                requests_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.commit()

async def get_user_subscription(user_id: int):
    """Check if user has active subscription"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT subscription_expiry FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                expiry = datetime.fromisoformat(row[0])
                if expiry > datetime.now():
                    return True
            return False

async def add_subscription(user_id: int, months: int = 1):
    """Add or extend subscription"""
    expiry = datetime.now() + timedelta(days=30 * months)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, subscription_expiry)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET subscription_expiry = ?
        """, (user_id, expiry, expiry))
        await db.commit()

async def log_notarization(user_id: int, tx_hash: str, contract_hash: str, paid: bool = False):
    """Log a notarization event"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO notarizations (user_id, tx_hash, contract_hash, paid)
            VALUES (?, ?, ?, ?)
        """, (user_id, tx_hash, contract_hash, paid))
        await db.commit()

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

async def send_ton_transaction(comment: str, amount_ton: float = 0.001):
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

async def poll_wallet_for_payments():
    """Background task to poll wallet for incoming payments with retry logic"""
    last_processed_lt = 0
    
    # Load last processed LT from DB
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT value FROM bot_state WHERE key = 'last_processed_lt'") as cursor:
                row = await cursor.fetchone()
                if row:
                    last_processed_lt = int(row[0])
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
                        except:
                            memo = str(in_msg.body)

                    print(f"📥 Incoming payment: {amount_ton} TON, memo: {memo}")

                    # Try to extract user_id from memo
                    user_id = None
                    try:
                        match = re.search(r'\d+', memo)
                        if match:
                            user_id = int(match.group())
                    except:
                        pass

                    if user_id:
                        # Check if it's a subscription payment (0.1 TON)
                        if amount_ton >= 0.095:  # Allow small variance
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
                                    except:
                                        pass

                        # Check if it's a single notarization payment (0.001 TON)
                        elif amount_ton >= 0.0009:  # Allow small variance
                            # Add to database as paid credit
                            async with aiosqlite.connect(DB_PATH) as db:
                                await db.execute("""
                                    INSERT OR IGNORE INTO users (user_id) VALUES (?)
                                """, (user_id,))
                                await db.execute("""
                                    UPDATE users
                                    SET total_paid = total_paid + ?
                                    WHERE user_id = ?
                                """, (amount_ton, user_id))
                                await db.commit()

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
                                    except:
                                        pass

                # Update max LT seen
                if tx.lt > new_max_lt:
                    new_max_lt = tx.lt

            # Update DB if we processed new transactions
            if new_max_lt > last_processed_lt:
                last_processed_lt = new_max_lt
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("""
                        INSERT INTO bot_state (key, value) VALUES ('last_processed_lt', ?)
                        ON CONFLICT(key) DO UPDATE SET value = ?
                    """, (str(last_processed_lt), str(last_processed_lt)))
                    await db.commit()

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
            else:
                print(f"❌ Error polling wallet (attempt {consecutive_errors}): {error_msg}")
        finally:
            if client:
                try:
                    await client.close_all()
                except:
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
    async with aiosqlite.connect(DB_PATH) as db:
        if referral_code and referral_code.startswith("REF"):
            # Extract referrer's user_id from referral code
            try:
                referrer_id = int(referral_code.replace("REF", ""))
                await db.execute("""
                    INSERT INTO users (user_id, referred_by)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET referred_by = ?
                    WHERE referred_by IS NULL
                """, (user_id, referrer_id, referrer_id))
                await db.commit()
                
                # Notify referrer
                try:
                    await bot.send_message(
                        referrer_id,
                        f"🎉 New referral! User {user_id} joined via your link.\n"
                        f"You'll earn 5% of their payments!"
                    )
                except:
                    pass
            except:
                pass
        else:
            # Just create user entry
            await db.execute("""
                INSERT OR IGNORE INTO users (user_id) VALUES (?)
            """, (user_id,))
            await db.commit()
    
    welcome_msg = (
        "🔐 **NotaryTON - Blockchain Infrastructure for TON**\n\n"
        "Auto-notarize memecoin launches with immutable on-chain proof.\n\n"
        "**Commands:**\n"
        "• /subscribe - Unlimited notarizations\n"
        "• /status - Your stats & subscription\n"
        "• /notarize - Manually notarize a contract\n"
        "• /api - Get API access for integrations\n"
        "• /referral - Earn 5% commission\n\n"
        "**Features:**\n"
        "✅ Auto-notarization in groups\n"
        "✅ Public API for third-party bots\n"
        "✅ Batch operations for high volume\n"
        "✅ Instant verification via inline mode\n\n"
        "💰 **Pricing:**\n"
        "• ⭐ 1 Star OR 💎 0.001 TON per seal\n"
        "• ⭐ 15 Stars OR 💎 0.1 TON/month unlimited\n\n"
        "🚀 **Become Infrastructure** - Every TON launch verified here."
    )
    
    await message.answer(welcome_msg, parse_mode="Markdown")

@dp.message(Command("subscribe"))
async def cmd_subscribe(message: types.Message):
    user_id = message.from_user.id

    # Create inline keyboard with payment options
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⭐ Pay with Stars (15 Stars)", callback_data="pay_stars_sub")],
        [types.InlineKeyboardButton(text="💎 Pay with TON (0.1 TON)", callback_data="pay_ton_sub")]
    ])

    await message.answer(
        f"💎 **Unlimited Monthly Subscription**\n\n"
        f"**Benefits:** Unlimited notarizations for 30 days\n\n"
        f"**Choose Payment Method:**\n"
        f"⭐ **Telegram Stars:** 15 Stars (~$0.20)\n"
        f"💎 **TON:** 0.1 TON (~$0.18)\n\n"
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
        f"Send **0.1 TON** to:\n"
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
        f"Send **0.001 TON** to:\n"
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
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("""
                    SELECT tx_hash, timestamp, contract_hash
                    FROM notarizations
                    WHERE contract_hash LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT 5
                """, (f"{query_text}%",)) as cursor:
                    rows = await cursor.fetchall()

                    if rows:
                        for i, row in enumerate(rows):
                            tx_hash, timestamp, contract_hash = row
                            results.append(
                                InlineQueryResultArticle(
                                    id=f"result_{i}",
                                    title=f"✅ Verified: {contract_hash[:16]}...",
                                    description=f"Notarized on {timestamp}",
                                    input_message_content=InputTextMessageContent(
                                        message_text=f"✅ **VERIFIED NOTARIZATION**\n\n"
                                                     f"🔐 Hash: `{contract_hash}`\n"
                                                     f"📅 Timestamp: {timestamp}\n"
                                                     f"⛓️ Blockchain: TON\n\n"
                                                     f"🔗 Verify: https://notaryton.com/api/v1/verify/{contract_hash}",
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
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE users SET total_paid = total_paid + ? WHERE user_id = ?
            """, (stars_value_ton, user_id))
            await db.commit()

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
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR IGNORE INTO users (user_id) VALUES (?)
            """, (user_id,))
            await db.execute("""
                UPDATE users SET total_paid = total_paid + 0.001 WHERE user_id = ?
            """, (user_id,))
            await db.commit()

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
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT total_paid, referral_earnings, referral_code
            FROM users WHERE user_id = ?
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            stats = {
                "total_paid": row[0] if row else 0,
                "referral_earnings": row[1] if row else 0,
                "referral_code": row[2] if row else None
            }
        
        async with db.execute("""
            SELECT COUNT(*) FROM notarizations WHERE user_id = ?
        """, (user_id,)) as cursor:
            stats["notarizations"] = (await cursor.fetchone())[0]

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
    
    # Generate referral code if doesn't exist
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT referral_code FROM users WHERE user_id = ?
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            
            if row and row[0]:
                referral_code = row[0]
            else:
                # Generate unique referral code
                referral_code = f"REF{user_id}"
                await db.execute("""
                    INSERT INTO users (user_id, referral_code)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET referral_code = ?
                """, (user_id, referral_code, referral_code))
                await db.commit()
        
        # Count referrals
        async with db.execute("""
            SELECT COUNT(*), COALESCE(SUM(total_paid), 0)
            FROM users WHERE referred_by = ?
        """, (user_id,)) as cursor:
            ref_count, ref_revenue = await cursor.fetchone()
    
    referral_url = f"https://t.me/NotaryTON_bot?start={referral_code}"
    
    await message.answer(
        f"🎁 **Referral Program**\n\n"
        f"**Your Referral Link:**\n"
        f"`{referral_url}`\n\n"
        f"**Commission:** 5% of referrals' payments\n"
        f"**Your Stats:**\n"
        f"• Referrals: {ref_count}\n"
        f"• Total Revenue: {ref_revenue:.4f} TON\n"
        f"• Your Earnings: {ref_revenue * 0.05:.4f} TON\n\n"
        f"💡 Share this link with other TON projects!",
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
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT total_paid FROM users WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0] >= 0.001:
                    has_credit = True

    if not has_sub and not has_credit:
        # Offer payment options
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⭐ Pay 1 Star", callback_data="pay_stars_single")],
            [types.InlineKeyboardButton(text="💎 Pay 0.001 TON", callback_data="pay_ton_single")],
            [types.InlineKeyboardButton(text="🚀 Unlimited (15 Stars/mo)", callback_data="pay_stars_sub")]
        ])

        await message.answer(
            "⚠️ **Payment Required**\n\n"
            "Choose how to pay for this notarization:\n\n"
            "⭐ **1 Star** - Quick & easy\n"
            "💎 **0.001 TON** - Native crypto\n"
            "🚀 **15 Stars/mo** - Unlimited access\n",
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

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT total_paid FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0] >= 0.001:
                return True, False
    return False, False


async def deduct_credit(user_id: int):
    """Deduct one notarization credit from user"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET total_paid = total_paid - 0.001 WHERE user_id = ?
        """, (user_id,))
        await db.commit()


def get_payment_keyboard():
    """Return standard payment keyboard"""
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⭐ Pay 1 Star", callback_data="pay_stars_single")],
        [types.InlineKeyboardButton(text="💎 Pay 0.001 TON", callback_data="pay_ton_single")],
        [types.InlineKeyboardButton(text="🚀 Unlimited (15 Stars/mo)", callback_data="pay_stars_sub")]
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
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("""
                    SELECT tx_hash, timestamp FROM notarizations
                    WHERE contract_hash = ? ORDER BY timestamp DESC LIMIT 1
                """, (text,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        await message.reply(
                            f"✅ **VERIFIED**\n\n"
                            f"Hash: `{text}`\n"
                            f"Timestamp: {row[1]}\n"
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
                f"⚠️ Send 0.001 TON to `{SERVICE_TON_WALLET}` (memo: `{user_id}`) to notarize!\n"
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
        await send_ton_transaction(comment, amount_ton=0.001)
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
            "💎 **0.001 TON** - Native crypto\n"
            "🚀 **15 Stars/mo** - Unlimited access\n",
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
    except:
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
    except:
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
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()

        # Check for CHIMPWIN promo (first 500 free seals)
        free_seal_msg = ""
        if promo_code == "CHIMPWIN":
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    UPDATE users SET total_paid = total_paid + 0.001 WHERE user_id = ?
                """, (user_id,))
                await db.commit()
            free_seal_msg = "\n\n🎁 **PROMO ACTIVATED!** You got 1 free seal. LFG!"

        welcome_msg = (
            "⚡🐸 **MEMESEAL TON**\n\n"
            "Seal your bags before the rug.\n"
            "One tap = on-chain proof you were early.\n\n"
            "**What you get:**\n"
            "• Instant hash on TON (under 1 sec)\n"
            "• Permanent verification link\n"
            "• Works with screenshots, wallet connects, anything\n\n"
            "**Commands:**\n"
            "• /start - Seal something now\n"
            "• /unlimited - Go infinite (0.1 TON/mo)\n"
            "• /api - Dev docs + referral link\n"
            "• /verify - Check any seal\n\n"
            "💰 **Price:** 1 Star or 0.001 TON (~$0.05)\n\n"
            "**Send me a file or screenshot to seal it forever!**\n\n"
            "receipts or GTFO 🐸"
            f"{free_seal_msg}"
        )

        await message.answer(welcome_msg, parse_mode="Markdown")

    @memeseal_dp.message(Command("unlimited"))
    async def memeseal_subscribe(message: types.Message):
        user_id = message.from_user.id

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⭐ 15 Stars - Go Unlimited", callback_data="ms_pay_stars_sub")],
            [types.InlineKeyboardButton(text="💎 0.1 TON - Same thing", callback_data="ms_pay_ton_sub")]
        ])

        await message.answer(
            "🚀 **UNLIMITED SEALS**\n\n"
            "Stop counting. Start sealing everything.\n\n"
            "**What you get:**\n"
            "• Unlimited seals for 30 days\n"
            "• API access included\n"
            "• Batch operations\n"
            "• Priority support (lol jk we respond to everyone)\n\n"
            "**Price:** 15 Stars OR 0.1 TON\n\n"
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
            f"Send **0.1 TON** to:\n"
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
            f"Send **0.001 TON** to:\n"
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
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
                await db.execute("UPDATE users SET total_paid = total_paid + 0.001 WHERE user_id = ?", (user_id,))
                await db.commit()
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
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT total_paid FROM users WHERE user_id = ?", (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0] >= 0.001:
                        has_credit = True

        if not has_sub and not has_credit:
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="⭐ 1 Star - Seal it", callback_data="ms_pay_stars_single")],
                [types.InlineKeyboardButton(text="💎 0.001 TON", callback_data="ms_pay_ton_single")],
                [types.InlineKeyboardButton(text="🚀 Go Unlimited", callback_data="ms_pay_stars_sub")]
            ])
            await message.answer(
                "💰 **PAY TO SEAL**\n\n"
                "1 Star or 0.001 TON.\n"
                "That's it. Then it's on-chain forever.\n\n"
                "Or go unlimited for 15 Stars. 🐸",
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
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("UPDATE users SET total_paid = total_paid - 0.001 WHERE user_id = ?", (user_id,))
                    await db.commit()

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
        except:
            pass

    @memeseal_dp.message(F.photo)
    async def memeseal_handle_photo(message: types.Message):
        """Handle screenshots/photos"""
        user_id = message.from_user.id
        has_sub = await get_user_subscription(user_id)

        has_credit = False
        if not has_sub:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT total_paid FROM users WHERE user_id = ?", (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0] >= 0.001:
                        has_credit = True

        if not has_sub and not has_credit:
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="⭐ 1 Star - Seal it", callback_data="ms_pay_stars_single")],
                [types.InlineKeyboardButton(text="💎 0.001 TON", callback_data="ms_pay_ton_single")],
                [types.InlineKeyboardButton(text="🚀 Go Unlimited", callback_data="ms_pay_stars_sub")]
            ])
            await message.answer(
                "📸 **Nice screenshot!**\n\n"
                "1 Star to seal it on TON forever.\n"
                "Proof you were there. 🐸",
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
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("UPDATE users SET total_paid = total_paid - 0.001 WHERE user_id = ?", (user_id,))
                    await db.commit()

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
        except:
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
    from fastapi.responses import FileResponse
    favicon_path = "static/favicon.ico"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    # Fallback to logo.png
    return FileResponse("static/logo.png", media_type="image/png")


from fastapi.responses import HTMLResponse

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

@app.get("/memeseal", response_class=HTMLResponse)
async def memeseal_landing():
    """MemeSeal TON - Degen landing page"""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MemeSeal TON ⚡🐸 - Proof or it didn't happen</title>
    <meta name="description" content="Seal your bags before the rug. Instant on-chain proof on TON. 1 Star or 0.001 TON per seal.">

    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://notaryton.com/memeseal">
    <meta property="og:title" content="MemeSeal TON ⚡🐸 - Proof or it didn't happen">
    <meta property="og:description" content="Seal your bags before the rug. Instant on-chain proof on TON. 1 Star or 0.001 TON per seal.">
    <meta property="og:image" content="https://notaryton.com/static/memeseal_banner.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:site_name" content="MemeSeal TON">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:url" content="https://notaryton.com/memeseal">
    <meta name="twitter:title" content="MemeSeal TON ⚡🐸 - Proof or it didn't happen">
    <meta name="twitter:description" content="Seal your bags before the rug. Receipts or GTFO 🐸">
    <meta name="twitter:image" content="https://notaryton.com/static/memeseal_banner.png">

    <!-- Favicon -->
    <link rel="icon" type="image/png" href="/static/memeseal_icon.png">
    <link rel="apple-touch-icon" href="/static/memeseal_icon.png">

    <!-- Analytics -->
    <script defer src="https://cloud.umami.is/script.js" data-website-id="5d783ccd-fca7-4957-ad7e-06cc2814da83"></script>
    <!-- End Analytics -->

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
            font-size: 2rem;
            color: #00ff88;
            text-shadow: 0 0 20px #00ff88, 0 0 40px #00ff88;
            margin-bottom: 15px;
        }}
        .tagline {{
            font-size: 1.3rem;
            color: #88ffbb;
            margin-bottom: 10px;
        }}
        .subtagline {{
            font-size: 1rem;
            color: #666;
            margin-bottom: 40px;
        }}
        .cta {{
            display: inline-block;
            background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
            color: #000;
            padding: 20px 50px;
            border-radius: 50px;
            text-decoration: none;
            font-size: 1.2rem;
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
        }}
        .feature:hover {{
            border-color: #00ff88;
            box-shadow: 0 0 30px rgba(0,255,136,0.2);
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
        .pricing {{
            padding: 60px 20px;
            text-align: center;
            background: #080810;
        }}
        .pricing h2 {{
            font-family: 'Press Start 2P', cursive;
            font-size: 1.3rem;
            margin-bottom: 15px;
            color: #00ff88;
        }}
        .pricing-sub {{
            color: #666;
            margin-bottom: 40px;
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
        }}
        .price-card h3 {{
            font-size: 1.2rem;
            margin-bottom: 15px;
            color: #fff;
        }}
        .price-card .price {{
            font-family: 'Press Start 2P', cursive;
            font-size: 1.5rem;
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
        .dev-section {{
            padding: 60px 20px;
            text-align: center;
            background: linear-gradient(180deg, #0a0a0f 0%, #0d1510 100%);
        }}
        .dev-section h2 {{
            font-family: 'Press Start 2P', cursive;
            font-size: 1.1rem;
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
        footer {{
            background: #000;
            color: #444;
            padding: 40px 20px;
            text-align: center;
            border-top: 1px solid #111;
        }}
        footer a {{
            color: #00ff88;
            text-decoration: none;
        }}
        .badge {{
            display: inline-block;
            background: #00ff8822;
            color: #00ff88;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.85rem;
            margin-top: 20px;
            border: 1px solid #00ff8844;
        }}
        .glow-text {{
            text-shadow: 0 0 10px currentColor;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.7; }}
        }}
        .pulse {{ animation: pulse 2s infinite; }}
    </style>
</head>
<body>
    <div class="hero">
        <img src="/static/memeseal_banner.png" alt="MemeSeal TON" class="banner">
        <h1>MEMESEAL TON ⚡🐸</h1>
        <p class="tagline">Seal your bags before the rug.</p>
        <p class="subtagline">One tap = on-chain proof you were early. No more "bro trust me" screenshots.</p>
        <a href="https://t.me/{MEMESEAL_USERNAME}" class="cta">START SEALING</a>
        <span class="badge">🔥 Costs less than a failed tx → 0.001 TON</span>
    </div>

    <div class="features">
        <div class="feature">
            <h3>⚡ Instant Hash on TON</h3>
            <p>Under 1 second. Your screenshot, wallet connect, voice note - whatever - gets sealed on-chain forever.</p>
        </div>
        <div class="feature">
            <h3>🔗 Permanent Verification</h3>
            <p>Anyone can check. No login, no KYC, no cope. Just paste the hash and see the proof.</p>
        </div>
        <div class="feature">
            <h3>🤖 Auto-Seal in Groups</h3>
            <p>Add @{MEMESEAL_USERNAME} to your raid channel. Every coin drop = auto-sealed with timestamp. Dev can't deny fair launch.</p>
        </div>
        <div class="feature">
            <h3>💰 5% Referral Forever</h3>
            <p>Plug it into your pump clone, DEX, sniper bot. When your users seal through your link → you eat forever.</p>
        </div>
    </div>

    <div class="pricing">
        <h2>DEGEN PRICING</h2>
        <p class="pricing-sub">no subscription bullshit unless you want it</p>
        <div class="price-cards">
            <div class="price-card">
                <h3>Pay As You Go</h3>
                <div class="price">1 ⭐ STAR</div>
                <div class="price-alt">or 0.001 TON (~$0.05)</div>
                <ul>
                    <li>Single seal</li>
                    <li>Instant on-chain proof</li>
                    <li>Permanent verify link</li>
                    <li>Perfect for 47 coins before breakfast</li>
                </ul>
            </div>
            <div class="price-card featured">
                <h3>Unlimited Monthly</h3>
                <div class="price">15 ⭐ STARS</div>
                <div class="price-alt">or 0.1 TON (~$0.50)</div>
                <ul>
                    <li>Unlimited seals</li>
                    <li>API access included</li>
                    <li>Batch operations</li>
                    <li>For real cookers who launch daily</li>
                </ul>
            </div>
        </div>
    </div>

    <div class="dev-section">
        <h2>DEVELOPERS / COOKERS</h2>
        <p>Public REST API + 5% referral kickback. Plug it into your pump.fun clone, your DEX, your sniper bot.</p>
        <div class="code-block">
            <code>
POST /api/v1/notarize<br>
{{<br>
&nbsp;&nbsp;"api_key": "your_telegram_id",<br>
&nbsp;&nbsp;"contract_address": "EQ...",<br>
&nbsp;&nbsp;"metadata": {{"coin": "FROG420"}}<br>
}}
            </code>
        </div>
        <a href="/docs" class="badge" style="margin-top: 30px; text-decoration: none;">📚 Full API Docs</a>
    </div>

    <footer>
        <p>Powered by TON | Built for degens | Will never rug you</p>
        <p style="margin-top: 15px;">
            <a href="https://t.me/{MEMESEAL_USERNAME}">Start Sealing</a> |
            <a href="https://t.me/JPandaJamez">Support</a> |
            <a href="/verify">Verify a Seal</a>
        </p>
        <p style="margin-top: 20px; font-size: 0.8rem;">© 2025 MemeSeal TON – receipts or GTFO 🐸</p>
    </footer>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def landing_page():
    """Marketing landing page"""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NotaryTON - Blockchain Notarization on TON</title>
    <meta name="description" content="Seal any file on TON blockchain. Instant. Immutable. Forever. Starting at 1 Star or 0.001 TON.">

    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://notaryton.com/">
    <meta property="og:title" content="NotaryTON - Blockchain Notarization on TON">
    <meta property="og:description" content="Seal any file on TON blockchain. Instant. Immutable. Forever. Starting at 1 Star or 0.001 TON.">
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
                <div class="price">1 Star <small>or 0.001 TON</small></div>
                <ul>
                    <li>Single notarization</li>
                    <li>Instant on-chain proof</li>
                    <li>Permanent verification URL</li>
                    <li>Works with any file</li>
                </ul>
            </div>
            <div class="price-card" style="border-color: #0a4d8c;">
                <h3>Monthly Unlimited</h3>
                <div class="price">15 Stars <small>or 0.1 TON</small></div>
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
        
        await send_ton_transaction(comment, amount_ton=0.001)
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
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT tx_hash, timestamp, user_id
                FROM notarizations
                WHERE contract_hash = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (contract_hash,)) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    return {
                        "verified": True,
                        "hash": contract_hash,
                        "tx_hash": row[0],
                        "timestamp": row[1],
                        "notarized_by": "NotaryTON",
                        "blockchain": "TON",
                        "explorer_url": f"https://tonscan.org/tx/{row[0]}"
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
                await send_ton_transaction(comment, amount_ton=0.001)
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
    """Get bot statistics"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM notarizations") as cursor:
            total_notarizations = (await cursor.fetchone())[0]

    return {
        "total_users": total_users,
        "total_notarizations": total_notarizations
    }

@app.on_event("startup")
async def on_startup():
    """Set webhooks for both bots on startup"""
    global BOT_USERNAME, MEMESEAL_USERNAME

    # Initialize database
    await init_db()

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
    print("🛑 Bot sessions closed (webhooks preserved)")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
