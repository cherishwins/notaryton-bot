# SealBet: TON Foundation Grant Proposal

> **Trustless Prediction Infrastructure for the Telegram Economy**
>
> Building the first non-custodial, peer-to-peer prediction market protocol on TON.

---

## Executive Summary

**Project:** SealBet - Trustless Prediction Market Protocol
**Category:** DeFi / Telegram Mini Apps
**Funding Request:** $35,000 (milestone-based)
**Timeline:** 16 weeks to mainnet launch
**Team:** Solo founder with shipped products (MemeSeal, MemeScan)

**One-liner:** SealBet brings Polymarket-style prediction markets to Telegram's 950M users—non-custodial, peer-to-peer, with on-chain proof of every prediction.

---

## The Problem

### Telegram Has a Trust Crisis

The Telegram crypto ecosystem is plagued by:

1. **Fake Alpha Callers** - Signal groups claim "92% accuracy" with zero proof
2. **Custodial Gambling Apps** - 126 gambling apps on TON, all holding user funds
3. **No Accountability** - Anyone can claim they "called it" after the fact
4. **Regulatory Targets** - Custodial casinos are easy enforcement targets

### The Gap

| What Exists | What's Missing |
|-------------|----------------|
| Polymarket ($3.74B monthly volume) | Not on Telegram, blocks US |
| TON gambling apps (126) | All custodial, house edge |
| Signal groups (3M+) | No verifiable track records |
| MemeSeal (timestamp proofs) | No prediction market integration |

**Result:** A $100M+ revenue opportunity sits unfilled on TON.

---

## The Solution: SealBet

### What We're Building

A **non-custodial prediction market protocol** native to Telegram:

```
┌─────────────────────────────────────────────────────────────┐
│                      SEALBET PROTOCOL                        │
│                                                              │
│  ┌───────────────┐    ┌───────────────┐    ┌──────────────┐ │
│  │    FACTORY    │───▶│    MARKETS    │───▶│   ORACLES    │ │
│  │               │    │               │    │              │ │
│  │ Creates pools │    │ Bonding curve │    │ Multi-source │ │
│  │ Sets params   │    │ Escrow funds  │    │ 3-of-5 vote  │ │
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

### Key Features

| Feature | Description | Why It Matters |
|---------|-------------|----------------|
| **Non-Custodial** | Smart contracts hold funds, not us | Eliminates counterparty risk |
| **Peer-to-Peer** | Users trade with each other | No house edge, legally defensible |
| **Bonding Curves** | Continuous liquidity, no order matching | Always liquid, fair pricing |
| **MemeSeal Proofs** | Every prediction timestamped on-chain | Verifiable track records |
| **Telegram Native** | Mini App, zero friction | 950M user distribution |

### How It Works

```
1. User opens SealBet Mini App in Telegram
2. Browses markets ("Will BTC hit $100K?")
3. Buys YES or NO shares via bonding curve
4. Optionally seals prediction (MemeSeal proof)
5. Shares sealed prediction card to socials
6. Market resolves via multi-source oracles
7. Winners claim payouts (0.5% fee)
8. Track record updates, reputation grows
```

---

## Why This Matters for TON

### Ecosystem Growth

| Metric | Impact |
|--------|--------|
| **TVL Growth** | Initial $50K+ liquidity, scaling to $1M+ |
| **Transaction Volume** | 10,000+ monthly transactions |
| **New Users** | 10,000+ new TON wallets in Year 1 |
| **Developer Tooling** | Open-source contracts for ecosystem |

### Strategic Alignment

1. **Telegram Mini Apps** - Native integration, frictionless UX
2. **DeFi on TON** - Novel primitive (prediction markets don't exist yet)
3. **Mass Adoption** - Familiar UX (betting), new infrastructure
4. **Open Source** - All contracts MIT licensed

### Competitive Position

| Competitor | Chain | Custodial | Telegram Native | TON |
|------------|-------|-----------|-----------------|-----|
| Polymarket | Polygon | No | No | No |
| Kalshi | Centralized | Yes | No | No |
| Azuro | Multi-chain | No | No | No |
| TON Casinos | TON | Yes | Partial | Yes |
| **SealBet** | **TON** | **No** | **Yes** | **Yes** |

**We're the only non-custodial prediction protocol built for Telegram.**

---

## Team

### Founder: Jesse

**Background:**
- Built and shipped **MemeSeal** - blockchain timestamping on TON
- Built and shipped **MemeScan** - meme coin terminal Mini App
- 10+ years software engineering experience
- Deep understanding of TON/Telegram ecosystem

**Existing Traction:**
- MemeSeal: Live on TON mainnet, processing seals
- MemeScan: Launched Mini App with real users
- Active in TON developer community

**GitHub:** [notaryton-bot](https://github.com/jesse/notaryton-bot) (private, can provide access)

---

## Technical Approach

### Smart Contracts (Tact)

```
contracts/
├── MarketFactory.tact    # Creates new markets
├── Market.tact           # Bonding curve + escrow
├── Oracle.tact           # Multi-source resolution
└── Reputation.tact       # Track record scoring
```

**Key Functions:**

```tact
// Market.tact
receive(msg: BuyShares) {
    // Calculate shares from bonding curve
    // Transfer TON to escrow
    // Mint share tokens to user
    // Emit event for indexer
}

