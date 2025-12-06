# MemeSeal / MemeScan - Cleanup & Roadmap
**Generated:** December 6, 2025

---

## FILES TO DELETE (Manual)

### Priority 1 - Root Junk Files
```bash
rm /home/jesse/dev/projects/personal/ton/notaryton-bot/=3.15.0
rm /home/jesse/dev/projects/personal/ton/notaryton-bot/Desktop-screenshot-*.png
rm /home/jesse/dev/projects/personal/ton/notaryton-bot/Create-new-application-*.png
rm /home/jesse/dev/projects/personal/ton/notaryton-bot/TON-Explorer-Transaction-*.png
rm /home/jesse/dev/projects/personal/ton/notaryton-bot/notary_ton_logo*.png
rm -rf /home/jesse/dev/projects/personal/ton/notaryton-bot/memescan/screeshotsforappmodbot/
```

### Priority 2 - Remove from Git History
```bash
cd /home/jesse/dev/projects/personal/ton/notaryton-bot
git rm -r --cached memescan-app/dist/
git rm -r --cached memescan-app/.vercel/
git rm -r --cached .pytest_cache/
```

### Priority 3 - Add to .gitignore
```
memescan-app/dist/
memescan-app/.vercel/
.pytest_cache/
```

---

## WHAT TO KEEP
- `meme_branding/` - Brand assets
- `memescan/brandimgs/` - Bot branding
- `static/` - All public assets
- `docs/archive/` - Historical reference

---

## SECURITY CHECK

Verify `.env` was never committed:
```bash
git log --all --full-history -- .env
```
**If found, rotate ALL tokens immediately.**

---

## NEXT STEPS ROADMAP

### DONE
- [x] MemeScan Mini App deployed to Vercel
- [x] TG Analytics integrated
- [x] Submitted to TON App Catalog (awaiting review)
- [x] BotFather menu button configured
- [x] Twitter auto-poster working

### THIS WEEK
| Task | Priority | Notes |
|------|----------|-------|
| Wait for App Catalog approval | High | 1 week review time |
| Run outreach.py on top 50 groups | High | Get first users |
| Post in TON Nest Founders Chat | Medium | Community intro |
| Monitor TG Analytics data | Medium | Verify it's working |

### NEXT 2 WEEKS
| Task | Priority | Notes |
|------|----------|-------|
| First deploy bot integration | High | Partner with bot operators |
| Public verification UI (notaryton.com/verify) | High | SEO traffic |
| Product Hunt launch prep | Medium | Position as "Stop Rugpulls" |
| Get to 100 users | High | Prove PMF |

### NEXT MONTH
| Task | Priority | Notes |
|------|----------|-------|
| Scale to 1,000 users | High | $180/month MRR target |
| 5+ API integrations | High | Lock-in effect |
| B2B outreach (STON.fi, DeDust) | Medium | Premium tier |
| Leaderboard for top referrers | Medium | Competitive dynamics |

---

## PROJECT STATUS SUMMARY

| Component | Status | URL |
|-----------|--------|-----|
| MemeSeal Bot | Live | @NotaryTON_bot |
| MemeScan Bot | Live | @MemeScanTON_bot |
| MemeScan Mini App | Live | https://memescan-ton.vercel.app |
| Backend | Live | Render (notaryton-bot) |
| Database | Live | Render PostgreSQL |
| Twitter Poster | Live | Auto-posts trending |
| App Catalog | Pending | Submitted, awaiting review (~1 week) |

---

## CODEBASE STRUCTURE

```
notaryton-bot/
├── bot.py              # Main MemeSeal bot
├── config.py           # Environment config
├── database.py         # PostgreSQL ops
├── social.py           # Twitter auto-poster
├── memescan/           # MemeScan bot
│   ├── bot.py
│   ├── api.py
│   └── twitter.py
├── memescan-app/       # React Mini App (Vercel)
├── docs/               # Documentation
└── tests/              # Test suite
```

---

## CONTACTS

- App Catalog questions: @tapps_center_moderation
- App reviews channel: https://t.me/trendingapps

---

## SESSION WINS (Dec 6, 2025)

1. Fixed Vercel deployment (memescan-ton.vercel.app)
2. Fixed TG Analytics (onload callback)
3. Organized Telegram chats (archived spam, muted noisy)
4. Submitted to TON App Catalog (all 5 steps complete)
5. Codebase audit complete
