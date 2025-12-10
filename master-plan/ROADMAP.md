# SealBet: Execution Roadmap

> **Week-by-week actionable plan to launch the trustless prediction protocol on TON.**
>
> **Priority: MemeMarket/SealBet FIRST. MemeMart later (or never).**

---

## Strategic Priority

| Priority | Product | Revenue Ceiling | Effort | Status |
|----------|---------|-----------------|--------|--------|
| **#1** | **MemeMarket/SealBet** | $100M+/year | High | **BUILD NOW** |
| #2 | MemeSeal | $500K/year | Low | Maintain |
| #3 | MemeScan | $100K/year | Low | Maintain |
| #4 | MemeMart | $500K/year | High | Defer 6+ months |

**Why MemeMarket first:**
- Highest revenue ceiling (prediction markets can do billions in volume)
- Software scales infinitely (no inventory, no shipping)
- Strongest ecosystem fit (MemeSeal proof integration is unique moat)
- First-mover on TON (no serious competitor)

---

## Overview

| Phase | Duration | Goal | Key Milestone |
|-------|----------|------|---------------|
| **Phase 1** | Weeks 1-4 | Validate | User research complete, go/no-go decision |
| **Phase 2** | Weeks 5-12 | Build MVP | Working Mini App with 5 markets |
| **Phase 3** | Weeks 13-16 | Launch | $50K volume, 500 users |
| **Phase 4** | Ongoing | Scale | Dominant TON prediction protocol |

---

## Phase 1: Validation (Weeks 1-4)

### Goal
Prove that meme traders and signal group admins want this product before writing code.

### Week 1: User Research Setup

**Objective**: Identify and recruit interview subjects

| Task | Owner | Deliverable |
|------|-------|-------------|
| Create interview script for meme traders | Jesse | 15-question doc |
| Create interview script for signal admins | Jesse | 10-question doc |
| Identify 30 meme traders in Telegram groups | Jesse | Contact list |
| Identify 15 signal group admins | Jesse | Contact list |
| Set up scheduling | Jesse | Booking system |

**Interview Questions (Traders)**:
1. How do you currently make predictions about meme coins?
2. Do you share your predictions publicly? Where?
3. How do you prove you called something before it happened?
4. Have you ever been scammed by a fake "alpha" caller?
5. Would you pay to timestamp your predictions on blockchain?
6. How much would you stake on a meme coin prediction?
7. What would make you trust a prediction market?
8. Do you use Telegram casino bots? Which ones?
9. What's broken about current prediction/betting options?
10. Would you pay a 0.5% fee on winnings?

**Interview Questions (Signal Admins)**:
1. How do you prove your track record to new subscribers?
2. What's your biggest challenge in building trust?
3. Would you integrate a seal/proof system for your calls?
4. How do your users verify your historical accuracy?
5. Would prediction markets help or hurt your business?

### Week 2: Conduct Interviews

**Objective**: Complete 20+ trader interviews, 10+ admin interviews

| Day | Target |
|-----|--------|
| Mon | 4 trader interviews |
| Tue | 4 trader interviews |
| Wed | 4 trader interviews |
| Thu | 4 trader interviews + 2 admin |
| Fri | 4 trader interviews + 2 admin |
| Sat | 3 admin interviews |
| Sun | 3 admin interviews |

**Documentation**:
- Record all calls (with permission)
- Take detailed notes
- Tag key insights

### Week 3: Analyze & Prototype

**Objective**: Synthesize findings, create clickable prototype

| Task | Owner | Deliverable |
|------|-------|-------------|
| Analyze interview transcripts | Jesse | Key insights doc |
| Identify top 3 pain points | Jesse | Priority list |
| Identify top 3 desired features | Jesse | Feature list |
| Create Figma wireframes | Jesse | 5-screen prototype |
| Build clickable prototype | Jesse | Figma prototype link |

**Key Questions to Answer**:
- Do traders want proof of predictions? (Y/N)
- Do they trust blockchain-based proof? (Y/N)
- What's the willingness to pay? ($X per seal, Y% fee)
- What market types are most desired?
- What's the minimum viable feature set?

### Week 4: Validate with MemeSeal Users

**Objective**: Test prototype with existing users

