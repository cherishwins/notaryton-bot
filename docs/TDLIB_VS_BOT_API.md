# TDLib vs Bot API - When to Use Which

> Technical decision reference for NotaryTON Labs architecture.

---

## Current Stack (Bot API via aiogram)

Our core stack uses **aiogram 3.15+** for Telegram bot interactions. This is:
- Lightweight, low memory
- Great for payments (TON, Stars)
- Handles core needs: commands, messages, inline queries, web apps
- Sufficient for 80-90% of crypto bot use cases

---

## What is TDLib?

TDLib (Telegram Database Library) is for building **full Telegram clients**, not just bots.

| Feature | Bot API (aiogram) | TDLib |
|---------|-------------------|-------|
| **Scope** | Bot interactions only | Full client (user accounts, UI) |
| **Resource Use** | Lightweight | Higher memory/disk (SQLite DB grows) |
| **Real-Time** | Polling/webhooks with limits | Fully asynchronous, stable on poor connections |
| **Customization** | Limited to bot features | Build custom Telegram-like apps |
| **TON Fit** | Great for payments/alerts | Better for deep client-side integrations |

---

## When TDLib is Worth It

### Use Cases That Justify TDLib
1. **Custom Client Development** - Standalone apps where users do actions without bot commands
2. **Real-Time Data at Scale** - Asynchronous updates avoid Bot API rate limits (100 connections)
3. **Client-Side Security** - Local encryption with user keys, client-side hashing before upload
4. **Mobile/Desktop Apps** - Cross-platform support (Android, iOS, WebAssembly)
5. **KOL Tracking Automation** - Process updates client-side, reduce server load

### Example Use Cases for NotaryTON
- Embed MemeScan rug score directly into chat view
- Automated KOL call capture via X/Twitter API in client
- Custom interface for Trader Intelligence
- Phase 4 mobile app with unified TON/Telegram experience

---

## When to Stick with Bot API

- Quick iterations and rapid deployment
- Core bot interactions (payments, alerts, commands)
- You don't need full client functionality
- Lower complexity and resource usage is priority

---

## Potential Implementation

If we do integrate TDLib:
1. Use Python wrapper (`pytdbot`) - aligns with existing stack
2. Hybrid approach: Bot for core, TDLib client for premium features
3. Gate behind $SEAL staking for access

---

## Key Insight

> Bot API suffices for 80-90% of crypto bots. TDLib complements by filling gaps in advanced use cases like predictive rug detection via ML in a client app.

Our current aiogram setup handles MemeSeal, MemeScan, and casino perfectly. TDLib becomes relevant for Phase 4 expansions (mobile apps, multi-chain, custom client experiences).

---

## References

- [TDLib Documentation](https://core.telegram.org/tdlib)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [TON Mini Apps Guide](https://docs.ton.org/develop/dapps/telegram-apps)
