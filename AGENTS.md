# AGENTS.md - NotaryTON Labs

> **Documentation for AI Coding Agents**  
> Last Updated: February 21, 2026

This file contains essential information for AI coding agents working on the NotaryTON Labs project. Read this before making any changes.

---

## 1. Project Overview

**NotaryTON Labs** is a suite of TON blockchain products built around three core offerings:

| Product | Description | Bot |
|---------|-------------|-----|
| **MemeSeal** | Blockchain timestamping for files/contracts. Revenue driver. | @MemeSealTON_bot |
| **MemeScan** | Token intelligence and rug detection for TON meme coins. | @MemeScanTON_bot |
| **Trader Intelligence** | KOL tracking and wallet analytics (data moat). | API only |

**Tagline:** "Proof or it didn't happen."

**Live URLs:**
- Main site: https://notaryton.com
- API Base: https://notaryton.com/api/v1/
- Telegram Channel: @MemeSealTON

---

## 2. Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| **Language** | Python | 3.11+ |
| **Bot Framework** | aiogram | 3.15+ |
| **API Server** | FastAPI + uvicorn | 0.115+ / 0.34+ |
| **Database** | PostgreSQL | 14+ (Render) |
| **Blockchain** | TON via pytoniq + TonAPI | 0.1.42+ |
| **ORM/DB Driver** | asyncpg | 0.30+ |
| **Frontend** | React + Vite + TypeScript | (memescan-app/) |
| **Smart Contracts** | TACT | (sealbet/) |
| **Payments** | Telegram Stars + native TON | - |
| **Hosting** | Render.com | Web Service |
| **Domain** | Cloudflare → Render | notaryton.com |

**Key External APIs:**
- TonAPI (real-time transaction webhooks)
- GeckoTerminal (token data, 30 req/min limit)
- STON.fi (DEX data)
- X/Twitter API v2 (social posting)

---

## 3. Repository Structure

```
notaryton-bot/
│
├── Core Application Files
│   ├── bot.py                  # MAIN FILE (~22K lines) - FastAPI + all Telegram handlers
│   ├── config.py               # All environment variables and constants
│   ├── database.py             # PostgreSQL connection + repository pattern
│   ├── crawler.py              # Token discovery + rug detection background task
│   └── social.py               # X/Twitter + Telegram channel posting
│
├── KOL Intelligence
│   ├── kol_models.py           # 82 KOL dataclasses with metadata
│   └── kol_repository.py       # KOL database operations + filtering
│
├── MemeScan Module
│   └── memescan/
│       ├── api.py              # TonAPI, GeckoTerminal, STON.fi clients
│       ├── bot.py              # MemeScan bot handlers
│       ├── models.py           # Token, Pool, SafetyLevel dataclasses
│       ├── formatter.py        # Message formatting
│       ├── twitter.py          # X/Twitter posting
│       └── main.py             # Standalone runner
│
├── Utilities
│   └── utils/
│       ├── i18n.py             # Translations (EN/RU/ZH)
│       ├── hashing.py          # SHA-256 utilities
│       └── memo.py             # Payment memo generation
│
├── Frontend
│   ├── templates/              # Jinja2 HTML templates
│   │   ├── index.html          # Landing page
│   │   ├── verify.html         # Seal verification
│   │   ├── feed.html           # Live token feed
│   │   └── score.html          # Rug score marketing
│   ├── static/                 # CSS, images, whitepaper
│   └── memescan-app/           # React/Vite frontend (separate deployment)
│
├── Testing
│   └── tests/
│       ├── conftest.py         # Pytest fixtures
│       ├── test_database.py    # Database operation tests
│       ├── test_api.py         # API endpoint tests
│       └── test_handlers.py    # Telegram handler tests
│
├── Documentation
│   ├── docs/                   # Comprehensive documentation
│   │   ├── README.md           # Docs index
│   │   ├── ARCHITECTURE.md     # System design
│   │   ├── API.md              # REST API reference
│   │   ├── DATABASE.md         # Schema documentation
│   │   └── DEPLOYMENT.md       # Deployment guide
│   ├── PRODUCT_MAP.md          # Complete product architecture
│   └── README.md               # Main project README
│
├── Configuration
│   ├── requirements.txt        # Python dependencies
│   ├── render.yaml             # Render deployment config
│   ├── runtime.txt             # Python version for Render
│   ├── pytest.ini              # Test configuration
│   └── .env.template           # Environment variable template
│
└── Smart Contracts
    └── sealbet/                # TACT smart contracts + frontend
```

---

## 4. Build and Test Commands

### Local Development Setup