| Task | Owner | Deliverable |
|------|-------|-------------|
| Select 50 MemeSeal power users | Jesse | User list |
| Share prototype via Telegram | Jesse | DM campaign |
| Collect feedback (survey) | Jesse | Survey results |
| Conduct 5 follow-up calls | Jesse | Call notes |
| Make go/no-go decision | Jesse | Decision doc |

**Go Criteria**:
- 70%+ of traders say they'd use prediction markets
- 50%+ of admins say they'd integrate seal proofs
- Average willingness to pay > $0.25 per seal
- At least 30 MemeSeal users commit to beta

**No-Go Criteria**:
- < 50% interest from traders
- Major legal concern raised
- No clear differentiation from existing options

---

## Phase 2: Build MVP (Weeks 5-12)

### Goal
Ship a working prediction market with 5 curated markets.

### Week 5-6: Smart Contract Development

**Objective**: Deploy core contracts to testnet

| Task | Owner | Deliverable |
|------|-------|-------------|
| Design bonding curve math | Jesse | Specification doc |
| Write Factory contract (Tact) | Jesse | Tested contract |
| Write Market contract (Tact) | Jesse | Tested contract |
| Write Oracle interface | Jesse | Tested contract |
| Deploy to testnet | Jesse | Testnet addresses |
| Write unit tests | Jesse | 80%+ coverage |

**Contract Architecture**:

```
Factory Contract
├── create_market(params) → Market
├── set_protocol_fee(bps)
├── add_oracle(address)
└── pause_protocol()

Market Contract
├── buy_shares(outcome, amount) → shares
├── sell_shares(outcome, shares) → amount
├── get_price(outcome) → price
├── submit_resolution(outcome)
├── dispute_resolution(bond)
├── finalize_resolution()
├── claim_winnings() → payout
└── refund() → original (if canceled)
```

### Week 7-8: Frontend Development

**Objective**: Build Next.js Mini App

| Task | Owner | Deliverable |
|------|-------|-------------|
| Set up Next.js 14 project | Jesse | Repo initialized |
| Integrate @telegram-apps/sdk | Jesse | Working init |
| Integrate @tonconnect/ui-react | Jesse | Wallet connect |
| Build market list page | Jesse | /markets route |
| Build market detail page | Jesse | /markets/[id] |
| Build trading UI (buy/sell) | Jesse | Trading component |
| Build portfolio page | Jesse | /portfolio |
| Build leaderboard page | Jesse | /leaderboard |
| Add haptic feedback | Jesse | All interactions |
| Mobile optimization | Jesse | Responsive UI |

**Tech Stack**:
```
next: 14.x
typescript: 5.x
tailwindcss: 3.x
@telegram-apps/sdk-react: latest
@tonconnect/ui-react: latest
zustand: 4.x
@tanstack/react-query: 5.x
recharts: 2.x
```

### Week 9-10: Backend & Oracle Integration

**Objective**: Build API and integrate oracles

| Task | Owner | Deliverable |
|------|-------|-------------|
| Set up FastAPI backend | Jesse | API server |
| Design PostgreSQL schema | Jesse | Migration files |
| Build market CRUD endpoints | Jesse | /api/markets |
| Build user endpoints | Jesse | /api/users |
| Build trade history endpoints | Jesse | /api/trades |
| Integrate Pyth Network | Jesse | Price oracle |
| Build oracle aggregator | Jesse | Multi-source |
| Set up TONAPI webhooks | Jesse | Payment detection |

**API Endpoints**:
```
GET  /api/markets           # List all markets
GET  /api/markets/:id       # Market details
POST /api/markets           # Create market (admin)
GET  /api/markets/:id/trades # Trade history

GET  /api/users/:id         # User profile
GET  /api/users/:id/positions # User positions
GET  /api/users/:id/history  # Trade history

GET  /api/leaderboard       # Top predictors
GET  /api/stats             # Protocol stats

POST /api/oracle/submit     # Submit resolution
POST /api/oracle/dispute    # Dispute resolution
```

### Week 11: MemeSeal Integration

**Objective**: Connect prediction sealing to MemeSeal

| Task | Owner | Deliverable |
|------|-------|-------------|
| Design seal data format | Jesse | Spec doc |
| Add "Seal Prediction" button | Jesse | UI component |
| Integrate MemeSeal bot API | Jesse | API integration |
| Generate shareable seal cards | Jesse | Image generator |
| Add referral links to shares | Jesse | Tracking |
| Build verification page | Jesse | /verify/[hash] |

