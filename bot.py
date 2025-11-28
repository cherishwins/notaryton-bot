import hashlib
import os
import re
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
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
TON_CENTER_API_KEY = os.getenv("TON_CENTER_API_KEY")
TON_WALLET_SECRET = os.getenv("TON_WALLET_SECRET")
SERVICE_TON_WALLET = os.getenv("SERVICE_TON_WALLET")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://notaryton.com")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
GROUP_IDS = os.getenv("GROUP_IDS", "").split(",")  # Comma-separated chat IDs

# Known deploy bots (add more as needed)
DEPLOY_BOTS = ["@tondeployer", "@memelaunchbot", "@toncoinbot"]

# Telegram Stars pricing (XTR currency)
# 1 Star ≈ $0.013
STARS_SINGLE_NOTARIZATION = 1   # 1 Star for single notarization
STARS_MONTHLY_SUBSCRIPTION = 15  # 15 Stars for monthly unlimited (~$0.20)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

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
                await client.close_all()
                return code if isinstance(code, bytes) else str(code).encode()
            else:
                print(f"No code found for address: {tx_id}")
                await client.close_all()
                return b""

        except Exception as addr_error:
            print(f"Could not parse as address: {addr_error}")
            # If not an address, try to fetch as transaction hash
            # For now, return the tx_id itself as data to hash
            await client.close_all()
            return tx_id.encode()

    except Exception as e:
        print(f"Error fetching contract code: {e}")
        return b""

async def send_ton_transaction(comment: str, amount_ton: float = 0.001):
    """Send TON transaction with comment (notarization proof)"""
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

        await client.close_all()
        return result
    except Exception as e:
        print(f"❌ Error sending transaction: {e}")
        print(f"   Make sure wallet has sufficient TON balance")
        raise

async def poll_wallet_for_payments():
    """Background task to poll wallet for incoming payments"""
    last_processed_lt = None  # Track last processed logical time

    while True:
        try:
            client = LiteBalancer.from_mainnet_config(trust_level=1)
            await client.start_up()

            # Get wallet address
            wallet_address = Address(SERVICE_TON_WALLET)

            # Get recent transactions
            try:
                transactions = await client.get_transactions(
                    address=wallet_address.to_str(),
                    count=10
                )

                for tx in transactions:
                    # Skip if we've already processed this transaction
                    if last_processed_lt and tx.lt <= last_processed_lt:
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
                            # Look for numeric user ID in memo
                            import re
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

                                # Notify user
                                try:
                                    await bot.send_message(
                                        user_id,
                                        "✅ **Subscription Activated!**\n\n"
                                        "You now have unlimited notarizations for 30 days!\n\n"
                                        "Use /notarize to seal your first contract. 🔒",
                                        parse_mode="Markdown"
                                    )
                                except Exception as notify_error:
                                    print(f"Could not notify user {user_id}: {notify_error}")

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

                                # Notify user
                                try:
                                    await bot.send_message(
                                        user_id,
                                        "✅ **Payment Received!**\n\n"
                                        f"You can now notarize one contract.\n\n"
                                        "Use /notarize to get started! 🔒",
                                        parse_mode="Markdown"
                                    )
                                except Exception as notify_error:
                                    print(f"Could not notify user {user_id}: {notify_error}")

                    # Update last processed lt
                    if not last_processed_lt or tx.lt > last_processed_lt:
                        last_processed_lt = tx.lt

            except Exception as tx_error:
                print(f"Error processing transactions: {tx_error}")

            await client.close_all()

        except Exception as e:
            print(f"Error polling wallet: {e}")

        await asyncio.sleep(30)  # Poll every 30 seconds

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

