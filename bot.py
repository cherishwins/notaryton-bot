import hashlib
import hmac
import json
import os
import re
import asyncio
import secrets
from datetime import datetime, timedelta
from urllib.parse import parse_qsl
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Update, LabeledPrice, PreCheckoutQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent, WebAppInfo
from dotenv import load_dotenv
# InternalMsgInfo comes through pytoniq (which re-exports pytoniq_core), the
# package requirements.txt actually declares.
from pytoniq import LiteBalancer, WalletV5R1, Address, InternalMsgInfo
import uvicorn

# Database layer (PostgreSQL with Neon)
from database import db, LEGACY_LOTTERY_VOID_KEY

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
# Telegram webhook paths are fixed and not secret. The bot token used to be the
# path, which wrote it into every access and error log. Telegram instead echoes
# TELEGRAM_WEBHOOK_SECRET back in X-Telegram-Bot-Api-Secret-Token on each update.
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
WEBHOOK_PATH = "/webhook/telegram"
MEMESEAL_WEBHOOK_PATH = "/webhook/memeseal" if MEMESEAL_BOT_TOKEN else None
MEMESCAN_WEBHOOK_PATH = "/webhook/memescan" if MEMESCAN_BOT_TOKEN else None
GROUP_IDS = os.getenv("GROUP_IDS", "").split(",")  # Comma-separated chat IDs

# TonAPI for real-time webhooks (replaces 30s polling!)
TONAPI_KEY = os.getenv("TONAPI_KEY", "")
TONAPI_WEBHOOK_SECRET = os.getenv("TONAPI_WEBHOOK_SECRET", "")

# Admin endpoints are disabled unless ADMIN_SECRET is set. It is sent in the
# X-Admin-Secret header, never the query string (which lands in access logs).
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")

def _env_flag(name: str) -> bool:
    """True only when the variable is exactly "true".

    Strict on purpose: these switches move money, so "True", "1", "yes" or a
    stray space leave them off rather than guessing what was meant.
    """
    return os.getenv(name, "") == "true"


# Money switches. Each is off unless set to the literal string "true".
# Paying a lottery prize or a withdrawal to a wallet the user names is the bot
# transferring value at a user's request, holding chips or referral balances
# is holding user funds, and running the lottery at all is running a lottery.
# None is turned on without a written Canadian legal opinion, so the code that
# does them stays dormant by default.
#
# CASINO_ENABLED: every /api/v1/casino/* route. Off: 503 before the body is read.
CASINO_ENABLED = _env_flag("CASINO_ENABLED")
# LOTTERY_ENABLED: the weekly lottery itself. Paying for a seal bought an
# entry, a draw picked a winner and a prize was recorded: purchase, chance
# and prize, which is a lottery under s.206 of the Criminal Code whether or
# not the prize is ever paid out. Off: no entries are made, the Sunday draw
# is not started (and execute_lottery_draw draws nothing), the pot and ticket
# routes answer 503, and the bots neither show nor promise tickets or a pot.
LOTTERY_ENABLED = _env_flag("LOTTERY_ENABLED")
# LOTTERY_AUTO_PAYOUT_ENABLED: the Sunday draw sends the pot in TON to the
# winner's saved wallet. Off: the prize is held in lottery_prizes. Whatever
# its value, no draw runs until POST /admin/void-legacy-lottery has run once
# (see execute_lottery_draw): the pre-fix pot may hold forged entries.
LOTTERY_AUTO_PAYOUT_ENABLED = _env_flag("LOTTERY_AUTO_PAYOUT_ENABLED")
# WITHDRAWALS_ENABLED: /withdraw sends referral earnings in TON. Lottery prizes
# are never part of that balance (see execute_lottery_draw), and
# /api/v1/casino/withdraw answers 503 while off and 501 when on.
WITHDRAWALS_ENABLED = _env_flag("WITHDRAWALS_ENABLED")


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


# How old (seconds) a Mini App's signed initData may be before the casino API
# refuses it. Telegram signs it once, when the Mini App opens.
CASINO_INIT_DATA_MAX_AGE = _positive_int_env("CASINO_INIT_DATA_MAX_AGE", 86400)

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


@app.middleware("http")
async def casino_switch(request: Request, call_next):
    """Refuse every casino API route while CASINO_ENABLED is off.

    A middleware, not a check in each handler, so the body is never read and a
    route added later cannot forget it. Added before CORS so CORS stays the
    outermost layer and the browser can still read the 503.
    """
    path = request.url.path
    if (path == "/api/v1/casino" or path.startswith("/api/v1/casino/")) and not CASINO_ENABLED:
        return JSONResponse({"error": "casino disabled"}, status_code=503)
    return await call_next(request)


@app.middleware("http")
async def lottery_switch(request: Request, call_next):
    """Refuse the pot and ticket routes while LOTTERY_ENABLED is off.

    The landing page and the casino Mini App poll them, and a pot shown for a
    lottery that is not running would still be advertising one. A middleware
    for the same reason as casino_switch.
    """
    path = request.url.path
    if (path == "/pot" or path == "/api/v1/lottery" or path.startswith("/api/v1/lottery/")) \
            and not LOTTERY_ENABLED:
        return JSONResponse({"error": "lottery disabled"}, status_code=503)
    return await call_next(request)


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
        "withdraw_paused": "⏸️ **Withdrawals are paused**\n\nTON withdrawals are switched off for now. Your balance is unchanged and no wallet was saved.",
        "withdraw_failed": "❌ **Withdrawal Failed**\n\n{amount} TON is held on your account for review. Please contact support.",
        "lottery_payout_paused": "⏸️ Automatic TON payouts are paused.\n\nYour prize of {amount} TON is recorded and held for you. It is not part of your /withdraw balance; it will be paid when payouts resume.",
        "lottery_prize_held": "🏆 Your prize of {amount} TON is recorded and held for you. No payout wallet is on file, so it will be paid by hand. It is not part of your /withdraw balance.",
        "lottery_payout_review": "⚠️ Sending your prize of {amount} TON did not confirm. It is held for review so it cannot be paid twice. Please contact support.",
        "casino_paused": "⏸️ **The casino is paused**\n\nIt is switched off for now. Your chips are unchanged.",
        "lottery_unavailable": "⏸️ **The lottery is not available**\n\nThere are no tickets, no pot and no draw. Sealing works as usual.",
        "ton_payment_credited": "✅ **Payment Received!**\n\n{amount} TON credited. You can now seal one file or contract.\n\nSend me a file or contract address! 🔒",
        "ton_payment_short": "✅ **Payment Received!**\n\n{amount} TON credited. Your balance is {balance} TON and one seal costs {price} TON.\n\nSend {short} TON more with the memo `{memo}` to seal.",
        "ton_seal_need_payment": "💎 **Pay with TON**\n\nSend **{price} TON** to:\n`{wallet}`\n\n**Memo:** `{memo}`\n\nYour file is kept. Once the payment is credited (about 3 minutes), tap the button below to seal it.",
        "ton_paid_button": "✅ I've paid, seal it",
        "seal_retry_unpaid": "⚠️ **Not paid yet**\n\nThis file has no payment behind it. Pay with Stars or TON, then seal it.",
        "api_requires_sub": "⚠️ **API access requires a subscription**\n\nSubscribe first, then run /api to get your key.",
        "ton_credit_send_file": "✅ **Payment received**\n\nYour TON credit is ready. Send your file again and I'll seal it.",
        "ton_not_credited_yet": "⏳ Your payment is not credited yet. It usually takes up to about 3 minutes. Tap again in a minute.",
        "casino_paused_checkout": "The casino is paused, so chips cannot be bought right now. You were not charged.",
        "referral_link_line": "🎁 **Your referral link:** {url}\n5% of every payment from people you refer.",
        "api_key_issued": "🔌 **NotaryTON API**\n\n**Your API key:** `{key}`\n\nKeep it secret. It is shown only once and replaces any key you had before. Run /api again for a new one.\n\n**Endpoints:**\n• POST {url}/api/v1/notarize\n• POST {url}/api/v1/batch\n• GET {url}/api/v1/verify/{{hash}}\n\nSend the key as `api_key` in the JSON body.",
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
        "withdraw_paused": "⏸️ **Вывод средств приостановлен**\n\nВывод TON сейчас отключён. Ваш баланс не изменился, кошелёк не сохранён.",
        "withdraw_failed": "❌ **Вывод не выполнен**\n\n{amount} TON удержаны на вашем счёте для проверки. Пожалуйста, свяжитесь с поддержкой.",
        "lottery_payout_paused": "⏸️ Автоматические выплаты TON приостановлены.\n\nВаш выигрыш {amount} TON записан и зарезервирован для вас. Он не входит в баланс /withdraw и будет выплачен, когда выплаты возобновятся.",
        "lottery_prize_held": "🏆 Ваш выигрыш {amount} TON записан и зарезервирован для вас. Кошелёк для выплаты не указан, поэтому он будет выплачен вручную. Он не входит в баланс /withdraw.",
        "lottery_payout_review": "⚠️ Отправка вашего выигрыша {amount} TON не подтвердилась. Он удержан для проверки, чтобы не быть выплаченным дважды. Пожалуйста, свяжитесь с поддержкой.",
        "casino_paused": "⏸️ **Казино приостановлено**\n\nСейчас оно отключено. Ваши фишки не изменились.",
        "lottery_unavailable": "⏸️ **Лотерея недоступна**\n\nНет ни билетов, ни банка, ни розыгрыша. Печати работают как обычно.",
        "ton_payment_credited": "✅ **Платёж получен!**\n\nЗачислено {amount} TON. Теперь вы можете запечатать один файл или контракт.\n\nОтправьте мне файл или адрес контракта! 🔒",
        "ton_payment_short": "✅ **Платёж получен!**\n\nЗачислено {amount} TON. Ваш баланс {balance} TON, одна печать стоит {price} TON.\n\nОтправьте ещё {short} TON с комментарием `{memo}`, чтобы запечатать.",
        "ton_seal_need_payment": "💎 **Оплата в TON**\n\nОтправьте **{price} TON** на:\n`{wallet}`\n\n**Комментарий:** `{memo}`\n\nВаш файл сохранён. Когда платёж будет зачислен (около 3 минут), нажмите кнопку ниже, чтобы запечатать его.",
        "ton_paid_button": "✅ Я оплатил, запечатать",
        "seal_retry_unpaid": "⚠️ **Ещё не оплачено**\n\nЗа этот файл нет оплаты. Оплатите Звёздами или TON, затем запечатайте.",
        "api_requires_sub": "⚠️ **Доступ к API требует подписки**\n\nСначала оформите подписку, затем выполните /api, чтобы получить ключ.",
        "ton_credit_send_file": "✅ **Платёж получен**\n\nВаш TON-кредит готов. Отправьте файл ещё раз, и я его запечатаю.",
        "ton_not_credited_yet": "⏳ Платёж ещё не зачислен. Обычно это занимает до 3 минут. Нажмите ещё раз через минуту.",
        "casino_paused_checkout": "Казино приостановлено, поэтому фишки сейчас купить нельзя. С вас ничего не списано.",
        "referral_link_line": "🎁 **Ваша реферальная ссылка:** {url}\n5% с каждого платежа приглашённых вами людей.",
        "api_key_issued": "🔌 **NotaryTON API**\n\n**Ваш API-ключ:** `{key}`\n\nХраните его в секрете. Он показывается только один раз и заменяет прежний ключ. Выполните /api снова, чтобы получить новый.\n\n**Эндпоинты:**\n• POST {url}/api/v1/notarize\n• POST {url}/api/v1/batch\n• GET {url}/api/v1/verify/{{hash}}\n\nПередавайте ключ как `api_key` в теле JSON.",
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
        "withdraw_paused": "⏸️ **提款已暂停**\n\nTON提款目前已关闭。您的余额未变,也未保存钱包地址。",
        "withdraw_failed": "❌ **提款失败**\n\n{amount} TON已保留在您的账户中等待审核。请联系客服。",
        "lottery_payout_paused": "⏸️ TON自动派奖已暂停。\n\n您的奖金 {amount} TON 已记录并为您保留。它不计入 /withdraw 余额,将在派奖恢复后支付。",
        "lottery_prize_held": "🏆 您的奖金 {amount} TON 已记录并为您保留。您尚未设置收款钱包,因此将人工支付。它不计入 /withdraw 余额。",
        "lottery_payout_review": "⚠️ 您的奖金 {amount} TON 发送未得到确认。为避免重复支付,已保留待审核。请联系客服。",
        "casino_paused": "⏸️ **赌场已暂停**\n\n目前已关闭。您的筹码未变。",
        "lottery_unavailable": "⏸️ **彩票暂不可用**\n\n目前没有彩票、奖池或开奖。封存功能照常使用。",
        "ton_payment_credited": "✅ **已收到付款!**\n\n已入账 {amount} TON。现在可以封存一个文件或合约。\n\n发送文件或合约地址给我! 🔒",
        "ton_payment_short": "✅ **已收到付款!**\n\n已入账 {amount} TON。您的余额为 {balance} TON,一次封存需要 {price} TON。\n\n请再发送 {short} TON,备注填写 `{memo}`,即可封存。",
        "ton_seal_need_payment": "💎 **使用TON支付**\n\n发送 **{price} TON** 到:\n`{wallet}`\n\n**备注:** `{memo}`\n\n您的文件已保留。付款入账后(约3分钟),点击下方按钮进行封存。",
        "ton_paid_button": "✅ 我已付款,封存",
        "seal_retry_unpaid": "⚠️ **尚未付款**\n\n此文件没有对应的付款。请先用星星或TON支付,然后封存。",
        "api_requires_sub": "⚠️ **API访问需要订阅**\n\n请先订阅,然后运行 /api 获取密钥。",
        "ton_credit_send_file": "✅ **已收到付款**\n\n您的TON额度已到账。请重新发送文件,我会为您封存。",
        "ton_not_credited_yet": "⏳ 您的付款尚未入账,通常最多需要约3分钟。请一分钟后再点一次。",
        "casino_paused_checkout": "赌场已暂停,目前无法购买筹码。您未被扣款。",
        "referral_link_line": "🎁 **您的推荐链接:** {url}\n您推荐的用户每笔付款,您可获得5%。",
        "api_key_issued": "🔌 **NotaryTON API**\n\n**您的API密钥:** `{key}`\n\n请妥善保密。它只显示一次,并会替换您之前的密钥。再次运行 /api 可获取新密钥。\n\n**接口:**\n• POST {url}/api/v1/notarize\n• POST {url}/api/v1/batch\n• GET {url}/api/v1/verify/{{hash}}\n\n请在JSON请求体中以 `api_key` 发送密钥。",
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

def get_text(user_id: int, key: str, /, **kwargs) -> str:
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


async def localized(user_id: int, key: str, /, **kwargs) -> str:
    """get_text in the user's saved language; English if the lookup fails.

    A message about money must still go out when the language lookup cannot.
    user_id and key are positional-only, so a template field named "key"
    (api_key_issued's {key}) is a format argument, not a clash.
    """
    try:
        await get_user_language(user_id)
    except Exception:
        pass
    return get_text(user_id, key, **kwargs)


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


async def _dm(user_id: int, text: str) -> bool:
    """Send a DM through whichever bot can reach the user. True if one did."""
    for send_bot in [memeseal_bot, bot]:
        if send_bot:
            try:
                await send_bot.send_message(user_id, text, parse_mode="Markdown")
                return True
            except Exception as e:
                print(f"⚠️ Could not DM {user_id} via {send_bot}: {e}")
    return False


