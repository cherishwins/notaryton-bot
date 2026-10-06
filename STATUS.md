# MemeSeal TON - Project Status

*Last updated: December 5, 2025*

---

## What Is This?

**MemeSeal** is a Telegram bot + casino mini app that:
1. Timestamps files on TON blockchain (proof of existence)
2. Runs casino games (slots, crash, roulette)
3. Weekly lottery (20% of all revenue feeds pot)

---

## QUICK LINKS (Bookmark These)

| What | URL |
|------|-----|
| **Bot** | https://t.me/MemeSealTON_bot |
| **Casino Mini App** | https://memeseal-casino.vercel.app |
| **Landing Page** | https://notaryton-bot.onrender.com |
| **Render Dashboard** | https://dashboard.render.com/web/srv-d4i1p8khg0os738nldt0 |
| **Lottery Pot API** | https://notaryton-bot.onrender.com/pot |
| **Health Check** | https://notaryton-bot.onrender.com/health |

---

## WHAT'S WORKING (Makes Money) ✅

| Feature | Status | Revenue |
|---------|--------|---------|
| **Seal Service** | ✅ LIVE | 3 Stars (~$0.06) per seal |
| **Unlimited Subscription** | ✅ LIVE | 50 Stars (~$1.00) or 0.3 TON per month |
| **Pay with Telegram Stars** | ✅ LIVE | Goes to your Telegram balance |
| **Pay with TON** | ✅ LIVE | 0.15 TON per seal |
| **Lottery System** | ⏸️ OFF by default (`LOTTERY_ENABLED`), legal opinion first | 20% of fees → weekly pot |
| **Referral System** | ✅ LIVE | 5% commission |

---

## WHAT'S BUILT BUT NOT MONETIZED YET ⚠️

| Feature | Status | Issue |
|---------|--------|-------|
| **Casino Mini App** | ✅ DEPLOYED | Demo mode - fake balance |
| **Slots Game** | ✅ BUILT | No real money integration |
| **Crash Game** | ✅ BUILT | No real money integration |
| **Roulette Game** | ✅ BUILT | No real money integration |
| **TON Wallet Connect** | ✅ BUILT | Connected but no deposits |

**To make casino real money:** Need to add Stars purchase for chips + database balance storage.

---

## PROJECT STRUCTURE

```
/ton/
├── notaryton-bot/              ← MAIN BACKEND (Render)
│   ├── bot.py                  ← Bot handlers, payments, API (5000+ lines)
│   ├── config.py               ← Environment variables
│   ├── database.py             ← PostgreSQL operations
│   ├── social.py               ← Twitter/X auto-posting
│   ├── static/                 ← Images, favicons
│   │   ├── favicon.ico         ← Matrix frog favicon
│   │   ├── memeseal_icon.png   ← Ad creative (square)
│   │   ├── memeseal_banner.png ← Ad creative (wide)
│   │   └── casino_interior.png ← Casino promo image
│   ├── AD_CAMPAIGN_GUIDE.md    ← How to run Telegram ads
│   ├── STATUS.md               ← This file
│   └── tests/                  ← pytest suite
│
└── memeseal-casino/            ← CASINO FRONTEND (Vercel)
    ├── src/
    │   ├── App.jsx             ← Main casino lobby
    │   ├── games/
    │   │   ├── SlotsGame.jsx   ← Politician slots
    │   │   ├── CrashGame.jsx   ← Frog rocket
    │   │   └── RouletteGame.jsx← Election roulette
    │   └── components/         ← UI components
    ├── public/                 ← Favicons
    └── index.html              ← Entry point
```

---

## DEPLOYMENTS

| Service | Platform | URL | Auto-Deploy |
|---------|----------|-----|-------------|
| Bot + API + Landing | Render | notaryton-bot.onrender.com | Yes (GitHub push) |
| Casino Mini App | Vercel | memeseal-casino.vercel.app | Yes (GitHub push) |

---

## BOT COMMANDS

