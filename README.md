# MemeSeal TON

**Proof or it didn't happen.**

Seal anything on the TON blockchain in seconds. Screenshots, contracts, files - timestamped forever.

---

## The Idea

You made a trade. You caught the pump. You saw the rug coming.

But screenshots can be faked. Timestamps can be edited. Without proof, it's just your word.

MemeSeal fixes this. One tap, sealed forever on TON. Immutable. Verifiable. Done.

---

## How It Works

1. **Send** - Drop any file, screenshot, or contract address to [@MemeSealTON_bot](https://t.me/MemeSealTON_bot)
2. **Pay** - 1 Star or 0.015 TON (that's about 5 cents)
3. **Sealed** - Your proof lives on TON blockchain forever

That's it. No signup. No wallet connection. No friction.

---

## Why People Use It

| Use Case | What They Seal |
|----------|---------------|
| **Traders** | Wallet balances, entry/exit screenshots |
| **Degens** | Token contracts before launch |
| **Builders** | Code commits, deployment proofs |
| **Disputes** | Conversations, agreements, receipts |

---

## Features

**Instant** - Payment detected in seconds, not minutes

**Cheap** - 1 Star (~$0.02) or 0.015 TON (~$0.05)

**Unlimited** - 15 Stars/month for infinite seals

**Verifiable** - Anyone can verify at notaryton.com/verify

**Lottery** - Every seal = lottery ticket. Weekly 100 TON pot.

**Referrals** - Earn 5% of every seal from your invites

---

## Quick Start

```
1. Open Telegram
2. Search @MemeSealTON_bot
3. Send /start
4. Drop a file
5. Pay with Stars or TON
6. Done. Sealed forever.
```

---

## Commands

| Command | What It Does |
|---------|-------------|
| `/start` | Begin here |
| `/status` | Check subscription & stats |
| `/subscribe` | Unlimited seals (15 Stars/mo) |
| `/pot` | See lottery pot & countdown |
| `/mytickets` | Your lottery entries |
| `/referral` | Get your invite link |
| `/withdraw` | Cash out referral earnings |
| `/lang` | Switch language (EN/RU/ZH) |

---

## Verify a Seal

Anyone can verify any seal - no account needed:

```
https://notaryton.com/api/v1/verify/{hash}
```

---

## API for Developers

Build notarization into your bot, dApp, or service:

```bash
curl -X POST https://notaryton.com/api/v1/notarize \
  -H 'Content-Type: application/json' \
  -d '{
    "api_key": "YOUR_TELEGRAM_USER_ID",
    "contract_address": "EQxxx...",
    "metadata": {"project": "MyToken"}
  }'
```

See full API docs: [API.md](API.md)

---

## Tech

- **Bot**: aiogram 3.15+ (Telegram)
- **Server**: FastAPI + uvicorn
- **Chain**: TON via pytoniq + TonAPI webhooks
- **Database**: PostgreSQL (Neon)
- **Payments**: Telegram Stars + native TON
- **Deploy**: Render.com
- **Domain**: notaryton.com

---

## Self-Host

```bash
# Clone
git clone https://github.com/cherishwins/notaryton-bot.git
cd notaryton-bot

# Configure (see .env.template for all options)
cp .env.template .env
# Edit .env with your keys

# Install
pip install -r requirements.txt

# Run
python bot.py
```

Required env vars:
- `BOT_TOKEN` - From @BotFather
- `TON_WALLET_SECRET` - 24-word mnemonic
- `SERVICE_TON_WALLET` - Your wallet address
- `DATABASE_URL` - PostgreSQL connection string

Optional but recommended:
- `TONAPI_KEY` - Instant payment detection
- `TWITTER_API_*` - Auto-post seals to X

---

## Support

- Telegram: [@MemeSealTON](https://t.me/MemeSealTON)
- Bot: [@MemeSealTON_bot](https://t.me/MemeSealTON_bot)
- Issues: [GitHub](https://github.com/cherishwins/notaryton-bot/issues)

---

## License

MIT

---

**Seal it. Post it. Become legend.**