async def legacy_lottery_voided() -> bool:
    """True once POST /admin/void-legacy-lottery has run. Any doubt reads as False."""
    try:
        return bool(await db.lottery.legacy_entries_voided())
    except Exception as e:
        print(f"⚠️ Could not read the legacy lottery void record: {type(e).__name__}: {e}")
        return False


async def enter_lottery(user_id: int, amount_stars: int) -> None:
    """Enter a payment or wager in the lottery. Nothing while LOTTERY_ENABLED is off.

    Every entry goes through here, so no payment path can buy a ticket
    while the lottery is off.
    """
    if LOTTERY_ENABLED:
        await db.lottery.add_entry(user_id, amount_stars=amount_stars)


def lottery_tickets_line(ticket_count: int, pot_grew_ton: str = "") -> str:
    """A seal message's ticket (and pot) lines and the blank line after them.

    "" while LOTTERY_ENABLED is off, so no message counts tickets or a pot
    that the lottery is not running.
    """
    if not LOTTERY_ENABLED:
        return ""
    lines = f"🎰 Lottery tickets: {ticket_count}\n"
    if pot_grew_ton:
        lines += f"💰 Pot grew +{pot_grew_ton} TON\n"
    return lines + "\n"


async def execute_lottery_draw():
    """Run one draw: pick a winner, tell them, and settle the prize.

    The prize goes into the lottery_prizes ledger, never into
    users.referral_earnings: /withdraw pays that balance, and a prize there
    would be cashed out by WITHDRAWALS_ENABLED alone. Nothing is drawn at
    all while LOTTERY_ENABLED is off, or until the legacy entries have been
    voided (POST /admin/void-legacy-lottery). TON leaves the service wallet
    only when LOTTERY_AUTO_PAYOUT_ENABLED is on and the winner has a wallet
    on file; every other case holds the prize for the operator.
    """
    from datetime import timezone

    if not LOTTERY_ENABLED:
        # Picking a winner and recording a prize is the lottery, paid or not.
        print("⏸️ LOTTERY DRAW SKIPPED: LOTTERY_ENABLED is off. Nothing was drawn, "
              "announced or recorded.")
        return None

    print("🎰 LOTTERY DRAW STARTING...")

    if not await legacy_lottery_voided():
        # The open pot may still hold the forged entries from before Round 1.
        # Drawing it would turn them into a recorded prize, a DM promising
        # payment and a public announcement, and the void would then find
        # nothing to void. So nothing is drawn until the operator decides.
        print("🚨 LOTTERY DRAW SKIPPED: the legacy lottery entries were never voided (bot_state key "
              f"{LEGACY_LOTTERY_VOID_KEY} is absent). Nothing was drawn, announced or recorded; "
              "the entries stay in the pot. Call POST /admin/void-legacy-lottery once, after "
              "auditing referral_earnings and casino chips, to start the weekly draws.")
        return None

    total_entries = await db.lottery.get_total_entries()
    if total_entries == 0:
        print("⚠️ No lottery entries - skipping draw")
        return None

    # Generate draw ID from timestamp
    draw_id = int(datetime.now(timezone.utc).timestamp())

    # Pick the winner! The prize is what this draw claimed, not a pot read
    # before the claim: an entry bought in between is in both or neither.
    result = await db.lottery.pick_winner(draw_id)

    if not result:
        print(f"❌ Lottery draw failed - no winner selected")
        return None

    winner_id = result.winner_id
    pot_stars = result.pot_stars
    pot_ton = result.pot_ton
    total_entries = result.entries

    print(f"🏆 LOTTERY WINNER: User {winner_id} wins {pot_stars} ⭐ ({pot_ton:.4f} TON)!")

    # Notify winner via DM
    winner_msg = (
        f"🏆🎰 **YOU WON THE LOTTERY!** 🎰🏆\n\n"
        f"Prize: **{pot_stars} ⭐** ({pot_ton:.4f} TON)\n"
        f"Entries: {total_entries} tickets in this draw\n\n"
        f"Congratulations, degen! 🐸"
    )
    await _dm(winner_id, winner_msg)

    # Announce on socials
    try:
        await social_poster.post_lottery_winner(winner_id, pot_ton, pot_stars)
    except Exception as e:
        print(f"⚠️ Could not post winner to socials: {e}")

    amount = f"{pot_ton:.4f}"
    try:
        if not LOTTERY_AUTO_PAYOUT_ENABLED:
            # Payouts are off: record the prize, move no TON, and say so.
            await db.lottery.record_prize(draw_id, winner_id, pot_ton, "held")
            print(f"✅ Prize of {amount} TON held for user {winner_id} (auto-payout disabled)")
            await _dm(winner_id, await localized(winner_id, "lottery_payout_paused", amount=amount))
            return winner_id

        winner = await db.users.get(winner_id)
        if not (winner and winner.withdrawal_wallet and pot_ton >= MIN_WITHDRAWAL_TON):
            # No wallet or pot too small: hold it for a manual payout.
            await db.lottery.record_prize(draw_id, winner_id, pot_ton, "held")
            print(f"✅ Prize of {amount} TON held for user {winner_id} (no wallet or below minimum)")
            await _dm(winner_id, await localized(winner_id, "lottery_prize_held", amount=amount))
            return winner_id

        # Recorded before the send, so a crash mid-send leaves a trace.
        await db.lottery.record_prize(draw_id, winner_id, pot_ton, "sending")
        try:
            await send_payout_transaction(
                winner.withdrawal_wallet,
                pot_ton,
                f"MemeSeal Lottery Win! {pot_stars} Stars"
            )
        except Exception as payout_err:
            # The transfer may have reached the chain before this raised (a
            # liteserver timeout after acceptance, close_all failing), so the
            # prize is held for review, never credited for a second payout.
            print(f"⚠️ Lottery payout of {amount} TON to user {winner_id} failed, held for review: "
                  f"{type(payout_err).__name__}: {payout_err}")
            await db.lottery.record_prize(draw_id, winner_id, pot_ton, "review")
            await _dm(winner_id, await localized(winner_id, "lottery_payout_review", amount=amount))
            return winner_id

        await db.lottery.record_prize(draw_id, winner_id, pot_ton, "paid")
        print(f"✅ Auto-payout {amount} TON to {winner.withdrawal_wallet[:20]}...")
        payout_msg = f"💸 **{amount} TON** sent to your wallet!\nCheck: tonscan.org/address/{winner.withdrawal_wallet}"
        await _dm(winner_id, payout_msg)
    except Exception as e:
        print(f"⚠️ Could not process winner payout: {type(e).__name__}: {e}")
    return winner_id


