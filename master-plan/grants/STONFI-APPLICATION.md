# STON.fi Grant Application - SealBet

**Apply here:** https://stonfi.notion.site/199f2441e97e80c59b15c6a6603789dd?pvs=105

---

## Project Name
SealBet - Trustless Prediction Market Protocol

## Project Description

SealBet is the first non-custodial, peer-to-peer prediction market on TON, native to Telegram. Users trade event outcome shares (YES/NO) via smart contracts, with no house edge and no custody risk.

**How it works:**
1. User opens Telegram Mini App
2. Browses prediction markets ("Will BTC hit $100K?")
3. Buys YES or NO shares
4. Market resolves via multi-source oracles
5. Winners claim payouts (2% protocol fee)

**Current status:** Smart contracts built and tested (10/10 tests passing), ready for testnet deployment.

## STON.fi SDK Integration Plan

We will integrate STON.fi SDK for:

1. **Token Swaps in Mini App**
   - Users can swap any TON token to participate in markets
   - One-click conversion from USDT/NOT/STON to market collateral
   - Reduces friction for users holding various tokens

2. **Liquidity Pool Integration**
   - Market liquidity backed by STON.fi pools
   - LP tokens as collateral option
   - Yield on idle market funds via STON.fi

3. **Price Oracle Backup**
   - Use STON.fi pool prices as secondary oracle source
   - Cross-reference with Pyth for manipulation resistance

**Technical approach:**
```typescript
// Example: Swap before betting
import { StonfiSDK } from '@ston-fi/sdk';

async function swapAndBet(tokenIn: string, amount: bigint, marketId: string, outcome: boolean) {
  // 1. Swap user's token to TON via STON.fi
  const swap = await stonfi.swap(tokenIn, 'TON', amount);

  // 2. Place bet with received TON
  await market.placeBet(outcome, swap.amountOut);
}
```

## Team Background

**Founder: Jesse**
- Built and shipped MemeSeal (blockchain timestamping on TON mainnet)
- Built and shipped MemeScan (meme coin terminal Mini App)
- 10+ years software engineering experience
- Active TON developer community member

**Existing TON Projects:**
- MemeSeal: Live, processing seals on mainnet
- MemeScan: Launched Mini App with real users

## Milestones & Timeline

| Week | Milestone | Deliverable |
|------|-----------|-------------|
| 1-2 | STON.fi SDK Integration | Swap functionality in Mini App |
| 3-4 | Testnet with Swaps | Working swap → bet flow |
| 5-6 | LP Integration | Pool-backed liquidity option |
| 7-8 | Mainnet Launch | Public with STON.fi integration |

## Grant Fund Usage

| Category | Amount | Purpose |
|----------|--------|---------|
| Smart Contract Audit | $5,000 | Security review of market contracts |
| Initial Liquidity | $3,000 | Seed first 5 markets |
| Infrastructure | $2,000 | Hosting, oracle costs (6 months) |
| **Total** | **$10,000** | |

## Why STON.fi Integration Matters

1. **User Experience** - No need to hold specific tokens, swap any asset
2. **Liquidity Depth** - STON.fi pools provide deep liquidity
3. **Ecosystem Synergy** - Drives volume to STON.fi DEX
4. **Price Discovery** - Pool prices as oracle backup

## Long-Term Vision

SealBet aims to become the default prediction infrastructure on TON:
- Year 1: 50K users, $3M volume
- Year 2: Protocol decentralization, governance token
- Integration: Deep STON.fi integration for all trading

We see STON.fi as critical infrastructure for DeFi on TON, and SealBet will drive significant swap volume as users convert tokens to participate in markets.

## Contact

- **Telegram:** @[YOUR_HANDLE]
- **Email:** [YOUR_EMAIL]
- **GitHub:** [YOUR_GITHUB]

---

## Checklist Before Submitting

- [ ] Fill out Notion form at link above
- [ ] Include project description
- [ ] Detail STON.fi SDK integration plan
- [ ] Explain team background
- [ ] List milestones with timeline
- [ ] Specify grant amount and usage
- [ ] Provide contact information
