# SealBet: Trustless Prediction Protocol on TON

> **Building Infrastructure for the Decentralized Economy**
>
> *"Put your money where your mouth is—sealed on-chain, settled by truth."*

---

## Executive Summary

SealBet is a **non-custodial, peer-to-peer prediction market protocol** on TON blockchain, native to Telegram. We're not building a casino—we're building the NYSE for predictions.

**What makes us different:**
- **Non-custodial**: Smart contracts hold funds, not us
- **Peer-to-peer**: Users trade with each other, not against the house
- **Proof integration**: Every prediction can be sealed via MemeSeal
- **Telegram-native**: 950M users, zero friction

**Key insight**: The Telegram ecosystem has 126 gambling apps but no dominant prediction protocol. We're filling that gap with infrastructure that's legally defensible and uniquely positioned through MemeSeal integration.

---

## The Legal Foundation

### Event Contracts vs. Gambling

| Gambling (Avoid) | Event Contracts (Our Play) |
|-----------------|---------------------------|
| Bet against the house | Peer-to-peer trading |
| House sets odds | Market makers set odds |
| House profits from losses | Exchange profits from fees |
| Entertainment purpose | Price discovery/information |
| State gambling laws | Federal derivatives (CFTC) |

### Legal Precedent

**Kalshi v. CFTC (2024)**: Federal court ruled that predicting event outcomes is a derivative, not a game of chance. CFTC dropped its appeal in May 2025.

**Polymarket's Position**: Successfully argued they're a "peer-to-peer exchange facilitating event contracts," not a gambling operator.

**Our Structure**:
- Non-custodial (smart contracts hold funds)
- Peer-to-peer (users trade with each other)
- Fee-based revenue (we profit from activity, not losses)
- Information framing (price discovery, not entertainment)

### Risk Mitigation

1. **US Geo-Block**: Restrict US users via IP blocking initially
2. **Event Contract Framing**: All marketing emphasizes "prediction markets" and "event contracts"
3. **Non-Custodial Architecture**: Smart contracts only, no admin keys to funds
4. **Multi-Source Oracles**: Transparent resolution with dispute mechanism

---

## Core Architecture

### Protocol Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      SEALBET PROTOCOL                        │
│                                                              │
│  ┌───────────────┐    ┌───────────────┐    ┌──────────────┐ │
│  │    FACTORY    │───▶│    MARKETS    │───▶│   ORACLES    │ │
│  │               │    │               │    │              │ │
│  │ Creates pools │    │ Bonding curve │    │ Multi-source │ │
│  │ Sets params   │    │ Escrow funds  │    │ 3-of-5 vote  │ │
│  │ Governance    │    │ Share tokens  │    │ Dispute flow │ │
│  └───────────────┘    └───────────────┘    └──────────────┘ │
│                              │                               │
│                              ▼                               │
│                    ┌───────────────────┐                    │
│                    │    MEMESEAL       │                    │
│                    │   INTEGRATION     │                    │
│                    │                   │                    │
│                    │ Timestamp proof   │                    │
│                    │ Reputation score  │                    │
│                    │ Social sharing    │                    │
│                    └───────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

### Smart Contract Components

#### 1. Factory Contract
- Creates new market contracts
- Registers approved oracles
- Sets protocol fee parameters
- Upgradeable via governance multi-sig

#### 2. Market Contract (per market)
- **Escrow Pool**: Holds all user deposits
- **Bonding Curve**: Calculates buy/sell prices
- **Share Tokens**: YES/NO Jettons (transferable)
- **Settlement Engine**: Processes oracle resolution

#### 3. Oracle Contract
- Aggregates multi-source data (Pyth, Chainlink, custom)
- 3-of-5 consensus threshold
- 6-hour dispute window
- Bond-to-challenge mechanism

#### 4. Reputation Contract
- Tracks sealed predictions per user
- Calculates accuracy scores
- Manages tier benefits (fee discounts, early access)

---

## Bonding Curve Pricing

### Why Bonding Curves?

| Order Book | Bonding Curve |
|-----------|---------------|
| Needs counterparty | Always liquid |
| Price gaps | Continuous pricing |
| Complex UX | Simple buy/sell |
| Fragmented liquidity | Single pool |

### How It Works

```
Price = f(Supply)

As more YES shares are bought:
  → YES price increases
  → NO price decreases
  → Prices always sum to ~$1.00

Early bettors get better odds (lower prices)
Late bettors pay premium (higher prices)
```

### Mathematical Model

Using Logarithmic Market Scoring Rule (LMSR):

```
Cost(q) = b * ln(e^(q_yes/b) + e^(q_no/b))

Where:
  q_yes = quantity of YES shares outstanding
  q_no = quantity of NO shares outstanding
  b = liquidity parameter (controls price sensitivity)
```

