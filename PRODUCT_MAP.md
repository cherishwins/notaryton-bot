# NotaryTON Labs - Complete Product Map

*Generated: December 6, 2025*

---

## Live Stats (Right Now)

```
Total Users:        4
Total Seals:        1
Lottery Pot:        500 Stars (~0.5 TON)
Lottery Players:    2
Next Draw:          Sunday 8pm UTC
```

---

## Product Architecture

```
                         NotaryTON Labs
                    (notaryton.com - Render)
                              |
        +---------+-----------+-----------+---------+
        |         |           |           |         |
    MemeSeal   MemeScan    Casino      API       Landing
    (Bot)      (Bot)      (Vercel)   (REST)      (Web)
```

---

## Product 1: MemeSeal (Core Revenue Driver)

### What It Does
Timestamps files on TON blockchain. Proof something existed at a specific time.

### Bots
- `@MemeSealTON_bot` - Main degen-branded bot
- `@NotaryTON_bot` - Professional/legacy bot (same backend)

### User Journey

```
USER SENDS FILE
      |
      v
+----------------+
| Bot receives   |
| Shows payment  |
| options        |
+----------------+
      |
      +-----> [Pay 1 Star] -----> Telegram Stars checkout
      |                                    |
      +-----> [Pay 0.015 TON] --> Shows wallet + memo
                                           |
                                           v
                              +------------------------+
                              | TonAPI webhook detects |
                              | payment, auto-seals    |
                              +------------------------+
                                           |
                                           v
                              +------------------------+
                              | 1. Hash file (SHA-256) |
                              | 2. Store in PostgreSQL |
                              | 3. Write to TON chain  |
                              | 4. Add lottery ticket  |
                              | 5. Post to X + TG      |
                              +------------------------+
                                           |
                                           v
                              +------------------------+
                              | User gets:             |
                              | - Verify link          |
                              | - Lottery ticket       |
                              | - Social post          |
                              +------------------------+
```

### Revenue Capture Points

| Action | Price | Revenue |
|--------|-------|---------|
| Single seal | 1 Star (~$0.02) | 80% to you, 20% to lottery |
| Single seal | 0.015 TON (~$0.05) | 80% to you, 20% to lottery |
| Monthly unlimited | 20 Stars (~$0.40) | 100% to you |
| Monthly unlimited | 0.3 TON (~$1.00) | 100% to you |
| Referral | 5% of referral's payments | Ongoing |

### Features Status

| Feature | Status | Notes |
|---------|--------|-------|
| Star payments | WORKING | Telegram checkout flow |
| TON payments | WORKING | TonAPI webhook auto-detection |
| File hashing | WORKING | SHA-256 |
| DB storage | WORKING | PostgreSQL on Render |
| Blockchain write | WORKING | pytoniq + WalletV5R1 |
| Lottery tickets | WORKING | Auto-added on each seal |
| Twitter auto-post | WORKING | Rate-limited |
| TG channel post | WORKING | @MemeSealTON |
| Subscription check | WORKING | 30-day tracking |
| Referral system | WORKING | 5% commission |
| Withdrawal | WORKING | Min 0.05 TON |
| i18n (EN/RU/ZH) | WORKING | Auto-detect from Telegram |

---

## Product 2: MemeScan (Free, Growth Driver)

### What It Does
Token scanner for TON meme coins. "Bloomberg for degens."

### Bot
- `@MemeScanTON_bot`

### User Journey

```
USER SENDS COMMAND
      |
      +-----> /trending --> Top 10 meme coins by volume
      |
      +-----> /new -------> Newly launched tokens
      |
      +-----> /check <addr> --> Token safety analysis
      |                              |
      |                              v
      |                    +-----------------+
      |                    | SAFE / CAUTION  |
      |                    | / DANGER score  |
      |                    | + holder dist   |
      |                    | + dev wallet %  |
      |                    | + liquidity     |
      |                    +-----------------+
      |
      +-----> /pools -----> Top liquidity pools
```

