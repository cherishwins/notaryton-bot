# Database Schema

> PostgreSQL on Render (Basic 256MB plan)

## Tables Overview

| Table | Purpose | Records |
|-------|---------|---------|
| users | User accounts, subscriptions, referrals | Growing |
| notarizations | Seal records with hashes | Growing |
| tracked_tokens | Token rug detection data moat | 30+ and growing |
| token_events | Significant token events (deploy, rug) | Growing |
| lottery_entries | Weekly lottery tickets | Cyclic |
| api_keys | API access keys | Small |
| bot_state | Key-value store for bot state | Tiny |
| pending_payments | Temporary payment records | Tiny |

---

## Core Tables

### users

Primary user table with subscriptions and referral system.

```sql
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,           -- Telegram user ID
    subscription_expiry TIMESTAMP,         -- Active sub expires
    total_paid DECIMAL(20, 8) DEFAULT 0,   -- Lifetime payments
    referral_code VARCHAR(20) UNIQUE,      -- User's referral code
    referred_by BIGINT REFERENCES users,   -- Who referred them
    referral_earnings DECIMAL(20, 8) DEFAULT 0,  -- 5% commission earned
    total_withdrawn DECIMAL(20, 8) DEFAULT 0,
    withdrawal_wallet VARCHAR(100),        -- TON wallet for payouts
    language VARCHAR(10) DEFAULT 'en',     -- en/ru/zh
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Key queries:**
```sql
-- Check subscription
SELECT subscription_expiry FROM users WHERE user_id = $1;

-- Get referral stats
SELECT referral_code, referral_earnings, total_withdrawn FROM users WHERE user_id = $1;
```

### notarizations

All sealed files/contracts.

```sql
CREATE TABLE notarizations (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    tx_hash VARCHAR(100),                  -- TON transaction hash (nullable)
    contract_hash VARCHAR(64) NOT NULL,    -- SHA-256 of content
    timestamp TIMESTAMP DEFAULT NOW(),
    paid BOOLEAN DEFAULT FALSE,
    via_api BOOLEAN DEFAULT FALSE          -- API vs Telegram
);
```

**Indexes:**
- `idx_notarizations_user_id` - User history
- `idx_notarizations_contract_hash` - Verification lookups
- `idx_notarizations_timestamp` - Recent seals

---

## Token Tracking Tables (DATA MOAT)

### tracked_tokens

Every token discovered and analyzed for rug detection.

```sql
CREATE TABLE tracked_tokens (
    address VARCHAR(100) PRIMARY KEY,      -- Jetton master address
    symbol VARCHAR(50),
    name VARCHAR(200),
    decimals INTEGER DEFAULT 9,
    deployer VARCHAR(100),                 -- Creator wallet
    total_supply DECIMAL(40, 0),

    -- Snapshot at first detection
    first_seen TIMESTAMP DEFAULT NOW(),
    initial_holder_count INTEGER DEFAULT 0,
    initial_top_holder_pct DECIMAL(10, 2), -- Dev wallet % at launch
    initial_liquidity_usd DECIMAL(20, 2),

    -- Safety analysis
    safety_score INTEGER DEFAULT 50,       -- 0-100 (80+ = safe)
    lp_locked BOOLEAN DEFAULT FALSE,
    ownership_renounced BOOLEAN DEFAULT FALSE,

    -- Rug detection
    first_dev_sell_at TIMESTAMP,           -- When dev first sold
    first_dev_sell_pct DECIMAL(10, 2),     -- % they sold
    rugged BOOLEAN DEFAULT FALSE,          -- Final rug verdict
    rugged_at TIMESTAMP,

    -- Current state (updated periodically)
    current_holder_count INTEGER DEFAULT 0,
    current_top_holder_pct DECIMAL(10, 2),
    current_price_usd DECIMAL(30, 18) DEFAULT 0,
    last_updated TIMESTAMP DEFAULT NOW()
);
```

**Safety Score Calculation:**
```python
safety_score = 50  # Default

# Holder count bonus/penalty
if holder_count >= 100:
    safety_score += 10
elif holder_count < 10:
    safety_score -= 20

# Dev concentration penalty
if dev_wallet_percent > 50:
    safety_score -= 30
elif dev_wallet_percent > 20:
    safety_score -= 15