| Command | What It Does |
|---------|--------------|
| `/start` | Welcome message + PLAY CASINO button |
| `/casino` | Open casino mini app |
| `/seal` | Instructions to seal a file |
| `/verify` | Check if a hash is sealed |
| `/unlimited` | Subscribe for unlimited seals |
| `/pot` | Show lottery pot status |
| `/mytickets` | Show your lottery tickets |
| `/referral` | Get your referral link |
| `/withdraw` | Withdraw earnings to TON wallet |

---

## REVENUE FLOW

```
USER ACTION                    YOU GET
─────────────────────────────────────────
Seals 1 file (3 Stars)   →    $0.06
Buys unlimited (50 Stars)→    $1.00
Referred user seals      →    5% of their payments

LOTTERY (only with LOTTERY_ENABLED=true; off by default):
20% of all payments → Weekly pot
Winner takes all (Sunday 00:00 UTC)
```

---

## BRANDING ASSETS

| File | Use For |
|------|---------|
| `static/memeseal_icon.png` | Telegram Ads (square) |
| `static/memeseal_banner.png` | Twitter/landing (wide) |
| `static/favicon.ico` | Browser tabs |
| `static/casino_interior.png` | Casino promo |
| `static/lottery_win.png` | Winner announcements |

---

## ENVIRONMENT VARIABLES (Render)

| Variable | Status | What It Does |
|----------|--------|--------------|
| BOT_TOKEN | ✅ Set | NotaryTON bot |
| MEMESEAL_BOT_TOKEN | ✅ Set | MemeSeal bot |
| TON_WALLET_SECRET | ✅ Set | 24-word mnemonic |
| SERVICE_TON_WALLET | ✅ Set | Receiving wallet |
| DATABASE_URL | ✅ Set | PostgreSQL connection |
| WEBHOOK_URL | ✅ Set | Bot webhook URL |
| TONAPI_KEY | ✅ Set | Payment detection |
| TWITTER_* | ✅ Set | Auto-posting |

---

## WHAT'S LEFT TO BUILD

### High Priority (Revenue)
- [ ] Casino real money (Stars → chips → play → cashout)
- [ ] "Buy Chips" button that creates Stars invoice
- [ ] Database-backed balance (not local state)

### Medium Priority (Growth)
- [ ] Domain (memeseal.io or memeseal.ton)
- [ ] More ad creatives / variations
- [ ] Telegram channel content

### Low Priority (Polish)
- [ ] GetBlock RPC fallback
- [ ] Analytics dashboard
- [ ] More games (blackjack, dice)

---

## QUICK COMMANDS

```bash
# Deploy bot (auto on push)
git push origin main

# Deploy casino manually
cd memeseal-casino && vercel --prod

# Check bot health
curl https://notaryton-bot.onrender.com/health

# Check lottery pot
curl https://notaryton-bot.onrender.com/pot

# Run tests
pytest tests/ -v
```

---

## TELEGRAM ADS

See `AD_CAMPAIGN_GUIDE.md` for:
- Exact ad copy to paste
- Image to upload
- Channels to target
- ROI estimates

---

## IF SOMETHING BREAKS

1. **Bot not responding?**
   - Check: https://notaryton-bot.onrender.com/health
   - Check Render logs in dashboard

2. **Casino blank page?**
   - Redeploy: `cd memeseal-casino && vercel --prod`
   - Check Vercel dashboard

3. **Payments not working?**
   - Check TonAPI webhook in Render logs
   - Verify TONAPI_KEY is set

4. **Need help?**
   - Read `.claude/CLAUDE.md` for context
   - This file has all the links

---

## CURRENT STATS

Check live at: https://notaryton-bot.onrender.com/pot

```
Lottery pot: ~500 Stars
Total users: 3
Total seals: 1
Next draw: Sunday 8pm UTC
```

---

## SOCIALS

| Platform | Handle |
|----------|--------|
| Telegram Bot | @MemeSealTON_bot |
| Telegram Channel | @MemeSealTON |
| Twitter/X | @MemeSealTON |

---

*Status: LIVE and ready for ads. Casino is demo-only until chips system built.*

*🐸💎 Diamond eyes are watching*
