# MemeScan / NotaryTON Documentation

> **Last Updated:** December 24, 2024

## Quick Links

| Doc | Description |
|-----|-------------|
| [Architecture](./ARCHITECTURE.md) | System design, infrastructure, data flow |
| [API Reference](./API.md) | All endpoints with examples |
| [Database Schema](./DATABASE.md) | Tables, relationships, indexes |
| [Roadmap](./ROADMAP.md) | Trader Intelligence vision & phases |
| [Deployment](./DEPLOYMENT.md) | Render setup, env vars, domains |

## What Is This?

**MemeScan** is a TON blockchain intelligence platform that:
1. **Tracks tokens** - Discovers and analyzes every new token on TON
2. **Detects rugs** - Scores tokens 0-100 based on holder concentration
3. **Builds data moat** - Historical database of tokens, rugs, and trader behavior

## Live URLs

| Service | URL |
|---------|-----|
| Live Feed | https://notaryton.com/feed |
| API | https://notaryton.com/api/v1/... |
| Bot | https://t.me/NotaryTON_bot |
| MemeSeal Bot | https://t.me/MemeSealTON_bot |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python + FastAPI + aiogram |
| Database | PostgreSQL (Render) |
| Blockchain | TON via TonAPI + pytoniq |
| Data Sources | GeckoTerminal, Ston.fi, TonAPI |
| Hosting | Render.com |
| Domain | notaryton.com |

## Repository Structure

```
notaryton-bot/
├── bot.py              # Main FastAPI app + Telegram bot
├── crawler.py          # Token discovery + rug detection
├── database.py         # PostgreSQL schema + repositories
├── config.py           # Environment variables
├── social.py           # X/Twitter + Telegram channel posting
├── memescan/           # Token analysis APIs
│   ├── api.py          # TonAPI, GeckoTerminal, Ston.fi clients
│   ├── models.py       # Token, Pool, SafetyLevel dataclasses
│   └── bot.py          # MemeScan Telegram bot handlers
├── templates/          # HTML templates
├── static/             # Assets
├── tests/              # pytest test suite
└── docs/               # This documentation
```