### Data Sources

| Source | What It Provides |
|--------|------------------|
| STON.fi API | Pools, volume, liquidity, prices |
| TonAPI | Holder distribution, wallet analysis |
| GeckoTerminal | Price feeds, market data |

### Revenue Model (Future)
- **Premium alerts** - Whale movements, launch sniping
- **API access** - For traders
- **Ad slots** - Projects pay for visibility

### Features Status

| Feature | Status | Notes |
|---------|--------|-------|
| /trending | WORKING | Top 10 by volume |
| /new | WORKING | New launches |
| /check | WORKING | Safety scoring |
| /pools | WORKING | STON.fi pools |
| Twitter auto-post | WORKING | @MemeScanTON |
| Premium features | NOT BUILT | Future |
| Whale alerts | NOT BUILT | Future |

---

## Product 3: Casino (Demo Mode)

### What It Does
Gambling mini-app embedded in Telegram.

### Access
- `memeseal-casino.vercel.app`
- Via `/casino` command in MemeSeal bot

### Games Available

| Game | Status | Notes |
|------|--------|-------|
| Slots | BUILT | Politician theme, animations |
| Crash | BUILT | Frog rocket, multiplier game |
| Roulette | BUILT | Election theme |

### User Journey (Current - DEMO)

```
USER TAPS /casino or PLAY button
      |
      v
+------------------+
| Telegram Mini    |
| App opens        |
| (Vercel hosted)  |
+------------------+
      |
      v
+------------------+
| Fake balance     |
| (Local state)    |
| No real money    |
+------------------+
      |
      v
+------------------+
| Play games       |
| Win/lose fake $  |
| No persistence   |
+------------------+
```

### What's Missing (To Make Real Money)

```
REQUIRED TO MONETIZE:
1. Stars -> Chips purchase flow
2. Database-backed balance
3. Chips -> Cashout flow
4. Win/loss persistence
5. House edge configuration
```

### Revenue Model (When Built)
- House edge on all games
- Star deposits for chips
- Potential rake on high-roller tables

---

## Product 4: REST API

### Endpoints

| Endpoint | Method | What It Does | Status |
|----------|--------|--------------|--------|
| `/api/v1/notarize` | POST | Seal a hash | WORKING |
| `/api/v1/verify/{hash}` | GET | Check if hash is sealed | WORKING |
| `/api/v1/batch` | POST | Batch seal (up to 50) | WORKING |
| `/api/v1/lottery/pot` | GET | Get pot stats | WORKING |
| `/api/v1/lottery/tickets/{user_id}` | GET | User's tickets | WORKING |
| `/api/v1/casino/bet` | POST | Place bet (demo) | DEMO ONLY |

### Authentication
- API keys (generated via `/api` command)
- Rate limit: 1000 requests/day

---

## Lottery System

### How It Works

```
EVERY SEAL PAYMENT
      |
      v
+------------------+
| 20% goes to pot  |
| User gets ticket |
+------------------+
      |
      v
SUNDAY 8PM UTC
      |
      v
+------------------+
| Random winner    |
| picked from all  |
| tickets (more    |
| tickets = more   |
| chances)         |
+------------------+
      |
      v
+------------------+
| Winner gets pot  |
| Auto-payout TON  |
| Announce on X+TG |
+------------------+
      |
      v
+------------------+
| Pot resets to 0  |
| New round starts |
+------------------+
```

### Current Pot
- 500 Stars (~0.5 TON)
- 2 participants
- 2 tickets total

---

## Referral System

### Flow

```
USER A gets referral link
      |
      v
t.me/MemeSealTON_bot?start=REF{user_id}
      |
      v
USER B clicks link, starts bot
      |
      v
USER B is tagged as referred_by = USER A
      |
      v
EVERY TIME USER B PAYS
      |
      v
USER A gets 5% commission
      |
      v
USER A can /withdraw to TON wallet (min 0.05 TON)
```