### Example Trade

```
Market: "Will $PEPE hit $0.01 by Dec 31?"

Initial state:
  YES price: $0.40 (40% probability)
  NO price: $0.60 (60% probability)

User buys 100 TON of YES at $0.40:
  → Receives 250 YES shares
  → YES price moves to $0.45
  → NO price moves to $0.55

If PEPE hits $0.01:
  → 250 shares × $1.00 = 250 TON
  → Minus 0.5% fee = 248.75 TON
  → Net profit: 148.75 TON (149% return)

If PEPE doesn't hit $0.01:
  → 250 shares × $0.00 = 0 TON
  → Loss: 100 TON
```

---

## User Flow

### Standard Trading Flow

```
1. OPEN MINI APP
   └── See trending markets
   └── Browse categories

2. SELECT MARKET
   └── View current YES/NO prices
   └── See volume, resolution time

3. BUY SHARES
   └── Choose YES or NO
   └── Enter amount (TON)
   └── See shares received & avg price
   └── Confirm transaction

4. [OPTIONAL] SEAL PREDICTION
   └── Pay 1 Star
   └── Get timestamped proof
   └── Shareable to socials

5. WAIT FOR RESOLUTION
   └── Oracle submits outcome
   └── 6-hour dispute window
   └── Resolution finalizes

6. CLAIM WINNINGS
   └── If correct: shares → TON
   └── 0.5% fee deducted
   └── Funds to wallet
```

### Market Creator Flow

```
1. PROPOSE MARKET
   └── Question text
   └── Resolution criteria (specific)
   └── Resolution time
   └── Oracle source

2. STAKE INITIAL LIQUIDITY
   └── Minimum 100 TON
   └── Sets initial odds

3. MARKET GOES LIVE
   └── After approval (or auto for verified creators)
   └── Trading begins

4. EARN CREATOR REWARDS
   └── 10% of protocol fees from market
   └── Reputation boost
```

---

## Oracle System

### Multi-Source Data Feeds

| Market Type | Primary Oracle | Backup Oracle |
|-------------|----------------|---------------|
| Crypto Prices | Pyth Network | RedStone |
| Sports | Chainlink Sports | Manual 3-of-5 |
| Politics | AP/Reuters | Manual 3-of-5 |
| Custom Events | Designated API | Manual 3-of-5 |

### Resolution Flow

```
1. RESOLUTION TIME REACHED
   │
   ▼
2. ORACLE SUBMITS OUTCOME
   └── 3-of-5 consensus required
   └── Signed data with evidence
   │
   ▼
3. DISPUTE WINDOW (6 hours)
   └── Anyone can challenge
   └── Requires 100 TON bond
   │
   ▼
4a. NO DISPUTE → Auto-finalize
   │
   ▼
4b. DISPUTED → DAO of Sealed Predictors votes
   └── Weighted by prediction accuracy
   └── 72-hour voting period
   └── Majority wins, minority forfeits bond
   │
   ▼
5. CLAIMS OPEN
   └── Winners claim shares × $1.00
   └── 0.5% fee deducted
```

### Reputation-Based Arbitration

**The Innovation**: Accurate forecasters become arbiters.

Users with high prediction accuracy (verified via sealed predictions) get voting power in disputes. This creates alignment:
- Accurate predictors have skin in the game
- Incentive to resolve correctly (maintain reputation)
- Decentralized without being random

---

## MemeSeal Integration: The Proof Economy

### Core Concept

Every prediction can be **sealed** with a timestamp proof. This transforms predictions from unverifiable claims into verifiable track records.

### Flow

```
1. USER MAKES PREDICTION
   └── Buys YES on "$PEPE > $0.01"

2. USER SEALS PREDICTION
   └── Pays 1 Star
   └── MemeSeal creates hash + timestamp
   └── Stored on TON blockchain

3. USER SHARES SEALED PREDICTION
   └── Shareable card with QR code
   └── Links to SealBet market
   └── Referral incentive attached

4. MARKET RESOLVES
   └── Oracle reports outcome
   └── Seal marked "VERIFIED ACCURATE" or "VERIFIED INACCURATE"

5. REPUTATION UPDATES
   └── User's public score adjusts
   └── Track record visible on profile
```

### Reputation Benefits

| Score | Fee Discount | Early Access | Special Features |
|-------|--------------|--------------|------------------|
| 0-50 | 0% | No | Basic trading |
| 51-70 | 10% | New markets | Leaderboard eligible |
| 71-85 | 20% | Exclusive markets | Market creation |
| 86-95 | 30% | All features | Oracle voting |
| 96-100 | 50% | VIP | Sponsored contests |

