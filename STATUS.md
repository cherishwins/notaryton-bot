# MemeSeal TON - Project Status

*Last updated: December 4, 2025 (evening)*

---

## What Is This?

**MemeSeal** is a Telegram bot that timestamps files on the TON blockchain. Users send a file, pay ~5 cents, and get permanent proof it existed at that moment.

**It is NOT:**
- A casino (though there's a lottery feature)
- A mini app (pure Telegram bot, no web app yet)
- A token (no $SEAL token... yet?)

---

## What's Working Right Now

| Feature | Status | Notes |
|---------|--------|-------|
| **Send file, get seal** | ✅ Working | Core feature |
| **Pay with Telegram Stars** | ✅ Working | 1 Star = 1 seal |
| **Pay with TON** | ✅ Working | 0.015 TON = 1 seal |
| **Unlimited subscription** | ✅ Working | 15 Stars or 0.3 TON/month |
| **Instant payment detection** | ✅ Working | TonAPI webhooks + HMAC verification |
| **Auto-seal on payment** | ✅ Working | Webhook triggers seal automatically |
| **Referral system** | ✅ Working | 5% commission |
| **Withdrawal to TON wallet** | ✅ Working | /withdraw command |
| **Multi-language** | ✅ Working | EN, RU, ZH |
| **Lottery tickets** | ✅ Working | Every seal = 1 ticket |
| **Lottery pot display** | ✅ Working | /pot shows current pot |
| **Lottery draw** | ✅ Working | Sundays midnight UTC, auto-payout |
| **X/Twitter auto-post** | ✅ Working | Seals + lottery winners post to X |
| **Landing page** | ✅ Working | notaryton.com |
| **Verification page** | ✅ Working | /verify endpoint |
| **REST API** | ✅ Working | /api/v1/notarize, /batch, /verify |

---

## What Was Just Fixed (Dec 4, 2025)

1. **Lottery draw scheduler** - Runs every Sunday at midnight UTC. Auto-pays winners who have withdrawal wallet set.

2. **TonAPI webhook security** - Added HMAC signature verification for webhook requests.

3. **Auto-seal on payment** - When webhook detects TON payment, automatically seals the pending file.

4. **Memo cleanup** - Expired payment memos are now cleaned up every 5 minutes.

5. **Code modularization** - Extracted `config.py` and `utils/` package for cleaner architecture.

### Previously Fixed
- Wallet version (WalletV5R1)
- TonAPI instant payment detection
- X/Twitter auto-posting
- Honest UX (no fake success messages)

---

## The Lottery (Not a Casino)

- **How it works:** Every seal = 1 lottery ticket
- **Pot:** 20% of seal fees go to pot
- **Draw:** Sundays at midnight UTC
- **Winner:** Random ticket wins entire pot
- **Current pot:** Check with /pot command

This is NOT a casino - no betting, no games. Just a raffle for people who use the seal service.

---

## Bots

| Bot | Username | Purpose |
|-----|----------|---------|
| **MemeSeal** | @MemeSealTON_bot | Main bot (degen branding) |
| **NotaryTON** | @NotaryTON_bot | Professional branding |

Both bots share the same database and wallet.

---

## Tech Stack

- **Hosting:** Render.com (auto-deploys from GitHub)
- **Database:** Render PostgreSQL
- **Blockchain:** TON (via pytoniq + TonAPI webhooks)
- **Payments:** Telegram Stars + native TON
- **Domain:** notaryton.com

---

## What's NOT Done Yet

| Feature | Priority | Notes |
|---------|----------|-------|
| **GetBlock fallback** | Medium | Backup RPC if liteservers slow |
| **Telegram Mini App** | Low | Rich UI for verification |
| **OpenTimestamps** | Low | Bitcoin-anchored timestamps |
| **OriginStamp** | Low | Legal-grade certificates |
| **Analytics dashboard** | Low | Track seals, revenue, users |

---

## Revenue Model

```
Per seal:     1 Star (~$0.02) or 0.015 TON (~$0.05)
Subscription: 15 Stars/month or 0.3 TON/month
Referrals:    5% commission to referrer
Lottery:      20% of fees go to pot (winner takes all)
```

---

## Key Files

| File | What It Does |
|------|-------------|
| `bot.py` | Main bot code (5,000 lines - handlers, payments, API) |
| `config.py` | All environment variables and constants |
| `database.py` | PostgreSQL operations |
| `social.py` | X/Twitter + channel posting |
| `utils/` | Extracted utilities (i18n, hashing, memo) |
| `tests/` | pytest test suite (21 tests, all passing) |
| `.env` | Your secrets (never commit!) |
| `.env.template` | Template for secrets |
| `.claude/CLAUDE.md` | AI working style guide |

---

## Environment Variables (Render)

These are set in Render dashboard:

| Variable | Status |
|----------|--------|
| BOT_TOKEN | ✅ Set |
| MEMESEAL_BOT_TOKEN | ✅ Set |
| TON_WALLET_SECRET | ✅ Set |
| SERVICE_TON_WALLET | ✅ Set |
| DATABASE_URL | ✅ Set |
| WEBHOOK_URL | ✅ Set |
| TONAPI_KEY | ✅ Set |
| TONAPI_WEBHOOK_SECRET | ⚠️ Optional (for HMAC verification) |
| TWITTER_API_KEY | ✅ Set |
| TWITTER_API_SECRET | ✅ Set |
| TWITTER_ACCESS_TOKEN | ✅ Set |
| TWITTER_ACCESS_TOKEN_SECRET | ✅ Set |

---

## Quick Commands

```bash
# Run locally
python bot.py

# Check wallet
python -c "... wallet check script ..."

# Deploy
git push origin main  # Auto-deploys to Render
```

---

## Links

- **Live bot:** https://t.me/MemeSealTON_bot
- **Website:** https://notaryton.com
- **Render dashboard:** https://dashboard.render.com/web/srv-d4i1p8khg0os738nldt0
- **GitHub:** https://github.com/cherishwins/notaryton-bot
- **TonAPI console:** https://tonconsole.com

---

## Next Steps

1. **Continue modularization** - Split bot.py into handlers/, payments/, api/
2. **Add GetBlock fallback** - Backup RPC for reliability
3. **Marketing** - Share in TON groups, get users
4. **Monitor first lottery draw** - Sunday midnight UTC

---

## Support

If something breaks:
1. Check Render logs
2. Check this STATUS.md
3. Ask Claude with context from `.claude/CLAUDE.md`

---

*Bot is running. All core features working. Next: modularization + marketing.*
