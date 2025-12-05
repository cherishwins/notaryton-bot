# MemeSeal TON - Project Status

*Last updated: December 4, 2025*

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
| **Send file, get seal** | ✅ Working | Core feature - just fixed today |
| **Pay with Telegram Stars** | ✅ Working | 1 Star = 1 seal |
| **Pay with TON** | ✅ Working | 0.015 TON = 1 seal |
| **Unlimited subscription** | ✅ Working | 15 Stars or 0.3 TON/month |
| **Instant payment detection** | ✅ Working | TonAPI webhooks (just added) |
| **Referral system** | ✅ Working | 5% commission |
| **Withdrawal to TON wallet** | ✅ Working | /withdraw command |
| **Multi-language** | ✅ Working | EN, RU, ZH |
| **Lottery tickets** | ✅ Working | Every seal = 1 ticket |
| **Lottery pot display** | ✅ Working | /pot shows current pot |
| **X/Twitter auto-post** | ✅ Working | Seals post to X (just added keys) |
| **Landing page** | ✅ Working | notaryton.com |
| **Verification page** | ✅ Working | /verify endpoint |

---

## What Was Just Fixed (Today)

1. **Wallet version mismatch** - Was using WalletV4R2 but wallet is V5R1. Seals were failing with "contract not initialized". Fixed.

2. **TonAPI webhooks** - Added instant payment detection. No more 30-second polling delay.

3. **X/Twitter integration** - Added your API keys to Render. Seals now auto-post.

4. **UX improvements** - Removed fake "0.69 seconds" success messages, added honest progress indicators, better error messages.

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
- **Database:** PostgreSQL on Neon
- **Blockchain:** TON (via pytoniq + TonAPI)
- **Payments:** Telegram Stars + native TON
- **Domain:** notaryton.com

---

## What's NOT Done Yet

| Feature | Status | Notes |
|---------|--------|-------|
| **Telegram Mini App** | Not started | Rich UI for verification |
| **Actual lottery draw** | Not implemented | Need cron job to pick winner |
| **GetBlock fallback** | Not added | Backup if liteservers slow |
| **OpenTimestamps** | Not added | Bitcoin-anchored timestamps |
| **OriginStamp** | Not added | Legal-grade certificates |
| **Mobile PWA** | Not started | - |

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
| `bot.py` | Main bot code (everything) |
| `database.py` | PostgreSQL operations |
| `social.py` | X/Twitter posting |
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
| TONAPI_KEY | ✅ Set (today) |
| TWITTER_API_KEY | ✅ Set (today) |
| TWITTER_API_SECRET | ✅ Set (today) |
| TWITTER_ACCESS_TOKEN | ✅ Set (today) |
| TWITTER_ACCESS_TOKEN_SECRET | ✅ Set (today) |

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

## Next Steps (When You're Rested)

1. **Test the seal** - Send a file to @MemeSealTON_bot, verify it works
2. **Check X/Twitter** - See if seals are posting to your X account
3. **Implement lottery draw** - Need actual weekly winner selection
4. **Marketing** - Share in TON groups, get users

---

## Support

If something breaks:
1. Check Render logs
2. Check this STATUS.md
3. Ask Claude with context from `.claude/CLAUDE.md`

---

*Go sleep. The bot is running. Test tomorrow.*
