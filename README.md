# NotaryTON - Auto-Notarization for TON Memecoin Launches

🔐 Bulletproof timestamping service for TON blockchain memecoin launches. Auto-notarize contract deployments in Telegram groups for 0.001 TON.

---

## 🚀 Features

### Core Functionality
- ✅ **Auto-Notarization**: Monitors Telegram groups for new coin launches
- ✅ **Contract Verification**: Fetches and hashes contract bytecode from transactions
- ✅ **Blockchain Timestamping**: Permanent proof stored on TON blockchain
- ✅ **Subscription System**: Unlimited monthly access for 0.1 TON
- ✅ **Payment Tracking**: SQLite database for users and notarizations
- ✅ **Manual Notarization**: Support for file uploads and manual contracts

### Bot Commands
- `/start` - Welcome message and feature overview
- `/subscribe` - Get unlimited monthly notarizations (0.1 TON)
- `/status` - Check subscription status
- `/notarize` - Manually notarize a contract or file

### API Endpoints
- `GET /` - Health check
- `GET /stats` - Bot statistics (users, notarizations)
- `POST /webhook/{token}` - Telegram webhook handler

---

## 💰 Pricing

| Plan | Price | Features |
|------|-------|----------|
| **Pay-as-you-go** | 0.001 TON (~$0.002) | Per notarization |
| **Monthly Unlimited** | 0.1 TON (~$0.18) | Unlimited for 30 days |
| **Referral Program** | 5% commission | For group admins |

---

## 🛠️ Tech Stack

- **Bot Framework**: aiogram 3.4.1 (Telegram)
- **Web Server**: FastAPI + uvicorn
- **Blockchain**: pytoniq (TON)
- **Database**: SQLite (aiosqlite)
- **Deployment**: Render.com
- **Domain**: notaryton.com (GoDaddy)

---

## 📦 Project Structure

```
notaryton-bot/
├── bot.py              # Main bot application
├── outreach.py         # Admin DM automation script
├── requirements.txt    # Python dependencies
├── render.yaml         # Render.com deployment config
├── .env                # Environment variables (SECRET!)
├── .env.example        # Template for environment variables
├── DEPLOYMENT.md       # Comprehensive deployment guide
├── README.md           # This file
├── .gitignore          # Git ignore rules
├── notaryton.db        # SQLite database (created on first run)
└── downloads/          # Temporary file storage
```

---

## 🚦 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in:

```bash
BOT_TOKEN=your_telegram_bot_token
TON_CENTER_API_KEY=your_toncenter_api_key
TON_WALLET_SECRET=your 24 word mnemonic
SERVICE_TON_WALLET=your_wallet_address
WEBHOOK_URL=http://localhost:8000
GROUP_IDS=
```

### 3. Run Locally (with ngrok)

```bash
# Terminal 1: Start ngrok
ngrok http 8000

# Terminal 2: Update .env with ngrok URL
# WEBHOOK_URL=https://abc123.ngrok.io

# Terminal 3: Run bot
python bot.py
```

### 4. Test

Open Telegram → @NotaryTON_bot → `/start`

---

## 🌐 Deploy to Production

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete step-by-step guide including:
- Render.com deployment
- GoDaddy domain configuration
- Webhook setup
- Group monitoring
- Admin outreach campaign

---

## 📊 Business Model

### Revenue Streams
1. **Per-Use Fees**: 0.001 TON per notarization
2. **Subscriptions**: 0.1 TON/month for unlimited access
3. **White-Label**: License bot to law firms for monthly fee

### Target Market
- TON memecoin deployers (100+ new coins/day)
- Crypto traders (proof against rugpulls)
- Group admins (5% referral commission)
- Law firms (document notarization)

### Growth Strategy
1. **Phase 1**: Auto-join top 50 TON groups
2. **Phase 2**: DM admins with referral program (outreach.py)
3. **Phase 3**: Product Hunt launch
4. **Phase 4**: Expand to file notarization for legal docs

---

## 🔒 Security

- ✅ Wallet seed phrase never exposed (server-side only)
- ✅ SQLite for local data (no cloud DB needed)
- ✅ HTTPS webhook (TLS encryption)
- ✅ Rate limiting on API endpoints
- ✅ Input validation on all user data

---

## 📈 Metrics & KPIs

Track via `/stats` endpoint:
- Total users
- Total notarizations
- Revenue (tracked in DB)
- Active subscriptions
- Referral conversions

---

## 🤝 Contributing

This is a solo project by [@jesselawson](https://github.com/jesselawson). Open to collaborators!

---

## 📄 License

MIT License - See LICENSE file

---

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/jesselawson/notaryton-bot/issues)
- **Telegram**: @NotaryTON_bot
- **Email**: [your-email]

---

## 🎯 Roadmap

- [x] Core bot functionality
- [x] Subscription system
- [x] Auto-notarization for groups
- [x] Admin outreach automation
- [ ] Full payment verification (TON wallet polling)
- [ ] Referral tracking & payouts
- [ ] Web dashboard for stats
- [ ] Multi-language support
- [ ] TON DNS integration
- [ ] Mobile app (PWA)

---

**Built with ❤️ for the TON community**

🔐 **Seal it for a nickel. Forever.**