receive(msg: ClaimWinnings) {
    // Verify market resolved
    // Verify user holds winning shares
    // Calculate payout (minus 0.5% fee)
    // Transfer TON to user
    // Burn shares
}
```

### Frontend (Next.js + Telegram Mini App)

```
apps/mini-app/
├── app/
│   ├── markets/          # Market list + detail
│   ├── portfolio/        # User positions
│   ├── leaderboard/      # Top predictors
│   └── seal/             # MemeSeal integration
├── components/
│   ├── TradingPanel/     # Buy/sell interface
│   ├── PriceChart/       # Bonding curve viz
│   └── SealCard/         # Shareable proof cards
└── lib/
    ├── ton/              # TON Connect integration
    └── contracts/        # Contract bindings
```

### Backend (FastAPI)

```
api/
├── markets/              # Market CRUD + indexing
├── users/                # Profiles + positions
├── oracle/               # Price feeds + resolution
└── seal/                 # MemeSeal integration
```

### Oracle System

| Market Type | Primary Source | Backup Source |
|-------------|----------------|---------------|
| Crypto Prices | Pyth Network | RedStone |
| Sports | The Odds API | Manual 3-of-5 |
| Events | Official APIs | Manual 3-of-5 |

**Resolution Flow:**
1. Resolution time reached
2. Oracle submits outcome (3-of-5 consensus)
3. 6-hour dispute window
4. Anyone can challenge with 100 TON bond
5. If disputed: DAO of high-reputation predictors votes
6. Resolution finalizes, claims open

---

## Roadmap & Milestones

### Phase 1: Validation (Weeks 1-4)

**Objective:** Prove demand before building

| Task | Deliverable |
|------|-------------|
| Interview 30 meme traders | User research report |
| Interview 15 signal group admins | Partner interest list |
| Build Figma prototype | Clickable prototype |
| Test with 50 MemeSeal users | Feedback synthesis |
| Go/No-Go decision | Decision document |

**Success Criteria:**
- 70%+ of traders express interest
- 50%+ of signal admins would integrate
- 30+ MemeSeal users commit to beta

**Milestone 1 Payment:** $0 (self-funded validation)

---

### Phase 2: MVP Build (Weeks 5-12)

**Objective:** Ship working prediction market

| Week | Task | Deliverable |
|------|------|-------------|
| 5-6 | Smart contracts | Factory + Market on testnet |
| 7-8 | Frontend | Next.js Mini App skeleton |
| 9-10 | Backend + Oracles | API + Pyth integration |
| 11 | MemeSeal Integration | Seal + share flow |
| 12 | Testing + Audit | Security review |

**Deliverables:**
- [ ] Smart contracts deployed to testnet
- [ ] Working Mini App connecting to testnet
- [ ] 5 curated markets created
- [ ] MemeSeal proof integration working
- [ ] Security audit completed

**Milestone 2 Payment:** $17,500 (50% of grant)

---

### Phase 3: Launch (Weeks 13-16)

**Objective:** Public launch with traction

| Week | Task | Deliverable |
|------|------|-------------|
| 13 | Closed beta | 200 MemeSeal users |
| 14 | Iterate on feedback | Bug fixes, UX improvements |
| 15 | Marketing prep | Announcements, social assets |
| 16 | Public launch | Open to 50K Telegram users |

**Deliverables:**
- [ ] Mainnet deployment
- [ ] 500+ active traders
- [ ] $50K+ trading volume
- [ ] 100+ sealed predictions
- [ ] US geo-blocking active

**Milestone 3 Payment:** $17,500 (50% of grant)

---

### Phase 4: Scale (Post-Grant)

**Self-sustaining via protocol fees:**

| Month | Users | Volume | Revenue |
|-------|-------|--------|---------|
| 3 | 2,000 | $200K | $1,000 |
| 6 | 10,000 | $500K | $2,500 |
| 12 | 50,000 | $3M | $15,000 |

---

## Budget Breakdown

### Total Request: $35,000

| Category | Amount | Details |
|----------|--------|---------|
| **Smart Contract Audit** | $15,000 | Professional security audit (TonBit or equivalent) |
| **Initial Liquidity** | $10,000 | Seed 5 launch markets (~2000 TON) |
| **Oracle Infrastructure** | $3,000 | Pyth integration, backup oracles |
| **Infrastructure** | $4,000 | Render hosting, Vercel, database (12 months) |
| **Bug Bounty** | $3,000 | Security incentive program |
| **Total** | **$35,000** | |

### What's NOT Included (Self-Funded)

| Category | Amount | Notes |
|----------|--------|-------|
| Founder salary | $0 | Self-funded during build |
| Marketing | $0 | Organic + existing audience |
| Legal | $0 | Non-custodial = minimal legal |

---

## Milestone Payment Schedule

| Milestone | Deliverable | Amount | Timing |
|-----------|-------------|--------|--------|
| **M1** | Go/No-Go Decision + Research | $0 | Week 4 |
| **M2** | Testnet MVP + Audit Complete | $17,500 | Week 12 |
| **M3** | Mainnet Launch + Traction | $17,500 | Week 16 |

**Total:** $35,000

---

## Success Metrics

### Week 16 (Launch)

| Metric | Target |
|--------|--------|
| Active traders | 500+ |
| Trading volume | $50,000+ |
| Sealed predictions | 100+ |
| Critical bugs | 0 |
| Markets live | 5+ |

### Month 6 (Growth)

| Metric | Target |
|--------|--------|
| Active traders | 10,000+ |
| Monthly volume | $500,000+ |
| User-created markets | 50+ |
| Signal group integrations | 3+ |

### Year 1 (Scale)

| Metric | Target |
|--------|--------|
| Active traders | 50,000+ |
| Annual volume | $3,000,000+ |
| Protocol revenue | $15,000+/month |
| Self-sustaining | Yes |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Smart contract bug | Medium | Critical | Audit + bug bounty + gradual rollout |
| Low liquidity | High | Medium | LP incentives + curated markets |
| Oracle manipulation | Low | High | Multi-source + dispute mechanism |
| Regulatory action | Low | High | Non-custodial + US geo-block |
| Competition | Medium | Medium | First-mover + MemeSeal moat |

---

## Why Fund SealBet?

### 1. Fills a Critical Gap
TON has 126 gambling apps but zero non-custodial prediction infrastructure. We're building the missing primitive.

### 2. Drives Ecosystem Growth
- New TVL to TON DeFi
- New transaction volume
- New users onboarded via Telegram
- Open-source contracts for ecosystem

### 3. Unique Moat
MemeSeal integration creates verifiable track records—something no competitor has. Every prediction becomes proof.

### 4. Proven Builder
Already shipped MemeSeal and MemeScan on TON. This isn't a first project—it's an expansion of working infrastructure.

### 5. Sustainable Model
0.5% fee on winning payouts = self-sustaining after launch. Grant funds infrastructure, not ongoing operations.

---

## Open Source Commitment

All smart contracts will be:
- MIT licensed
- Fully documented
- Available on GitHub
- Verifiable on TON Explorer

**Why:** We're building infrastructure, not a moat. Open source grows the ecosystem.

---

## Contact

**Founder:** Jesse
**Telegram:** @[your_handle]
**Email:** [your_email]
**GitHub:** [your_github]
**Existing Projects:**
- MemeSeal: [link]
- MemeScan: [link]

---

## Appendix A: Technical Specifications

### Bonding Curve Math (LMSR)

```
Cost(q) = b * ln(e^(q_yes/b) + e^(q_no/b))

