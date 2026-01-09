# START HERE

> Quick context for each session. Read this first.

---

## WHAT THIS IS

**MemeSeal** - Bloomberg for Meme Coins + On-Chain Proof on TON blockchain.

**Full details:** See `docs/MASTER.md`

---

## CURRENT STATUS (Jan 8, 2026)

### LIVE
- ✅ @MemeSealTON_bot - Casino + lottery
- ✅ @NotaryTON_bot - Timestamping
- ✅ https://notaryton.com - Main backend (Render)
- ✅ https://casino.notaryton.com - Casino Mini App (Vercel)
- ✅ https://memescan-astro.vercel.app - Token scanner (Vercel)

### IN PROGRESS
- 🔄 TON Nest incubator - INVITED, need to complete onboarding
- 🔄 Waiting on grant responses (STON.fi, swap.coffee)
- 🔄 TON Builders Analytics - SDK added, waiting for data

### AUDIT COMPLETED
- 📋 See `docs/AUDIT_REPORT_2026_01.md` for full codebase audit
- 🔒 Fixed hardcoded API keys in config.py
- ⚠️ Action needed: Rotate TonAPI keys at tonconsole.com

### NEXT UP
- [ ] Rotate TonAPI keys (SECURITY - exposed in git history)
- [ ] Test casino Mini App to verify analytics tracking
- [ ] KOL tracker feature completion
- [ ] TON ID integration (need CLIENT_ID from @boldov)

---

## QUICK COMMANDS

```bash
# Check bot health
curl https://notaryton-bot.onrender.com/health

# Deploy memeseal-casino
cd ~/dev/projects/personal/ton/memeseal-casino && vercel --prod

# Deploy memescan
cd ~/dev/projects/personal/ton/memescan-astro && vercel --prod

# Check Render deploys
# Use: mcp__render__list_deploys with serviceId: srv-d4i1p8khg0os738nldt0
```

---

## KEY FILES

| File | What |
|------|------|
| `docs/AUDIT_REPORT_2026_01.md` | Latest codebase audit with action items |
| `docs/MASTER.md` | Full product reference |
| `docs/WHALE_SWARM_INTEL.md` | Whale tactics, ecosystem choke points, swarm playbook |
| `docs/X402_FLASH_AUCTION_INTEL.md` | Payment protocols, flash auction model, AI agent automation |
| `docs/STRATEGY.md` | Business model, GTM, network effects |
| `docs/ENV-VARS.md` | All API keys needed |
| `bot.py` | Main bot code |
| `database.py` | All DB schemas |
| `config.py` | Environment config |

---

## REPOS

| Repo | Path | Deploy |
|------|------|--------|
| notaryton-bot | `~/dev/projects/personal/ton/notaryton-bot` | Render (auto) |
| memeseal-casino | `~/dev/projects/personal/ton/memeseal-casino` | Vercel |
| memescan-astro | `~/dev/projects/personal/ton/memescan-astro` | Vercel |

---

## DASHBOARDS

- **Render:** https://dashboard.render.com/web/srv-d4i1p8khg0os738nldt0
- **Vercel:** https://vercel.com/of8
- **TON Builders:** https://builders.ton.org
- **GitHub:** https://github.com/cherishwins

---

*Update this file as priorities change.*