```bash
# 1. Clone and setup
cd /home/jesse/dev/projects/personal/ton/notaryton-bot
cp .env.template .env
# Edit .env with your values

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the bot
python bot.py
```

### Testing Commands

```bash
# Run all tests
pytest tests/ -v

# Run specific test types
pytest tests/ -v -m unit           # Unit tests only
pytest tests/ -v -m integration    # Integration tests only
pytest tests/ -v -m "not slow"     # Skip slow tests

# Run with coverage
pytest tests/ -v --cov=.

# Syntax check (quick validation)
python -m py_compile bot.py
```

### Hot Reload Development

```bash
# Run FastAPI with hot reload (for web development)
uvicorn bot:app --reload --port 8000
```

---

## 5. Code Style Guidelines

### Python Style

- **Clear > clever** - Code should be readable first
- **Comments explain "why", not "what"**
- **Functions do one thing** - Keep functions under 50 lines when possible
- **Type hints** - Use typing for function signatures
- **Async/await** - All database and network operations are async
- **f-strings** - Use f-strings for string formatting

### Example Pattern

```python
async def get_user_with_subscription(user_id: int) -> Optional[User]:
    """
    Fetch user and check if subscription is active.
    
    Returns None if user not found.
    Subscription check handles timezone-aware comparison.
    """
    user = await db.users.get(user_id)
    if not user:
        return None
    return user if user.has_active_subscription else None
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Constants | UPPER_SNAKE_CASE | `STARS_SINGLE_NOTARIZATION = 3` |
| Functions | snake_case | `async def get_user_subscription(...)` |
| Classes | PascalCase | `class TokenCrawler:` |
| Variables | snake_case | `user_id`, `contract_hash` |
| Private | _leading_underscore | `_crawl_interval` |

### Error Handling

- **User-facing errors** - Send helpful messages to users via Telegram
- **Log with context** - Always include relevant IDs in error logs
- **Graceful degradation** - Never crash the bot; handle errors at boundaries

```python
try:
    result = await risky_operation()
except Exception as e:
    print(f"❌ Error in risky_operation for user {user_id}: {e}")
    await message.reply("⚠️ Something went wrong. Please try again.")
```

---

## 6. Testing Instructions

### Test Organization

Tests are organized by type using pytest markers:

- `@pytest.mark.unit` - Fast tests with no external dependencies
- `@pytest.mark.integration` - Tests requiring database/network
- `@pytest.mark.slow` - Tests taking >1 second

### Running Tests

```bash
# From project root
pytest tests/ -v

# Run specific file
pytest tests/test_database.py -v

# Run with markers
pytest tests/ -v -m unit
```

### Test Database

Tests use a temporary SQLite database created in `conftest.py`. The fixture `test_db` provides an isolated database for each test.

### Adding New Tests

```python
# tests/test_feature.py
import pytest

@pytest.mark.unit
@pytest.mark.asyncio
async def test_new_feature(test_db, sample_user_id):
    """Test description."""
    # Arrange
    expected = "result"
    
    # Act
    actual = await new_feature_function(test_db, sample_user_id)
    
    # Assert
    assert actual == expected
```

---

## 7. Security Considerations

### Critical Security Rules

1. **NEVER commit secrets** - All secrets in environment variables only
2. **NEVER log secrets** - Wallet mnemonics, API keys stay out of logs
3. **Validate all user input** - Telegram IDs, addresses, amounts
4. **Rate limit public endpoints** - Prevent abuse
5. **Use HTTPS only** - Webhooks must use TLS

### Environment Variables (Secrets)

These MUST be set in Render Dashboard, never in code:

```bash
BOT_TOKEN=                    # Telegram bot token
MEMESEAL_BOT_TOKEN=           # Second bot token
TON_WALLET_SECRET=            # 24-word mnemonic (CRITICAL - NEVER LOG)
SERVICE_TON_WALLET=           # Wallet address
TON_CENTER_API_KEY=           # TonCenter API
TONAPI_KEY=                   # TonAPI key
TWITTER_API_KEY=              # X API
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_SECRET=
DATABASE_URL=                 # PostgreSQL connection string
```

### HMAC Verification

TonAPI webhooks use HMAC signature verification:

```python
signature = hmac.new(
    TONAPI_WEBHOOK_SECRET.encode(),
    await request.body(),
    hashlib.sha256
).hexdigest()

if signature != request.headers.get("X-TonAPI-Signature"):
    return JSONResponse({"error": "Invalid signature"}, status_code=401)