def next_lottery_draw_after(now):
    """The first Sunday 00:00 UTC strictly after `now`.

    Strictly after: the old loop computed today's midnight whenever it was
    still hour 0 on a Sunday, so right after a draw it slept a negative time
    and drew again, over and over, until 01:00.
    """
    days_until_sunday = (6 - now.weekday()) % 7
    next_draw = (now + timedelta(days=days_until_sunday)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    if next_draw <= now:
        next_draw += timedelta(days=7)
    return next_draw


# Module-level so tests can replace the waits of the background loops without
# patching asyncio.sleep for the whole process.
_sleep = asyncio.sleep
# Likewise for the background seal tasks the MemeSeal handlers start.
_spawn = asyncio.create_task


# 🎰 LOTTERY DRAW TASK - picks winner every Sunday at 00:00 UTC (midnight)
async def run_sunday_lottery_draw():
    """Background task: Run lottery draw every Sunday at 00:00 UTC (midnight)"""
    from datetime import timezone

    # The draw this loop last woke for. A sleep can end a little early (the
    # event loop's clock is not the wall clock), and measuring from "now"
    # would then schedule that same Sunday again and draw twice.
    last_draw = None
    while True:
        try:
            now = datetime.now(timezone.utc)
            next_draw = next_lottery_draw_after(now if last_draw is None else max(now, last_draw))
            sleep_seconds = (next_draw - now).total_seconds()
            hours_until = sleep_seconds / 3600
            print(f"🎰 Lottery draw scheduled for {next_draw.strftime('%Y-%m-%d %H:%M UTC')} ({hours_until:.1f}h from now)")

            # Sleep until draw time
            await _sleep(sleep_seconds)
            last_draw = next_draw

            # === DRAW TIME ===
            await execute_lottery_draw()

        except Exception as e:
            print(f"❌ Lottery draw error: {e}")
            # Don't crash - sleep 1 hour and retry
            await _sleep(3600)


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

# A TON payment's comment is the payer's Telegram user id and nothing else.
# The whole comment must be the id: searching for any digits would pull a
# number out of a seal hash or an API caller's project name.
_MEMO_USER_ID = re.compile(r"\s*(\d{1,19})\s*")


def decode_text_comment(body) -> str:
    """The text comment in a message body, or "" if it has none.

    A text comment is op 0 (32 bits) followed by a snake-encoded UTF-8 string,
    which is what wallets (and pytoniq, for our own seals) write. Any other
    body, including an empty one or one with a non-zero op, is not a comment.
    """
    if body is None:
        return ""
    try:
        s = body.begin_parse()
        if s.remaining_bits < 32 or s.load_uint(32) != 0:
            return ""
        return s.load_snake_string()
    except Exception:
        return ""


def parse_incoming_payment(tx, service_address):
    """(amount_nano, memo, src) for a TON payment into the service wallet, else None.

    Only an internal, non-bounced message from another address is a payment.
    The wallet's own outgoing transactions start with an external message, and
    every seal is a transfer from the service wallet to itself whose comment
    can carry text an API caller chose, so both are skipped.
    """
    msg = getattr(tx, "in_msg", None)
    info = getattr(msg, "info", None)
    if not isinstance(info, InternalMsgInfo) or info.bounced:
        return None
    src = info.src
    if not isinstance(src, Address):
        return None
    if isinstance(service_address, str):
        service_address = Address(service_address)
    if src.to_str(is_user_friendly=False) == service_address.to_str(is_user_friendly=False):
        return None
    return info.value_coins, decode_text_comment(msg.body), src


def memo_user_id(memo: str):
    """The Telegram user id a payment comment names, or None."""
    match = _MEMO_USER_ID.fullmatch(memo or "")
    if not match:
        return None
    user_id = int(match.group(1))
    return user_id if 0 < user_id < 2**63 else None


# A payment below this is dust and credits nothing (the old single-seal floor).
TON_MIN_CREDIT = 0.014
# A payment at or above this buys a month (0.3 TON, less a little for fees).
TON_SUBSCRIPTION_CREDIT = 0.28


async def _notify_user(user_id: int, text: str) -> None:
    """Best-effort DM about a payment. A failed DM never undoes a credit."""
    for b in [bot, memeseal_bot]:
        if b:
            try:
                await b.send_message(user_id, text, parse_mode="Markdown")
                return
            except Exception:
                pass


async def credit_incoming_payment(user_id: int, amount_ton: float, progress: dict | None = None,
                                  tx_key: str | None = None):
    """Credit one TON payment to user_id. Payer first, referrer last.

    The payer's credit comes first so that a failure part way leaves the
    payer paid and, at worst, a referrer commission missing, never the
    reverse. Once the payer is credited, progress["payer_credited"] is set
    and the ledger row says 'payer_credited', so a later failure is never
    read as "the payer was not paid". process_incoming_payment records the rest.
    """
    if amount_ton >= TON_SUBSCRIPTION_CREDIT:
        await add_subscription(user_id, months=1)
    else:
        await db.users.ensure_exists(user_id)
        await db.users.add_payment(user_id, amount_ton)
    if progress is not None:
        progress["payer_credited"] = True
    if tx_key:
        await db.ton_payments.set_status(tx_key, "payer_credited")

    if amount_ton >= TON_SUBSCRIPTION_CREDIT:
        await enter_lottery(user_id, 20)
        print(f"✅ Activated subscription for user {user_id}")
        text = (
            "✅ **Subscription Activated!**\n\n"
            "You now have unlimited notarizations for 30 days!\n\n"
            "Send me a file or contract address to seal it! 🔒"
        )
    else:
        await enter_lottery(user_id, 1)
        print(f"✅ Credited {amount_ton} TON to user {user_id}")
        # Sealing needs a balance of TON_SINGLE_SEAL, so only say "you can
        # seal" when the balance really allows it; otherwise say what is short.
        balance = await db.users.get_total_paid(user_id)
        if balance >= TON_SINGLE_SEAL:
            text = await localized(user_id, "ton_payment_credited", amount=f"{amount_ton:.4f}")
        else:
            text = await localized(
                user_id, "ton_payment_short", amount=f"{amount_ton:.4f}",
                balance=f"{balance:.4f}", price=f"{TON_SINGLE_SEAL}",
                short=f"{TON_SINGLE_SEAL - balance:.4f}", memo=user_id)

    user = await db.users.get(user_id)
    if user and user.referred_by:
        commission = amount_ton * 0.05
        await db.users.add_referral_earnings(user.referred_by, commission)
        print(f"💰 Credited {commission:.4f} TON to referrer {user.referred_by}")

    await _notify_user(user_id, text)


class PaymentNotRecorded(Exception):
    """Money arrived and nothing durable says so yet (the ledger write failed).

    The poller must not move past such a transaction: it stops and reads it
    again next poll. The ledger's ON CONFLICT makes that re-read idempotent.
    """


def ton_tx_key(service_address, lt: int) -> str:
    """The idempotency key of a transaction on the service wallet: account and LT."""
    if isinstance(service_address, str):
        service_address = Address(service_address)
    return f"{service_address.to_str(is_user_friendly=False)}:{lt}"


async def process_incoming_payment(tx_key: str, amount_nano: int, memo: str) -> bool:
    """Credit a parsed payment at most once. True if this call credited it.

    The claim (an INSERT that does nothing on conflict) comes before any
    credit, so a restart, a replayed window or a second poller cannot
    credit the same transaction again. TON that cannot be credited (a memo
    that is not a user id, or dust) is recorded as 'unmatched'. If the
    claim or that record cannot be written, PaymentNotRecorded is raised and
    the poller reads the transaction again later.
    """
    amount_ton = amount_nano / 1e9
    print(f"📥 Incoming payment: {amount_ton} TON, memo: {memo[:64]!r}")
    user_id = memo_user_id(memo)
    try:
        if not user_id or amount_ton < TON_MIN_CREDIT:
            await db.ton_payments.record_uncredited(tx_key, amount_nano, memo, "unmatched")
            print(f"📝 Payment {tx_key} not credited (memo is not a user id, or below "
                  f"{TON_MIN_CREDIT} TON): recorded as 'unmatched' for review")
            return False
        claimed = await db.ton_payments.claim(tx_key, user_id, amount_nano)
    except Exception as e:
        raise PaymentNotRecorded(f"{type(e).__name__}: {e}") from e
    if not claimed:
        print(f"↩️ Payment {tx_key} already processed, skipping")
        return False
    progress = {"payer_credited": False}
    try:
        await credit_incoming_payment(user_id, amount_ton, progress, tx_key)
    except Exception:
        # 'failed': the payer was not credited. 'partial': the payer was,
        # and a later step (lottery entry, referral commission) was not.
        status = "partial" if progress["payer_credited"] else "failed"
        try:
            await db.ton_payments.set_status(tx_key, status)
        except Exception as mark_err:
            print(f"⚠️ Could not mark {tx_key} {status} (the row keeps its last status): "
                  f"{type(mark_err).__name__}")
        raise
    try:
        await db.ton_payments.set_status(tx_key, "credited")
    except Exception as e:
        print(f"⚠️ Payment {tx_key} was credited in full, but 'credited' was not recorded "
              f"(the row says 'payer_credited'): {type(e).__name__}")
    return True


# Where the poller has read up to. A new key, not the old "last_processed_lt":
# the old poller advanced that key while crediting nothing (and the TonAPI
# webhook credited instead), so resuming from it would credit again what the
# webhook already did. A missing key means: start at the wallet's newest
# transaction and credit nothing before it.
TON_POLLER_LT_KEY = "ton_poller_lt_v2"
# How far back one poll may page (pytoniq fetches 16 per round trip). More new
# transactions than this between polls is logged as a gap for reconciliation.
TON_POLL_MAX_TXS = 512
# On the first anchor, this many of the newest transactions are recorded for
# reconciliation (see _anchor_poller).
TON_ANCHOR_LOOKBACK = 64
# bot_state keys "<prefix><from_lt>:<to_lt>" mark ranges the poller skipped.
TON_POLLER_GAP_PREFIX = "ton_poller_gap:"
TON_POLL_INTERVAL = 180

# Set by the signed TonAPI webhook to make the poller look now instead of at
# its next interval. The webhook only wakes the poller; it credits nothing.
_payment_poll_wakeup = asyncio.Event()


async def _wait_for_poll(seconds: float) -> None:
    """Wait for the next poll: the interval, or sooner if the webhook fires."""
    try:
        await asyncio.wait_for(_payment_poll_wakeup.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass
    _payment_poll_wakeup.clear()


async def _load_poller_lt():
    """The stored LT, or None if none is stored. Retries until the read works.

    A failed read must not be mistaken for "no LT": starting from 0 would
    walk the whole recent history and credit it again.
    """
    delay = 5
    while True:
        try:
            value = await db.bot_state.get(TON_POLLER_LT_KEY)
            return int(value) if value is not None else None
        except Exception as e:
            print(f"⚠️ Could not load the poller position, crediting nothing until it loads "
                  f"(retry in {delay}s): {type(e).__name__}: {e}")
            await _sleep(delay)
            delay = min(delay * 2, 300)


async def _anchor_poller(client, wallet_address) -> int:
    """Set the poller's first position: the wallet's newest transaction.

    Nothing at or before it is credited. The anchor comes from the account
    state, so a wallet with no transactions yet anchors at 0 and its first
    payment is credited (pytoniq's get_transactions raises IndexError on an
    empty history). The last TON_ANCHOR_LOOKBACK incoming payments before
    the anchor are recorded as 'precutover' in ton_payments_processed: the
    old webhook may or may not have credited them, and the operator checks.
    """
    _state, shard_account = await asyncio.wait_for(
        client.raw_get_account_state(wallet_address), timeout=30)
    anchor = int(shard_account.last_trans_lt) if shard_account else 0
    if anchor:
        recent = await asyncio.wait_for(
            client.get_transactions(address=wallet_address.to_str(), count=TON_ANCHOR_LOOKBACK),
            timeout=120)
        for tx in recent:
            if tx.lt > anchor:
                continue  # arrived after the anchor: the next poll credits it
            try:
                payment = parse_incoming_payment(tx, wallet_address)
            except Exception:
                continue
            if payment is None:
                continue
            amount_nano, memo, _src = payment
            key = ton_tx_key(wallet_address, tx.lt)
            await db.ton_payments.record_uncredited(key, amount_nano, memo, "precutover")
            print(f"📝 Before the anchor, not credited by the poller: lt={tx.lt} "
                  f"{amount_nano / 1e9} TON memo={memo[:64]!r} (recorded as 'precutover')")
    await db.bot_state.set(TON_POLLER_LT_KEY, str(anchor))
    print(f"⚓ Payment poller anchored at LT {anchor}; earlier transactions are not credited")
    return anchor


async def poll_wallet_for_payments():
    """Background task: credit incoming TON payments, each exactly once."""
    wallet_address = Address(SERVICE_TON_WALLET)
    last_processed_lt = await _load_poller_lt()
    if last_processed_lt is not None:
        print(f"🔄 Resuming payment polling from LT: {last_processed_lt}")

    consecutive_errors = 0
    max_backoff = 300  # Max 5 minutes between retries

    # Reuse client to reduce memory churn (only recreate on errors)
    client = None
    client_uses = 0
    MAX_CLIENT_USES = 20  # Recreate after 20 uses to prevent memory buildup

    while True:
        try:
            # Create or recreate client as needed
            if client is None or client_uses >= MAX_CLIENT_USES:
                if client:
                    try:
                        await client.close_all()
                    except Exception:
                        pass
                client = LiteBalancer.from_mainnet_config(trust_level=1)
                await asyncio.wait_for(client.start_up(), timeout=30)
                client_uses = 0
                print("🔗 LiteBalancer client (re)initialized")

            client_uses += 1

            if last_processed_lt is None:
                # First run: anchor at the newest transaction, credit nothing.
                last_processed_lt = await _anchor_poller(client, wallet_address)
            else:
                # Everything newer than the stored LT, paging back as far as
                # TON_POLL_MAX_TXS (to_lt stops the paging at our position).
                try:
                    transactions = await asyncio.wait_for(
                        client.get_transactions(address=wallet_address.to_str(),
                                                count=TON_POLL_MAX_TXS, to_lt=last_processed_lt),
                        timeout=120
                    )
                except IndexError:
                    # pytoniq raises IndexError for an account with no
                    # transactions at all; only possible while anchored at 0.
                    if last_processed_lt:
                        raise
                    transactions = []
                transactions = [t for t in transactions if t.lt > last_processed_lt]
                transactions.sort(key=lambda x: x.lt)

                if len(transactions) >= TON_POLL_MAX_TXS:
                    oldest = transactions[0]
                    if getattr(oldest, "prev_trans_lt", 0) > last_processed_lt:
                        print(f"🚨 More than {TON_POLL_MAX_TXS} transactions since LT {last_processed_lt}: "
                              f"LT {last_processed_lt}..{oldest.prev_trans_lt} was NOT examined, reconcile by hand")
                        # Durable, so the range survives a restart and a lost log.
                        await db.bot_state.set(
                            f"{TON_POLLER_GAP_PREFIX}{last_processed_lt}:{oldest.prev_trans_lt}",
                            f"{datetime.utcnow().isoformat()}Z")

                for tx in transactions:
                    # One malformed message, or one failed credit, must not
                    # stall every payment behind it: once its row is in
                    # ton_payments_processed ('failed', 'partial' or
                    # 'claimed'), it is logged and passed. A payment with no
                    # row yet (the database refused the claim) stops the
                    # page here, unread, and is read again next poll.
                    try:
                        payment = parse_incoming_payment(tx, wallet_address)
                        if payment is not None:
                            amount_nano, memo, _src = payment
                            await process_incoming_payment(ton_tx_key(wallet_address, tx.lt), amount_nano, memo)
                    except PaymentNotRecorded as e:
                        print(f"⚠️ Payment at lt={tx.lt} could not be recorded; the poller stays at LT "
                              f"{last_processed_lt} and reads it again: {e}")
                        raise
                    except Exception as e:
                        print(f"❌ Payment at lt={tx.lt} not processed, needs manual review: {type(e).__name__}: {e}")

                    # Saved after each transaction, so a crash re-reads at most
                    # one, and the claim above makes that re-read a no-op.
                    last_processed_lt = tx.lt
                    await db.bot_state.set(TON_POLLER_LT_KEY, str(last_processed_lt))

            # Success - reset error counter
            consecutive_errors = 0

        except asyncio.TimeoutError:
            consecutive_errors += 1
            print(f"⚠️ Wallet polling timeout (attempt {consecutive_errors})")
            # Force client recreation on timeout
            if client:
                try:
                    await client.close_all()
                except Exception:
                    pass
            client = None
        except Exception as e:
            consecutive_errors += 1
            error_msg = str(e)
            # Don't spam logs with the same Liteserver error
            if "651" in error_msg:
                print(f"⚠️ Liteserver sync issue (attempt {consecutive_errors}) - will retry")
            elif "lt not in db" in error_msg or "cannot find block" in error_msg:
                # Stale liteserver state: retry with a fresh client. The LT
                # is kept on purpose. Resetting it to 0 used to replay every
                # recent payment, which would now credit them again.
                print(f"⚠️ Stale block reference detected - recreating client")
            else:
                print(f"❌ Error polling wallet (attempt {consecutive_errors}): {error_msg}")
            # Force client recreation on error
            if client:
                try:
                    await client.close_all()
                except Exception:
                    pass
            client = None

        # Exponential backoff on errors (30s -> 60s -> 120s -> 240s -> 300s max)
        if consecutive_errors > 0:
            backoff = min(30 * (2 ** (consecutive_errors - 1)), max_backoff)
            print(f"🔄 Retrying in {backoff}s...")
            await _sleep(backoff)
        else:
            await _wait_for_poll(TON_POLL_INTERVAL)

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
        f"⏱️ Activates within about 3 minutes after sending\n"
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
        f"⏱️ Credit added within about 3 minutes\n"
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

async def answer_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """Approve a Stars payment, except chips while the casino is off.

    A chip invoice made before CASINO_ENABLED was turned off can still be
    paid; the chips could not be used and there is no refund path, so the
    payment is declined before any Stars move.
    """
    payload = pre_checkout_query.invoice_payload or ""
    if payload.startswith("casino_chips_") and not CASINO_ENABLED:
        user_id = pre_checkout_query.from_user.id
        await pre_checkout_query.answer(
            ok=False, error_message=await localized(user_id, "casino_paused_checkout"))
        return
    await pre_checkout_query.answer(ok=True)


@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """Handle pre-checkout query - must respond within 10 seconds"""
    await answer_pre_checkout(pre_checkout_query)


async def credit_casino_chips(message: types.Message, user_id: int, chips_amount: int):
    """Credit chips bought with Stars (1 Star = 1 chip), from either bot.

    Chip invoices are issued by MemeSeal when it is configured, so both bots'
    successful_payment handlers come here.
    """
    await db.users.ensure_exists(user_id)
    new_balance = await db.casino.add_chips(user_id, chips_amount)

    # Bonus chips for larger purchases (Patrick Collison: price anchoring)
    bonus = 0
    if chips_amount >= 500:
        bonus = chips_amount // 5  # 20% bonus
        new_balance = await db.casino.add_chips(user_id, bonus)
    elif chips_amount >= 100:
        bonus = chips_amount // 10  # 10% bonus
        new_balance = await db.casino.add_chips(user_id, bonus)

    bonus_msg = f"\n🎁 **BONUS:** +{bonus} chips!" if bonus > 0 else ""
    pot_msg = "\n\n20% of all bets feed the lottery pot! 🎫" if LOTTERY_ENABLED else ""

    await message.answer(
        f"🎰💰 **CHIPS LOADED!**\n\n"
        f"✅ **+{chips_amount} chips** added{bonus_msg}\n"
        f"💎 **New Balance:** {new_balance} chips\n\n"
        f"🐸 **LET'S GO DEGEN!**\n\n"
        f"Open the casino to play:\n"
        f"• 🎰 Politician Slots (100x jackpot)\n"
        f"• 🚀 Frog Rocket (crash game)\n"
        f"• 🎯 Election Roulette"
        f"{pot_msg}",
        parse_mode="Markdown"
    )
    print(f"🎰 Casino chips purchased: {chips_amount} chips for user {user_id}")


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
        await enter_lottery(user_id, payment.total_amount)
        tickets_msg = ""
        if LOTTERY_ENABLED:
            ticket_count = await db.lottery.count_user_entries(user_id)
            tickets_msg = f"🎰 **+{payment.total_amount} LOTTERY TICKETS!** (Total: {ticket_count})\n"

        await message.answer(
            "✅ **Subscription Activated!**\n\n"
            "You now have **unlimited notarizations** for 30 days!\n\n"
            "Use /notarize to seal your first contract.\n"
            "Use /api to get API access for integrations.\n\n"
            f"{tickets_msg}"
            "🔒 Thank you for supporting NotaryTON!",
            parse_mode="Markdown"
        )

    elif payload.startswith("single_"):
        # Add single notarization credit
        await db.users.ensure_exists(user_id)
        await db.users.add_payment(user_id, TON_SINGLE_SEAL)

        # 🎰 LOTTERY: Add entry (1 Star = 1 ticket, 20% goes to pot)
        await enter_lottery(user_id, payment.total_amount)
        tickets_msg = ""
        if LOTTERY_ENABLED:
            ticket_count = await db.lottery.count_user_entries(user_id)
            tickets_msg = f"🎰 **+1 LOTTERY TICKET!** (Total: {ticket_count})\n"

        await message.answer(
            "✅ **Payment Received!**\n\n"
            "You can now notarize **one contract or file**.\n\n"
            "Send me:\n"
            "• A contract address (EQ...)\n"
            "• Or upload a file\n\n"
            f"{tickets_msg}"
            "🔒 I'll seal it on TON blockchain forever!",
            parse_mode="Markdown"
        )

    elif payload.startswith("casino_chips_"):
        # 🎰💰 CASINO CHIPS PURCHASE: 1 Star = 1 chip
        await credit_casino_chips(message, user_id, payment.total_amount)


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
    if LOTTERY_ENABLED:
        ticket_count = await db.lottery.count_user_entries(user_id)
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
    """Post seal announcement to X and Telegram channel (rate-limited).

    The pot and next draw are in it only while LOTTERY_ENABLED is on.
    """
    try:
        if not LOTTERY_ENABLED:
            await announce_seal(file_hash)
            return
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


async def lottery_win_chance(user_id: int) -> float:
    """The user's chance in the next draw, in percent.

    The draw is weighted by the stars behind each entry (pick_winner), so
    this is the user's stars over all stars, not a count of rows.
    """
    total = await db.lottery.get_entry_stars()
    if total <= 0:
        return 0.0
    return await db.lottery.get_entry_stars(user_id) / total * 100


@dp.message(Command("pot"))
async def cmd_pot(message: types.Message):
    """Show current lottery pot - DEGEN MODE 🎰 (Agent 8: Enhanced)"""
    user_id = message.from_user.id
    if not LOTTERY_ENABLED:
        await message.answer(await localized(user_id, "lottery_unavailable"), parse_mode="Markdown")
        return
    pot_stars = await db.lottery.get_pot_size_stars()
    pot_ton = await db.lottery.get_pot_size_ton()
    total_entries = await db.lottery.get_total_entries()
    unique_players = await db.lottery.get_unique_participants()
    user_tickets = await db.lottery.count_user_entries(user_id)
    next_draw = get_next_draw_date()
    countdown = get_countdown_to_draw()

    # Calculate user's odds
    if total_entries > 0 and user_tickets > 0:
        win_chance = await lottery_win_chance(user_id)
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
    if not LOTTERY_ENABLED:
        await message.answer(await localized(user_id, "lottery_unavailable"), parse_mode="Markdown")
        return
    ticket_count = await db.lottery.count_user_entries(user_id)
    total_entries = await db.lottery.get_total_entries()
    pot_stars = await db.lottery.get_pot_size_stars()
    pot_ton = await db.lottery.get_pot_size_ton()
    unique_players = await db.lottery.get_unique_participants()
    countdown = get_countdown_to_draw()

    win_chance = await lottery_win_chance(user_id)

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

    # Sending TON to a wallet the user names is a transfer at the user's
    # request: off unless WITHDRAWALS_ENABLED. Checked first, so a paused
    # /withdraw changes nothing, the saved wallet included (the lottery
    # auto-payout would otherwise pay whatever address was last registered).
    if not WITHDRAWALS_ENABLED:
        await message.answer(await localized(user_id, "withdraw_paused"), parse_mode="Markdown")
        return

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

    # Record the withdrawal before sending. The old order (send, then record)
    # let two concurrent commands both read the same balance and both pay it.
    # reserve_withdrawal debits under a row lock, so the second one gets 0.
    amount = await db.users.reserve_withdrawal(user_id, MIN_WITHDRAWAL_TON)
    if amount <= 0:
        await message.answer(
            f"⚠️ **Minimum Withdrawal: {MIN_WITHDRAWAL_TON} TON**\n\n"
            f"Your balance: {0:.4f} TON\n\n"
            f"Keep sharing your /referral link to earn more!",
            parse_mode="Markdown"
        )
        return

    try:
        await send_payout_transaction(
            destination=wallet_address,
            amount_ton=amount,
            memo=f"NotaryTON Referral Payout"
        )
    except Exception as e:
        # The send may have reached the chain before it raised, so the amount
        # stays reserved and an operator reconciles it; refunding here could
        # pay twice. The user sees no exception text.
        print(f"❌ Withdrawal of {amount:.4f} TON for user {user_id} failed, held for review: {type(e).__name__}: {e}")
        await message.answer(
            await localized(user_id, "withdraw_failed", amount=f"{amount:.4f}"),
            parse_mode="Markdown"
        )
        return

    await message.answer(
        f"✅ **Withdrawal Sent!**\n\n"
        f"**Amount:** {amount:.4f} TON\n"
        f"**To:** `{wallet_address[:20]}...`\n\n"
        f"TX will appear in ~30 seconds.\n"
        f"Check: tonscan.org/address/{wallet_address}",
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
        await message.answer(await localized(user_id, "api_requires_sub"), parse_mode="Markdown")
        return

    key = await issue_api_key(user_id)
    await message.answer(
        await localized(user_id, "api_key_issued", key=key, url=WEBHOOK_URL),
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


async def deduct_credit(user_id: int) -> bool:
    """Take one seal's credit before the seal is sent. True if it was taken.

    One conditional UPDATE: check_user_can_notarize is only a read, and
    concurrent updates (an album, parallel webhook delivery) all pass it,
    so the debit itself is the check. One credit pays for one seal.
    """
    return await db.users.deduct_payment(user_id, TON_SINGLE_SEAL)


async def take_seal_payment(user_id: int, has_sub: bool) -> bool:
    """Pay for one seal now: free for a subscriber, else one credit, atomically."""
    return has_sub or await deduct_credit(user_id)


async def give_back_seal_payment(user_id: int, has_sub: bool) -> None:
    """A seal that was paid for and not sent gives its credit back."""
    if has_sub:
        return
    try:
        await db.users.add_payment(user_id, TON_SINGLE_SEAL)
    except Exception as e:
        print(f"⚠️ Could not give back a seal credit to {user_id}, needs manual review: {type(e).__name__}")


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

    # Paid before the seal is sent, given back if it is not.
    if not await take_seal_payment(user_id, has_sub):
        await message.reply(
            "⚠️ **Payment Required**\n\n"
            f"Contract detected: `{contract_id[:20]}...`\n\n"
            "Choose how to pay:",
            parse_mode="Markdown",
            reply_markup=get_payment_keyboard()
        )
        return

    # Notarize the contract
    sent = False
    try:
        await message.reply("⏳ Fetching contract and sealing on TON...")

        contract_code = await get_contract_code_from_tx(contract_id)
        if not contract_code:
            await give_back_seal_payment(user_id, has_sub)
            await message.reply(
                "❌ **Could not fetch contract**\n\n"
                "Make sure the address is valid and the contract is deployed.",
                parse_mode="Markdown"
            )
            return

        contract_hash = hash_data(contract_code)
        comment = f"NotaryTON:Contract:{contract_hash[:16]}"
        await send_ton_transaction(comment, amount_ton=TON_SINGLE_SEAL)
        sent = True
        await log_notarization(user_id, contract_id, contract_hash, paid=True)

        await message.reply(
            f"✅ **SEALED!**\n\n"
            f"Contract: `{contract_id[:30]}...`\n"
            f"Hash: `{contract_hash}`\n\n"
            f"🔗 Verify: {WEBHOOK_URL}/api/v1/verify/{contract_hash}\n\n"
            f"Sealed on TON blockchain forever! 🔒",
            parse_mode="Markdown"
        )
    except Exception as e:
        if not sent:
            await give_back_seal_payment(user_id, has_sub)
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

    # Paid before the seal is sent, given back if it is not.
    if not await take_seal_payment(user_id, has_sub):
        await message.answer(
            "⚠️ **Payment Required to Notarize**\n\n"
            "Choose how to pay:",
            parse_mode="Markdown",
            reply_markup=get_payment_keyboard()
        )
        return

    file_path = None
    sent = False
    try:
        # Download file
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        file_path = f"downloads/{file_id}"
        os.makedirs("downloads", exist_ok=True)
        await bot.download_file(file.file_path, file_path)

        # Hash it
        file_hash = hash_file(file_path)
        comment = f"NotaryTON:File:{file_hash[:16]}"

        await send_ton_transaction(comment)
        sent = True
        await log_notarization(user_id, "manual_file", file_hash, paid=True)

        await message.answer(
            f"✅ **SEALED!**\n\n"
            f"File: `{message.document.file_name}`\n"
            f"Hash: `{file_hash}`\n\n"
            f"🔗 Verify: {WEBHOOK_URL}/api/v1/verify/{file_hash}\n\n"
            f"Proof stored on TON blockchain forever! 🔒",
            parse_mode="Markdown"
        )
    except Exception as e:
        if not sent:
            await give_back_seal_payment(user_id, has_sub)
        await message.answer(f"❌ Error: {str(e)}")

    # Clean up
    try:
        if file_path:
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

    # Paid before the seal is sent, given back if it is not.
    if not await take_seal_payment(user_id, has_sub):
        await message.answer(
            "📸 **Nice screenshot!**\n\n"
            "3 Stars to seal it on TON forever.\n"
            "Proof you were there. 🔐",
            parse_mode="Markdown",
            reply_markup=get_payment_keyboard()
        )
        return

    file_path = None
    sent = False
    try:
        # Download largest photo
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_path = f"downloads/{photo.file_id}.jpg"
        os.makedirs("downloads", exist_ok=True)
        await bot.download_file(file.file_path, file_path)

        file_hash = hash_file(file_path)
        comment = f"NotaryTON:Screenshot:{file_hash[:12]}"

        await send_ton_transaction(comment)
        sent = True
        await log_notarization(user_id, "screenshot", file_hash, paid=True)

        await message.answer(
            f"✅ **SCREENSHOT SEALED!**\n\n"
            f"Hash: `{file_hash}`\n\n"
            f"🔗 Verify: {WEBHOOK_URL}/api/v1/verify/{file_hash}\n\n"
            f"Proof secured on TON forever! 🔒",
            parse_mode="Markdown"
        )
    except Exception as e:
        if not sent:
            await give_back_seal_payment(user_id, has_sub)
        await message.answer(f"❌ Error: {str(e)}")

    try:
        if file_path:
            os.remove(file_path)
    except Exception:
        pass


# ========================
# MEMESEAL TON HANDLERS (Degen branding)
# ========================

# MemeSeal callbacks that decide whether a seal is paid for. Module level (and
# registered inside the block below) so tests can drive them without a
# MemeSeal token. background_seal_ton / background_seal_stars are defined in
# that block and looked up when a callback runs.

async def memeseal_ton_single(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    # Taken out synchronously, so two taps cannot both seal the same file.
    file_info = pending_files.pop(user_id, None)
    if file_info is None:
        await callback.answer()
        can_notarize, _has_sub = await check_user_can_notarize(user_id)
        if can_notarize:
            # The file expired while the payment was being credited: the
            # credit is there, so ask for the file, not for another payment.
            await callback.message.answer(
                await localized(user_id, "ton_credit_send_file"), parse_mode="Markdown")
            return
        await callback.message.answer(
            f"💎 **Pay with TON**\n\n"
            f"Send **0.15 TON** to:\n"
            f"`{SERVICE_TON_WALLET}`\n\n"
            f"**Memo:** `{user_id}`\n\n"
            f"Then send your file - I'll seal it instantly! 🐸⚡",
            parse_mode="Markdown"
        )
        return

    if file_info.get("paid"):
        # Already paid (a Stars seal that failed): seal it, charge nothing,
        # and keep the payment on the file if this attempt fails too.
        await callback.answer()
        await _seal_paid_file(user_id, file_info, callback.message.answer)
        return

    # Seal only against a credited payment, taken in one conditional debit
    # before the seal. This button used to seal straight away with no
    # payment at all, and every seal costs the service wallet fees. A TON
    # payment is credited by the poller.
    can_notarize, has_sub = await check_user_can_notarize(user_id)
    if not (can_notarize and await take_seal_payment(user_id, has_sub)):
        # Kept for the next tap, with a fresh timestamp: the payment can take
        # minutes to be credited, and the file must outlive that.
        already_asked = file_info.get("ton_payment_asked", False)
        file_info["ton_payment_asked"] = True
        file_info["timestamp"] = time.time()
        pending_files[user_id] = file_info
        if already_asked:
            # The instructions were shown already: a short "not yet", not
            # the whole payment request again.
            await callback.answer(await localized(user_id, "ton_not_credited_yet"), show_alert=True)
            return
        await callback.answer()
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=await localized(user_id, "ton_paid_button"),
                                        callback_data="ms_pay_ton_single")],
        ])
        await callback.message.answer(
            await localized(user_id, "ton_seal_need_payment", price=f"{TON_SINGLE_SEAL}",
                            wallet=SERVICE_TON_WALLET, memo=user_id),
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return

    await callback.answer()
    file_info.pop("ton_payment_asked", None)
    file_info["paid"] = True
    file_info["charged_credit"] = not has_sub

    # ✅ HONEST PROGRESS - show real status, no fake success
    progress_msg = await callback.message.answer(
        f"⏳ **SEALING TO BLOCKCHAIN...**\n\n"
        f"Your file is being timestamped on TON.\n"
        f"This takes 5-15 seconds.\n\n"
        f"_Please wait..._",
        parse_mode="Markdown"
    )

    # 🔥 BACKGROUND SEAL - do the actual work
    _spawn(background_seal_ton(
        user_id=user_id,
        file_info=file_info,
        message_to_edit=progress_msg
    ))


async def _seal_paid_file(user_id: int, file_info: dict, send) -> None:
    """Seal a file whose payment already went through, charging nothing.

    background_seal_stars keeps the file's paid flag when the seal fails,
    so a later retry still seals it for free.
    """
    progress_msg = await send(
        f"⏳ **RETRYING...**\n\n"
        f"Sealing to blockchain.\n"
        f"This takes 5-15 seconds.\n\n"
        f"_Please wait..._",
        parse_mode="Markdown"
    )
    ticket_count = await db.lottery.count_user_entries(user_id)
    _spawn(background_seal_stars(
        user_id=user_id,
        file_info=file_info,
        message_to_edit=progress_msg,
        ticket_count=ticket_count
    ))


async def memeseal_retry_seal(callback: types.CallbackQuery):
    """Handle retry button for failed seals"""
    user_id = callback.from_user.id
    await callback.answer("🔄 Retrying...")

    file_info = pending_files.pop(user_id, None)
    if file_info is None:
        await callback.message.edit_text(
            "⚠️ **Session Expired**\n\n"
            "Please send your file again to seal it.",
            parse_mode="Markdown"
        )
        return

    # pending_files also holds files nobody has paid for yet (a file sent
    # without credit waits there for payment). A retry seals only a file
    # whose payment went through, or one a credit now covers.
    if not file_info.get("paid"):
        can_notarize, has_sub = await check_user_can_notarize(user_id)
        if not (can_notarize and await take_seal_payment(user_id, has_sub)):
            pending_files[user_id] = file_info
            await callback.message.answer(
                await localized(user_id, "seal_retry_unpaid"),
                parse_mode="Markdown",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="⭐ Pay 3 Stars & Seal Now", callback_data="ms_pay_stars_single")],
                    [types.InlineKeyboardButton(text="💎 Pay 0.15 TON instead", callback_data="ms_pay_ton_single")],
                ])
            )
            return
        file_info["paid"] = True

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
    _spawn(background_seal_stars(
        user_id=user_id,
        file_info=file_info,
        message_to_edit=progress_msg,
        ticket_count=ticket_count
    ))


