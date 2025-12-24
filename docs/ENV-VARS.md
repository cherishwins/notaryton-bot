# Environment Variables - All Projects

> Complete list of every API key needed across all projects

---

## 🎯 QUICK SUMMARY

| Project | Env Vars Needed | Deploy To |
|---------|-----------------|-----------|
| **notaryton-bot** | 14 vars | Render |
| **memescan-astro** | 0 (static) | Vercel |
| **memeseal-casino** | 0 (client-side) | Vercel |
| **seal-casino** | 0 (client-side) | Vercel |
| **seal-tokens** | 0 (client-side) | Vercel |
| **blockburnnn** | 1 var | Vercel |

---

## 1. notaryton-bot (Render)

**Dashboard:** https://dashboard.render.com/web/srv-d4i1p8khg0os738nldt0/env

### Required ✅

| Variable | Where to Get | Description |
|----------|--------------|-------------|
| `BOT_TOKEN` | @BotFather → /newbot or /token | NotaryTON bot token |
| `MEMESEAL_BOT_TOKEN` | @BotFather | MemeSealTON bot token |
| `DATABASE_URL` | Render PostgreSQL | `postgresql://user:pass@host/db?sslmode=require` |
| `TON_WALLET_SECRET` | Your wallet seed | 24-word mnemonic (space separated) |
| `SERVICE_TON_WALLET` | Your wallet address | `EQ...` address for receiving |

### Recommended 🔶

| Variable | Where to Get | Description |
|----------|--------------|-------------|
| `TONAPI_KEY` | https://tonconsole.com → API Keys | For holder data, webhooks |
| `TONAPI_WEBHOOK_SECRET` | TonConsole webhooks | HMAC verification |
| `TON_CENTER_API_KEY` | https://toncenter.com | Backup RPC |
| `TWITTER_API_KEY` | https://developer.x.com | X posting |
| `TWITTER_API_SECRET` | X Developer Portal | X posting |
| `TWITTER_ACCESS_TOKEN` | X Developer Portal | X posting |
| `TWITTER_ACCESS_SECRET` | X Developer Portal | X posting |
| `CHANNEL_ID` | Telegram channel ID | `@MemeSealTON` or numeric |

### Optional 🔹

| Variable | Where to Get | Description |
|----------|--------------|-------------|
| `WEBHOOK_URL` | Your domain | Default: `https://notaryton.com` |
| `GROUP_IDS` | Telegram group IDs | Comma-separated |
| `SEAL_CASINO_ADDRESS` | Smart contract | Casino contract address |
| `SEAL_TOKENS_ADDRESS` | Smart contract | Token factory address |
| `TONAPI_CASINO_KEY` | TonConsole | Webhook for casino |
| `TONAPI_TOKENS_KEY` | TonConsole | Webhook for tokens |

---

## 2. memescan-astro (Vercel)

**Static site - NO ENV VARS REQUIRED**

Just deploy:
```bash
cd memescan-astro
vercel --prod
```

---

## 3. memeseal-casino (Vercel)

**Client-side Mini App - NO ENV VARS REQUIRED**

Uses Telegram WebApp SDK (runs inside Telegram).

Deploy:
```bash
cd memeseal-casino
vercel --prod
```

---

## 4. seal-casino (Vercel)

**Client-side Mini App - NO ENV VARS REQUIRED**

Deploy:
```bash
cd seal-casino
vercel --prod
```

---

## 5. seal-tokens (Vercel)

**Client-side Mini App - NO ENV VARS REQUIRED**

Deploy:
```bash
cd seal-tokens
vercel --prod
```

---

## 6. blockburnnn (Vercel)

**1 optional var**

| Variable | Where to Get | Description |
|----------|--------------|-------------|
| `NEXT_PUBLIC_API_NINJAS_KEY` | https://api-ninjas.com/register | Crypto prices (free tier: 10k/mo) |

Deploy:
```bash
cd blockburnnn
vercel --prod
```

---

## 🔑 WHERE TO GET API KEYS

### Telegram Bots
1. Open @BotFather
2. `/newbot` or `/mybots` → select bot → API Token
3. Copy the token

### TonAPI / TonConsole
1. Go to https://tonconsole.com
2. Sign in with Telegram
3. Projects → Create Project
4. API Keys → Generate
5. Webhooks → Create (for payment detection)

### X/Twitter
1. Go to https://developer.x.com
2. Sign up for Developer account
3. Create App → Get keys
4. Free tier: 17 posts/day

### TON Center
1. Go to https://toncenter.com
2. Get API key (free tier available)

### API Ninjas
1. Go to https://api-ninjas.com/register
2. Free tier: 10,000 requests/month

---

## 🚀 DEPLOYMENT COMMANDS

### Deploy Everything to Vercel (no env vars needed)

```bash
# memescan-astro
cd /home/jesse/dev/projects/personal/ton/memescan-astro
vercel --prod

# memeseal-casino
cd /home/jesse/dev/projects/personal/ton/memeseal-casino
vercel --prod

# seal-casino
cd /home/jesse/dev/projects/personal/ton/seal-casino
vercel --prod

# seal-tokens
cd /home/jesse/dev/projects/personal/ton/seal-tokens
vercel --prod

# blockburnnn
cd /home/jesse/dev/projects/personal/ton/blockburnnn
vercel --prod
```

### NotaryTON Bot (Render)
Auto-deploys on git push. Or manually:
1. Go to https://dashboard.render.com
2. Select notaryton-bot
3. Manual Deploy → Deploy latest commit

---

## 📋 CHECKLIST

### Already Configured ✅
- [x] `BOT_TOKEN` - NotaryTON
- [x] `MEMESEAL_BOT_TOKEN` - MemeSealTON
- [x] `DATABASE_URL` - Render PostgreSQL
- [x] `TONAPI_KEY` - Token data
- [x] `TWITTER_*` - X posting

### Need to Verify 🔍
- [ ] `TON_WALLET_SECRET` - Check if correct
- [ ] `SERVICE_TON_WALLET` - Check if correct
- [ ] `TONAPI_WEBHOOK_SECRET` - May need update

---

## 🔒 SECURITY NOTES

1. **NEVER commit .env files** - They're in .gitignore
2. **Rotate keys** if exposed
3. **Use Render's env var UI** - Not files
4. **TON_WALLET_SECRET** is your money - guard it

---

*Last updated: December 23, 2025*
