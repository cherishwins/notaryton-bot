# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MEMESCAN ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────┐ │
│  │  TELEGRAM    │     │   WEB UI     │     │      EXTERNAL APIs       │ │
│  │   BOTS       │     │              │     │                          │ │
│  │              │     │  /feed       │     │  - GeckoTerminal         │ │
│  │ @NotaryTON   │     │  /verify     │     │  - TonAPI                │ │
│  │ @MemeSealTON │     │  /whitepaper │     │  - Ston.fi               │ │
│  └──────┬───────┘     └──────┬───────┘     └────────────┬─────────────┘ │
│         │                    │                          │               │
│         └────────────────────┼──────────────────────────┘               │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                        FASTAPI SERVER                              │  │
│  │                         (bot.py)                                   │  │
│  │                                                                    │  │
│  │  Endpoints:                                                        │  │
│  │  - /webhook/{token}    Telegram webhooks                          │  │
│  │  - /api/v1/tokens/*    Token data APIs                            │  │
│  │  - /score/{address}    Rug score lookup                           │  │
│  │  - /feed               Live SSE dashboard                         │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
│              ┌───────────────┼───────────────┐                          │
│              │               │               │                          │
│              ▼               ▼               ▼                          │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────────┐   │
│  │   CRAWLER     │  │   DATABASE    │  │    BACKGROUND TASKS       │   │
│  │  (crawler.py) │  │ (database.py) │  │                           │   │
│  │               │  │               │  │  - Payment polling        │   │
│  │  - Token      │  │  PostgreSQL   │  │  - Lottery draws          │   │
│  │    discovery  │  │  on Render    │  │  - Pending cleanup        │   │
│  │  - Safety     │  │               │  │  - Twitter posting        │   │
│  │    scoring    │  │  Tables:      │  │                           │   │
│  │  - Rug        │  │  - users      │  └───────────────────────────┘   │
│  │    detection  │  │  - tokens     │                                  │
│  │               │  │  - events     │                                  │
│  └───────────────┘  └───────────────┘                                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Token Discovery Flow

```
GeckoTerminal API
       │
       ▼ (every 60 seconds)
┌──────────────┐
│   Crawler    │ ──► get_new_pools()
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   TonAPI     │ ──► get_jetton_holders()
└──────┬───────┘     get_jetton_info()
       │
       ▼
┌──────────────┐
│ Safety Score │ ──► Calculate 0-100 based on:
│  Calculation │     - Top holder %
└──────┬───────┘     - Holder count
       │             - LP locked
       ▼
┌──────────────┐
│  PostgreSQL  │ ──► INSERT INTO tracked_tokens
└──────┬───────┘     INSERT INTO token_events
       │
       ▼
┌──────────────┐
│  SSE Stream  │ ──► Push to /api/v1/tokens/live
└──────────────┘
```

### Rug Detection Flow

```
Tracked Token
       │
       ▼ (periodic check)
┌──────────────┐
│ Re-analyze   │ ──► Fetch current holder distribution
└──────┬───────┘
       │
       ├──► Dev sold 90%+ ──► MARK AS RUGGED
       │
       └──► Holders dropped 80%+ ──► MARK AS RUGGED
                    │
                    ▼
            ┌──────────────┐
            │ token_events │ ──► type='rug'
            └──────────────┘
```

## Infrastructure

### Render Services

| Service | Type | Plan | Cost |
|---------|------|------|------|
| notaryton-bot | Web Service | Starter | $7/mo |
| notaryton-db | PostgreSQL | Basic 256MB | $7/mo |

### Domain

- **notaryton.com** → Cloudflare → Render

### Environment Variables

See [DEPLOYMENT.md](./DEPLOYMENT.md) for full list.

## Key Components

### bot.py (~3800 lines)
- FastAPI app with all routes
- Telegram bot handlers (aiogram)
- Payment processing (Stars + TON)
- API endpoints

### crawler.py
- Token discovery loop
- Safety analysis
- Rug detection
- Database persistence

### database.py
- PostgreSQL connection pool
- Repository pattern (UserRepository, TokenRepository, etc.)
- Schema auto-creation

### memescan/api.py
- GeckoTerminal client (30 req/min)
- TonAPI client (with API key)
- Ston.fi client (no rate limits)

## Scaling Considerations

### Current Limits
- Render Starter: 512MB RAM, shared CPU
- PostgreSQL Basic: 256MB, 1GB storage
- GeckoTerminal: 30 requests/minute

### When to Upgrade
- 1GB+ database → PostgreSQL Starter ($7)
- High traffic → Render Standard ($25)
- More API calls → TonAPI paid tier

### Horizontal Scaling
- Crawler can run as separate worker
- Multiple API instances behind load balancer
- Read replicas for PostgreSQL