async def memeseal_payment_success(message: types.Message):
    """MemeSeal's successful Stars payment: chips, a subscription, or one seal."""
    user_id = message.from_user.id
    payment = message.successful_payment
    payload = payment.invoice_payload

    if payload.startswith("casino_chips_"):
        # Chip invoices come from this bot (api_casino_buy_chips): the
        # Stars buy chips, not a seal credit. Wagers make lottery entries.
        await credit_casino_chips(message, user_id, payment.total_amount)
        return

    # 🎰 LOTTERY: Add entry for EVERY payment
    await db.users.ensure_exists(user_id)
    await enter_lottery(user_id, payment.total_amount)
    ticket_count = await db.lottery.count_user_entries(user_id)

    if "sub" in payload:
        await add_subscription(user_id, months=1)
        tickets_msg = (f"🎰 **+{payment.total_amount} LOTTERY TICKETS!**\n"
                       f"Total tickets: {ticket_count}\n\n") if LOTTERY_ENABLED else ""
        await message.answer(
            "🚨 **UNLIMITED MODE ACTIVATED** 🟢\n\n"
            "⚡ 30 days of infinite seals unlocked!\n\n"
            f"{tickets_msg}"
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
                f"{lottery_tickets_line(ticket_count)}"
                f"_Please wait..._",
                parse_mode="Markdown"
            )

            # Seal in background
            _spawn(background_seal_stars(
                user_id=user_id,
                file_info=file_info,
                message_to_edit=progress_msg,
                ticket_count=ticket_count
            ))
        else:
            await db.users.add_payment(user_id, TON_SINGLE_SEAL)
            tickets_msg = f"🎰 **+1 LOTTERY TICKET!** ({ticket_count} total)\n" if LOTTERY_ENABLED else ""
            await message.answer(
                "🚨 **PAYMENT CONFIRMED** 🟢\n\n"
                "1 ⭐ Star received!\n\n"
                "Now send me what you want sealed.\n"
                "File, screenshot, whatever.\n\n"
                f"{tickets_msg}"
                "🐸⚡",
                parse_mode="Markdown"
            )


async def memeseal_api(message: types.Message):
    """MemeSeal's /api: a key for subscribers, and everyone's referral link.

    MemeSeal has no /referral command, so this is where its users find the
    link. It points at NotaryTON, whose /start records the referrer;
    MemeSeal's /start reads its argument as a promo code and records none.
    """
    user_id = message.from_user.id
    referral = await localized(user_id, "referral_link_line",
                               url=f"https://t.me/{BOT_USERNAME}?start=REF{user_id}")
    if not await get_user_subscription(user_id):
        await message.answer(
            await localized(user_id, "api_requires_sub") + "\n\n" + referral, parse_mode="Markdown")
        return
    key = await issue_api_key(user_id)
    await message.answer(
        await localized(user_id, "api_key_issued", key=key, url=WEBHOOK_URL) + "\n\n" + referral,
        parse_mode="Markdown"
    )


