"""
MemeSeal TON - Configuration
All environment variables and constants in one place.
"""
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

# =============================================================================
# TELEGRAM BOT TOKENS
# =============================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
MEMESEAL_BOT_TOKEN = os.getenv("MEMESEAL_BOT_TOKEN")

# Webhook configuration
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://notaryton.com")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
MEMESEAL_WEBHOOK_PATH = f"/webhook/{MEMESEAL_BOT_TOKEN}" if MEMESEAL_BOT_TOKEN else None

# Bot usernames (set on startup, these are defaults)
BOT_USERNAME = "NotaryTON_bot"
MEMESEAL_USERNAME = "MemeSealTON_bot"

# =============================================================================
# TON BLOCKCHAIN
# =============================================================================
TON_CENTER_API_KEY = os.getenv("TON_CENTER_API_KEY")
TON_WALLET_SECRET = os.getenv("TON_WALLET_SECRET")
SERVICE_TON_WALLET = os.getenv("SERVICE_TON_WALLET")

# TonAPI for real-time webhooks (replaces 30s polling!)
TONAPI_KEY = os.getenv("TONAPI_KEY", "")
TONAPI_WEBHOOK_SECRET = os.getenv("TONAPI_WEBHOOK_SECRET", "")

# =============================================================================
# PRICING
# =============================================================================
# Telegram Stars pricing (XTR currency)
# 1 Star ~ $0.02-0.05 depending on purchase method
STARS_SINGLE_NOTARIZATION = 1   # 1 Star for single notarization
STARS_MONTHLY_SUBSCRIPTION = 20  # 20 Stars for monthly unlimited (~$1.00)

# TON pricing
TON_SINGLE_SEAL = 0.015  # 0.015 TON per seal (~$0.05)
TON_MONTHLY_SUB = 0.3    # 0.3 TON for monthly unlimited (~$1.00)

# Minimum withdrawal amount
MIN_WITHDRAWAL_TON = 0.05

# =============================================================================
# REFERRAL & LOTTERY
# =============================================================================
REFERRAL_COMMISSION = 0.05  # 5% commission on referrals
LOTTERY_POT_SHARE = 0.20    # 20% of fees go to lottery pot

# =============================================================================
# GROUPS & DEPLOY BOTS
# =============================================================================
GROUP_IDS = os.getenv("GROUP_IDS", "").split(",")  # Comma-separated chat IDs
DEPLOY_BOTS = ["@tondeployer", "@memelaunchbot", "@toncoinbot"]

# =============================================================================
# SOCIAL MEDIA
# =============================================================================
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")  # Telegram announcement channel

# =============================================================================
# DATABASE
# =============================================================================
DATABASE_URL = os.getenv("DATABASE_URL", "")

# =============================================================================
# RATE LIMITS
# =============================================================================
API_RATE_LIMIT_PER_DAY = 1000
BATCH_MAX_CONTRACTS = 50