### Viral Loop

```
┌─────────────────┐
│  User Predicts  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  User Seals     │───────────────────┐
└────────┬────────┘                   │
         │                            │
         ▼                            │
┌─────────────────┐                   │
│  User Shares    │    ┌──────────────▼──────────────┐
│  (with referral)│    │  New User Clicks           │
└────────┬────────┘    │  Gets Odds Boost Coupon    │
         │             │  Referrer Gets 10% of Fees │
         │             └─────────────────────────────┘
         ▼
┌─────────────────┐
│ Market Resolves │
│ Seal = Proof    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Reputation Grows│───────────┐
│ More Followers  │           │
└────────┬────────┘           │
         │                    │
         └────────────────────┘
              (Loop continues)
```

---

## Revenue Model

### Core Revenue Streams

| Stream | Rate | When Charged |
|--------|------|--------------|
| Winning Payout Fee | 0.5% | On winning redemptions |
| LP Performance Share | 10% | On LP earnings |
| Market Creation Fee | 10 TON | When creating market |

### Value-Added Services (Optional)

| Service | Price | Description |
|---------|-------|-------------|
| Data Feeds | Subscription | Real-time odds API for traders |
| Premium Analytics | 5 Stars/mo | Advanced charts, alerts |
| x402 Micropayments | Per-action | Pay-per-prediction (no deposits) |

### Fee Distribution

```
Winning Payout Fee (0.5%):
├── 40% → Protocol Treasury
├── 30% → Lottery Pool (MemeSeal lottery)
├── 20% → Oracle Operators
└── 10% → Market Creator

LP Performance Share (10%):
├── 70% → Protocol Treasury
└── 30% → Development Fund
```

### Revenue Projections

| Metric | Month 1 | Month 3 | Month 6 | Year 1 |
|--------|---------|---------|---------|--------|
| Trading Volume | $50K | $200K | $500K | $3M |
| Revenue (0.5%) | $250 | $1K | $2.5K | $15K |
| Active Users | 500 | 2K | 10K | 50K |
| Active Markets | 10 | 50 | 200 | 1K |

### Value Alignment

**What we DON'T do:**
- No rake (extractive)
- No house edge (misaligned)
- No custody fees (legal liability)

**What we DO:**
- Fee only on wins (aligned with user success)
- LP share only on earnings (aligned with liquidity)
- Data products (B2B, no user cost)

---

## Launch Markets

### Phase 1: Curated Markets (5)

1. **"Will BTC exceed $100,000 by Dec 31, 2025?"**
   - Oracle: Pyth Network
   - Resolution: Daily close price
   - Liquidity: 500 TON

2. **"Will $PEPE market cap exceed $10B by Jan 31, 2026?"**
   - Oracle: CoinGecko API
   - Resolution: Market cap at midnight UTC
   - Liquidity: 200 TON

3. **"Will TON price exceed $10 by Q1 2026?"**
   - Oracle: Pyth Network
   - Resolution: Daily close on Mar 31
   - Liquidity: 300 TON

4. **"Will Telegram reach 1B MAU by Mar 2026?"**
   - Oracle: Official Telegram announcement
   - Resolution: First official confirmation
   - Liquidity: 200 TON

5. **"Will ETH ETF net inflows exceed $10B by end of 2025?"**
   - Oracle: Bloomberg/Reuters data
   - Resolution: Cumulative flow report
   - Liquidity: 300 TON

### Phase 2: User-Created Markets

After validating the model, enable verified users (reputation > 70) to create markets with:
- Minimum 100 TON liquidity
- Clear resolution criteria
- Approved oracle source

### Phase 3: Exotic Markets

- Multiple outcomes (elections, competitions)
- Conditional markets ("If X, will Y?")
- Scalar markets (exact price prediction)

---

## Technical Stack

### Smart Contracts

```
Language: Tolk (new TON language, 40% less gas than FunC)
Framework: TON SDK
Testing: Local TON sandbox
Audit: TBD (budget for professional audit)
```

### Frontend

```
Framework: Next.js 14 (App Router)
Language: TypeScript
Styling: Tailwind CSS
State: Zustand
Data: TanStack Query
Charts: Recharts
Telegram: @telegram-apps/sdk-react
Wallet: @tonconnect/ui-react
```

### Backend

```
API: Python FastAPI
Database: PostgreSQL (Render)
Cache: Redis
Queue: Background workers
Hosting: Render.com
```

### Infrastructure

```
Mini App: Vercel
API: Render Web Service
Database: Render PostgreSQL
Smart Contracts: TON Mainnet
Oracles: Pyth Network + custom
```

---

## Roadmap

### Phase 1: Validate (Weeks 1-4)

**Goal**: Prove demand exists

