# NotaryTON Bot - AI Agent Instructions

## Project Overview
A Telegram bot for auto-notarizing TON blockchain memecoin launches. Single-file monolith (`bot.py`) combining FastAPI webhook server, aiogram bot handlers, and TON blockchain integration. Deployed on Render.com with webhook architecture (no polling).

## Architecture & Key Components

### Hybrid FastAPI + aiogram Setup
- FastAPI handles webhook endpoint (`/webhook/{BOT_TOKEN}`) and stats API
- aiogram Dispatcher processes Telegram updates fed from webhook
- No `dp.start_polling()`—only webhook mode via `dp.feed_update(bot, update)`
- Server runs on port 8000 with uvicorn

### Database (SQLite)
- `notaryton.db` with 3 tables: `users`, `notarizations`, `pending_payments`
- All DB operations use `aiosqlite` (async context managers)
- Created on startup via `init_db()` in `@app.on_event("startup")`

### TON Blockchain Integration
- Uses `pytoniq` library (LiteBalancer + WalletV4R2)
- Wallet initialized from 24-word mnemonic in `TON_WALLET_SECRET`
- Transactions send comments formatted as `NotaryTON:Launch:{hash[:16]}`
- `get_contract_code_from_tx()`: Fetches contract bytecode via LiteBalancer
- `poll_wallet_for_payments()`: Background task with exponential backoff retry logic

## Critical Environment Variables
Required in `.env` (never commit—see `.env.example`):
- `BOT_TOKEN`: Telegram bot API token
- `TON_WALLET_SECRET`: 24-word mnemonic (space-separated)
- `SERVICE_TON_WALLET`: TON wallet address for receiving payments
- `WEBHOOK_URL`: Public URL (e.g., `https://notaryton.com` or `https://notaryton.onrender.com`)
- `GROUP_IDS`: Comma-separated Telegram chat IDs for monitoring (can be empty)

## Development Workflow

### Local Testing (with ngrok)
```bash
# Terminal 1: Start ngrok
ngrok http 8000

# Terminal 2: Update WEBHOOK_URL in .env with ngrok URL
# WEBHOOK_URL=https://abc123.ngrok.io

# Terminal 3: Run bot
pyenv shell 3.12.11  # Or your Python version
python bot.py
```

### Deployment
- Render.com deployment via `render.yaml` (auto-deploys from GitHub)
- Custom domain configured in GoDaddy DNS (CNAME to Render)
- See `DEPLOYMENT.md` for complete setup with actual credentials

## Code Patterns & Conventions

### Message Handlers
- Use `@dp.message(Command("commandname"))` for slash commands
- Use `@dp.message(F.text)` for text pattern matching
- Always check subscription with `await get_user_subscription(user_id)` before paid actions
- Reply with payment instructions including user ID as memo

### Auto-Notarization Flow
1. `handle_text_message()` filters for known `DEPLOY_BOTS` usernames
2. Extract TX ID via regex pattern `r"tx:\s*([A-Za-z0-9]+)"`
3. Fetch contract bytecode (stub), hash with SHA-256, send TON transaction
4. Log to `notarizations` table with `paid=True` if user has subscription

### File Notarization
- `@dp.message(F.document)` downloads file to `downloads/` directory
- Hash file with `hash_file()`, send transaction, clean up file
- Always create `downloads/` dir if not exists

## External Dependencies
- **aiogram 3.4.1**: Telegram bot framework (v3 async API)
- **pytoniq**: TON SDK (not `tonpy` or `tonclient`)
- **aiosqlite**: Async SQLite for DB operations
- **FastAPI + uvicorn**: Web server for webhook

## Common Pitfalls
- **Never use polling**: This is a webhook-only bot—`start_polling()` will conflict with FastAPI
- **Wallet must have balance**: Bot can't send transactions if wallet is empty (check tonscan.org)
- **Webhook URL mismatch**: Ensure `WEBHOOK_URL` matches actual deployed URL (Render or custom domain)
- **Group IDs format**: Must be numeric chat IDs (negative numbers) or `@username`, comma-separated

## Strategic Infrastructure Features

### Public API Endpoints (Revenue Multipliers)
- **POST /api/v1/notarize** - Third-party bots can integrate NotaryTON
- **POST /api/v1/batch** - High-volume batch notarization (50 contracts/request)
- **GET /api/v1/verify/{hash}** - Public verification (builds trust/network effects)
- Authentication via Telegram user_id as API key (subscription required)

### Referral System (Network Effects)
- Users get unique referral codes: `REF{user_id}`
- 5% commission on all referrals' payments
- Tracked in `referred_by` column, earnings in `referral_earnings`
- `/referral` command shows stats and shareable link

### Business Model Evolution
1. **B2C**: Individual traders subscribe ($0.18/month)
2. **B2B**: Deploy bots integrate via API (become dependencies)
3. **Network**: Referrals create viral growth (5% incentive)
4. **Data**: Verified contract registry = valuable dataset

### Completed Core Features
- ✅ `get_contract_code_from_tx()`: Fetches account state via pytoniq LiteBalancer
- ✅ `poll_wallet_for_payments()`: Monitors incoming TON, parses memos, auto-activates subs
- ✅ Referral tracking: DB schema + handlers + /referral command

## Admin Scripts
- `outreach.py`: Standalone script to DM group admins with referral program pitch
- Logs sent messages to `outreach_sent.csv` to avoid duplicates
- Targets groups in `TARGET_GROUPS` list, rate-limited to 1 DM/second

## Testing Commands
- `/start` - Basic functionality check
- `/subscribe` - Shows payment instructions (0.1 TON)
- `/status` - Verifies subscription checking logic
- `/notarize` - Manual notarization flow
- Send file to test document hashing

## Monetization & Growth Strategy

### Revenue Streams (Diversified)
1. **Subscriptions**: $0.18/month × 1000 users = $180/month baseline
2. **API Usage**: Other bots depend on us = recurring revenue
3. **Batch Operations**: High-volume clients (exchanges, aggregators)
4. **White-Label**: License to law firms, notaries ($50-500/month each)
5. **Data Licensing**: Verified contract database to analytics platforms

### Competitive Moats
- **First-mover**: Own "notarization" category on TON
- **Network effects**: More verifications = more trust = more usage
- **API dependencies**: Other bots integrate, become locked-in
- **Blockchain proof**: Immutable audit trail nobody else has
- **Referral flywheel**: Users recruit users for 5% commission

### GTM Tactics
1. Auto-join top 100 TON Telegram groups (where launches happen)
2. DM group admins with referral offers (outreach.py script)
3. Partner with deploy bots (they pin NotaryTON, earn referral %)
4. Product Hunt launch: "Blockchain Notary for Crypto Launches"
5. Build public verification UI (SEO for contract searches)

### Key Metrics to Track
- Daily Active Users (DAU)
- Notarizations/day (proxy for TON memecoin activity)
- API requests/day (B2B adoption)
- Referral conversion rate
- Subscription renewal rate (aim for >70%)

## Technical Scaling Considerations
- Current: Single SQLite file (fine up to ~100k notarizations)
- Next: PostgreSQL + read replicas (if >1M notarizations/month)
- API rate limiting: Implement per-key limits (use FastAPI middleware)
- Batch processing: Queue system for >100 concurrent requests
- Webhook reliability: Add retry logic with exponential backoff

## References
- TON blockchain explorer: https://tonscan.org
- aiogram v3 docs: https://docs.aiogram.dev/en/latest/
- pytoniq examples: https://github.com/yungwine/pytoniq
- TON API docs: https://tonapi.io/
- FastAPI best practices: https://fastapi.tiangolo.com/