async def memeseal_casino(message: types.Message):
    """Open the casino mini app"""
    if not CASINO_ENABLED:
        await message.answer(await localized(message.from_user.id, "casino_paused"), parse_mode="Markdown")
        return
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="🎰 OPEN CASINO",
            web_app=WebAppInfo(url="https://casino.notaryton.com")
        )]
    ])
    pot_line = "• 20% of ALL bets feed the lottery pot\n" if LOTTERY_ENABLED else ""

    await message.answer(
        "🎰🐸 **MEMESEAL CASINO**\n\n"
        "**GAMES:**\n"
        "• 🎰 Politician Slots (100x jackpot)\n"
        "• 🚀 Frog Rocket (crash game)\n"
        "• 🎯 Election Roulette\n\n"
        "**THE DEAL:**\n"
        f"{pot_line}"
        "• Connect TON wallet to play\n"
        "• Win big or feed the frogs\n\n"
        "Tap below to enter the casino 👇",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


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

        lottery_step = "**4.** 🎰 Get lottery ticket (20% feeds pot!)\n" if LOTTERY_ENABLED else ""
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
            f"{lottery_step}\n"
            "👇 **Send something to seal it forever**"
            f"{free_seal_msg}"
        )

        # Add helpful buttons. The casino button only while the casino API
        # is on: with it off every call the Mini App makes answers 503.
        buttons = []
        if CASINO_ENABLED:
            buttons.append([types.InlineKeyboardButton(
                text="🎰 PLAY CASINO",
                web_app=WebAppInfo(url="https://casino.notaryton.com")
            )])
        if LOTTERY_ENABLED:
            buttons.append([types.InlineKeyboardButton(text="💰 Check Lottery Pot", callback_data="ms_check_pot")])
        buttons += [
            [types.InlineKeyboardButton(text="🚀 Go Unlimited (20 ⭐/mo)", callback_data="ms_pay_stars_sub")]
        ]
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)

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
        if not LOTTERY_ENABLED:
            await callback.message.answer(
                await localized(callback.from_user.id, "lottery_unavailable"), parse_mode="Markdown")
            return
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

    memeseal_dp.callback_query(F.data == "ms_pay_ton_single")(memeseal_ton_single)

    async def _give_back_ton_seal_credit(user_id: int, file_info: dict):
        """A seal that did not happen gives its credit back.

        The file is then unpaid again, so "Try Again" checks for a credit
        once more instead of sealing for free.
        """
        if file_info.pop("charged_credit", False):
            try:
                await db.users.add_payment(user_id, TON_SINGLE_SEAL)
            except Exception as e:
                print(f"⚠️ Could not give back a seal credit to {user_id}, needs manual review: {type(e).__name__}")
        file_info["paid"] = False

    async def background_seal_ton(user_id: int, file_info: dict, message_to_edit):
        """Background task to seal file and update message with real link"""
        file_hash = None
        file_path = None
        sealed = False

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
                # The TON payment that bought this credit already earned its
                # ticket when the poller credited it.
                ticket_count = await db.lottery.count_user_entries(user_id)

                # ✅ UPDATE MESSAGE WITH REAL LINK
                await message_to_edit.edit_text(
                    f"🚨 **TON PAYMENT CONFIRMED** 🟢\n\n"
                    f"✅ **SEALED FOREVER!** 🐸⚡\n\n"
                    f"Hash: `{file_hash}`\n"
                    f"🔗 Verify: notaryton.com/api/v1/verify/{file_hash}\n\n"
                    f"{lottery_tickets_line(ticket_count, '0.003')}"
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
                await _give_back_ton_seal_credit(user_id, file_info)
                pending_files[user_id] = file_info

        except Exception as e:
            print(f"❌ Background seal error: {e}")
            if not sealed:
                await _give_back_ton_seal_credit(user_id, file_info)
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

    memeseal_dp.pre_checkout_query()(answer_pre_checkout)

    memeseal_dp.message(F.successful_payment)(memeseal_payment_success)

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
                f"{lottery_tickets_line(ticket_count, '0.002')}"
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
                        f"{lottery_tickets_line(ticket_count)}"
                        f"_We'll keep trying automatically!_",
                        parse_mode="Markdown",
                        reply_markup=retry_keyboard
                    )
                    # Store for retry; the Stars invoice was paid.
                    file_info["paid"] = True
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
                    file_info["paid"] = True
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
    memeseal_dp.callback_query(F.data == "ms_retry_seal")(memeseal_retry_seal)

    memeseal_dp.message(Command("api"))(memeseal_api)

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
        if not LOTTERY_ENABLED:
            await message.answer(
                await localized(message.from_user.id, "lottery_unavailable"), parse_mode="Markdown")
            return
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

    memeseal_dp.message(Command("casino"))(memeseal_casino)

    @memeseal_dp.message(Command("mytickets"))
    async def memeseal_mytickets(message: types.Message):
        """Show user's lottery tickets - DEGEN STYLE"""
        user_id = message.from_user.id
        if not LOTTERY_ENABLED:
            await message.answer(await localized(user_id, "lottery_unavailable"), parse_mode="Markdown")
            return
        ticket_count = await db.lottery.count_user_entries(user_id)
        win_chance = await lottery_win_chance(user_id)

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

        # Paid before the seal is sent (one credit, one seal), given back if it is not.
        if not await take_seal_payment(user_id, has_sub):
            await message.answer(await localized(user_id, "no_sub"), parse_mode="Markdown")
            return

        file_path = None
        sent = False
        try:
            # Download and seal
            file_id = message.document.file_id
            file = await memeseal_bot.get_file(file_id)
            file_path = f"downloads/{file_id}"
            os.makedirs("downloads", exist_ok=True)
            await memeseal_bot.download_file(file.file_path, file_path)

            file_hash = hash_file(file_path)
            comment = f"MemeSeal:{file_hash[:16]}"

            await send_ton_transaction(comment)
            sent = True
            await log_notarization(user_id, "memeseal_file", file_hash, paid=True)

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
            if not sent:
                await give_back_seal_payment(user_id, has_sub)
            await message.answer(f"❌ Seal failed: {str(e)}")

        try:
            if file_path:
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

        # Paid before the seal is sent (one credit, one seal), given back if it is not.
        if not await take_seal_payment(user_id, has_sub):
            await message.answer(await localized(user_id, "no_sub"), parse_mode="Markdown")
            return

        file_path = None
        sent = False
        try:
            # Download largest photo
            photo = message.photo[-1]
            file = await memeseal_bot.get_file(photo.file_id)
            file_path = f"downloads/{photo.file_id}.jpg"
            os.makedirs("downloads", exist_ok=True)
            await memeseal_bot.download_file(file.file_path, file_path)

            file_hash = hash_file(file_path)
            comment = f"MemeSeal:Screenshot:{file_hash[:12]}"

            await send_ton_transaction(comment)
            sent = True
            await log_notarization(user_id, "memeseal_photo", file_hash, paid=True)

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
            if not sent:
                await give_back_seal_payment(user_id, has_sub)
            await message.answer(f"❌ Seal failed: {str(e)}")

        try:
            if file_path:
                os.remove(file_path)
        except Exception:
            pass

# ========================
# FASTAPI ENDPOINTS
# ========================

def telegram_secret_ok(request: Request) -> bool:
    """True only if the update carries the secret_token we registered with Telegram."""
    if not TELEGRAM_WEBHOOK_SECRET:
        return False
    given = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    return hmac.compare_digest(given.encode(), TELEGRAM_WEBHOOK_SECRET.encode())

def admin_ok(request: Request) -> bool:
    """True only if ADMIN_SECRET is set and the X-Admin-Secret header matches it."""
    if not ADMIN_SECRET:
        return False
    given = request.headers.get("X-Admin-Secret", "")
    return hmac.compare_digest(given.encode(), ADMIN_SECRET.encode())

@app.post(WEBHOOK_PATH)
async def webhook_handler(request: Request):
    """Handle incoming webhook updates from Telegram (NotaryTON)"""
    if not telegram_secret_ok(request):
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
    update = Update(**(await request.json()))
    await dp.feed_update(bot, update)
    return {"ok": True}

# MemeSeal webhook endpoint
if MEMESEAL_WEBHOOK_PATH:
    @app.post(MEMESEAL_WEBHOOK_PATH)
    async def memeseal_webhook_handler(request: Request):
        """Handle incoming webhook updates from Telegram (MemeSeal)"""
        if not telegram_secret_ok(request):
            return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
        update = Update(**(await request.json()))
        await memeseal_dp.feed_update(memeseal_bot, update)
        return {"ok": True}

# MemeScan webhook endpoint (meme coin terminal)
if MEMESCAN_WEBHOOK_PATH:
    @app.post(MEMESCAN_WEBHOOK_PATH)
    async def memescan_webhook_handler(request: Request):
        """Handle incoming webhook updates from Telegram (MemeScan)"""
        if not telegram_secret_ok(request):
            return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
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
    A signed TonAPI notice that the service wallet saw a transaction.

    It wakes the payment poller and credits nothing itself. It used to credit
    from the webhook body as well, with no source check and a loose digit
    match on the comment, and with no shared record of what was credited: the
    same payment was credited once here and once by the poller, and the
    bot's own seals (self-transfers whose comment an API caller chooses)
    were credited as payments. The poller is now the one crediting path,
    and it reads the transaction from the chain, not from this body.
    """
    # Fail closed: without a secret anyone could make us poll on demand.
    if not TONAPI_WEBHOOK_SECRET:
        print("⚠️ TonAPI webhook rejected: TONAPI_WEBHOOK_SECRET is not set")
        return JSONResponse({"ok": False, "error": "Webhook not configured"}, status_code=503)
    body = await request.body()
    signature = request.headers.get("X-TonAPI-Signature", "")
    expected = hmac.new(
        TONAPI_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        print(f"⚠️ TonAPI webhook: Invalid signature")
        return JSONResponse({"ok": False, "error": "Invalid signature"}, status_code=401)

    _payment_poll_wakeup.set()
    return {"ok": True, "queued": True}


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
        # Fail closed: without a secret anyone could POST forged contract events.
        if not TONCONSOLE_CASINO_SECRET:
            print("⚠️ Casino webhook rejected: TONCONSOLE_CASINO_SECRET is not set")
            return JSONResponse({"ok": False, "error": "Webhook not configured"}, status_code=503)
        body = await request.body()
        signature = request.headers.get("X-Signature", "")
        expected = hmac.new(
            TONCONSOLE_CASINO_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            print(f"⚠️ Casino webhook: Invalid signature")
            return JSONResponse({"ok": False, "error": "Invalid signature"}, status_code=401)

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
        # Fail closed: without a secret anyone could POST forged contract events.
        if not TONCONSOLE_TOKENS_SECRET:
            print("⚠️ Tokens webhook rejected: TONCONSOLE_TOKENS_SECRET is not set")
            return JSONResponse({"ok": False, "error": "Webhook not configured"}, status_code=503)
        body = await request.body()
        signature = request.headers.get("X-Signature", "")
        expected = hmac.new(
            TONCONSOLE_TOKENS_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            print(f"⚠️ Tokens webhook: Invalid signature")
            return JSONResponse({"ok": False, "error": "Invalid signature"}, status_code=401)

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
    return ("<html><head><title>MemeSeal Terms</title><style>body{background:#0d0d0d;color:#00ff41;font-family:monospace;padding:40px;max-width:800px;margin:0 auto}h1{color:#39ff14}h2{color:#00ffff;margin-top:30px}a{color:#ff00ff}</style></head><body><h1>MemeSeal Terms of Service</h1><p>Last updated: December 2024</p><h2>1. Acceptance</h2><p>By using MemeSeal, you agree to these terms.</p><h2>2. Service</h2><p>MemeSeal provides blockchain timestamping on TON." + (" 20% of fees go to lottery pot." if LOTTERY_ENABLED else "") + "</p><h2>3. Payments</h2><p>Payments via Telegram Stars or TON are final.</p><h2>4. No Guarantees</h2><p>Service provided as-is. DYOR. NFA.</p><h2>5. Contact</h2><p><a href='https://t.me/MemeSealTON'>Telegram</a></p></body></html>")


@app.get("/memescan", response_class=HTMLResponse)
async def memescan_landing(request: Request):
    """MemeScan - TON Meme Terminal Landing Page"""
    return templates.TemplateResponse(request, "memescan/landing.html")


@app.get("/memescan/litepaper", response_class=HTMLResponse)
async def memescan_litepaper(request: Request):
    """MemeScan Litepaper - readable whitepaper"""
    return templates.TemplateResponse(request, "memescan/litepaper.html")


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

    Now with ENTITY DETECTION from ton-labels (2,958 known addresses):
    - Scammers: Instant 0 score, red badge, CRITICAL warning
    - CEX/DEX: High score, verified entity badge
    - Validators: Highest trust score

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

        # ENTITY DETECTION: Check known_wallets first
        known = await db.wallets.get_wallet_label(address)
        if known:
            import json
            extra = {}
            if known.notes:
                try:
                    extra = json.loads(known.notes)
                except:
                    pass

            category = known.label
            entity_scores = {
                'validator': 95, 'cex': 85, 'dex': 80, 'bridge': 75,
                'liquid_staking': 80, 'lending': 75, 'infrastructure': 80,
                'fund': 70, 'merchant': 65, 'gaming': 60, 'tradingbot': 60,
                'scammer': 0, 'scripted-activity': 40,
            }

            if category == 'scammer':
                subcategory = extra.get('subcategory', '')
                warnings = [f"🚨 KNOWN SCAMMER: {known.owner_name or 'Unknown'}"]
                if subcategory:
                    warnings.append(f"⚠️ Type: {subcategory.replace('_', ' ').title()}")
                if extra.get('description'):
                    warnings.append(f"ℹ️ {extra['description']}")

                return {
                    "success": True,
                    "score": 0,
                    "badge": "red",
                    "verdict": "SCAMMER",
                    "token": {"address": address, "symbol": "⚠️", "name": known.owner_name or "SCAMMER", "holder_count": 0, "top_wallet_percent": 0},
                    "warnings": warnings,
                    "entityInfo": {"category": category, "label": known.owner_name, "website": extra.get('website')},
                    "powered_by": "notaryton.com"
                }

            # Known good entity
            score = entity_scores.get(category, 60)
            badge = "green" if score >= 80 else "yellow"
            verdict = "VERIFIED" if score >= 80 else "KNOWN"

            return {
                "success": True,
                "score": score,
                "badge": badge,
                "verdict": verdict,
                "token": {"address": address, "symbol": "✓", "name": known.owner_name or category.upper(), "holder_count": 0, "top_wallet_percent": 0},
                "warnings": [],
                "entityInfo": {
                    "category": category,
                    "label": known.owner_name,
                    "website": extra.get('website'),
                    "verified": True
                },
                "powered_by": "notaryton.com"
            }

        # No known entity - proceed with token analysis
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


# ========================
# LIVE TOKEN FEED - SSE
# ========================

from decimal import Decimal

def json_serialize(obj):
    """Custom JSON serializer for types not serializable by default."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

async def token_event_generator():
    """Server-Sent Events generator for live token feed."""
    last_count = 0
    while True:
        try:
            # Get latest tokens
            tokens = await db.tokens.get_recent(limit=5)
            stats = await db.tokens.get_stats()

            # Build event data (convert Decimals to float for JSON)
            data = {
                "stats": stats,
                "latest": [
                    {
                        "address": t.address,
                        "symbol": t.symbol,
                        "name": t.name,
                        "score": int(t.safety_score) if t.safety_score else 0,
                        "holders": int(t.current_holder_count) if t.current_holder_count else 0,
                        "top_pct": round(float(t.current_top_holder_pct or 0), 1),
                        "rugged": bool(t.rugged),
                        "badge": "green" if (t.safety_score or 0) >= 80 else ("yellow" if (t.safety_score or 0) >= 50 else "red"),
                        "time": t.first_seen.strftime("%H:%M:%S") if t.first_seen else None,
                    }
                    for t in tokens
                ],
                "new_count": stats["total_tracked"] - last_count if last_count > 0 else 0,
            }
            last_count = stats["total_tracked"]

            yield f"data: {json.dumps(data, default=json_serialize)}\n\n"
            await asyncio.sleep(5)  # Update every 5 seconds

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            await asyncio.sleep(10)


@app.get("/api/v1/tokens/live")
async def api_live_token_feed():
    """Live token feed via Server-Sent Events."""
    return StreamingResponse(
        token_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )


@app.get("/feed", response_class=HTMLResponse)
async def live_feed_page():
    """Live token scanner feed - cyberpunk style."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LIVE FEED - MemeScan</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Space Mono', monospace;
            background: #0a0a0f;
            color: #00ff88;
            min-height: 100vh;
            overflow-x: hidden;
        }
        .scanlines {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: repeating-linear-gradient(
                0deg,
                rgba(0,0,0,0.1) 0px,
                rgba(0,0,0,0.1) 1px,
                transparent 1px,
                transparent 2px
            );
            pointer-events: none;
            z-index: 1000;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header {
            border-bottom: 2px solid #00ff88;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        h1 {
            font-size: 2rem;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .live-dot {
            width: 12px; height: 12px;
            background: #ff0040;
            border-radius: 50%;
            animation: pulse 1s infinite;
            box-shadow: 0 0 10px #ff0040;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.2); }
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-box {
            background: #111;
            border: 1px solid #00ff8844;
            padding: 15px;
            text-align: center;
        }
        .stat-value {
            font-size: 2rem;
            font-weight: bold;
        }
        .stat-label { font-size: 0.7rem; color: #888; margin-top: 5px; }
        .tokens { display: flex; flex-direction: column; gap: 10px; }
        .token {
            background: #111;
            border: 1px solid #00ff8844;
            padding: 15px;
            display: grid;
            grid-template-columns: 1fr auto auto auto;
            gap: 20px;
            align-items: center;
            transition: all 0.3s;
            animation: slideIn 0.5s ease-out;
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(-20px); }
            to { opacity: 1; transform: translateX(0); }
        }
        .token:hover { border-color: #00ff88; background: #1a1a2e; }
        .token-info h3 { font-size: 1rem; margin-bottom: 5px; }
        .token-info .addr { font-size: 0.65rem; color: #666; }
        .badge {
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.7rem;
            font-weight: bold;
        }
        .badge.green { background: #00ff8833; color: #00ff88; border: 1px solid #00ff88; }
        .badge.yellow { background: #ffaa0033; color: #ffaa00; border: 1px solid #ffaa00; }
        .badge.red { background: #ff004033; color: #ff0040; border: 1px solid #ff0040; }
        .score { font-size: 1.5rem; font-weight: bold; }
        .time { color: #666; font-size: 0.8rem; }
        .new-alert {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #00ff88;
            color: #000;
            padding: 15px 25px;
            font-weight: bold;
            animation: fadeIn 0.3s;
            z-index: 999;
        }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        footer {
            margin-top: 50px;
            text-align: center;
            color: #444;
            font-size: 0.8rem;
        }
        footer a { color: #00ff88; }
    </style>
</head>
<body>
    <div class="scanlines"></div>
    <div class="container">
        <header>
            <h1>
                <span class="live-dot"></span>
                MEMESCAN LIVE FEED
                <span style="color: #666; font-size: 0.8rem;">v1.0</span>
            </h1>
        </header>

        <div class="stats">
            <div class="stat-box">
                <div class="stat-value" id="total">-</div>
                <div class="stat-label">TOKENS TRACKED</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="safe" style="color: #00ff88;">-</div>
                <div class="stat-label">SAFE (80+)</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="rugged" style="color: #ff0040;">-</div>
                <div class="stat-label">RUGGED</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="rate">-</div>
                <div class="stat-label">RUG RATE %</div>
            </div>
        </div>

        <h2 style="margin-bottom: 15px; color: #888; font-size: 0.9rem;">LATEST DISCOVERIES</h2>
        <div class="tokens" id="tokens"></div>

        <footer>
            Powered by <a href="https://notaryton.com">NotaryTON</a> | Data updates every 5 seconds
        </footer>
    </div>

    <div id="alert" class="new-alert" style="display: none;"></div>

    <script>
        const evtSource = new EventSource('/api/v1/tokens/live');
        let lastTotal = 0;

        evtSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.error) return;

            // Update stats
            document.getElementById('total').textContent = data.stats.total_tracked;
            document.getElementById('safe').textContent = data.stats.safe_count;
            document.getElementById('rugged').textContent = data.stats.rugged_count;
            document.getElementById('rate').textContent = data.stats.rug_rate + '%';

            // Show alert for new tokens
            if (data.new_count > 0 && lastTotal > 0) {
                const alert = document.getElementById('alert');
                alert.textContent = `+${data.new_count} NEW TOKEN${data.new_count > 1 ? 'S' : ''} DETECTED`;
                alert.style.display = 'block';
                setTimeout(() => alert.style.display = 'none', 3000);
            }
            lastTotal = data.stats.total_tracked;

            // Update token list
            const container = document.getElementById('tokens');
            container.innerHTML = data.latest.map(t => `
                <div class="token">
                    <div class="token-info">
                        <h3>${t.symbol || '???'}</h3>
                        <div class="addr">${t.address.slice(0, 12)}...${t.address.slice(-8)}</div>
                    </div>
                    <div class="badge ${t.badge}">${t.badge.toUpperCase()}</div>
                    <div class="score" style="color: ${t.badge === 'green' ? '#00ff88' : (t.badge === 'yellow' ? '#ffaa00' : '#ff0040')}">${t.score}</div>
                    <div class="time">${t.time || '-'}</div>
                </div>
            `).join('');
        };

        evtSource.onerror = () => console.log('SSE reconnecting...');
    </script>
</body>
</html>
"""


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


# ========================
# KOL INTELLIGENCE API - THE DATA MOAT
# ========================

# Initialize KOL repository lazily
_kol_repo = None

async def get_kol_repo():
    """Get or create KOL repository."""
    global _kol_repo
    if _kol_repo is None:
        from kol_repository import KOLRepository
        _kol_repo = KOLRepository(db.pool)
        await _kol_repo.init_schema()
    return _kol_repo


@app.get("/api/v1/kols")
async def api_kols_list(
    chain: str = None,
    category: str = None,
    min_reputation: int = 0,
    limit: int = 50
):
    """List tracked KOLs with optional filters."""
    try:
        repo = await get_kol_repo()
        kols = await repo.list_all(
            chain_focus=chain,
            category=category,
            min_reputation=min_reputation,
            limit=min(limit, 100)
        )
        return {
            "success": True,
            "count": len(kols),
            "kols": [
                {
                    "id": k.id,
                    "name": k.name,
                    "x_handle": k.x_handle,
                    "telegram_channel": k.telegram_channel,
                    "chain_focus": k.chain_focus,
                    "category": k.category,
                    "tier": k.tier,
                    "total_calls": k.total_calls,
                    "win_rate": k.win_rate,
                    "rug_rate": k.rug_rate,
                    "avg_return_pct": k.avg_return_pct,
                    "best_call_return": k.best_call_return,
                    "reputation_score": k.reputation_score,
                    "verified_wallet": k.verified_wallet,
                }
                for k in kols
            ],
            "powered_by": "notaryton.com"
        }
    except Exception as e:
        print(f"KOL list error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/v1/kols/leaderboard")
async def api_kols_leaderboard(limit: int = 20):
    """Get top-performing KOLs by win rate."""
    try:
        repo = await get_kol_repo()
        leaders = await repo.get_leaderboard(limit=min(limit, 50))
        return {
            "success": True,
            "leaderboard": leaders,
            "powered_by": "notaryton.com"
        }
    except Exception as e:
        print(f"Leaderboard error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/v1/kols/stats")
async def api_kols_stats():
    """Get KOL tracking statistics."""
    try:
        repo = await get_kol_repo()
        stats = await repo.get_stats()
        return {
            "success": True,
            "stats": stats,
            "powered_by": "notaryton.com"
        }
    except Exception as e:
        print(f"KOL stats error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/v1/kols/{kol_id}")
async def api_kol_detail(kol_id: int):
    """Get detailed KOL profile."""
    try:
        repo = await get_kol_repo()
        kol = await repo.get(kol_id)
        if not kol:
            return {"success": False, "error": "KOL not found"}

        wallets = await repo.get_kol_wallets(kol_id)

        return {
            "success": True,
            "kol": {
                "id": kol.id,
                "name": kol.name,
                "x_handle": kol.x_handle,
                "telegram_handle": kol.telegram_handle,
                "telegram_channel": kol.telegram_channel,
                "chain_focus": kol.chain_focus,
                "category": kol.category,
                "tier": kol.tier,
                "x_followers": kol.x_followers,
                "avg_likes": kol.avg_likes,
                "avg_views": kol.avg_views,
                "total_calls": kol.total_calls,
                "winning_calls": kol.winning_calls,
                "rug_calls": kol.rug_calls,
                "win_rate": kol.win_rate,
                "rug_rate": kol.rug_rate,
                "avg_return_pct": kol.avg_return_pct,
                "best_call_return": kol.best_call_return,
                "reputation_score": kol.reputation_score,
                "verified_wallet": kol.verified_wallet,
                "notes": kol.notes,
                "first_seen": kol.first_seen.isoformat() if kol.first_seen else None,
                "last_active": kol.last_active.isoformat() if kol.last_active else None,
            },
            "wallets": [
                {
                    "address": w.wallet_address,
                    "chain": w.chain,
                    "verified": w.verified,
                    "total_trades": w.total_trades,
                    "total_pnl_usd": w.total_pnl_usd,
                }
                for w in wallets
            ],
            "powered_by": "notaryton.com"
        }
    except Exception as e:
        print(f"KOL detail error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/v1/kols/calls/recent")
async def api_kol_calls_recent(chain: str = None, limit: int = 50):
    """Get recent KOL calls."""
    try:
        repo = await get_kol_repo()
        calls = await repo.get_recent_calls(chain=chain, limit=min(limit, 100))
        return {
            "success": True,
            "count": len(calls),
            "calls": calls,
            "powered_by": "notaryton.com"
        }
    except Exception as e:
        print(f"Recent calls error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/v1/kols/calls/token/{token_address}")
async def api_kol_calls_for_token(token_address: str):
    """Get all KOL calls for a specific token."""
    try:
        repo = await get_kol_repo()
        calls = await repo.get_calls_for_token(token_address)
        return {
            "success": True,
            "token_address": token_address,
            "count": len(calls),
            "calls": calls,
            "powered_by": "notaryton.com"
        }
    except Exception as e:
        print(f"Token calls error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/v1/kols/wallet/{wallet_address}")
async def api_kol_by_wallet(wallet_address: str):
    """Find KOL associated with a wallet address."""
    try:
        repo = await get_kol_repo()
        result = await repo.find_kol_by_wallet(wallet_address)
        if result:
            return {
                "success": True,
                "found": True,
                "kol": result,
                "powered_by": "notaryton.com"
            }
        return {
            "success": True,
            "found": False,
            "message": "No KOL linked to this wallet"
        }
    except Exception as e:
        print(f"Wallet lookup error: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/v1/kols/seed")
