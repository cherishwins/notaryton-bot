# Telegram + TON Ecosystem Arsenal

> Your complete toolkit for building legendary products on the future of money.

---

## Table of Contents

1. [Telegram APIs](#1-telegram-apis)
2. [TON Blockchain APIs](#2-ton-blockchain-apis)
3. [MCP Servers](#3-mcp-servers)
4. [DeFi & DEX APIs](#4-defi--dex-apis)
5. [Telegram Stars Deep Dive](#5-telegram-stars-deep-dive)
6. [Python Libraries](#6-python-libraries)
7. [Mini App Development](#7-mini-app-development)
8. [Recommended MCP Setup](#8-recommended-mcp-setup)

---

## 1. Telegram APIs

### Official Telegram Bot API

**Base URL:** `https://api.telegram.org/bot<token>/`

**Latest Version:** Bot API 8.1+ (December 2025)

#### Key Features for MemeSeal

| Feature | Description | Docs |
|---------|-------------|------|
| **Stars Payments** | In-app digital currency | [Stars API](https://core.telegram.org/bots/payments-stars) |
| **Paid Subscriptions** | Recurring Stars billing | [Subscriptions](https://core.telegram.org/api/subscriptions) |
| **Gifts API** | Send/receive collectible gifts | [Gifts API](https://core.telegram.org/api/gifts) |
| **Affiliate Programs** | Revenue sharing (Bot API 8.1) | [Changelog](https://core.telegram.org/bots/api-changelog) |
| **Mini Apps** | WebApp integration | [Mini Apps](https://core.telegram.org/bots/webapps) |
| **Webhooks** | Real-time updates | [Webhooks](https://core.telegram.org/bots/webhooks) |

#### Bot API 8.0+ Highlights

```
- 10 new Mini App features (full-screen, home screen shortcuts)
- Paid subscriptions with multiple tiers
- Gift management for business accounts
- Premium subscription gifting via Stars
- Transaction type differentiation
- Max price increased to 10,000 Stars
- Paid messages support
```

### Mini Apps / WebApp API

**Docs:** [core.telegram.org/bots/webapps](https://core.telegram.org/bots/webapps)

#### Available Methods

```javascript
// User & Theme
Telegram.WebApp.initData          // Auth data
Telegram.WebApp.initDataUnsafe    // Parsed user info
Telegram.WebApp.colorScheme       // 'light' | 'dark'
Telegram.WebApp.themeParams       // Theme colors

// UI Controls
Telegram.WebApp.MainButton        // Bottom action button
Telegram.WebApp.BackButton        // Navigation back
Telegram.WebApp.SettingsButton    // Settings gear icon

// Features
Telegram.WebApp.HapticFeedback    // Vibration patterns
Telegram.WebApp.CloudStorage      // Per-user storage (up to 1MB)
Telegram.WebApp.BiometricManager  // Fingerprint/FaceID
Telegram.WebApp.Accelerometer     // Motion sensing
Telegram.WebApp.Gyroscope         // Orientation sensing

// Actions
Telegram.WebApp.openInvoice()     // Stars payment
Telegram.WebApp.openTelegramLink()
Telegram.WebApp.showPopup()
Telegram.WebApp.showAlert()
Telegram.WebApp.showConfirm()
Telegram.WebApp.showScanQrPopup()
Telegram.WebApp.requestContact()
Telegram.WebApp.requestWriteAccess()
```

#### Haptic Feedback Types

```javascript
// Impact (collision feedback)
HapticFeedback.impactOccurred('light')   // Small UI elements
HapticFeedback.impactOccurred('medium')  // Medium elements
HapticFeedback.impactOccurred('heavy')   // Large elements
HapticFeedback.impactOccurred('rigid')   // Hard surface
HapticFeedback.impactOccurred('soft')    // Soft surface

// Notification
HapticFeedback.notificationOccurred('success')
HapticFeedback.notificationOccurred('warning')
HapticFeedback.notificationOccurred('error')

// Selection
HapticFeedback.selectionChanged()
```

### MTProto API (Advanced)

**For:** Direct Telegram client access (userbot features)

**Libraries:**
- **Telethon** (Python): `pip install telethon`
- **Pyrogram** (Python): `pip install pyrogram`
- **GramJS** (JavaScript)

**Use Cases:**
- Read message history beyond bot limits
- Access user accounts (with authorization)
- Build custom clients
- Channel statistics

---

## 2. TON Blockchain APIs

### TONAPI (tonapi.io) - Recommended

**Console:** [tonconsole.com](https://tonconsole.com)

**Free Tier:** Available (rate limited)

#### Key Features

| Feature | Description |
|---------|-------------|
| **REST API** | Full blockchain data access |
| **Webhooks** | Real-time transaction notifications |
| **Streaming** | SSE event streams (deprecated, use webhooks) |
| **Gasless Txs** | Sponsor user transactions |
| **Push Notifications** | Tonkeeper integration |
| **TonAnalytics** | SQL queries on blockchain data |

#### Webhook Subscriptions

```python
# Account transactions
POST /v2/webhooks/account-tx
{
    "url": "https://your-server.com/webhook",
    "accounts": ["EQA..."]
}

# New contract deployments
POST /v2/webhooks/new-contracts
{
    "url": "https://your-server.com/webhook"
}

# Message opcode subscriptions
POST /v2/webhooks/opcode
{
    "url": "https://your-server.com/webhook",
    "opcode": "0x0f8a7ea5"  # Jetton transfer
}
```

#### HMAC Signature Verification (You Have This!)

```python
# From your bot.py implementation
def verify_tonapi_signature(body: bytes, signature: str) -> bool:
    expected = hmac.new(
        TONAPI_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### TON Center API

**URL:** [toncenter.com](https://toncenter.com)

**Free Tier:** Rate limited, API key available from [@tonapibot](https://t.me/tonapibot)

#### Endpoints

```
GET /api/v2/getAddressBalance
GET /api/v2/getTransactions
GET /api/v2/getWalletInformation
POST /api/v2/sendBoc
GET /api/v2/runGetMethod
```

### TON HTTP API (Self-Hosted)

**GitHub:** [ton-blockchain/ton-http-api](https://github.com/ton-blockchain/ton-http-api)

**Use Case:** Maximum decentralization, no rate limits

### TON Connect 2.0

**Docs:** [docs.ton.org/develop/dapps/ton-connect](https://docs.ton.org/v3/guidelines/ton-connect/overview)

**SDK:** `npm install @tonconnect/sdk @tonconnect/ui`

#### Features

- QR code wallet connection
- Transaction signing
- Proof verification (authenticate wallet ownership)
- Multi-wallet support (Tonkeeper, MyTonWallet, etc.)

```typescript
import { TonConnect } from '@tonconnect/sdk';

const connector = new TonConnect({
    manifestUrl: 'https://your-app.com/tonconnect-manifest.json'
});

// Connect wallet
connector.connect({ universalLink: 'https://tonkeeper.com/tc' });

// Sign transaction
await connector.sendTransaction({
    validUntil: Math.floor(Date.now() / 1000) + 600,
    messages: [{
        address: 'EQ...',
        amount: '100000000' // 0.1 TON in nanotons
    }]
});
```

---

## 3. MCP Servers

### TON Blockchain MCP Servers

#### ton-blockchain-mcp (Recommended)

**GitHub:** [devonmojito/ton-blockchain-mcp](https://github.com/devonmojito/ton-blockchain-mcp)

**Tools:**
- `analyze_address` - Balance, jettons, NFTs, activity
- `get_transaction_details` - Transaction analysis
- `find_hot_trends` - Trending tokens/pools
- `analyze_trading_patterns` - DEX activity analysis
- `get_ton_price` - Real-time TON price
- `get_jetton_price` - Token prices

**Config:**
```json
{
    "mcpServers": {
        "ton-mcp-server": {
            "command": "python",
            "args": ["-m", "tonmcp.mcp_server"],
            "env": {
                "TON_API_KEY": "your-tonapi-key"
            }
        }
    }
}
```

#### ton-access-mcp

**GitHub:** [aiopinions/ton-access-mcp](https://github.com/aiopinions/ton-access-mcp)

**Features:**
- Decentralized access (multiple nodes)
- Health checking & load balancing
- Mainnet + Testnet support

### Crypto Data MCP Servers

| Server | Description | GitHub |
|--------|-------------|--------|
| **CoinGecko MCP** | 15k+ coins, trending, DeFi | [Official Docs](https://docs.coingecko.com/reference/mcp-server) |
| **DexPaprika MCP** | 5M tokens, 20+ chains | [coinpaprika/dexpaprika-mcp](https://github.com/coinpaprika/dexpaprika-mcp) |
| **whale-tracker-mcp** | Whale transaction alerts | [kukapay/whale-tracker-mcp](https://github.com/kukapay/whale-tracker-mcp) |
| **crypto-feargreed-mcp** | Fear & Greed Index | [kukapay/crypto-feargreed-mcp](https://github.com/kukapay/crypto-feargreed-mcp) |

### Telegram MCP Servers

| Server | Description | GitHub |
|--------|-------------|--------|
| **telegram-mcp** | Full MTProto client | [chigwell/telegram-mcp](https://github.com/chigwell/telegram-mcp) |
| **mcp-telegram** | Bot API wrapper | [sparfenyuk/mcp-telegram](https://github.com/sparfenyuk/mcp-telegram) |
| **telegram-bot-mcp** | Comprehensive Bot API | [guangxiangdebizi/telegram-mcp](https://github.com/guangxiangdebizi/telegram-mcp) |

### Social Media MCP Servers

| Server | Description | GitHub |
|--------|-------------|--------|
| **x-mcp-server** | Twitter/X API v2 | [BioInfo/x-mcp-server](https://github.com/BioInfo/x-mcp-server) |
| **mcp-twitter-server** | 53 tools, analytics | [crazyrabbitLTC/mcp-twitter-server](https://github.com/crazyrabbitLTC/mcp-twitter-server) |
| **slack-mcp-server** | Full Slack integration | [korotovsky/slack-mcp-server](https://github.com/korotovsky/slack-mcp-server) |

### Database MCP Servers

| Server | Description | GitHub |
|--------|-------------|--------|
| **postgres-mcp** | Read/write PostgreSQL | [GarethCott/enhanced-postgres-mcp-server](https://github.com/GarethCott/enhanced-postgres-mcp-server) |
| **supabase-mcp** | Full Supabase integration | [supabase-community/supabase-mcp](https://github.com/supabase-community/supabase-mcp) |
| **redis-mcp** | Redis with NL interface | [Official Blog](https://redis.io/blog/introducing-model-context-protocol-mcp-for-redis/) |

### Development MCP Servers

| Server | Description | Source |
|--------|-------------|--------|
| **github-mcp** | 100+ GitHub API tools | [github/github-mcp-server](https://github.com/github/github-mcp-server) |
| **vercel-mcp** | Deploy & manage | [Vercel Docs](https://vercel.com/docs/mcp) |
| **cloudflare-mcp** | Workers & KV | [Cloudflare Blog](https://blog.cloudflare.com/remote-model-context-protocol-servers-mcp/) |

### Awesome Lists

- **[awesome-crypto-mcp-servers](https://github.com/badkk/awesome-crypto-mcp-servers)** - Crypto focused
- **[awesome-web3-mcp-servers](https://github.com/demcp/awesome-web3-mcp-servers)** - Web3/DeFi focused
- **[awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers)** - 7000+ servers
- **[PulseMCP Directory](https://www.pulsemcp.com/servers)** - Searchable directory

---

## 4. DeFi & DEX APIs

### STON.fi (Recommended DEX)

**Docs:** [docs.ston.fi](https://docs.ston.fi)

**SDK:** `npm install @ston-fi/sdk`

#### Features

- Token swaps (direct & multi-hop)
- Liquidity provision (single-sided supported)
- Referral system with vaults
- Stable swaps (Curve-style)

#### Swap Example

```typescript
import { DEX, pTON } from '@ston-fi/sdk';

const dex = new DEX.v2.Router();

// Swap TON -> USDT
const txParams = await dex.getSwapTonToJettonTxParams({
    userWalletAddress: walletAddress,
    offerAmount: toNano('1'),
    askJettonAddress: USDT_ADDRESS,
    minAskAmount: '1000000', // Min USDT (6 decimals)
    proxyTon: pTON.v2_1,
});
```

#### API Endpoints

```
GET /v1/pools                    # All liquidity pools
GET /v1/assets                   # All tradeable assets
GET /v1/swap/simulate            # Quote for swap
GET /v1/wallets/{addr}/operations # User's swap history
```

### DeDust

**Docs:** [docs.dedust.io](https://docs.dedust.io)

**SDK:** `npm install @dedust/sdk`

#### Features

- Volatile & stable pools
- Multi-hop trades
- Python SDK: [ClickoTON-Foundation/dedust](https://github.com/ClickoTON-Foundation/dedust)

### Aggregators

| Service | Description | Docs |
|---------|-------------|------|
| **Omniston** | Cross-chain aggregator | [STON.fi Docs](https://docs.ston.fi) |
| **TON Swap** | Simple swap interface | [tonswap.org](https://tonswap.org) |

---

## 5. Telegram Stars Deep Dive

### Exchange Rates (December 2025)

| Metric | Value |
|--------|-------|
| **Market Rate** | ~$0.013/Star (77 Stars/$1) |
| **Developer Share** | 100% (no Telegram commission!) |
| **Minimum Withdrawal** | 1,000 Stars |
| **Withdrawal Wait** | 21 days |
| **Max Invoice Price** | 10,000 Stars |

### Payment Flow

```
1. Bot sends invoice (sendInvoice / createInvoiceLink)
2. User pays with Stars
3. Telegram sends PreCheckoutQuery → Must answer within 10 seconds
4. Telegram sends SuccessfulPayment message
5. Store telegram_payment_charge_id (REQUIRED for refunds!)
```

### Critical Code: Store Payment Charge ID

```python
@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    payment = message.successful_payment

    # CRITICAL: Store this for refunds!
    charge_id = payment.telegram_payment_charge_id

    await db.execute("""
        INSERT INTO star_payments
        (user_id, telegram_payment_charge_id, amount_stars, payload)
        VALUES ($1, $2, $3, $4)
    """, message.from_user.id, charge_id, payment.total_amount,
        payment.invoice_payload)
```

### Refund API

```python
await bot.refund_star_payment(
    user_id=user_id,
    telegram_payment_charge_id=charge_id
)
```

### Stars vs TON Comparison

| Factor | Stars | TON Direct |
|--------|-------|------------|
| **User Friction** | Zero | High (wallet setup) |
| **Transaction Speed** | Instant | ~1 minute |
| **Developer Fees** | 0% | Gas (~$0.01) |
| **Refunds** | Built-in API | Manual |
| **Target Audience** | Everyone | Crypto-natives |
| **On-chain Proof** | No | Yes |

### Recommended Strategy

**Hybrid approach (what MemeSeal does):**
- **Stars:** 90% of users - zero friction, instant
- **TON:** 10% of users - whales, on-chain proof needed

---

## 6. Python Libraries

### Bot Development

| Library | Description | Install |
|---------|-------------|---------|
| **aiogram 3.x** | Async Telegram bot framework | `pip install aiogram` |
| **python-telegram-bot** | Alternative framework | `pip install python-telegram-bot` |
| **Telethon** | MTProto client | `pip install telethon` |
| **Pyrogram** | MTProto client | `pip install pyrogram` |

### TON Blockchain

| Library | Description | Install |
|---------|-------------|---------|
| **pytoniq** | Native ADNL, full-featured | `pip install pytoniq` |
| **pytoniq-core** | Core types & crypto | `pip install pytoniq-core` |
| **tonutils** | High-level utilities | `pip install tonutils` |
| **pytonapi** | TONAPI wrapper | `pip install pytonapi` |
| **pytoncenter** | TON Center wrapper | `pip install pytoncenter` |
| **tonsdk** | Basic SDK | `pip install tonsdk` |

### DEX Integration

| Library | Description | Install |
|---------|-------------|---------|
| **stonfi-sdk** | STON.fi Python SDK | (via tonutils) |
| **dedust** | DeDust Python SDK | `pip install dedust` |

### Your Current Stack

```python
# From requirements.txt (assumed)
aiogram>=3.15.0        # Telegram bot
pytoniq>=0.1.40        # TON blockchain
pytonapi               # TONAPI integration
asyncpg                # PostgreSQL async
aiohttp                # HTTP client
python-dotenv          # Environment vars
tweepy                 # Twitter API
```

---

## 7. Mini App Development

### Tech Stack Options

| Framework | Pros | Cons |
|-----------|------|------|
| **React + Vite** | Fast, popular, good tooling | Bundle size |
| **Next.js** | SSR, API routes | Complex |
| **Svelte** | Tiny bundles | Smaller ecosystem |
| **Vue.js** | Easy to learn | Less popular in crypto |

### Telegram Mini App Libraries

```bash
# Official SDK
npm install @telegram-apps/sdk

# React bindings
npm install @telegram-apps/sdk-react

# UI components
npm install @telegram-apps/telegram-ui
```

### TON Integration for Mini Apps

```bash
# TON Connect UI
npm install @tonconnect/ui-react

# TON SDK
npm install @ton/ton @ton/core @ton/crypto
```

### Your MemeScan Mini App Stack

```
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- @telegram-apps/sdk-react
- @tonconnect/ui-react
- Vercel (hosting)
```

---

## 8. Recommended MCP Setup

### For MemeSeal Development

Add these to your Claude Code MCP config:

```json
{
    "mcpServers": {
        "ton-blockchain": {
            "command": "python",
            "args": ["-m", "tonmcp.mcp_server"],
            "cwd": "/path/to/ton-blockchain-mcp/src",
            "env": {
                "TON_API_KEY": "${TONAPI_KEY}"
            }
        },
        "telegram-mcp": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-telegram"]
        },
        "github": {
            "command": "gh",
            "args": ["mcp-server"]
        },
        "postgres": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-postgres"],
            "env": {
                "DATABASE_URL": "${DATABASE_URL}"
            }
        }
    }
}
```

### Installation Commands

```bash
# TON Blockchain MCP
git clone https://github.com/devonmojito/ton-blockchain-mcp.git
cd ton-blockchain-mcp
pip install -r requirements.txt

# GitHub MCP (already have via gh CLI)
gh extension install github/gh-mcp

# Telegram MCP (you already have this configured!)
# Using: sparfenyuk/mcp-telegram
```

---

## Quick Reference

### API Endpoints

```
Telegram Bot API:  https://api.telegram.org/bot<token>/
TONAPI:            https://tonapi.io/v2/
TON Center:        https://toncenter.com/api/v2/
STON.fi:           https://api.ston.fi/v1/
DeDust:            https://api.dedust.io/v2/
```

### Key Environment Variables

```bash
# Telegram
BOT_TOKEN=              # From @BotFather
TELEGRAM_API_ID=        # From my.telegram.org
TELEGRAM_API_HASH=      # From my.telegram.org

# TON
TONAPI_KEY=             # From tonconsole.com
TON_WALLET_MNEMONIC=    # 24-word seed phrase
TONAPI_WEBHOOK_SECRET=  # For webhook verification

# Database
DATABASE_URL=           # PostgreSQL connection string

# Social
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_SECRET=
```

### Useful Links

- **Telegram Bot API:** [core.telegram.org/bots/api](https://core.telegram.org/bots/api)
- **TON Docs:** [docs.ton.org](https://docs.ton.org)
- **TONAPI Console:** [tonconsole.com](https://tonconsole.com)
- **STON.fi Docs:** [docs.ston.fi](https://docs.ston.fi)
- **MCP Protocol:** [modelcontextprotocol.io](https://modelcontextprotocol.io)
- **Awesome MCP:** [github.com/punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers)

---

## What's Next?

### Immediate Opportunities

1. **Add TON MCP Server** - Natural language blockchain queries
2. **Fix Stars Payment Tracking** - Store `telegram_payment_charge_id`
3. **Add `/paysupport`** - Telegram ToS requirement

### Future Integrations

1. **STON.fi Integration** - Let users swap tokens
2. **NFT Minting** - Turn seals into collectibles
3. **Whale Alerts** - Track big wallet movements
4. **Price Feeds** - Real-time crypto data in bot

---

*Last Updated: December 2025*
*Built for MemeSeal by Claude*