**Seal Data Structure**:
```json
{
  "type": "sealbet_prediction",
  "market_id": "abc123",
  "market_question": "Will BTC > $100K?",
  "outcome": "YES",
  "shares": 100,
  "entry_price": 0.45,
  "timestamp": 1704067200,
  "user_address": "EQ...",
  "signature": "..."
}
```

### Week 12: Testing & Security

**Objective**: Audit and harden before launch

| Task | Owner | Deliverable |
|------|-------|-------------|
| Internal security review | Jesse | Findings doc |
| Fix critical/high issues | Jesse | Patched code |
| Load testing | Jesse | Performance report |
| Submit for external audit | Jesse | Audit engagement |
| Bug bounty setup | Jesse | Bounty program |
| Deploy to mainnet | Jesse | Production contracts |

**Security Checklist**:
- [ ] Reentrancy protection
- [ ] Integer overflow checks
- [ ] Access control validation
- [ ] Oracle manipulation resistance
- [ ] Front-running mitigation
- [ ] Emergency pause functionality
- [ ] Upgrade mechanism safety

---

## Phase 3: Launch (Weeks 13-16)

### Goal
Public launch with $50K volume and 500 users.

### Week 13: Closed Beta

**Objective**: Test with 200 MemeSeal power users

| Task | Owner | Deliverable |
|------|-------|-------------|
| Select 200 beta users | Jesse | User list |
| Create 5 launch markets | Jesse | Live markets |
| Seed initial liquidity (500 TON) | Jesse | Funded pools |
| Send beta invites | Jesse | DM campaign |
| Set up feedback channel | Jesse | Telegram group |
| Monitor for bugs/issues | Jesse | Daily review |

**Launch Markets**:
1. BTC > $100K by Dec 31, 2025
2. $PEPE market cap > $10B by Jan 31
3. TON > $10 by Mar 31, 2026
4. Telegram 1B MAU by Mar 2026
5. ETH ETF $10B inflows by end 2025

### Week 14: Metrics & Iteration

**Objective**: Measure, learn, improve

| Metric | Target | Actual |
|--------|--------|--------|
| Beta signups | 200 | ? |
| Active traders | 50 | ? |
| Total volume | $10K | ? |
| Avg trade size | $50 | ? |
| Seals generated | 100 | ? |
| Bug reports | < 10 | ? |

**Key Questions**:
- Is the UX intuitive?
- Are bonding curve prices fair?
- Do users understand sealing?
- What's the share rate?
- Where do users drop off?

| Task | Owner | Deliverable |
|------|-------|-------------|
| Analyze metrics | Jesse | Analytics report |
| Prioritize fixes | Jesse | Bug/feature list |
| Implement top 5 fixes | Jesse | Updated code |
| A/B test onboarding | Jesse | Test results |
| Optimize bonding curve | Jesse | Parameter tuning |

### Week 15: Marketing Prep

**Objective**: Prepare for public launch

| Task | Owner | Deliverable |
|------|-------|-------------|
| Create launch announcement | Jesse | Blog post |
| Design social assets | Jesse | Graphics pack |
| Write Twitter thread | Jesse | 10-tweet thread |
| Prepare Telegram announcement | Jesse | Message draft |
| Reach out to influencers | Jesse | 10 DMs sent |
| Set up tracking | Jesse | Analytics ready |

**Launch Messaging**:
- "The first non-custodial prediction market on TON"
- "Prove your calls, build your reputation"
- "No house edge. No custody. Pure peer-to-peer."
- "Seal your predictions on blockchain"

### Week 16: Public Launch

**Objective**: Open to 50K Telegram users

| Day | Task |
|-----|------|
| Mon | Final testing, dry run |
| Tue | Deploy final contracts |
| Wed | **LAUNCH DAY** - Announcements go live |
| Thu | Monitor, fix urgent issues |
| Fri | First metrics review |
| Sat-Sun | Community engagement |

**Launch Day Checklist**:
- [ ] Contracts deployed and verified
- [ ] Mini App live on production URL
- [ ] Announcement posted to X/Twitter
- [ ] Announcement posted to Telegram
- [ ] MemeSeal users notified
- [ ] Monitoring dashboards active
- [ ] Support channel staffed
- [ ] US geo-blocking active

