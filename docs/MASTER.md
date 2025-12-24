# MEMESEAL - Master Reference

> **One-liner:** Bloomberg Terminal for Meme Coins + On-Chain Proof System on TON

---

## WHAT WE'RE BUILDING

**MemeSeal** is a suite of tools for TON blockchain traders:

| Product | What It Does | Status |
|---------|--------------|--------|
| **MemeScan** | Real-time meme coin scanner with safety scores, rug detection, whale alerts | LIVE |
| **NotaryTON** | On-chain timestamping - "proof you were early" | LIVE |
| **MemeSeal Casino** | Telegram Mini App casino with lottery | LIVE |
| **KOL Tracker** | Influencer call tracking with wallet verification | In Development |

---

## LIVE PRODUCTS

### 1. MemeScan - Token Scanner
- **URL:** https://memescan-astro.vercel.app
- **Bot:** @MemeScanTON_bot (planned)
- **What:** Real-time scanning of new TON tokens. Safety scores, holder analysis, rug alerts.
- **Tech:** Astro + React, TonAPI integration

### 2. NotaryTON - Blockchain Timestamping
- **URL:** https://notaryton.com
- **Bot:** @NotaryTON_bot
- **What:** Pay 1 Star (~$0.05) to seal any file/screenshot on TON blockchain forever.
- **Use case:** Prove you called a trade, document launches, legal timestamps
- **Tech:** Python/aiogram, PostgreSQL, TON blockchain

### 3. MemeSeal Casino - Telegram Mini App
- **URL:** https://casino.notaryton.com
- **Bot:** @MemeSealTON_bot
- **What:** Gamified experience with slots, coin flip, weekly lottery
- **Tech:** React/Vite, Telegram Mini App SDK

---

## TELEGRAM BOTS

| Bot | Purpose | Status |
|-----|---------|--------|
| @MemeSealTON_bot | Main bot - casino, lottery, sealing | LIVE |
| @NotaryTON_bot | Timestamping service | LIVE |
| @MemeScanTON_bot | Token scanner alerts | Planned |

---

## DOMAINS & INFRASTRUCTURE

| Domain | Points To | Purpose |
|--------|-----------|---------|
| notaryton.com | Render (notaryton-bot) | Main API + landing |
| casino.notaryton.com | Vercel (memeseal-casino) | Casino Mini App |
| api.notaryton.com | Render | API endpoints |
| memescan-astro.vercel.app | Vercel | Token scanner |

### Hosting
- **Render:** notaryton-bot (Python backend, PostgreSQL)
- **Vercel:** memeseal-casino, memescan-astro (static/React)
- **GitHub:** github.com/cherishwins/*

---

## REPOS & CODE

| Repo | What | Deploy |
|------|------|--------|
| notaryton-bot | Main Python backend, all bots, API | Render |
| memeseal-casino | Casino Mini App (React) | Vercel |
| memescan-astro | Token scanner (Astro) | Vercel |
| seal-casino | Casino smart contracts (FunC) | TON blockchain |
| seal-tokens | Token factory contracts (FunC) | TON blockchain |

---

## REVENUE MODEL

| Stream | Price | Status |
|--------|-------|--------|
| Per-seal fee | 1 Star ($0.05) or 0.015 TON | LIVE |
| Unlimited subscription | 20 Stars/month | LIVE |
| Lottery | 20% of fees → weekly pot | LIVE |
| Referrals | 5% commission | LIVE |
| Casino house edge | TBD | Planned |

---

## TECH STACK

- **Backend:** Python 3.11, aiogram 3.15, FastAPI
- **Database:** PostgreSQL (Render)
- **Blockchain:** TON (pytoniq, TonAPI)
- **Frontend:** React, Astro, Vite
- **Smart Contracts:** FunC, Blueprint
- **Payments:** Telegram Stars, TON native

---

## GRANTS & FUNDING

| Program | Amount | Status |
|---------|--------|--------|
| TON Nest (Incubator) | TBD | INVITED (Dec 6) |
| STON.fi Grants | Up to $10K | Applied |
| swap.coffee Grants | $2.5-10K | Applied |
| Open League DeFi | Up to $520K | Target |

---

## TEAM

- **Jesse** - Founder, Product, Ops
- **Claude** - AI Dev Partner

---

## CHANNELS & COMMUNITY

| Platform | Handle | Purpose |
|----------|--------|---------|
| Telegram Channel | @MemeSealTON | Announcements |
| Telegram Group | (TBD) | Community |
| X/Twitter | @MemeSealTON | Marketing |

---

## KEY METRICS (Current)

- Bots deployed: 2 live
- Mini Apps: 2 live
- Smart contracts: 2 in development
- Tokens tracked: 1000+ daily
- Database tables: 15+

---

## QUICK LINKS

- **Dashboard:** https://dashboard.render.com
- **Vercel:** https://vercel.com/of8
- **TON Builders:** https://builders.ton.org
- **GitHub:** https://github.com/cherishwins

---

## DOCS INDEX

| Doc | What's In It |
|-----|--------------|
| [API.md](./API.md) | All API endpoints |
| [DATABASE.md](./DATABASE.md) | Schema reference |
| [ENV-VARS.md](./ENV-VARS.md) | All environment variables |
| [ROADMAP.md](./ROADMAP.md) | Feature timeline |
| [INVENTORY.md](./INVENTORY.md) | Complete asset inventory |

---

*Last updated: December 24, 2025*
