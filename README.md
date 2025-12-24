# NotaryTON Labs

**Proof or it didn't happen.**

A suite of TON blockchain products: notarization, token intelligence, and trader analytics.

---

## Quick Links

| What | Where |
|------|-------|
| **Live Site** | [notaryton.com](https://notaryton.com) |
| **Seal Bot** | [@MemeSealTON_bot](https://t.me/MemeSealTON_bot) |
| **Scan Bot** | [@MemeScanTON_bot](https://t.me/MemeScanTON_bot) |
| **Channel** | [@MemeSealTON](https://t.me/MemeSealTON) |
| **API Docs** | [docs/API.md](docs/API.md) |
| **Full Docs** | [docs/README.md](docs/README.md) |

---

## Products

### 1. MemeSeal (Revenue Driver)

Blockchain timestamping for the masses. Seal files on TON forever.

```
Send file → Pay 1 Star → Sealed on TON → Verify anytime
```

**Features:**
- Instant payments (Stars or TON)
- Weekly lottery (20% of fees to pot)
- Referral system (5% commission)
- Multi-language (EN/RU/ZH)

### 2. MemeScan (Growth Driver)

Token intelligence for TON meme coins. "Bloomberg for degens."

```
/check <token> → Safety score + holder analysis + rug detection
```

**Features:**
- Rug score (0-100 based on holder concentration)
- Live token feed with SSE streaming
- Token discovery crawler
- STON.fi and GeckoTerminal integration

### 3. Trader Intelligence (Data Moat)

KOL tracking and wallet analytics. Proprietary database.

```
82 KOLs → Track calls → Correlate wallets → Score performance
```

**Features:**
- 82 curated KOLs across 19 languages
- Filter by language/category/chain
- Wallet tracking infrastructure
- Call outcome tracking (future)

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Bot Framework | aiogram 3.15+ |
| API Server | FastAPI + uvicorn |
| Database | PostgreSQL (Render) |
| Blockchain | TON via pytoniq + TonAPI |
| Data Sources | GeckoTerminal, STON.fi, TonAPI |
| Payments | Telegram Stars + native TON |
| Hosting | Render.com |
| Domain | notaryton.com (Cloudflare) |

---

## Repository Structure

```
notaryton-bot/
├── bot.py              # Main FastAPI + Telegram bot (all endpoints)
├── crawler.py          # Token discovery + rug detection
├── database.py         # PostgreSQL schema + repositories
├── config.py           # Environment variables + constants
├── social.py           # X/Twitter + Telegram channel posting
│
├── kol_models.py       # KOL dataclasses + 82 seed profiles
├── kol_repository.py   # KOL database operations
│
├── memescan/           # Token scanner module
│   ├── api.py          # TonAPI, GeckoTerminal, STON.fi clients
│   ├── models.py       # Token, Pool, SafetyLevel dataclasses
│   ├── bot.py          # MemeScan bot handlers
│   ├── formatter.py    # Message formatting
│   └── twitter.py      # X/Twitter posting
│
├── utils/              # Shared utilities
│   ├── i18n.py         # Translations (EN/RU/ZH)
│   ├── hashing.py      # SHA-256 utilities
│   └── memo.py         # Payment memo generation
│
├── templates/          # HTML templates (landing, verify, feed)
├── static/             # Assets (CSS, images, whitepaper)
├── tests/              # pytest test suite
├── docs/               # Documentation
│
└── memescan-app/       # React frontend (Astro)
```

---

## Key Files Explained

| File | Purpose |
|------|---------|
| `bot.py` | **The monolith.** All Telegram handlers, FastAPI endpoints, payment processing, webhooks. Start here. |
| `crawler.py` | Background token discovery. Finds new tokens, calculates rug scores, stores in DB. |
| `database.py` | All PostgreSQL tables and repository classes. Users, seals, lottery, subscriptions, tokens, wallets. |
| `config.py` | Every environment variable. Never hardcode secrets. |
| `kol_models.py` | 82 KOL profiles with metadata (telegram, edge, engagement, chain_focus). |
| `kol_repository.py` | CRUD operations for KOLs. Filter by language/category/chain. |
| `memescan/api.py` | External API clients (TonAPI, GeckoTerminal, STON.fi). |

---

## API Endpoints

### Notarization

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/notarize` | POST | Seal a hash on TON |
| `/api/v1/verify/{hash}` | GET | Check if hash is sealed |
| `/api/v1/batch` | POST | Batch seal (up to 50) |

### Token Intelligence

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/tokens` | GET | List tracked tokens |
| `/api/v1/tokens/rugged` | GET | Tokens flagged as rugs |
| `/api/v1/rug-score/{address}` | GET | Get rug score for token |
| `/feed` | GET | SSE live token feed |

### KOL Intelligence

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/kols` | GET | List all KOLs |
| `/api/v1/kols/by-language/{lang}` | GET | Filter by language |
| `/api/v1/kols/by-category/{cat}` | GET | Filter by category |
| `/api/v1/kols/by-chain/{chain}` | GET | Filter by chain focus |
| `/api/v1/kols/filters` | GET | Available filter options |
| `/api/v1/kols/seed` | POST | Seed database with 82 KOLs |

### Lottery & Stats

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/pot` | GET | Current lottery pot |
| `/api/v1/lottery/pot` | GET | Detailed pot stats |
| `/health` | GET | Service health check |

---

## Self-Host

```bash
# Clone
git clone https://github.com/cherishwins/notaryton-bot.git
cd notaryton-bot

# Configure
cp .env.template .env
# Edit .env with your keys

# Install
pip install -r requirements.txt

# Run
python bot.py
```

### Required Environment Variables

```bash
BOT_TOKEN=           # From @BotFather
TON_WALLET_SECRET=   # 24-word mnemonic
SERVICE_TON_WALLET=  # Your wallet address
DATABASE_URL=        # PostgreSQL connection string
```

### Optional (Recommended)

```bash
TONAPI_KEY=          # Instant payment detection
TWITTER_API_KEY=     # Auto-post to X
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_SECRET=
```

See `config.py` for all available options.

---

## Bot Commands

### MemeSeal (@MemeSealTON_bot)

| Command | What It Does |
|---------|-------------|
| `/start` | Begin here |
| `/status` | Check subscription & stats |
| `/subscribe` | Unlimited seals (15 Stars/mo) |
| `/pot` | See lottery pot & countdown |
| `/mytickets` | Your lottery entries |
| `/referral` | Get your invite link |
| `/withdraw` | Cash out referral earnings |
| `/lang` | Switch language (EN/RU/ZH) |

### MemeScan (@MemeScanTON_bot)

| Command | What It Does |
|---------|-------------|
| `/start` | Welcome message |
| `/check <address>` | Safety analysis for token |
| `/trending` | Top 10 tokens by volume |
| `/new` | Recently launched tokens |
| `/pools` | Top liquidity pools |

---

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/README.md](docs/README.md) | **Start here.** Documentation index. |
| [docs/API.md](docs/API.md) | Full API reference with examples |
| [docs/DATABASE.md](docs/DATABASE.md) | Schema, tables, relationships |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, data flow |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Trader Intelligence roadmap |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Render setup, domains, env vars |
| [PRODUCT_MAP.md](PRODUCT_MAP.md) | Complete product architecture |

---

## Development

```bash
# Run tests
pytest tests/ -v

# Syntax check
python -m py_compile bot.py

# Run locally with hot reload
uvicorn bot:app --reload --port 8000
```

---

## Support

- **Telegram**: [@MemeSealTON](https://t.me/MemeSealTON)
- **Bot**: [@MemeSealTON_bot](https://t.me/MemeSealTON_bot)
- **Issues**: [GitHub](https://github.com/cherishwins/notaryton-bot/issues)

---

## License

MIT

---

**Seal it. Scan it. Track it. Become legend.**
