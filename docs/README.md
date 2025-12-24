# NotaryTON Labs Documentation

> **Last Updated:** December 24, 2025

Welcome to the NotaryTON Labs documentation. This index will help you find what you need.

---

## Quick Start

**New to the project?** Start here:

1. Read the main [README.md](../README.md) for project overview
2. Read [ARCHITECTURE.md](./ARCHITECTURE.md) to understand how it works
3. Check [DEPLOYMENT.md](./DEPLOYMENT.md) if you're setting up

---

## Documentation Index

### Core Docs

| Document | Description | When to Read |
|----------|-------------|--------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System design, data flow, component relationships | Understanding how the system works |
| [API.md](./API.md) | All REST endpoints with examples | Building integrations or debugging |
| [DATABASE.md](./DATABASE.md) | PostgreSQL schema, tables, indexes | Working with data or debugging queries |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Render setup, env vars, domains | Setting up or troubleshooting deployment |
| [ROADMAP.md](./ROADMAP.md) | Trader Intelligence phases | Planning future development |

### Product Docs

| Document | Description |
|----------|-------------|
| [../PRODUCT_MAP.md](../PRODUCT_MAP.md) | Complete product architecture with user flows |
| [STRATEGY.md](./STRATEGY.md) | Business strategy and positioning |
| [VISION_DECK.md](./VISION_DECK.md) | Pitch deck content |

### Grant Materials

| Document | Description |
|----------|-------------|
| [GRANT_PITCH.md](./GRANT_PITCH.md) | Grant application pitch |
| [WHITEPAPER_GRANT.md](./WHITEPAPER_GRANT.md) | Technical whitepaper for grants |

### Archive

Older docs moved to [archive/](./archive/) for reference.

---

## Live URLs

| Service | URL | Description |
|---------|-----|-------------|
| Main Site | https://notaryton.com | Landing page with lottery pot |
| Live Feed | https://notaryton.com/feed | SSE token stream |
| API Base | https://notaryton.com/api/v1/ | REST API |
| Rug Score | https://notaryton.com/score | Marketing page for token safety |
| Seal Bot | https://t.me/MemeSealTON_bot | Main product |
| Scan Bot | https://t.me/MemeScanTON_bot | Token scanner |
| Channel | https://t.me/MemeSealTON | Announcements |

---

## Products Overview

### 1. MemeSeal (Revenue)

Blockchain notarization. Users pay Stars or TON to seal files on-chain forever.

**Key Files:**
- `bot.py` - Telegram handlers, payment processing
- `database.py` - Seal storage, lottery, subscriptions
- `social.py` - Auto-posting to X and Telegram channel

**Revenue:**
- 1 Star (~$0.02) or 0.015 TON per seal
- 15 Stars/month unlimited subscription
- 20% to lottery pot, 5% referral commission

### 2. MemeScan (Growth)

Token scanner for TON meme coins. Free to drive adoption.

**Key Files:**
- `memescan/` - All scanner logic
- `crawler.py` - Token discovery, rug detection
- `memescan/api.py` - TonAPI, GeckoTerminal, STON.fi clients

**Features:**
- Safety scoring (0-100 rug score)
- Holder concentration analysis
- Live token feed

### 3. Trader Intelligence (Data Moat)

KOL tracking and wallet analytics. Proprietary competitive advantage.

**Key Files:**
- `kol_models.py` - 82 KOL profiles with metadata
- `kol_repository.py` - Database operations, filtering
- `database.py` - Wallet tracking tables

**Data:**
- 82 KOLs across 19 languages, 6 categories
- Wallet tracking infrastructure
- Call outcome tracking (planned)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Bot** | aiogram 3.15+ (Telegram Bot API) |
| **API** | FastAPI + uvicorn |
| **Database** | PostgreSQL (Render managed) |
| **Blockchain** | TON via pytoniq + LiteBalancer |
| **Payments** | Telegram Stars + native TON (TonAPI webhooks) |
| **External APIs** | TonAPI, GeckoTerminal, STON.fi |
| **Hosting** | Render.com (Web Service) |
| **Domain** | Cloudflare (proxied to Render) |
| **Social** | X/Twitter API v2 |

---

## Repository Structure

```
notaryton-bot/
│
├── bot.py                  # THE MAIN FILE - FastAPI + Telegram bot
├── config.py               # All environment variables
├── database.py             # PostgreSQL tables + repositories
├── crawler.py              # Token discovery + rug detection
├── social.py               # X/Twitter + TG channel posting
│
├── kol_models.py           # KOL dataclasses + 82 seed profiles
├── kol_repository.py       # KOL CRUD + filtering
│
├── memescan/               # Token scanner module
│   ├── __init__.py
│   ├── api.py              # External API clients
│   ├── bot.py              # MemeScan bot handlers
│   ├── models.py           # Token, Pool, SafetyLevel
│   ├── formatter.py        # Message formatting
│   ├── twitter.py          # X posting
│   └── main.py             # Standalone runner
│
├── utils/                  # Shared utilities
│   ├── __init__.py
│   ├── i18n.py             # Translations (EN/RU/ZH)
│   ├── hashing.py          # SHA-256
│   └── memo.py             # Payment memo generation
│
├── templates/              # Jinja2 HTML templates
│   ├── index.html          # Landing page
│   ├── verify.html         # Seal verification
│   ├── feed.html           # Live token feed
│   └── score.html          # Rug score marketing
│
├── static/                 # Static assets
│   ├── css/
│   ├── images/
│   ├── whitepaper.md
│   └── memescan/
│       └── litepaper.md
│
├── tests/                  # pytest tests
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_database.py
│   └── test_handlers.py
│
├── docs/                   # THIS FOLDER
│   ├── README.md           # You are here
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── DATABASE.md
│   ├── DEPLOYMENT.md
│   ├── ROADMAP.md
│   └── archive/            # Old docs
│
├── memescan-app/           # React/Astro frontend
│
├── .claude/                # Claude Code instructions
│   └── CLAUDE.md
│
├── requirements.txt        # Python dependencies
├── Procfile                # Render start command
├── .env.template           # Environment template
└── README.md               # Main project README
```

---

## Environment Variables

See [DEPLOYMENT.md](./DEPLOYMENT.md) for full list. Critical ones:

```bash
# Required
BOT_TOKEN=              # From @BotFather
DATABASE_URL=           # PostgreSQL connection
TON_WALLET_SECRET=      # 24-word mnemonic
SERVICE_TON_WALLET=     # Your TON address

# Recommended
TONAPI_KEY=             # Instant payment detection
TWITTER_API_KEY=        # Social posting
```

---

## Common Tasks

### Add a new KOL

Edit `kol_models.py`, add to `GROK_KOL_SEED`, then call `/api/v1/kols/seed`.

### Check rug score

```bash
curl https://notaryton.com/api/v1/rug-score/EQ...
```

### View live feed

```bash
curl -N https://notaryton.com/feed
```

### Run locally

```bash
pip install -r requirements.txt
cp .env.template .env
# Edit .env
python bot.py
```

---

## Need Help?

- **Telegram**: [@MemeSealTON](https://t.me/MemeSealTON)
- **GitHub Issues**: [Open an issue](https://github.com/cherishwins/notaryton-bot/issues)

---

*Last generated by Claude on December 24, 2025*