**Success Criteria (Week 16)**:
- 500+ unique users
- $50K+ trading volume
- 100+ sealed predictions
- < 5 critical bugs
- Positive community sentiment

---

## Phase 4: Scale (Weeks 17+)

### Goal
Become the dominant prediction protocol on TON.

### Month 2 Focus: Growth Features

| Task | Target |
|------|--------|
| Add liquidity incentives | 10% of LP earnings |
| Launch public leaderboards | Top 100 predictors |
| Social sharing improvements | One-click share |
| First signal group partnership | 1 integration |
| Add 3 new market categories | Sports, politics, events |

### Month 3 Focus: User-Created Markets

| Task | Target |
|------|--------|
| Enable verified user market creation | Rep > 70 |
| Build market approval queue | Moderation system |
| Add market creator rewards | 10% of fees |
| Launch market creation tutorial | Video + docs |
| Target: 50 user-created markets | Quality reviewed |

### Month 6 Focus: Protocol Expansion

| Task | Target |
|------|--------|
| Squad leaderboards | Team competitions |
| Pooled tournaments | Prize pools |
| Signal channel integrations | 5+ partners |
| Sports markets (major leagues) | NBA, NFL, etc |
| Political markets | Elections |

### Year 1 Focus: Decentralization

| Task | Target |
|------|--------|
| Governance token design | Tokenomics |
| Token generation event | Launch |
| DAO formation | Governance structure |
| Protocol ownership transfer | Decentralized |
| Foundation establishment | Legal entity |

---

## Resource Requirements

### Technical Infrastructure

| Service | Monthly Cost | Purpose |
|---------|--------------|---------|
| Render Web Service | $25 | API backend |
| Render PostgreSQL | $50 | Database |
| Vercel Pro | $20 | Mini App hosting |
| TON Mainnet | ~$50 | Gas fees |
| Pyth Network | Free tier | Oracle data |
| **Total** | **~$145/mo** | |

### One-Time Costs

| Item | Cost | Purpose |
|------|------|---------|
| Smart contract audit | $5-15K | Security |
| Initial liquidity | 500 TON (~$2.5K) | Market seeding |
| Bug bounty fund | $2K | Security incentive |
| **Total** | **~$10-20K** | |

### Time Allocation

| Phase | Hours/Week | Focus |
|-------|-----------|-------|
| Phase 1 | 20-30 | Research & interviews |
| Phase 2 | 40-50 | Development |
| Phase 3 | 30-40 | Launch & marketing |
| Phase 4 | 20-30 | Growth & maintenance |

---

## Risk Checkpoints

### Go/No-Go at Week 4

**Continue if**:
- 70%+ of traders want prediction markets
- 50%+ of admins would integrate seals
- Clear path to sustainable economics

**Pivot if**:
- < 50% interest from target users
- Major regulatory concern identified
- Better opportunity discovered

### Launch Review at Week 12

**Continue if**:
- All contracts pass security review
- Beta testers report positive experience
- Key metrics tracking working

**Delay if**:
- Critical security issue found
- Major UX problems unfixed
- Oracle integration failing

### Scale Decision at Week 20

**Scale up if**:
- $100K+ monthly volume
- 1000+ active users
- Positive unit economics

**Pivot/pause if**:
- < $25K monthly volume
- User growth stalled
- Negative community sentiment

---

## What About MemeMart?

**Defer to Month 6+ minimum.**

MemeMart is a viable business but:
1. Linear scaling (more sales = more work)
2. Operational complexity (inventory, shipping, returns)
3. Lower ceiling ($500K/year vs $100M+/year)
4. Distracts from the higher-leverage opportunity

**Revisit when**:
- MemeMarket generating $10K+/month
- Revenue to hire operations help
- Proven audience to sell to
- Time/bandwidth available

---

## Success Metrics Summary

| Phase | Metric | Target |
|-------|--------|--------|
| Week 4 | Validated demand | 70% would use |
| Week 12 | Working MVP | 5 markets live |
| Week 16 | Public launch | 500 users, $50K volume |
| Month 3 | Growth | 2K users, $200K volume |
| Month 6 | Scale | 10K users, $500K volume |
| Year 1 | Dominance | 50K users, $3M volume |

---

## Next Document

Continue to [SEALBET.md](./SEALBET.md) for detailed protocol specification.

---

*"Focus on the $100M opportunity. The $500K opportunity can wait."*