async def api_kol_seed(request: Request):
    """Seed database with Grok KOL intel (admin only)."""
    if not admin_ok(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    try:
        repo = await get_kol_repo()
        count = await repo.seed_from_grok()
        return {
            "success": True,
            "seeded": count,
            "message": f"Added {count} new KOLs from Grok intel"
        }
    except Exception as e:
        print(f"Seed error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/v1/kols/by-language/{lang}")
async def api_kols_by_language(lang: str, limit: int = 50):
    """Filter KOLs by language code (en, ru, zh, etc.)."""
    try:
        repo = await get_kol_repo()
        kols = await repo.get_by_language(lang.lower(), limit)
        return {
            "success": True,
            "language": lang.lower(),
            "count": len(kols),
            "kols": [kol.to_dict() for kol in kols]
        }
    except Exception as e:
        print(f"KOL language filter error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/v1/kols/by-category/{category}")
async def api_kols_by_category(category: str, limit: int = 50):
    """Filter KOLs by category (general, ton, watchdog, solana, cross_chain, regional)."""
    try:
        repo = await get_kol_repo()
        kols = await repo.get_by_category(category.lower(), limit)
        return {
            "success": True,
            "category": category.lower(),
            "count": len(kols),
            "kols": [kol.to_dict() for kol in kols]
        }
    except Exception as e:
        print(f"KOL category filter error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/v1/kols/by-chain/{chain}")
async def api_kols_by_chain(chain: str, limit: int = 50):
    """Filter KOLs by chain focus (ton, sol, eth, btc, multi, etc.)."""
    try:
        repo = await get_kol_repo()
        kols = await repo.get_by_chain(chain.lower(), limit)
        return {
            "success": True,
            "chain": chain.lower(),
            "count": len(kols),
            "kols": [kol.to_dict() for kol in kols]
        }
    except Exception as e:
        print(f"KOL chain filter error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/v1/kols/filters")
async def api_kol_filters():
    """Get available filter options for KOL queries."""
    try:
        repo = await get_kol_repo()
        languages = await repo.get_available_languages()
        categories = await repo.get_available_categories()
        chains = await repo.get_available_chains()
        return {
            "success": True,
            "filters": {
                "languages": languages,
                "categories": categories,
                "chains": chains
            }
        }
    except Exception as e:
        print(f"KOL filters error: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# TON ID OAUTH INTEGRATION
# =============================================================================

@app.get("/auth/tonid/start")
async def tonid_auth_start(user_id: int = None):
    """
    Start TON ID OAuth flow.
    Returns authorization URL for redirect.
    """
    try:
        from tonid import start_auth_session, TONID_CLIENT_ID

        if not TONID_CLIENT_ID:
            return {"success": False, "error": "TON ID not configured. Contact @boldov for CLIENT_ID."}

        auth_url, pkce = start_auth_session(user_id or 0)

        return {
            "success": True,
            "auth_url": auth_url,
            "state": pkce.state,
            "message": "Redirect user to auth_url"
        }
    except Exception as e:
        print(f"TON ID start error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/auth/tonid/callback")
async def tonid_auth_callback(code: str = None, state: str = None, error: str = None):
    """
    TON ID OAuth callback handler.
    Exchanges code for tokens and stores verified user.
    """
    from starlette.responses import RedirectResponse

    if error:
        return RedirectResponse(url=f"https://notaryton.com/?auth_error={error}")

    if not code or not state:
        return RedirectResponse(url="https://notaryton.com/?auth_error=missing_params")

    try:
        from tonid import complete_auth

        user = await complete_auth(code, state)

        if not user:
            return RedirectResponse(url="https://notaryton.com/?auth_error=auth_failed")

        # Store verified user in database
        await db.execute("""
            INSERT INTO verified_users (
                telegram_id, tonid_sub, wallet_address, wallet_raw,
                name, picture_url, twitter_verified, youtube_verified
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (telegram_id) DO UPDATE SET
                tonid_sub = EXCLUDED.tonid_sub,
                wallet_address = EXCLUDED.wallet_address,
                wallet_raw = EXCLUDED.wallet_raw,
                name = EXCLUDED.name,
                picture_url = EXCLUDED.picture_url,
                twitter_verified = EXCLUDED.twitter_verified,
                youtube_verified = EXCLUDED.youtube_verified,
                updated_at = NOW()
        """,
            user.telegram_id,
            user.sub,
            user.wallet_address,
            user.wallet_raw,
            user.name,
            user.picture,
            user.twitter_verified,
            user.youtube_verified
        )

        print(f"✅ TON ID verified: TG={user.telegram_id}, wallet={user.wallet_address}")

        # Redirect to success page
        return RedirectResponse(url=f"https://notaryton.com/?verified=true&wallet={user.wallet_address or ''}")

    except Exception as e:
        print(f"TON ID callback error: {e}")
        return RedirectResponse(url=f"https://notaryton.com/?auth_error=server_error")


@app.get("/api/v1/verified/{telegram_id}")
async def api_get_verified_user(telegram_id: int):
    """Get verified user info by Telegram ID"""
    try:
        row = await db.fetchrow("""
            SELECT telegram_id, tonid_sub, wallet_address, name, picture_url,
                   twitter_verified, youtube_verified, is_kol, kol_id, verified_at
            FROM verified_users WHERE telegram_id = $1
        """, telegram_id)

        if not row:
            return {"success": False, "error": "User not verified"}

        return {
            "success": True,
            "verified": True,
            "user": {
                "telegram_id": row["telegram_id"],
                "tonid_sub": row["tonid_sub"],
                "wallet": row["wallet_address"],
                "name": row["name"],
                "picture": row["picture_url"],
                "twitter_verified": row["twitter_verified"],
                "youtube_verified": row["youtube_verified"],
                "is_kol": row["is_kol"],
                "kol_id": row["kol_id"],
                "verified_at": row["verified_at"].isoformat() if row["verified_at"] else None
            }
        }
    except Exception as e:
        print(f"Verified user lookup error: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/v1/verified/link-kol")
async def api_link_verified_to_kol(telegram_id: int, kol_id: int):
    """Link a verified user to their KOL profile"""
    try:
        # Check if user is verified
        verified = await db.fetchrow(
            "SELECT id FROM verified_users WHERE telegram_id = $1",
            telegram_id
        )

        if not verified:
            return {"success": False, "error": "User must be verified with TON ID first"}

        # Check if KOL exists
        kol = await db.fetchrow("SELECT id, name FROM kols WHERE id = $1", kol_id)
        if not kol:
            return {"success": False, "error": "KOL not found"}

        # Link them
        await db.execute("""
            UPDATE verified_users
            SET is_kol = TRUE, kol_id = $1, updated_at = NOW()
            WHERE telegram_id = $2
        """, kol_id, telegram_id)

        print(f"✅ Linked TG {telegram_id} to KOL {kol['name']}")

        return {
            "success": True,
            "message": f"Linked to KOL: {kol['name']}",
            "kol_id": kol_id
        }
    except Exception as e:
        print(f"KOL link error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/v1/verified/stats")
async def api_verified_stats():
    """Get verification statistics"""
    try:
        total = await db.fetchval("SELECT COUNT(*) FROM verified_users")
        with_wallet = await db.fetchval(
            "SELECT COUNT(*) FROM verified_users WHERE wallet_address IS NOT NULL"
        )
        twitter_verified = await db.fetchval(
            "SELECT COUNT(*) FROM verified_users WHERE twitter_verified = TRUE"
        )
        kols_verified = await db.fetchval(
            "SELECT COUNT(*) FROM verified_users WHERE is_kol = TRUE"
        )

        return {
            "success": True,
            "stats": {
                "total_verified": total,
                "with_wallet": with_wallet,
                "twitter_verified": twitter_verified,
                "kols_verified": kols_verified
            }
        }
    except Exception as e:
        print(f"Verified stats error: {e}")
        return {"success": False, "error": str(e)}


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
    return templates.TemplateResponse(request, "verify.html", {"memeseal_username": MEMESEAL_USERNAME})


@app.get("/memeseal")
async def memeseal_redirect():
    """Redirect /memeseal to root for backwards compatibility"""
    return RedirectResponse(url="/", status_code=301)


@app.get("/whitepaper", response_class=HTMLResponse)
async def whitepaper(request: Request):
    """FROGS FOREVER - The Vision"""
    return templates.TemplateResponse(request, "whitepaper.html")


@app.get("/", response_class=HTMLResponse)
async def landing_page_memeseal(request: Request):
    """MemeSeal TON - Main landing page"""
    return templates.TemplateResponse(request, "landing.html", {
        "memeseal_username": MEMESEAL_USERNAME,
        "lottery_enabled": LOTTERY_ENABLED,
    })

@app.get("/notaryton", response_class=HTMLResponse)
async def landing_page_legacy(request: Request):
    """Legacy NotaryTON landing page"""
    return templates.TemplateResponse(request, "notaryton.html", {
        "bot_username": BOT_USERNAME
    })

@app.get("/score", response_class=HTMLResponse)
async def rugscore_page(request: Request):
    """Rug Score landing page - marketing hook for token safety checks"""
    return templates.TemplateResponse(request, "score.html")

# ========================
# PUBLIC API ENDPOINTS (Make NotaryTON essential infrastructure)
# ========================

# ========================
# API KEYS
# ========================
# The API used to take the caller's Telegram user id as its key. Ids are
# public, so anyone could name any subscriber and make the service wallet
# pay the fees of a 0.15 TON self-transfer per call, without limit. A key is
# now a random secret shown once by /api; only its SHA-256 is stored.

API_KEY_PREFIX = "nt_"
# Seals one key may order per hour, counted per process (each worker keeps its
# own count, so the effective limit is this times the number of workers).
API_SEALS_PER_HOUR = _positive_int_env("API_SEALS_PER_HOUR", 30)
_api_seal_times = {}  # user_id -> deque of seal timestamps in the last hour


def api_key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def issue_api_key(user_id: int) -> str:
    """A new API key for user_id, replacing any earlier one. Returns it in clear, once."""
    key = API_KEY_PREFIX + secrets.token_urlsafe(32)
    await db.api_keys.replace_for_user(user_id, api_key_hash(key))
    return key


async def api_key_user(data):
    """(user_id, None) for a body carrying a valid API key, else (None, 401 response)."""
    key = data.get("api_key") if isinstance(data, dict) else None
    if not isinstance(key, str) or not key.startswith(API_KEY_PREFIX) or len(key) > 128:
        return None, JSONResponse({"success": False, "error": "invalid api key"}, status_code=401)
    record = await db.api_keys.get(api_key_hash(key))
    if record is None:
        return None, JSONResponse({"success": False, "error": "invalid api key"}, status_code=401)
    return record.user_id, None


def api_take_seals(user_id: int, count: int, now=None) -> bool:
    """Reserve `count` seals in user_id's hourly budget. False (and nothing taken) if over."""
    from collections import deque
    now = time.time() if now is None else now
    times = _api_seal_times.setdefault(user_id, deque())
    while times and now - times[0] >= 3600:
        times.popleft()
    if len(times) + count > API_SEALS_PER_HOUR:
        return False
    times.extend([now] * count)
    return True


def _api_rate_limited():
    return JSONResponse(
        {"success": False, "error": "rate limit exceeded", "limit_per_hour": API_SEALS_PER_HOUR},
        status_code=429,
    )


async def _api_body(request: Request):
    try:
        data = await request.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None


@app.post("/api/v1/notarize")
async def api_notarize(request: Request):
    """
    Public API for third-party services to notarize contracts

    POST /api/v1/notarize
    {
        "api_key": "nt_...",             // from /api in the bot (subscribers)
        "contract_address": "EQ...",     // TON address or tx hash
        "metadata": {                    // Optional
            "project_name": "MyCoin",
            "launch_date": "2025-11-24"
        }
    }

    Returns: {"success": true, "hash": "...", "tx_url": "https://tonscan.org/..."}
    """
    data = await _api_body(request)
    if data is None:
        return JSONResponse({"success": False, "error": "invalid body"}, status_code=400)
    try:
        user_id, denied = await api_key_user(data)
    except Exception as e:
        print(f"❌ API key lookup error: {type(e).__name__}: {e}")
        return JSONResponse({"success": False, "error": "internal error"}, status_code=500)
    if denied:
        return denied

    try:
        contract_id = data.get("contract_address", "")
        metadata = data.get("metadata") or {}
        if not isinstance(contract_id, str) or not contract_id:
            return {"success": False, "error": "Missing api_key or contract_address"}
        if not isinstance(metadata, dict):
            metadata = {}

        # Check if user has subscription or credits
        has_sub = await get_user_subscription(user_id)
        if not has_sub:
            return {
                "success": False,
                "error": "No active subscription",
                "subscribe_url": f"https://t.me/NotaryTON_bot?start=subscribe"
            }

        if not api_take_seals(user_id, 1):
            return _api_rate_limited()

        # Fetch and notarize contract
        contract_code = await get_contract_code_from_tx(contract_id)
        if not contract_code:
            return {"success": False, "error": "Failed to fetch contract"}

        contract_hash = hash_data(contract_code)
        comment = f"NotaryTON:API:{contract_hash[:16]}"

        # Add metadata to comment if provided
        project_name = metadata.get("project_name")
        if isinstance(project_name, str) and project_name:
            comment = f"NotaryTON:{project_name[:20]}:{contract_hash[:12]}"

        await send_ton_transaction(comment, amount_ton=TON_SINGLE_SEAL)
        await log_notarization(user_id, contract_id, contract_hash, paid=True)
        try:
            await db.api_keys.record_usage(api_key_hash(data["api_key"]))
        except Exception:
            pass

        return {
            "success": True,
            "hash": contract_hash,
            "contract": contract_id,
            "timestamp": datetime.now().isoformat(),
            "tx_url": "https://tonscan.org/",
            "verify_url": f"{WEBHOOK_URL}/api/v1/verify/{contract_hash}"
        }

    except Exception as e:
        print(f"❌ API notarize error: {type(e).__name__}: {e}")
        return {"success": False, "error": "notarization failed"}

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
        "api_key": "nt_...",
        "contracts": [
            {"address": "EQ...", "name": "Coin1"},
            {"address": "EQ...", "name": "Coin2"}
        ]
    }

    Returns: Array of results. Every contract counts against the key's
    hourly seal budget; a batch that would exceed it is refused whole.
    """
    data = await _api_body(request)
    if data is None:
        return JSONResponse({"success": False, "error": "invalid body"}, status_code=400)
    try:
        user_id, denied = await api_key_user(data)
    except Exception as e:
        print(f"❌ API key lookup error: {type(e).__name__}: {e}")
        return JSONResponse({"success": False, "error": "internal error"}, status_code=500)
    if denied:
        return denied

    try:
        contracts = data.get("contracts", [])
        if not isinstance(contracts, list) or not contracts:
            return {"success": False, "error": "Missing api_key or contracts"}
        contracts = [c for c in contracts[:50] if isinstance(c, dict)]  # Limit to 50 per batch

        # Must have subscription for batch operations
        has_sub = await get_user_subscription(user_id)
        if not has_sub:
            return {
                "success": False,
                "error": "Subscription required for batch operations",
                "subscribe_url": f"https://t.me/NotaryTON_bot?start=subscribe"
            }

        if len(contracts) > API_SEALS_PER_HOUR:
            # Charged whole against the hourly budget, so a larger batch can
            # never succeed: say so, rather than a 429 that waiting cannot fix.
            return JSONResponse({"success": False, "error": "batch larger than hourly budget",
                                 "limit_per_hour": API_SEALS_PER_HOUR}, status_code=400)
        if not api_take_seals(user_id, len(contracts)):
            return _api_rate_limited()

        results = []
        for contract in contracts:
            address = contract.get("address", "")
            try:
                name = contract.get("name", "")
                name = name if isinstance(name, str) else ""

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
                print(f"❌ API batch item error: {type(e).__name__}: {e}")
                results.append({
                    "success": False,
                    "address": address if isinstance(address, str) else "",
                    "error": "notarization failed"
                })

        try:
            await db.api_keys.record_usage(api_key_hash(data["api_key"]))
        except Exception:
            pass

        return {
            "success": True,
            "processed": len(results),
            "results": results
        }

    except Exception as e:
        print(f"❌ API batch error: {type(e).__name__}: {e}")
        return {"success": False, "error": "batch failed"}


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
        win_chance = await lottery_win_chance(user_id)

        return {
            "success": True,
            "user_id": user_id,
            "tickets": ticket_count,
            "win_chance_percent": round(win_chance, 2),
            "total_entries": total_entries
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ========================
# CASINO API 🎰
# Off unless CASINO_ENABLED (see casino_switch). When on, every route that acts
# for a user takes the user from Telegram Mini App initData, sent in the
# X-Telegram-Init-Data header and verified against the bot token. A user_id in
# the path or body is never trusted: it used to let anyone spend, mint and
# enter the lottery as anyone.
# ========================

# Reasons a casino request is refused. A closed set: nothing from the request
# or from an exception is ever echoed back.
INIT_DATA_MISSING = "missing init data"
INIT_DATA_MALFORMED = "malformed init data"
INIT_DATA_BAD_SIGNATURE = "bad init data signature"
INIT_DATA_EXPIRED = "init data expired"
INIT_DATA_NO_USER = "init data has no user"
INIT_DATA_MAX_LENGTH = 8192
INIT_DATA_CLOCK_SKEW = 60


def validate_telegram_init_data(init_data, bot_tokens, max_age, now=None):
    """(user_id, None) if Telegram signed init_data and it is fresh, else (None, reason).

    Telegram's Mini App spec: secret_key = HMAC_SHA256(key="WebAppData",
    msg=bot_token); the hash field is hex HMAC_SHA256(key=secret_key,
    msg=data_check_string), where data_check_string is every other field as
    key=value, sorted by key, joined by newlines. Any of bot_tokens may have
    signed it, because the casino opens from both NotaryTON and MemeSeal.
    """
    if not init_data:
        return None, INIT_DATA_MISSING
    if len(init_data) > INIT_DATA_MAX_LENGTH:
        return None, INIT_DATA_MALFORMED
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None, INIT_DATA_MALFORMED
    fields = {}
    for key, value in pairs:
        if key in fields:
            return None, INIT_DATA_MALFORMED
        fields[key] = value
    received = fields.pop("hash", "")
    if not received:
        return None, INIT_DATA_MALFORMED

    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields)).encode()
    signed = False
    for token in bot_tokens:
        if not token:
            continue
        secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret_key, data_check_string, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected.encode(), received.encode()):
            signed = True
    if not signed:
        return None, INIT_DATA_BAD_SIGNATURE

    try:
        auth_date = int(fields.get("auth_date", ""))
    except ValueError:
        return None, INIT_DATA_MALFORMED
    now = time.time() if now is None else now
    if auth_date > now + INIT_DATA_CLOCK_SKEW:
        return None, INIT_DATA_MALFORMED
    if now - auth_date > max_age:
        return None, INIT_DATA_EXPIRED

    try:
        user = json.loads(fields.get("user", ""))
    except ValueError:
        return None, INIT_DATA_NO_USER
    user_id = user.get("id") if isinstance(user, dict) else None
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        return None, INIT_DATA_NO_USER
    return user_id, None


def casino_user(request: Request):
    """(user_id, None) for a request with valid initData, else (None, 401 response)."""
    user_id, reason = validate_telegram_init_data(
        request.headers.get("X-Telegram-Init-Data", ""),
        (BOT_TOKEN, MEMESEAL_BOT_TOKEN),
        CASINO_INIT_DATA_MAX_AGE,
    )
    if reason:
        return None, JSONResponse({"success": False, "error": reason}, status_code=401)
    return user_id, None


async def _casino_body(request: Request):
    """The JSON object in the body, or None."""
    try:
        data = await request.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _whole_chips(value, low: int, high: int):
    """value if it is an int in [low, high] (not a bool, not a float), else None."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if low <= value <= high else None


def _bad_request(error: str):
    return JSONResponse({"success": False, "error": error}, status_code=400)


MAX_CHIP_WAGER = 1_000_000


# A wager smaller than this adds no lottery entry: 20% of it rounds down to 0.
MIN_LOTTERY_WAGER = 5


