# Project Inventory & Domain Strategy

> Everything we've built, where it lives, and what needs registration

---

## 🚀 DEPLOYED APPS

| App | Type | Live URL | Hosting | GitHub | Status |
|-----|------|----------|---------|--------|--------|
| **NotaryTON Bot** | Python API + Bot | https://notaryton-bot.onrender.com | Render | [cherishwins/notaryton-bot](https://github.com/cherishwins/notaryton-bot) | ✅ Live |
| **NotaryTON Web** | Domain | https://notaryton.com | → Render | (same) | ✅ Live |
| **MemeScan Astro** | Astro Site | https://memescan-astro.vercel.app | Vercel | [cherishwins/memescan-astro](https://github.com/cherishwins/memescan-astro) | ✅ Live |
| **MemeSeal Casino** | React Mini App | https://memeseal-casino.vercel.app | Vercel | [cherishwins/memeseal-casino](https://github.com/cherishwins/memeseal-casino) | ✅ Live |
| **Seal Casino** | Mini App | (check Vercel) | Vercel | [cherishwins/seal-casino](https://github.com/cherishwins/seal-casino) | ⚠️ Check |
| **Seal Tokens** | Mini App | (check Vercel) | Vercel | [cherishwins/seal-tokens](https://github.com/cherishwins/seal-tokens) | ⚠️ Check |
| **BlockBurnnn** | Next.js App | (check Vercel) | Vercel | [jpandadev/blockburnnn](https://github.com/jpandadev/blockburnnn) | ⚠️ Check |

---

## 🤖 TELEGRAM BOTS

| Bot | Username | Purpose | Status |
|-----|----------|---------|--------|
| **NotaryTON** | [@NotaryTON_bot](https://t.me/NotaryTON_bot) | Original notarization bot | ✅ Live |
| **MemeSeal** | [@MemeSealTON_bot](https://t.me/MemeSealTON_bot) | Main bot - seals + token intel | ✅ Live |

---

## 📺 TELEGRAM CHANNELS

| Channel | Username | Purpose | Status |
|---------|----------|---------|--------|
| **MemeSeal Announcements** | [@MemeSealTON](https://t.me/MemeSealTON) | Auto-posts rugs, alerts | ✅ Live |

---

## 🌐 DOMAINS

| Domain | Points To | Purpose | Registrar |
|--------|-----------|---------|-----------|
| **notaryton.com** | Render (notaryton-bot) | Main API + bot | ? |
| **memescan.xyz** | (if owned) | Token terminal | ? |
| (others?) | | | |

---

## 🔗 API INTEGRATIONS

| Service | Purpose | Status |
|---------|---------|--------|
| **TonAPI** | Webhooks for payments, holder data | ✅ Active |
| **GeckoTerminal** | Token discovery, prices | ✅ Active |
| **X/Twitter** | Auto-posting (Free tier: 17/day) | ✅ Active |
| **Telegram Stars** | In-app payments | ✅ Active |

---

## 📋 REGISTRATION CHECKLIST

### Done ✅
- [x] GitHub repos created
- [x] Render deployment (notaryton-bot)
- [x] Vercel deployments (Mini Apps)
- [x] Telegram bots registered
- [x] X/Twitter API keys

### To Do 🔲
- [ ] **TON Builders Portal** - https://builders.ton.org/
- [ ] **STON.fi Grant** - https://stonfi.notion.site/199f2441e97e80c59b15c6a6603789dd
- [ ] **swap.coffee Grant** - https://bit.ly/TONSwapCoffee
- [ ] **Telegram Mini Apps** - Register in @BotFather
- [ ] **TON App Directory** - List apps in ecosystem
- [ ] **DeFiLlama** - List for TVL tracking (when applicable)

---

## 🏗️ ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMESEAL ECOSYSTEM                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐ │
│  │  Telegram    │     │   Web API    │     │   Mini Apps  │ │
│  │    Bots      │     │  (FastAPI)   │     │   (React)    │ │
│  │              │     │              │     │              │ │
│  │ @MemeSealTON │────▶│ notaryton.com│◀────│ memeseal-    │ │
│  │ @NotaryTON   │     │              │     │ casino.app   │ │
│  └──────────────┘     └──────┬───────┘     └──────────────┘ │
│                              │                               │
│                              ▼                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    DATA LAYER                          │  │
│  │  PostgreSQL (Render) + Token Crawler + KOL Database   │  │
│  └───────────────────────────────────────────────────────┘  │
│                              │                               │
│                              ▼                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                 EXTERNAL SERVICES                      │  │
│  │  TonAPI | GeckoTerminal | X/Twitter | Telegram Stars  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 💰 REVENUE STREAMS

| Source | How | Rate |
|--------|-----|------|
| **Seals** | Users pay to timestamp | 3 Stars / 0.15 TON |
| **Subscriptions** | Monthly unlimited | 50 Stars / 1 TON |
| **Lottery** | 20% of fees pooled | Weekly draw |
| **Referrals** | 5% commission | Ongoing |
| **API** | Developer access | Subscription |
| **Grants** | Applications | $12.5-20K potential |

---

## 📱 MINI APP REGISTRATION

To list Mini Apps officially:

1. **@BotFather** → `/newapp` or `/setmenubutton`
2. Set web_app URL to your Vercel deployment
3. Add to bot menu

### Apps to Register:
- [ ] MemeScan Terminal → memescan-astro.vercel.app
- [ ] SealBet (when ready) → TBD
- [ ] Casino (if launching) → memeseal-casino.vercel.app

---

## 🔍 DISCOVERY PLATFORMS

Where to list for visibility:

| Platform | URL | Priority |
|----------|-----|----------|
| **TON Builders** | https://builders.ton.org | 🔴 High |
| **TON App** | https://ton.app | 🔴 High |
| **DappRadar** | https://dappradar.com/submit-dapp | 🟡 Medium |
| **DeFiLlama** | https://github.com/DefiLlama/DefiLlama-Adapters | 🟡 Medium |
| **Product Hunt** | https://producthunt.com | 🟢 Later |

---

## 📝 NOTES

- **notaryton.com** is the canonical domain
- All Mini Apps should use bot's web_app feature
- Crawler runs continuously building data moat
- X auto-posting uses Free tier (17 posts/day limit)

---

*Last updated: December 23, 2025*