@dp.message(F.text)
async def handle_text_message(message: types.Message):
    """Handle text messages - look for deploy bot patterns"""
    text = message.text
    user_id = message.from_user.id

    # Check if message is from a known deploy bot
    sender_username = f"@{message.from_user.username}" if message.from_user.username else None

    if sender_username not in DEPLOY_BOTS:
        return  # Ignore messages not from deploy bots

    # Look for tx pattern: "tx: [tx_id]" or similar
    tx_pattern = r"tx:\s*([A-Za-z0-9]+)"
    match = re.search(tx_pattern, text, re.IGNORECASE)

    if not match:
        return

    tx_id = match.group(1)

    # Check if user has subscription
    has_sub = await get_user_subscription(user_id)

    if not has_sub:
        await message.reply(
            f"🔍 **New Launch Detected!**\n\n"
            f"TX: `{tx_id}`\n\n"
            f"⚠️ Send 0.001 TON to `{SERVICE_TON_WALLET}` (memo: `{user_id}`) to auto-notarize!\n"
            f"Or /subscribe for unlimited access.",
            parse_mode="Markdown"
        )
        return

    # Fetch contract code and notarize
    try:
        contract_code = await get_contract_code_from_tx(tx_id)
        if not contract_code:
            await message.reply("❌ Failed to fetch contract code")
            return

        # Hash the contract code
        contract_hash = hash_data(contract_code)

        # Send notarization transaction
        comment = f"NotaryTON:Launch:{contract_hash[:16]}"
        await send_ton_transaction(comment, amount_ton=0.001)

        # Log notarization
        await log_notarization(user_id, tx_id, contract_hash, paid=True)

        await message.reply(
            f"✅ **Auto-Notarized!**\n\n"
            f"Contract Hash: `{contract_hash}`\n"
            f"Proof TX: Check https://tonscan.org for latest\n\n"
            f"Sealed on TON blockchain forever! 🔒",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

@dp.message(F.document)
async def handle_document(message: types.Message):
    """Handle file uploads for manual notarization"""
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
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⭐ Pay 1 Star", callback_data="pay_stars_single")],
            [types.InlineKeyboardButton(text="💎 Pay 0.001 TON", callback_data="pay_ton_single")],
            [types.InlineKeyboardButton(text="🚀 Unlimited (15 Stars/mo)", callback_data="pay_stars_sub")]
        ])

        await message.answer(
            "⚠️ **Payment Required to Notarize**\n\n"
            "Choose how to pay:\n\n"
            "⭐ **1 Star** - Quick & easy\n"
            "💎 **0.001 TON** - Native crypto\n"
            "🚀 **15 Stars/mo** - Unlimited access\n",
            parse_mode="Markdown",
            reply_markup=keyboard
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
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    UPDATE users
                    SET total_paid = total_paid - 0.001
                    WHERE user_id = ?
                """, (user_id,))
                await db.commit()

        await message.answer(
            f"✅ **SEALED!**\n\n"
            f"File: `{message.document.file_name}`\n"
            f"Hash: `{file_hash}`\n\n"
            f"Proof stored on TON blockchain forever! 🔒\n"
            f"Check: https://tonscan.org/address/{SERVICE_TON_WALLET}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

    # Clean up
    try:
        os.remove(file_path)
    except:
        pass

# ========================
# FASTAPI ENDPOINTS
# ========================

@app.post(WEBHOOK_PATH)
async def webhook_handler(request: Request):
    """Handle incoming webhook updates from Telegram"""
    update = Update(**(await request.json()))
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "running", "bot": "NotaryTON", "version": "2.0-memecoin"}

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
async def landing_page():
    """Marketing landing page"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NotaryTON - Blockchain Notarization on TON</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #0f3460 100%);
            color: #fff;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container { max-width: 600px; text-align: center; }
        .logo { font-size: 4rem; margin-bottom: 20px; }
        h1 { font-size: 2.5rem; margin-bottom: 10px; background: linear-gradient(90deg, #00d4ff, #7b2cbf); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .tagline { font-size: 1.3rem; color: #aaa; margin-bottom: 30px; }
        .features { text-align: left; margin: 30px 0; }
        .feature { display: flex; align-items: center; margin: 15px 0; font-size: 1.1rem; }
        .feature span { margin-right: 15px; font-size: 1.5rem; }
        .cta {
            display: inline-block;
            background: linear-gradient(90deg, #0088cc, #00d4ff);
            color: #fff;
            padding: 18px 40px;
            border-radius: 50px;
            text-decoration: none;
            font-size: 1.2rem;
            font-weight: 600;
            margin-top: 20px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .cta:hover { transform: translateY(-2px); box-shadow: 0 10px 30px rgba(0,136,204,0.4); }
        .price { margin-top: 30px; color: #888; }
        .price strong { color: #00d4ff; font-size: 1.3rem; }
        footer { margin-top: 50px; color: #555; font-size: 0.9rem; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🔐</div>
        <h1>NotaryTON</h1>
        <p class="tagline">Seal any file on TON blockchain. Instant. Immutable. Forever.</p>

        <div class="features">
            <div class="feature"><span>⚡</span> Instant blockchain notarization</div>
            <div class="feature"><span>🔒</span> Immutable proof of existence</div>
            <div class="feature"><span>📄</span> Works with any file or contract</div>
            <div class="feature"><span>🤖</span> Simple Telegram bot interface</div>
            <div class="feature"><span>🔌</span> API for developers & integrations</div>
        </div>

        <a href="https://t.me/NotaryTON_bot" class="cta">🚀 Start Notarizing</a>

        <p class="price">Starting at <strong>0.001 TON</strong> per notarization (~$0.005)</p>

        <footer>
            <p>Powered by TON Blockchain</p>
        </footer>
    </div>
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
    """Set webhook and join groups on startup"""
    # Initialize database
    await init_db()

    # Set webhook
    webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(webhook_url, drop_pending_updates=True)
    print(f"✅ Webhook set to: {webhook_url}")

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
    print("🛑 Bot session closed (webhook preserved)")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