---

## Data Flow Diagram

```
                    TELEGRAM
                       |
                       v
+------------------+   +------------------+   +------------------+
|   MemeSeal Bot   |   |   MemeScan Bot   |   |   NotaryTON Bot  |
|  @MemeSealTON    |   |  @MemeScanTON    |   |   @NotaryTON     |
+------------------+   +------------------+   +------------------+
         |                     |                      |
         +----------+----------+----------------------+
                    |
                    v
            +---------------+
            |   FastAPI     |
            |   (bot.py)    |
            | Port 10000    |
            +---------------+
                    |
      +-------------+-------------+
      |             |             |
      v             v             v
+-----------+  +-----------+  +-----------+
| PostgreSQL|  | TON Chain |  | External  |
| (Render)  |  | (pytoniq) |  | APIs      |
+-----------+  +-----------+  +-----------+
                                   |
                    +--------------+-------------+
                    |              |             |
                    v              v             v
              +---------+    +---------+   +-----------+
              | TonAPI  |    | STON.fi |   | GeckoTerm |
              +---------+    +---------+   +-----------+


                    WEBHOOKS
                       |
      +----------------+----------------+
      |                |                |
      v                v                v
+-----------+    +-----------+    +-----------+
| Telegram  |    | TonAPI    |    | Twitter   |
| Bot API   |    | Payments  |    | API v2    |
+-----------+    +-----------+    +-----------+
```

---

## Value Capture Summary

### Revenue Streams (Active)

| Stream | Price | Volume | Status |
|--------|-------|--------|--------|
| Single seals | $0.02-0.05 | Low | WORKING |
| Subscriptions | $0.40-1.00/mo | None yet | WORKING |
| Referral fees | 5% commission | None yet | WORKING |

### Revenue Streams (Not Built)

| Stream | Potential | Effort |
|--------|-----------|--------|
| Casino gambling | High | Medium (need chips system) |
| MemeScan premium | Medium | Low (add paywall) |
| API usage fees | Low | Low (add pricing tier) |
| Ad slots in MemeScan | Medium | Low (add ad injection) |

---

## What's WORKING

1. **MemeSeal core flow** - File -> Pay -> Seal -> Verify
2. **Star payments** - Telegram checkout
3. **TON payments** - Auto-detection via TonAPI webhook
4. **Lottery system** - Pot grows, draws work
5. **Referral system** - Tracking + withdrawals
6. **MemeScan commands** - All 4 commands work
7. **Social auto-posting** - X + Telegram channel
8. **Multi-language** - EN/RU/ZH
9. **REST API** - All endpoints functional
10. **Landing page** - notaryton.com with live pot counter

---

## What's BROKEN / NOT BUILT

| Item | Status | Priority | Effort |
|------|--------|----------|--------|
| Casino real money | NOT BUILT | HIGH | 2-3 days |
| memeseal.vercel.app | 401 ERROR | LOW | Delete it |
| Lottery auto-payout | UNTESTED | HIGH | Test needed |
| Premium MemeScan | NOT BUILT | MEDIUM | 1-2 days |
| Whale alerts | NOT BUILT | LOW | 2-3 days |

---

## Infrastructure

| Component | Platform | URL | Cost |
|-----------|----------|-----|------|
| Backend | Render | notaryton-bot.onrender.com | Starter plan |
| Database | Render PostgreSQL | Internal | 256MB free tier |
| Casino | Vercel | memeseal-casino.vercel.app | Free tier |
| Domain | Cloudflare | notaryton.com | Proxied to Render |

---

## Next Steps

1. **Resubmit to TON App** with notaryton.com (not broken Vercel link)
2. **Register on TON Builders** for grant access
3. **Apply for STON.fi grant** (MemeScan uses their API)
4. **Build casino chips system** (highest revenue potential)
5. **Get first 100 users** for grant traction proof

---

*NotaryTON Labs - Proof or it didn't happen*