- [ ] Interview 20 meme coin traders
- [ ] Interview 10 signal group admins
- [ ] Prototype one market type
- [ ] Test with 50 MemeSeal power users
- [ ] Gather feedback, iterate

**Deliverables**:
- User research summary
- MVP spec refinement
- Go/no-go decision

### Phase 2: Build MVP (Weeks 5-12)

**Goal**: Functional prediction market

- [ ] Deploy bonding curve contract (testnet)
- [ ] Deploy escrow + settlement contracts
- [ ] Build Next.js Mini App
- [ ] Integrate TON Connect
- [ ] Integrate Pyth oracles
- [ ] Integrate MemeSeal for proofs
- [ ] Security audit
- [ ] Deploy to mainnet

**Deliverables**:
- Working Mini App
- 5 curated markets live
- Sealed-share feature

### Phase 3: Launch (Weeks 13-16)

**Goal**: Public launch with traction

- [ ] Closed beta (200 MemeSeal users)
- [ ] Measure key metrics
- [ ] Fix bugs, optimize UX
- [ ] Open to 50K Telegram users
- [ ] US geo-blocking active
- [ ] Marketing push

**Deliverables**:
- $50K+ trading volume
- 500+ active users
- Press coverage

### Phase 4: Scale (Ongoing)

**Goal**: Dominant protocol on TON

- [ ] Add liquidity incentives
- [ ] Launch leaderboards + social
- [ ] Partner with signal groups
- [ ] Expand market types
- [ ] User-created markets
- [ ] Governance token

---

## Risk Assessment

### Legal Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Classified as gambling | Medium | High | Non-custodial, P2P, event contract framing |
| US enforcement | Medium | High | Geo-block US IPs |
| Multi-jurisdiction issues | Low | Medium | TON = global, no specific jurisdiction |

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Smart contract bug | Medium | Critical | Audit, bug bounty, gradual rollout |
| Oracle manipulation | Low | High | Multi-source, dispute mechanism |
| Front-running | Medium | Medium | Commit-reveal scheme |

### Market Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Low liquidity | High | Medium | LP incentives, bootstrap key markets |
| Competition | Medium | Medium | First-mover, MemeSeal moat |
| User education | Medium | Low | Simple UX, progressive disclosure |

---

## Competitive Moat

### Why We Win

1. **First non-custodial prediction protocol on TON**
   - No serious competitor yet
   - 126 apps, all custodial casinos

2. **MemeSeal integration**
   - Unique proof-of-prediction feature
   - Built-in reputation system
   - Viral sharing mechanism

3. **Telegram distribution**
   - 950M users
   - Zero-friction onboarding
   - Native payments (Stars + TON)

4. **Trust through transparency**
   - All code open source
   - All settlements on-chain
   - All proofs verifiable

5. **Community-first**
   - Existing MemeSeal users
   - Lottery integration
   - Signal group partnerships

---

## Success Metrics

### Week 1 Targets

- [ ] 50 beta users
- [ ] 5 markets live
- [ ] $10K trading volume
- [ ] Zero critical bugs

### Month 1 Targets

- [ ] 500 active users
- [ ] 20 markets
- [ ] $50K trading volume
- [ ] MemeSeal integration live
- [ ] First sealed prediction shared

### Month 3 Targets

- [ ] 2,000 active users
- [ ] 50 markets
- [ ] $200K trading volume
- [ ] Leaderboards launched
- [ ] First signal group partnership

### Month 6 Targets

- [ ] 10,000 active users
- [ ] 200 markets
- [ ] $500K trading volume
- [ ] User-created markets
- [ ] 3+ signal group integrations

### Year 1 Targets

- [ ] 50,000 active users
- [ ] 1,000+ markets
- [ ] $3M trading volume
- [ ] Governance token launch
- [ ] Protocol decentralization

---

## The Vision

**We're not building a casino.**

We're building trust infrastructure for the degen economy.

- Traders need proof of their calls → We provide seals
- Signal groups need accountability → We provide track records
- Users need to know who's honest → We provide reputation

**"Proof or it didn't happen"** becomes **"Prove it or shut up."**

SealBet transforms Telegram's trustless chatter into a verifiable economy of ideas.

---

## Next Steps

1. **Read**: [LEGAL.md](./LEGAL.md) - Legal structure details
2. **Read**: [TECH-STACK.md](./TECH-STACK.md) - Full technical architecture
3. **Read**: [CONTRACTS.md](./CONTRACTS.md) - Smart contract specifications
4. **Read**: [ROADMAP.md](./ROADMAP.md) - Detailed execution timeline

---

*"Deploy the contracts, seed the first markets, and let 950 million users finally put their money where their mouth is—sealed on-chain, settled by truth."*