Where:
  q_yes = quantity of YES shares outstanding
  q_no = quantity of NO shares outstanding
  b = liquidity parameter (controls price sensitivity)
```

**Example Trade:**
```
Market: "BTC > $100K by Dec 31?"
Current: YES = $0.40, NO = $0.60

User buys 100 TON of YES at $0.40:
  → Receives ~250 YES shares
  → YES price moves to ~$0.45
  → NO price moves to ~$0.55

If BTC > $100K:
  → 250 shares × $1.00 = 250 TON
  → Minus 0.5% fee = 248.75 TON
  → Net profit: 148.75 TON
```

### Contract Interfaces

```tact
contract Market {
    // State
    factory: Address;
    question: String;
    resolutionTime: Int;
    yesSupply: Int;
    noSupply: Int;
    resolved: Bool;
    outcome: Bool?;

    // Buy shares
    receive(msg: BuyShares) { ... }

    // Sell shares
    receive(msg: SellShares) { ... }

    // Submit resolution (oracle only)
    receive(msg: SubmitResolution) { ... }

    // Dispute resolution
    receive(msg: DisputeResolution) { ... }

    // Claim winnings
    receive(msg: ClaimWinnings) { ... }

    // Get current prices
    get fun getPrice(outcome: Bool): Int { ... }
}
```

---

## Appendix B: Competitive Analysis

### Polymarket
- **Volume:** $3.74B/month (Oct 2024)
- **Chain:** Polygon
- **Telegram:** No
- **US Access:** Blocked
- **Custody:** Non-custodial
- **Gap:** Not on Telegram, not on TON

### Kalshi
- **Volume:** $50B+ annualized
- **Chain:** Centralized
- **Telegram:** No
- **US Access:** Yes (CFTC registered)
- **Custody:** Custodial
- **Gap:** Centralized, not crypto-native

### Azuro
- **Volume:** $500M+ lifetime
- **Chain:** Multi (Polygon, Gnosis, etc.)
- **Telegram:** Limited
- **US Access:** Blocked
- **Custody:** Non-custodial
- **Gap:** Not on TON, sports-focused

### TON Gambling Apps
- **Count:** 126 apps
- **Custody:** All custodial
- **House Edge:** Yes
- **Predictions:** None focused
- **Gap:** No non-custodial prediction market

---

## Appendix C: Legal Framework

### Event Contracts vs Gambling

| Gambling | Event Contracts (SealBet) |
|----------|---------------------------|
| Bet against house | Peer-to-peer trading |
| House sets odds | Market makers set odds |
| House profits from losses | Exchange profits from fees |
| Entertainment purpose | Price discovery |
| State gambling laws | Federal derivatives (CFTC) |

### Precedent

**Kalshi v. CFTC (Sept 2024):** Federal court ruled prediction markets are derivatives, not gambling. CFTC dropped appeal May 2025.

**Polymarket:** Successfully argued P2P exchange of event contracts is not gambling operation.

### Our Structure

1. **Non-custodial:** Smart contracts hold funds
2. **Peer-to-peer:** Users trade with each other
3. **Fee-based:** We profit from activity, not outcomes
4. **Event contracts:** Price discovery framing

### Risk Mitigation

- US IP blocking at launch
- "Event contracts" language throughout
- No admin keys to user funds
- Multi-source oracle resolution

---

*"Building the infrastructure layer for degen finance—one sealed prediction at a time."*