```

**Rug Detection Triggers:**
1. Dev sold >90% of holdings
2. Holder count dropped >80% from initial

### token_events

Timeline of significant events per token.

```sql
CREATE TABLE token_events (
    id SERIAL PRIMARY KEY,
    token_address VARCHAR(100) REFERENCES tracked_tokens(address),
    event_type VARCHAR(50),  -- 'deploy', 'first_sell', 'whale_dump', 'rug', 'moon'
    event_data JSONB,        -- Flexible metadata
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Event Types:**
| Type | When | event_data example |
|------|------|-------------------|
| deploy | First seen | `{"symbol": "PEPE", "holder_count": 5}` |
| first_sell | Dev first sells | `{"pct_sold": 15.5}` |
| whale_dump | Top holder sells >10% | `{"wallet": "EQ...", "pct": 25}` |
| rug | Marked as rugged | `{"detection_method": "dev_exit"}` |
| moon | 10x from launch | `{"initial_mcap": 1000, "current": 10000}` |

---

## Lottery Tables

### lottery_entries

Weekly lottery tickets (20% of each seal payment).

```sql
CREATE TABLE lottery_entries (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    amount_stars INTEGER DEFAULT 1,        -- Stars paid
    created_at TIMESTAMP DEFAULT NOW(),
    draw_id INTEGER,                       -- NULL = current draw
    won BOOLEAN DEFAULT FALSE
);
```

**Draw Logic:**
1. Every Sunday midnight UTC
2. Random entry wins (weighted by ticket count)
3. Winner gets pot (20% of all fees that week)
4. All entries get `draw_id` set, winner gets `won = TRUE`

---

## Utility Tables

### api_keys

```sql
CREATE TABLE api_keys (
    key VARCHAR(64) PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT NOW(),
    last_used TIMESTAMP,
    requests_count INTEGER DEFAULT 0
);
```

### bot_state

Simple key-value store for persistent state.

```sql
CREATE TABLE bot_state (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT
);
```

Used for: last lottery draw ID, maintenance mode, etc.

### pending_payments

Temporary records for TON payment matching.

```sql
CREATE TABLE pending_payments (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    amount DECIMAL(20, 8),
    memo VARCHAR(200),                     -- Contains user ID
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Indexes

```sql
-- User lookups
CREATE INDEX idx_users_referral_code ON users(referral_code);
CREATE INDEX idx_users_referred_by ON users(referred_by);

-- Notarization queries
CREATE INDEX idx_notarizations_user_id ON notarizations(user_id);
CREATE INDEX idx_notarizations_contract_hash ON notarizations(contract_hash);
CREATE INDEX idx_notarizations_timestamp ON notarizations(timestamp DESC);

-- Token tracking
CREATE INDEX idx_tracked_tokens_first_seen ON tracked_tokens(first_seen DESC);
CREATE INDEX idx_tracked_tokens_safety_score ON tracked_tokens(safety_score);
CREATE INDEX idx_tracked_tokens_rugged ON tracked_tokens(rugged);
CREATE INDEX idx_token_events_address ON token_events(token_address);
CREATE INDEX idx_token_events_type ON token_events(event_type);

-- Lottery
CREATE INDEX idx_lottery_entries_user_id ON lottery_entries(user_id);
CREATE INDEX idx_lottery_entries_draw_id ON lottery_entries(draw_id);

-- API
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
```

---

## Repository Pattern

All database access goes through repository classes:

```python
from database import db

# Initialize on startup
await db.connect()

# Access via repositories
user = await db.users.get(user_id)
await db.notarizations.create(user_id, hash)
stats = await db.tokens.get_stats()
await db.lottery.add_entry(user_id, stars=3)

# Cleanup
await db.disconnect()
```

**Repositories:**
- `db.users` - UserRepository
- `db.notarizations` - NotarizationRepository
- `db.tokens` - TokenRepository
- `db.lottery` - LotteryRepository
- `db.api_keys` - ApiKeyRepository
- `db.bot_state` - BotStateRepository

---

## Connection

```python
# asyncpg with SSL (required for Render)
self._pool = await asyncpg.create_pool(
    url,
    min_size=2,
    max_size=10,
    command_timeout=30,
    ssl='require'
)
```

**Environment Variable:**
```
DATABASE_URL=postgresql://user:pass@host/dbname?sslmode=require
```

---

## Future: Trader Intelligence Tables

Phase 2 will add:

```sql
-- Trader profiles
CREATE TABLE traders (
    wallet_address VARCHAR(100) PRIMARY KEY,
    telegram_username VARCHAR(100),
    x_username VARCHAR(100),
    total_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5, 2),
    avg_roi DECIMAL(10, 2),
    verified BOOLEAN DEFAULT FALSE
);

-- Trade history
CREATE TABLE trader_trades (
    id SERIAL PRIMARY KEY,
    wallet_address VARCHAR(100) REFERENCES traders,
    token_address VARCHAR(100) REFERENCES tracked_tokens,
    trade_type VARCHAR(10),  -- 'buy', 'sell'
    amount DECIMAL(40, 0),
    price_usd DECIMAL(30, 18),
    timestamp TIMESTAMP
);
```

See [ROADMAP.md](./ROADMAP.md) for full Trader Intelligence vision.
