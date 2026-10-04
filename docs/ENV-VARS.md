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

### Money switches (off unless exactly `true`)

These move value at a user's request or hold user balances. Leave them unset
until a written Canadian legal opinion says otherwise.

| Variable | Default | Description |
|----------|---------|-------------|
| `CASINO_ENABLED` | off | `/api/v1/casino/*`. Off: 503. On: user routes need `X-Telegram-Init-Data` signed by `BOT_TOKEN` or `MEMESEAL_BOT_TOKEN` |
| `CASINO_INIT_DATA_MAX_AGE` | 86400 | Seconds signed initData stays valid |
| `LOTTERY_AUTO_PAYOUT_ENABLED` | off | Sunday draw sends the pot in TON to the winner's wallet. Off: the prize is held in `lottery_prizes` for the operator. Whatever its value, no draw runs at all until `POST /admin/void-legacy-lottery` has run (below) |
| `WITHDRAWALS_ENABLED` | off | `/withdraw` sends referral earnings in TON. `/api/v1/casino/withdraw`: 503 while off, 501 when on (no cash-out exists) |
| `API_SEALS_PER_HOUR` | 30 | Seals one `/api` key may order per hour (counted per worker process). Also the largest batch `/api/v1/batch` accepts |

Lottery prizes are never part of the `/withdraw` balance: each draw writes one
row to `lottery_prizes` (`held`, `sending`, `paid` or `review`), and only
`LOTTERY_AUTO_PAYOUT_ENABLED` can send one.

### Right after deploying this version: the legacy lottery void

The Sunday draw does not run until the void below has been done: it logs
`LOTTERY DRAW SKIPPED` every Sunday 00:00 UTC and draws, announces and records
nothing, so the legacy pot stays in place for the void. Do it right after the
deploy, before you turn on any switch:

1. Call `POST /admin/void-legacy-lottery` once, with the `X-Admin-Secret`
   header (401 without it, and always 401 while `ADMIN_SECRET` is unset):

   ```bash
   curl -X POST -H "X-Admin-Secret: $ADMIN_SECRET" https://<host>/admin/void-legacy-lottery
   ```

   It voids every undrawn `lottery_entries` row made before the call
   (`draw_id = -1`), house user 1 rows included, because the old open
   `/api/v1/casino/bet` let anyone forge entries and `/admin/seed-lottery`
   added unbacked house entries, and nothing in the table tells those apart
   from tickets bought with Stars. Honest tickets are voided too, which is why
   it does not run on its own: nothing voids entries at startup.

   In the same transaction it takes back casino chips that forged wins
   minted: the old open `/api/v1/casino/play` credited any `payout` the client
   sent (`casino_balances.total_won`), and wagering those chips would make new
   lottery entries after the void. Each balance with `total_won > 0` becomes
   `GREATEST(0, chips - total_won)`, which keeps only what deposits can explain.

   It records the counts and time in `bot_state` key
   `migration_lottery_legacy_voided_v1` and answers
   `{"ok": true, "already_done": false, "voided": <n>, "at": "<UTC time>", "chip_balances_cut": <n>}`.
   A second call changes nothing and answers `"already_done": true` with the
   first run's figures.
2. Audit `users.referral_earnings`. Older versions credited lottery prizes
   (including any from a forged pot) to that balance, and `/withdraw` pays it.
   Compare it against the referral commissions you expect and against past
   winners (`lottery_entries.won = TRUE`) before letting anyone withdraw.
3. Audit the casino chips the void left: `SELECT user_id, chips,
   total_deposited, total_wagered, total_won FROM casino_balances WHERE chips > 0
   ORDER BY chips DESC`. Every remaining chip should be explained by
   `total_deposited` (chips bought with Stars, plus the purchase bonus) less
   `total_wagered`. Investigate any balance that is not before turning on
   `CASINO_ENABLED`: chips are wagered into the lottery pot.

### Right after deploying this version: the TON payment cutover

TON payments are credited only by the poller now; the TonAPI webhook only
wakes it. On its first start the poller anchors at the wallet's newest
transaction (bot_state key `ton_poller_lt_v2`, logged as `⚓ Payment poller
anchored at LT <n>`) and credits nothing at or before it. Payments that
arrived while no version was crediting (the deploy window, a suspension of
the host, a failed webhook delivery) are not credited automatically:

1. The poller records the newest 64 incoming payments at or before the anchor
   in `ton_payments_processed` with status `precutover` and their memo. For each,
   and for any older transfer to `SERVICE_TON_WALLET` since the old bot last
   credited (its bot_state key `last_processed_lt`, or the date the host was
   suspended), check on an explorer whether the user was credited; credit by
   hand those with a numeric memo that were not, and set their row's status to
   `credited` (or insert a row keyed `<wallet raw address>:<lt>`).
2. Never delete `ton_poller_lt_v2`: without it the poller anchors again at
   the newest transaction and skips everything in between. Restoring an older
   database dump without it has the same effect.

### The TON payments review queue

`SELECT * FROM ton_payments_processed WHERE status <> 'credited' ORDER BY created_at`
is the queue. Statuses:

| Status | Meaning | What to do |
|--------|---------|------------|
| `claimed` | Crediting began; the payer's credit was not confirmed | Check the user's balance or subscription before crediting by hand |
| `payer_credited` | Payer credited; lottery entry, referral or DM did not finish | Do not credit the payer again |
| `partial` | Payer credited; lottery entry or referral commission failed | Do not credit the payer again; add the missing step if wanted |
| `failed` | The payer's credit failed and was not applied | Credit by hand |
| `unmatched` | TON arrived with a memo that is not a user id, or below 0.014 TON | Read `memo`; credit or refund by hand |
| `precutover` | Arrived before the poller's first anchor | See the cutover steps above |

More than 512 new transactions between two polls leave a range the poller did
not read. It logs `🚨 More than 512 transactions` and writes a bot_state key
`ton_poller_gap:<from_lt>:<to_lt>`; reconcile that LT range on an explorer
(`SELECT * FROM bot_state WHERE key LIKE 'ton_poller_gap:%'`).

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
