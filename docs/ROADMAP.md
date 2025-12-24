# Trader Intelligence Roadmap

> Building the data moat that correlates on-chain behavior with social media calls

## Vision

**The Problem:** Crypto traders make "calls" on X/Telegram but there's no way to verify:
- Did they actually buy before calling?
- Did they sell at the top while followers held bags?
- What's their real win rate vs claimed wins?

**The Solution:** Build a proprietary database that:
1. Tracks every token launch on TON from day zero
2. Records all wallet transactions (buys/sells)
3. Correlates wallets with social media accounts
4. Calculates real trader performance metrics

**The Moat:** This data accumulates daily. The longer we run, the more valuable the dataset becomes. Competitors would need months/years to catch up.

---

## Current State (Phase 0) ✅

**Live at notaryton.com**

| Feature | Status |
|---------|--------|
| Token discovery (GeckoTerminal) | ✅ Running |
| Safety scoring (0-100) | ✅ Working |
| Holder analysis (TonAPI) | ✅ Working |
| Rug detection (dev exit, holder exodus) | ✅ Working |
| Live SSE feed | ✅ /feed endpoint |
| Token stats API | ✅ /api/v1/tokens/* |

**Database:** 30+ tokens tracked and growing

---

## Phase 1: Wallet Tracking (Q1 2025)

### Goal
Track WHO is buying each token, not just token stats.

### New Data Collected

```
Token Launch → Track initial buyers
             → Record buy amounts
             → Snapshot wallet history
             → Tag whale wallets (>$10k)
             → Monitor for sells
```

### Database Additions

```sql
-- Holder snapshots for each token
CREATE TABLE holder_snapshots (
    id SERIAL PRIMARY KEY,
    token_address VARCHAR(100) REFERENCES tracked_tokens,
    wallet_address VARCHAR(100),
    balance DECIMAL(40, 0),
    balance_usd DECIMAL(20, 2),
    pct_of_supply DECIMAL(10, 4),
    snapshot_at TIMESTAMP DEFAULT NOW()
);

-- Known wallets (whales, devs, exchanges)
CREATE TABLE known_wallets (
    address VARCHAR(100) PRIMARY KEY,
    label VARCHAR(100),            -- 'whale', 'exchange', 'dev', 'influencer'
    owner_name VARCHAR(100),       -- Optional: known identity
    notes TEXT
);
```

### Implementation

1. **Crawler Enhancement:**
   - On new token: snapshot top 20 holders
   - Every 15 mins: re-snapshot tracked tokens
   - Detect holder changes (new whales, exits)

2. **New Endpoints:**
   - `GET /api/v1/tokens/{address}/holders` - Current top holders
   - `GET /api/v1/tokens/{address}/holder-history` - Holder changes over time
   - `GET /api/v1/wallets/{address}/activity` - What tokens did wallet trade

3. **Events:**
   - `whale_entry` - New whale >5% enters
   - `whale_exit` - Whale dumps >50% of holdings
   - `dev_sell` - Deployer wallet sells

### Value Unlock
- See coordinated wallet movements (pump groups)
- Identify "smart money" wallets that consistently win
- Early warning on rug: dev sells before announcement

---

## Phase 2: Trader Profiles (Q2 2025)

### Goal
Build profiles for traders linking wallets to social identities.

### Data Model

```sql
CREATE TABLE traders (
    id SERIAL PRIMARY KEY,

    -- Identity (may have multiple wallets)
    display_name VARCHAR(100),
    telegram_username VARCHAR(100),
    telegram_id BIGINT,
    x_username VARCHAR(100),

    -- Linked wallets
    primary_wallet VARCHAR(100),
    verified_at TIMESTAMP,           -- When they proved wallet ownership

    -- Aggregate stats (computed)
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5, 2),          -- % of trades that were profitable
    total_pnl_usd DECIMAL(20, 2),    -- Net profit/loss
    avg_hold_time_hours DECIMAL(10, 2),
    best_trade_roi DECIMAL(10, 2),
    worst_trade_roi DECIMAL(10, 2),

    -- Reputation
    reputation_score INTEGER DEFAULT 50,  -- 0-100
    flags TEXT[],                    -- ['verified', 'whale', 'rug_history']

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE TABLE trader_wallets (
    wallet_address VARCHAR(100) PRIMARY KEY,
    trader_id INTEGER REFERENCES traders,
    label VARCHAR(50),               -- 'main', 'trading', 'cold'
    verified BOOLEAN DEFAULT FALSE,
    added_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE trader_trades (
    id SERIAL PRIMARY KEY,
    trader_id INTEGER REFERENCES traders,
    wallet_address VARCHAR(100),
    token_address VARCHAR(100) REFERENCES tracked_tokens,

    trade_type VARCHAR(10),          -- 'buy', 'sell'
    amount_tokens DECIMAL(40, 0),
    amount_usd DECIMAL(20, 2),
    price_per_token DECIMAL(30, 18),

    tx_hash VARCHAR(100),
    timestamp TIMESTAMP
);
```

### Wallet Verification Methods

1. **Self-Submit** (easiest)
   - User sends small amount (0.001 TON) with memo
   - We verify memo matches their Telegram ID
   - Link wallet to profile

2. **X API Monitoring** (requires API access)
   - Monitor X for "just aped $TOKEN" posts
   - Match wallet activity within time window
   - Probabilistic linking

3. **Manual Verification**
   - User posts signed message
   - Cryptographic proof of wallet ownership

### Endpoints

```
GET /api/v1/traders/{username}
    → Profile, stats, trade history

GET /api/v1/traders/{username}/calls
    → Their X/Telegram calls with outcomes

GET /api/v1/traders/leaderboard
    → Top traders by win rate, PnL

POST /api/v1/traders/verify
    → Submit wallet verification
```

---

## Phase 3: Social Correlation (Q3 2025)

### Goal
Link social media "calls" to actual trading behavior.

### Data Collection

```sql
CREATE TABLE social_calls (
    id SERIAL PRIMARY KEY,

    -- Source
    platform VARCHAR(20),            -- 'x', 'telegram'
    post_id VARCHAR(100),
    author_username VARCHAR(100),
    author_trader_id INTEGER REFERENCES traders,

    -- Content
    token_address VARCHAR(100) REFERENCES tracked_tokens,
    call_type VARCHAR(20),           -- 'buy', 'sell', 'moon', 'avoid'
    confidence VARCHAR(20),          -- 'high', 'medium', 'low'

    -- Outcome (computed later)
    price_at_call DECIMAL(30, 18),
    price_24h_later DECIMAL(30, 18),
    price_7d_later DECIMAL(30, 18),
    roi_24h DECIMAL(10, 2),
    roi_7d DECIMAL(10, 2),

    posted_at TIMESTAMP,
    captured_at TIMESTAMP DEFAULT NOW()
);
```

### Collection Methods

1. **Manual Submission**
   - Users can submit calls they see
   - Earn rewards for accurate submissions

2. **Telegram Channel Monitoring**
   - Join influencer channels
   - Parse messages for token mentions
   - Link to our token database

3. **X API Monitoring** (if budget allows)
   - Track crypto influencers
   - Capture calls with token mentions
   - Match to on-chain data

### Analytics

```
Did trader buy before calling?
    → Check wallet activity < 1 hour before post

Did trader sell while followers held?
    → Compare trader exit timing vs bag holder losses

Call accuracy rate:
    → % of calls that were profitable at 24h/7d

Front-running score:
    → Average time between buy and public call
```

---

## Phase 4: Intelligence Products (Q4 2025)

### Products

1. **Trader Leaderboard**
   - Public ranking by verified performance
   - Filter by: win rate, total PnL, specialty (memes, DeFi, etc.)
   - Subscription for detailed analytics

2. **Smart Alerts**
   - "Whale X just bought $TOKEN"
   - "Trader with 80% win rate just called $Y"
   - "Dev wallet selling - potential rug"

3. **API Access**
   - Sell data to trading bots
   - Feed to analytics platforms
   - Premium tier for real-time data

4. **Verification Badges**
   - "Verified Trader" - linked wallet, >50 trades
   - "Profitable Trader" - >60% win rate over 3 months
   - "Diamond Hands" - avg hold time >7 days

### Revenue Model

| Product | Price | Target |
|---------|-------|--------|
| Basic Feed | Free | Everyone |
| Smart Alerts | $10/mo | Active traders |
| Full API | $100/mo | Bots, platforms |
| Verification Badge | $50 one-time | Influencers |

---

## Infrastructure Scaling

### Current ($14/mo)
- Render Starter: 512MB RAM
- PostgreSQL Basic: 256MB, 1GB storage

### Phase 1 ($25/mo)
- Render Standard: 1GB RAM
- PostgreSQL Starter: 1GB storage

### Phase 2+ ($50-100/mo)
- Dedicated crawler worker
- Larger PostgreSQL instance
- Redis for caching

### When to Scale
- Database >500MB → Upgrade PostgreSQL
- >100 req/min → Upgrade web service
- Crawler lagging → Separate worker

---

## Timeline Summary

| Phase | Target | Key Milestone |
|-------|--------|---------------|
| 0 | Done | Token tracking live |
| 1 | Q1 2025 | Wallet tracking + holder snapshots |
| 2 | Q2 2025 | Trader profiles + verification |
| 3 | Q3 2025 | Social media correlation |
| 4 | Q4 2025 | Paid intelligence products |

---

## Success Metrics

**Phase 1:**
- 1,000+ unique wallets tracked
- 100+ whale wallets labeled

**Phase 2:**
- 500+ verified trader profiles
- 10,000+ recorded trades

**Phase 3:**
- 1,000+ social calls captured
- Correlation accuracy >80%

**Phase 4:**
- $1,000/mo recurring revenue
- 100+ API subscribers

---

## The Data Moat Thesis

Every day we run:
- More tokens tracked = more historical context
- More wallets monitored = better pattern recognition
- More trades recorded = richer trader profiles
- More calls correlated = higher accuracy

A competitor starting today would need:
1. Our codebase (open source won't help without data)
2. Months of continuous data collection
3. Manual effort to verify wallet-social links

**The moat is TIME. Start now, compound daily.**
