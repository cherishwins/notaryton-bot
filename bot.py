import hashlib
import os
import re
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Update
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

        # Parse tx_id and fetch transaction
        # This is a simplified version - you'll need to implement full tx parsing
        # For now, return placeholder
        # TODO: Implement actual transaction fetching and code extraction

        await client.close_all()
        return b"contract_code_placeholder"
    except Exception as e:
        print(f"Error fetching contract code: {e}")
        return b""

async def send_ton_transaction(comment: str, amount_ton: float = 0.01):
    """Send TON transaction with comment"""
    try:
        client = LiteBalancer.from_mainnet_config(trust_level=1)
        await client.start_up()

        mnemonics = TON_WALLET_SECRET.split()
        wallet = await WalletV4R2.from_mnemonic(provider=client, mnemonics=mnemonics)

        await wallet.transfer(
            destination=SERVICE_TON_WALLET,
            amount=int(amount_ton * 1e9),  # Convert to nanotons
            body=comment
        )

        await client.close_all()
        return "Transaction sent"
    except Exception as e:
        print(f"Error sending transaction: {e}")
        raise

async def poll_wallet_for_payments():
    """Background task to poll wallet for incoming payments"""
    while True:
        try:
            client = LiteBalancer.from_mainnet_config(trust_level=1)
            await client.start_up()

            # TODO: Implement actual wallet polling logic
            # 1. Get recent transactions
            # 2. Match to pending payments
            # 3. Activate subscriptions

            await client.close_all()
        except Exception as e:
            print(f"Error polling wallet: {e}")

        await asyncio.sleep(30)  # Poll every 30 seconds

# ========================
# BOT HANDLERS
# ========================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🔐 **NotaryTON - Auto-Notarization for TON Memecoin Launches**\n\n"
        "**Commands:**\n"
        "/subscribe - Get unlimited monthly notarizations (0.1 TON)\n"
        "/status - Check your subscription status\n"
        "/notarize - Manually notarize a contract\n\n"
        "**Auto-Notarization:**\n"
        "I auto-notarize new coin launches in monitored groups!\n"
        "Cost: 0.001 TON per notarization",
        parse_mode="Markdown"
    )

@dp.message(Command("subscribe"))
async def cmd_subscribe(message: types.Message):
    user_id = message.from_user.id
    await message.answer(
        f"💎 **Unlimited Monthly Subscription**\n\n"
        f"**Price:** 0.1 TON (~$0.18)\n"
        f"**Benefits:** Unlimited notarizations for 30 days\n\n"
        f"**To activate:**\n"
        f"Send 0.1 TON to:\n"
        f"`{SERVICE_TON_WALLET}`\n\n"
        f"Include your user ID in memo: `{user_id}`\n\n"
        f"Your subscription will activate within 1 minute!",
        parse_mode="Markdown"
    )

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    user_id = message.from_user.id
    has_sub = await get_user_subscription(user_id)

    if has_sub:
        await message.answer("✅ **Active Subscription**\n\nYou have unlimited notarizations!", parse_mode="Markdown")
    else:
        await message.answer("❌ **No Active Subscription**\n\nUse /subscribe to get unlimited access!", parse_mode="Markdown")

@dp.message(Command("notarize"))
async def cmd_notarize(message: types.Message):
    user_id = message.from_user.id
    has_sub = await get_user_subscription(user_id)

    if not has_sub:
        await message.answer(
            "⚠️ **Payment Required**\n\n"
            f"Send 0.001 TON to: `{SERVICE_TON_WALLET}`\n"
            f"Include your user ID: `{user_id}`\n\n"
            f"Or use /subscribe for unlimited access!",
            parse_mode="Markdown"
        )
        return

    await message.answer(
        "📄 **Manual Notarization**\n\n"
        "Please send the contract address or TX ID to notarize.",
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

    if not has_sub:
        await message.answer(
            f"⚠️ Send 0.001 TON to `{SERVICE_TON_WALLET}` (memo: `{user_id}`) first!",
            parse_mode="Markdown"
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

        await message.answer(
            f"✅ **SEALED!**\n\n"
            f"Hash: `{file_hash}`\n"
            f"Check https://tonscan.org",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

    # Clean up
    os.remove(file_path)

# ========================
# FASTAPI ENDPOINTS
# ========================

@app.post(WEBHOOK_PATH)
async def webhook_handler(request: Request):
    """Handle incoming webhook updates from Telegram"""
    update = Update(**(await request.json()))
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {"status": "running", "bot": "NotaryTON", "version": "2.0-memecoin"}

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
    """Delete webhook on shutdown"""
    await bot.delete_webhook()
    await bot.session.close()
    print("🛑 Webhook deleted")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