```

### Database Security

- PostgreSQL SSL required (`ssl='require'`)
- Connection pooling (min: 2, max: 10)
- Command timeout: 30 seconds
- No SQL injection - use parameterized queries only

---

## 8. Deployment Process

### Render.com Deployment

The application deploys to Render.com using `render.yaml`:

```yaml
services:
  - type: web
    name: notaryton-bot
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: python bot.py
    healthCheckPath: /health
```

### Deployment Steps

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Your changes"
   git push origin main
   ```

2. **Auto-deploy:** Render auto-deploys on push to main

3. **Verify:**
   ```bash
   curl https://notaryton.com/health
   # Should return: {"status": "running"}
   ```

### Manual Deploy (Render Dashboard)

1. Go to Render Dashboard
2. Select `notaryton-bot` service
3. Click "Manual Deploy" → "Deploy latest commit"

### Database Migrations

The application auto-creates tables on startup. No manual migrations needed for new tables.

---

## 9. Key Architectural Patterns

### Repository Pattern

Database access goes through repository classes:

```python
from database import db

# Initialize on startup
await db.connect()

# Use repositories
user = await db.users.get(user_id)
await db.notarizations.create(user_id, hash)
await db.tokens.update_safety_score(address, score)

# Cleanup
await db.disconnect()
```

### Webhook Architecture

- Telegram bot uses webhooks (not polling) for production
- TonAPI webhooks provide instant payment detection
- All webhooks verified with HMAC signatures

### Background Tasks

- Token crawler runs as `asyncio.create_task()`
- Lottery draw scheduled (Sundays at midnight UTC)
- Payment polling as fallback (only if webhooks fail)

---

## 10. Common Tasks Reference

### Adding a New Command

1. Add handler in `bot.py`:
```python
@dp.message(Command("newcmd"))
async def cmd_newcmd(message: types.Message):
    """Handler docstring."""
    await message.reply("Response text")
```

2. Add to help text in `TRANSLATIONS` dict
3. Test locally
4. Deploy

### Adding a New KOL

1. Edit `kol_models.py`
2. Add to `GROK_KOL_SEED` list
3. Call `/api/v1/kols/seed` endpoint

### Checking Logs

```bash
# Via Render CLI
render logs -s notaryton-bot --tail

# Or view in Render Dashboard → Service → Logs
```

### Database Queries

```bash
# Connect to Render PostgreSQL
psql $DATABASE_URL

# Common queries
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM notarizations WHERE paid = true;
SELECT * FROM tracked_tokens ORDER BY first_seen DESC LIMIT 10;
```

---

## 11. File-Specific Notes

### bot.py
- **The monolith** - All Telegram handlers, FastAPI endpoints, payment processing
- ~22,000 lines - use search to navigate
- Key sections: handlers, API endpoints, payment processing, background tasks

### database.py
- PostgreSQL connection pool management
- Repository classes for each table
- Dataclass models for type safety

### config.py
- Single source of truth for all config
- Environment variables loaded via `python-dotenv`
- Pricing constants, rate limits

### crawler.py
- Background token discovery
- Safety score calculation
- Rug detection logic

---

## 12. Troubleshooting

### Bot Not Responding

1. Check Render logs for errors
2. Verify webhook: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
3. Check health endpoint: `curl https://notaryton.com/health`

### Database Connection Issues

1. Verify `DATABASE_URL` is set
2. Check SSL mode is enabled
3. Verify Render PostgreSQL is running

### Payment Detection Issues

1. Check `TONAPI_KEY` is set correctly
2. Verify webhook secret matches TonAPI dashboard
3. Check logs for HMAC verification errors

---

## 13. External Resources

| Resource | URL |
|----------|-----|
| Telegram Bot API | https://core.telegram.org/bots/api |
| Telegram Payments (Stars) | https://core.telegram.org/bots/payments-stars |
| TonAPI Docs | https://docs.tonconsole.com/tonapi/ |
| aiogram Docs | https://docs.aiogram.dev/ |
| FastAPI Docs | https://fastapi.tiangolo.com/ |
| Render Docs | https://docs.render.com/ |

---

## 14. Product Principles

When making changes, remember:

1. **User Experience Above All** - Instant feedback, honest communication, reduce friction
2. **Simple > Complex** - Three options max. Two is better. One is best.
3. **Quality is Non-Negotiable** - Code should work the first time
4. **Ship Fast, Iterate Faster** - Perfect is the enemy of shipped

**Brand Elements:**
- Frog emoji (🐸) is part of brand identity
- "Proof or it didn't happen" is the tagline
- Multi-language support is important (EN/RU/ZH)

---

*"Design is not just what it looks like and feels like. Design is how it works."* — Steve Jobs