async def _wager_chips(user_id: int, bet: int):
    """Debit a wager and enter it in the lottery. (debited, entry_stars, chips).

    The lottery entry is sized from chips actually taken from the user's
    balance, which only a verified Stars payment fills, never from a number
    the caller sends. No debit, no entry. The entry is exactly 20% of the
    wager, rounded down: rounding a 1-chip bet up to a 1-star entry made
    many tiny bets worth more tickets and pot than one big one. While
    LOTTERY_ENABLED is off there is no entry at all (entry_stars is 0).
    """
    debited, chips = await db.casino.deduct_chips(user_id, bet)
    if not debited:
        return False, 0, chips
    entry_stars = bet // 5 if LOTTERY_ENABLED else 0  # 20% of the wager feeds the pot
    if entry_stars > 0:
        await enter_lottery(user_id, entry_stars)
    return True, entry_stars, chips


@app.post("/api/v1/casino/bet")
async def api_casino_bet(request: Request):
    """
    Wager chips from the authenticated user's balance; the wager feeds the lottery.

    POST /api/v1/casino/bet   (header X-Telegram-Init-Data)
    {
        "amount": 10,          // whole chips
        "game": "slots|roulette|crash"
    }
    """
    user_id, denied = casino_user(request)
    if denied:
        return denied
    data = await _casino_body(request)
    if data is None:
        return _bad_request("invalid body")
    amount = _whole_chips(data.get("amount"), 1, MAX_CHIP_WAGER)
    if amount is None:
        return _bad_request("invalid amount")
    game = data.get("game")
    game = game[:32] if isinstance(game, str) else "casino"

    try:
        debited, entry_stars, chips = await _wager_chips(user_id, amount)
        if not debited:
            return {"success": False, "error": "Insufficient chips", "chips": chips}
        ticket_count = await db.lottery.count_user_entries(user_id)
    except Exception as e:
        print(f"❌ Casino bet error: {type(e).__name__}: {e}")
        return JSONResponse({"success": False, "error": "internal error"}, status_code=500)

    return {
        "success": True,
        "lottery_entry": entry_stars > 0,
        "tickets_added": 1 if entry_stars > 0 else 0,
        "total_tickets": ticket_count,
        "lottery_contribution": entry_stars,
        "chips": chips,
        "game": game,
        "message": "Bet recorded. +1 lottery ticket!" if entry_stars > 0
                   else f"Bet recorded. Bets under {MIN_LOTTERY_WAGER} chips add no lottery ticket."
                   if LOTTERY_ENABLED else "Bet recorded."
    }


# ========================
# CASINO CHIPS SYSTEM 🎰💰
# Chips are bought with Telegram Stars
# ========================

@app.post("/api/v1/casino/buy-chips")
async def api_casino_buy_chips(request: Request):
    """
    Create a Telegram Stars invoice for buying casino chips.
    1 Star = 1 Chip (simple conversion)

    POST /api/v1/casino/buy-chips   (header X-Telegram-Init-Data)
    {
        "amount": 100  // Stars/chips to buy
    }

    Returns invoice_url to open in Telegram WebApp
    """
    user_id, denied = casino_user(request)
    if denied:
        return denied
    data = await _casino_body(request)
    if data is None:
        return _bad_request("invalid body")
    amount = data.get("amount", 100)
    if isinstance(amount, bool) or not isinstance(amount, int):
        return _bad_request("invalid amount")
    if amount < 10:
        return {"success": False, "error": "Minimum purchase is 10 chips"}
    if amount > 10000:
        return {"success": False, "error": "Maximum purchase is 10,000 chips"}

    try:
        # Ensure user exists
        await db.users.ensure_exists(user_id)

        # Create Telegram Stars invoice
        prices = [LabeledPrice(label=f"{amount} Casino Chips", amount=amount)]

        # Use memeseal_bot for casino (degen branding)
        active_bot = memeseal_bot if memeseal_bot else bot

        invoice = await active_bot.create_invoice_link(
            title=f"{amount} Casino Chips 🎰",
            description=f"Buy {amount} chips to play slots, crash, and roulette."
                        + (" 20% of bets feed the lottery!" if LOTTERY_ENABLED else ""),
            payload=f"casino_chips_{user_id}_{amount}_{int(time.time())}",
            currency="XTR",  # Telegram Stars
            prices=prices,
            provider_token="",  # Empty for Stars
        )
    except Exception as e:
        print(f"❌ Casino buy-chips error: {type(e).__name__}: {e}")
        return JSONResponse({"success": False, "error": "could not create invoice"}, status_code=502)

    return {
        "success": True,
        "invoice_url": invoice,
        "amount": amount,
        "message": f"Open invoice to buy {amount} chips!"
    }


@app.get("/api/v1/casino/balance/{user_id}")
async def api_casino_balance(user_id: str, request: Request):
    """
    The authenticated user's casino chip balance. The path id must be theirs.

    GET /api/v1/casino/balance/123456789   (header X-Telegram-Init-Data)
    """
    authed_id, denied = casino_user(request)
    if denied:
        return denied
    if user_id != str(authed_id):
        return JSONResponse({"success": False, "error": "forbidden"}, status_code=403)

    try:
        # Ensure user exists
        await db.users.ensure_exists(authed_id)

        balance = await db.casino.get_balance(authed_id)
        lottery_tickets = await db.lottery.count_user_entries(authed_id)
    except Exception as e:
        print(f"❌ Casino balance error: {type(e).__name__}: {e}")
        return JSONResponse({"success": False, "error": "internal error"}, status_code=500)

    return {
        "success": True,
        "user_id": authed_id,
        "chips": balance.chips,
        "total_wagered": balance.total_wagered,
        "total_won": balance.total_won,
        "total_deposited": balance.total_deposited,
        "total_withdrawn": balance.total_withdrawn,
        "net_profit": balance.total_won - balance.total_wagered,
        "lottery_tickets": lottery_tickets
    }


@app.post("/api/v1/casino/play")
async def api_casino_play(request: Request):
    """
    Wager chips on a game played in the Mini App.

    POST /api/v1/casino/play   (header X-Telegram-Init-Data)
    {
        "bet_amount": 10,
        "game": "slots|roulette|crash",
        "result": "lose"
    }

    The games run in the browser, so the server cannot know who won. It used
    to credit whatever "payout" the client sent, which minted chips at will.
    Now a play only debits the wager; a claimed win is refused with 501 and
    changes nothing, until outcomes are computed server-side.
    """
    user_id, denied = casino_user(request)
    if denied:
        return denied
    data = await _casino_body(request)
    if data is None:
        return _bad_request("invalid body")
    if data.get("result", "lose") == "win" or data.get("payout"):
        return JSONResponse(
            {"success": False, "error": "payouts are not supported"},
            status_code=501,
        )
    bet_amount = _whole_chips(data.get("bet_amount"), 1, MAX_CHIP_WAGER)
    if bet_amount is None:
        return {"success": False, "error": "Bet amount must be positive"}

    try:
        debited, entry_stars, chips = await _wager_chips(user_id, bet_amount)
    except Exception as e:
        print(f"❌ Casino play error: {type(e).__name__}: {e}")
        return JSONResponse({"success": False, "error": "internal error"}, status_code=500)
    if not debited:
        return {"success": False, "error": "Insufficient chips", "chips": chips}

    return {
        "success": True,
        "result": "lose",
        "bet": bet_amount,
        "chips": chips,
        "lottery_contribution": entry_stars,
        "message": "Better luck next time! You fed the lottery pot 🐸" if LOTTERY_ENABLED
                   else "Better luck next time! 🐸"
    }


@app.post("/api/v1/casino/withdraw")
async def api_casino_withdraw(request: Request):
    """
    Cash chips out to a TON wallet. Not available.

    It used to debit the chips and answer "queued" with no queue behind it,
    destroying them. Paying chips out in TON is a transfer at the user's
    request, so it is closed behind WITHDRAWALS_ENABLED (503 while off), and
    even then answers 501 and touches nothing until a real, reviewed cash-out
    exists.
    """
    user_id, denied = casino_user(request)
    if denied:
        return denied
    if not WITHDRAWALS_ENABLED:
        return JSONResponse({"success": False, "error": "withdrawals paused"}, status_code=503)
    return JSONResponse({"success": False, "error": "chip cash-out is not implemented"}, status_code=501)


@app.get("/api/v1/casino/stats")
async def api_casino_stats():
    """
    Get overall casino statistics.
    """
    try:
        stats = await db.casino.get_stats()
        pot_stars = await db.lottery.get_pot_size_stars()
        
        return {
            "success": True,
            "total_players": stats["total_players"],
            "total_deposits": stats["total_deposits"],
            "total_wagered": stats["total_wagered"],
            "total_payouts": stats["total_payouts"],
            "house_edge_collected": stats["total_wagered"] - stats["total_payouts"],
            "chips_in_play": stats["chips_in_play"],
            "lottery_pot_stars": pot_stars
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/v1/casino/leaderboard")
async def api_casino_leaderboard(limit: int = 10):
    """
    Get top casino players by net profit.
    """
    try:
        leaderboard = await db.casino.get_leaderboard(limit)
        return {
            "success": True,
            "leaderboard": leaderboard
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


# Admin endpoint to seed lottery pot (protected by ADMIN_SECRET, see admin_ok)
@app.post("/admin/seed-lottery")
async def seed_lottery(request: Request, amount_stars: int = 2500):
    """Removed: it added unbacked "house" entries to a pot paid out in TON.

    A pot must only hold stars somebody paid. The legacy house entries are
    voided by POST /admin/void-legacy-lottery.
    """
    if not admin_ok(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return JSONResponse({"error": "seeding the lottery is no longer supported"}, status_code=410)


@app.post("/admin/void-legacy-lottery")
async def void_legacy_lottery(request: Request):
    """Void every undrawn lottery entry made before this call, once.

    The pre-Round-1 pot mixes tickets bought with Stars, entries forged
    through the unauthenticated casino bet route, and unbacked house entries
    for user 1; nothing in the table tells them apart. This voids all of
    them (draw_id = -1) and records the count and time in bot_state. It is
    the operator's call, not a startup migration, because honest tickets go
    too. In the same transaction it takes back the casino chips that
    client-claimed wins could account for. Until it has run, no draw runs
    at all. A second call changes nothing and reports the first run.
    """
    if not admin_ok(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    result = await db.lottery.void_legacy_entries()
    return {"ok": True, **result}


@app.post("/admin/import-ton-labels")
async def import_ton_labels(request: Request):
    """Import ton-labels data into known_wallets table (one-time migration)"""
    if not admin_ok(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    import json
    from pathlib import Path

    # Load the ton-labels data
    labels_path = Path(__file__).parent / "scripts" / "ton-labels-compiled.json"
    if not labels_path.exists():
        return {"error": f"Labels file not found at {labels_path}"}

    with open(labels_path) as f:
        data = json.load(f)

    imported = 0
    skipped = 0

    for address, info in data['addresses'].items():
        label = info.get('category', 'unknown')
        owner_name = info.get('label') or info.get('organization', '')

        notes_data = {
            'website': info.get('website'),
            'subcategory': info.get('subcategory'),
            'description': info.get('description'),
            'tags': info.get('tags', []),
            'source': 'ton-labels'
        }
        notes_data = {k: v for k, v in notes_data.items() if v}
        notes = json.dumps(notes_data) if notes_data else None

        try:
            await db.wallets.label_wallet(address, label, owner_name, notes)
            imported += 1
        except Exception as e:
            skipped += 1

    return {
        "success": True,
        "imported": imported,
        "skipped": skipped,
        "total": data['total'],
        "stats": data['stats']
    }


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

    return templates.TemplateResponse(request, "dashboard.html", {
        "total_users": total_users,
        "total_notarizations": total_notarizations,
        "notarizations_24h": notarizations_24h or 0,
        "users_24h": users_24h or 0,
        "total_revenue": total_revenue or 0,
        "total_referrals": total_referrals or 0,
        "top_referrers": top_referrers,
        "recent_seals": recent_seals
    })

async def register_webhook(tg_bot: Bot, path: str, name: str):
    """Register a Telegram webhook, retrying with backoff until Telegram accepts it.

    Runs as a background task so an unreachable API, a bad token or a rejected
    URL never stops the HTTP server: /health and the TonAPI payment webhooks
    stay up while this keeps trying. drop_pending_updates=False keeps the files
    users sent while we were down (e.g. during a redeploy).
    """
    delay = 5
    while True:
        try:
            await tg_bot.set_webhook(
                f"{WEBHOOK_URL}{path}",
                secret_token=TELEGRAM_WEBHOOK_SECRET,
                drop_pending_updates=False,
            )
            print(f"✅ {name} webhook registered")
            return
        except Exception as e:
            # Errors can quote the Bot API URL, which contains the token.
            reason = str(e).replace(tg_bot.token, "<token>")
            print(f"⚠️ {name} webhook registration failed, retrying in {delay}s: {type(e).__name__}: {reason}")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 300)

async def announce_bots():
    """Fetch the bots' usernames and announce in GROUP_IDS.

    A background task for the same reason as register_webhook: when Telegram
    accepts the connection but never answers, each call waits out aiogram's 60s
    timeout, and none of that may delay the HTTP server. Until a lookup succeeds
    the hardcoded usernames stay in place.
    """
    global BOT_USERNAME, MEMESEAL_USERNAME

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

    # Join groups
    for group_id in GROUP_IDS:
        if group_id.strip():
            try:
                await bot.send_message(group_id, "🔐 NotaryTON is now monitoring this group for auto-notarization!")
                print(f"✅ Joined group: {group_id}")
            except Exception as e:
                print(f"❌ Failed to join group {group_id}: {e}")

@app.on_event("startup")
async def on_startup():
    """Set webhooks for both bots on startup"""

    # Initialize database (PostgreSQL via Neon)
    await db.connect()

    if not await legacy_lottery_voided():
        print("🚨 POST /admin/void-legacy-lottery has never run: the Sunday draw is skipped "
              "(nothing drawn, announced or paid) until it does.")

    # Initialize social media poster (X + Telegram channel)
    social_poster.initialize()

    # Usernames and group announcements also call Telegram, which can hang for
    # aiogram's 60s timeout per call: do them in the background (see announce_bots).
    asyncio.create_task(announce_bots())

    # Register webhooks in the background (see register_webhook). Without the
    # secret every update would be rejected, so registering would be pointless.
    if TELEGRAM_WEBHOOK_SECRET:
        asyncio.create_task(register_webhook(bot, WEBHOOK_PATH, "NotaryTON"))
        if memeseal_bot and MEMESEAL_WEBHOOK_PATH:
            asyncio.create_task(register_webhook(memeseal_bot, MEMESEAL_WEBHOOK_PATH, "MemeSeal"))
        if memescan_bot and MEMESCAN_WEBHOOK_PATH:
            asyncio.create_task(register_webhook(memescan_bot, MEMESCAN_WEBHOOK_PATH, "MemeScan"))
    else:
        print("⚠️ TELEGRAM_WEBHOOK_SECRET is not set: webhooks not registered, Telegram updates will be rejected")

    # Start MemeScan Twitter auto-poster (if enabled)
    if os.getenv("MEMESCAN_TWITTER_ENABLED", "").lower() == "true":
        memescan_twitter.initialize()
        asyncio.create_task(memescan_twitter.run_auto_poster(interval_seconds=1800))
        print("✅ MemeScan Twitter auto-poster started (every 30 min)")

    # Start payment polling task (it has no wallet to watch without SERVICE_TON_WALLET)
    if SERVICE_TON_WALLET:
        asyncio.create_task(poll_wallet_for_payments())
    else:
        print("⚠️ SERVICE_TON_WALLET is not set: TON payment poller not started")

    # 🐸 Start pending payment cleanup task
    asyncio.create_task(cleanup_pending_payments())

    # 🎰 Start lottery draw task (Sunday 00:00 UTC), only while the lottery runs
    if LOTTERY_ENABLED:
        asyncio.create_task(run_sunday_lottery_draw())
    else:
        print("⏸️ LOTTERY_ENABLED is off: no lottery entries are made and the Sunday draw is not started")

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
