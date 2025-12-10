# MemeMarket: P2P Prediction Exchange

## What It Is

A non-custodial, peer-to-peer prediction market built on TON, accessible via Telegram Mini App. Users trade outcome tokens with each other - we never hold funds or take the other side of bets.

---

## How It Works

### The Core Mechanic

```
┌─────────────────────────────────────────────────────────────────┐
│                         MARKET EXAMPLE                          │
│                                                                 │
│  "Will BTC be above $120,000 on December 31, 2025?"            │
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │       YES           │    │        NO           │            │
│  │    Price: $0.65     │    │    Price: $0.35     │            │
│  │    (65% chance)     │    │    (35% chance)     │            │
│  └─────────────────────┘    └─────────────────────┘            │
│                                                                 │
│  If you buy YES at $0.65 and BTC IS above $120K:               │
│  • Your YES token is worth $1.00                               │
│  • Profit: $0.35 per token (54% return)                        │
│                                                                 │
│  If BTC is NOT above $120K:                                    │
│  • Your YES token is worth $0.00                               │
│  • Loss: $0.65 per token                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Key Principles

1. **Non-Custodial**: User funds stay in smart contract escrow, never our wallets
2. **P2P Matching**: Every YES buyer matches with a NO buyer
3. **Oracle Resolution**: Outcomes determined by verifiable data sources
4. **Transparent Fees**: 2% on winning positions only

---

## Market Types

### Phase 1: Crypto Markets (Easiest Oracles)

| Market Type | Example | Oracle Source |
|-------------|---------|---------------|
| **Price Targets** | "BTC above $150K by March?" | RedStone price feeds |
| **Meme Coin Races** | "Which pumps more: PEPE vs DOGE?" | DEX price feeds |
| **TVL Milestones** | "TON TVL hits $1B?" | DefiLlama API |
| **Token Launches** | "New token hits $10M mcap in 24h?" | On-chain data |

### Phase 2: Sports Markets (API Oracles)

| Market Type | Example | Oracle Source |
|-------------|---------|---------------|
| **Game Outcomes** | "Lakers beat Celtics?" | The Odds API |
| **Point Spreads** | "Chiefs -7.5?" | Sports data feeds |
| **Player Props** | "LeBron over 25 points?" | Stats APIs |
| **Tournament Winners** | "Super Bowl champion?" | Official results |

### Phase 3: Event Markets (Optimistic Oracles)

| Market Type | Example | Oracle Source |
|-------------|---------|---------------|
| **Crypto Events** | "ETH ETF approved by June?" | UMA-style oracle |
| **Tech/Business** | "Apple announces AI chip?" | Community consensus |
| **Meme Culture** | "Elon tweets DOGE this week?" | Verifiable tweets |

---

## Smart Contract Architecture

### Contract Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                      MEMEMARKET CONTRACTS                       │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│    ROUTER     │     │  MARKET       │     │   ORACLE      │
│   (Main)      │     │  FACTORY      │     │   ADAPTER     │
├───────────────┤     ├───────────────┤     ├───────────────┤
│ Entry point   │     │ Creates new   │     │ Connects to   │
│ for all calls │     │ markets       │     │ data sources  │
│ Fee config    │     │ Tracks all    │     │ Verifies      │
│ Admin funcs   │     │ active mkts   │     │ outcomes      │
└───────────────┘     └───────────────┘     └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │   MARKET          │
                    │   (Per Question)  │
                    ├───────────────────┤
                    │ Order book        │
                    │ YES/NO tokens     │
                    │ Escrow            │
                    │ Settlement        │
                    └───────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ POSITION │    │ POSITION │    │ POSITION │
        │ (User A) │    │ (User B) │    │ (User C) │
        └──────────┘    └──────────┘    └──────────┘
```

### Order Matching Logic

```
User A wants to BUY 100 YES @ $0.60
User B wants to BUY 100 NO @ $0.40

┌─────────────────────────────────────────────────────────────────┐
│  User A sends $60 to contract (wants YES)                      │
│  User B sends $40 to contract (wants NO)                       │
│                                                                 │
│  Contract creates:                                              │
│  • 100 YES tokens for User A                                   │
│  • 100 NO tokens for User B                                    │
│  • $100 total locked in escrow                                 │
│                                                                 │
│  Resolution:                                                    │
│  • If YES wins: User A gets $100 (minus 2% fee = $98)          │
│  • If NO wins: User B gets $100 (minus 2% fee = $98)           │
└─────────────────────────────────────────────────────────────────┘
```

### Tact Contract Skeleton

```tact
// market.tact - Single market contract

import "@stdlib/deploy";
import "@stdlib/ownable";

message CreateOrder {
    side: Bool;          // true = YES, false = NO
    amount: Int as coins;
    price: Int;          // 0-100 representing probability
}

message CancelOrder {
    orderId: Int;
}

message ResolveMarket {
    outcome: Bool;       // true = YES won, false = NO won
    oracleSignature: Slice;
}

contract Market with Deployable, Ownable {
    owner: Address;
    question: String;
    resolutionTime: Int;
    oracleAddress: Address;
    resolved: Bool;
    outcome: Bool;

    // Order book
    yesOrders: map<Int, Order>;
    noOrders: map<Int, Order>;

    // Positions
    positions: map<Address, Position>;

    // Escrow
    totalEscrowed: Int;

    init(owner: Address, question: String, resolutionTime: Int, oracle: Address) {
        self.owner = owner;
        self.question = question;
        self.resolutionTime = resolutionTime;
        self.oracleAddress = oracle;
        self.resolved = false;
        self.outcome = false;
        self.totalEscrowed = 0;
    }

    receive(msg: CreateOrder) {
        require(!self.resolved, "Market resolved");
        require(now() < self.resolutionTime, "Market closed");
        require(msg.price > 0 && msg.price < 100, "Invalid price");

        // Lock funds in contract
        let amount = context().value;
        require(amount >= msg.amount, "Insufficient funds");

        // Try to match with existing orders
        self.matchOrder(msg.side, msg.amount, msg.price, sender());
    }

    receive(msg: ResolveMarket) {
        require(sender() == self.oracleAddress, "Only oracle");
        require(now() >= self.resolutionTime, "Too early");
        require(!self.resolved, "Already resolved");

        // Verify oracle signature
        self.verifyOracleSignature(msg.oracleSignature);

        self.resolved = true;
        self.outcome = msg.outcome;

        // Winners can now claim
    }

    receive("claim") {
        require(self.resolved, "Not resolved");

        let position = self.positions.get(sender());
        require(position != null, "No position");

        let payout = self.calculatePayout(position!!, self.outcome);
        let fee = payout * 2 / 100;  // 2% fee
        let netPayout = payout - fee;

        // Send payout
        send(SendParameters{
            to: sender(),
            value: netPayout,
            mode: SendIgnoreErrors
        });

        // Clear position
        self.positions.set(sender(), null);
    }

    // Internal functions
    fun matchOrder(side: Bool, amount: Int, price: Int, trader: Address) {
        // Matching logic here
    }

    fun calculatePayout(position: Position, outcome: Bool): Int {
        // Payout calculation
    }

    fun verifyOracleSignature(sig: Slice) {
        // Oracle verification
    }
}
```

---

## Oracle Integration

### RedStone for Crypto Prices

RedStone is already integrated with TON. We use their push model:

```
┌─────────────────────────────────────────────────────────────────┐
│                    REDSTONE ORACLE FLOW                         │
│                                                                 │
│  1. User submits order with price data attached                │
│  2. Contract verifies RedStone signature on-chain              │
│  3. If valid, price is used for settlement                     │
│                                                                 │
│  Benefits:                                                      │
│  • No need to constantly update prices on-chain                │
│  • User pays gas for oracle data                               │
│  • Data integrity verified cryptographically                   │
└─────────────────────────────────────────────────────────────────┘
```

**Supported Assets**: BTC, ETH, TON, USDT, and 1000+ other assets

**Documentation**: https://docs.ton.org/ecosystem/oracles/redstone

### Sports Oracles (Custom)

For sports, we build a simple oracle service:

```
┌─────────────────────────────────────────────────────────────────┐
│                    SPORTS ORACLE FLOW                           │
│                                                                 │
│  1. Our backend fetches results from The Odds API              │
│  2. Results signed with our oracle key                         │
│  3. Anyone can submit signed result to contract                │
│  4. Contract verifies signature, settles market                │
│                                                                 │
│  Trust Model:                                                   │
│  • API data is verifiable (multiple sources)                   │
│  • Signature proves we attested to result                      │
│  • Disputes can be raised (staking mechanism)                  │
└─────────────────────────────────────────────────────────────────┘
```

### Dispute Resolution

For contested outcomes:

```
┌─────────────────────────────────────────────────────────────────┐
│                    DISPUTE FLOW                                 │
│                                                                 │
│  1. Oracle submits result                                      │
│  2. 24-hour challenge period                                   │
│  3. Anyone can dispute by staking 100 TON                      │
│  4. If disputed:                                               │
│     - Community vote (token holders)                           │
│     - Loser forfeits stake                                     │
│     - Winner gets stake + original bet                         │
│                                                                 │
│  Prevents: Oracle manipulation, obvious errors                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Revenue Model

### Fee Structure

| Fee Type | Amount | When Charged |
|----------|--------|--------------|
| **Trading Fee** | 2% | On winning positions only |
| **Market Creation** | 1 TON | When creating new market |
| **Early Exit** | 1% | If selling position before resolution |

### Revenue Projections

| Scenario | Monthly Volume | 2% Fee | Monthly Revenue |
|----------|----------------|--------|-----------------|
| **Conservative** | $100K | $2K | $2,000 |
| **Moderate** | $1M | $20K | $20,000 |
| **Optimistic** | $10M | $200K | $200,000 |

### Fee Distribution

```
Total Fees Collected
        │
        ├── 50% → Treasury (operations, development)
        │
        ├── 30% → Lottery Pool (weekly jackpot)
        │
        └── 20% → Referral Commissions
```

---

## User Experience

### Creating a Position

```
┌─────────────────────────────────────────────────────────────────┐
│  MEMEMARKET                                        [Wallet: ◉]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🔥 TRENDING MARKET                                             │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Will BTC hit $150,000 by March 31, 2025?               │   │
│  │                                                          │   │
│  │  [=============================>           ] 73% YES     │   │
│  │                                                          │   │
│  │  Volume: $45,230    Ends: 112 days                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │   BUY YES       │    │    BUY NO       │                    │
│  │   @ $0.73       │    │    @ $0.27      │                    │
│  │                 │    │                 │                    │
│  │  Max win: 37%   │    │  Max win: 270%  │                    │
│  └─────────────────┘    └─────────────────┘                    │
│                                                                 │
│  Amount: [___________] TON                                     │
│                                                                 │
│  [ PLACE ORDER ]                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Order Flow

1. User connects TON wallet (TON Connect)
2. Selects market and side (YES/NO)
3. Enters amount
4. Confirms transaction in wallet
5. Funds locked in smart contract
6. Position appears in portfolio
7. At resolution, winner can claim

---

## Technical Implementation

### Frontend (Next.js Mini App)

```typescript
// Key components needed

// 1. Market List
const MarketList = () => {
  // Fetch active markets from indexer
  // Display trending, new, closing soon
}

// 2. Market Detail
const MarketDetail = ({ marketId }) => {
  // Order book visualization
  // Price chart
  // Buy YES/NO buttons
}

// 3. Portfolio
const Portfolio = () => {
  // User's open positions
  // P&L tracking
  // Claim winnings
}

// 4. TON Connect integration
const WalletConnect = () => {
  // Connect wallet
  // Sign transactions
}
```

### Backend Services

```
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND SERVICES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. INDEXER                                                     │
│     - Watches blockchain for market events                     │
│     - Builds queryable database of markets/positions           │
│     - Calculates real-time prices                              │
│                                                                 │
│  2. ORACLE SERVICE                                              │
│     - Fetches external data (sports, prices)                   │
│     - Signs resolution messages                                │
│     - Submits to contracts                                      │
│                                                                 │
│  3. API                                                         │
│     - Market data endpoints                                     │
│     - User position endpoints                                   │
│     - WebSocket for real-time updates                          │
│                                                                 │
│  4. NOTIFICATION BOT                                            │
│     - Position updates                                          │
│     - Market resolution alerts                                  │
│     - Price movement notifications                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Data Sources

| Data Type | Source | Cost |
|-----------|--------|------|
| **Crypto Prices** | RedStone Oracle | Free (on-chain) |
| **Sports Odds/Results** | The Odds API | Free tier: 500 req/month |
| **Historical Prices** | CoinGecko API | Free tier available |
| **On-chain Data** | TON RPC | Self-hosted or provider |

---

## Security Considerations

### Smart Contract Security

1. **Auditing**: Professional audit before mainnet (CertiK, Trail of Bits)
2. **Bug Bounty**: 10% of treasury for valid bugs
3. **Gradual Rollout**: Testnet → Limited mainnet → Full launch
4. **Upgradability**: Router upgradeable with timelock, markets immutable

### Oracle Security

1. **Multiple Sources**: Cross-check data from multiple APIs
2. **Signature Verification**: All oracle data cryptographically signed
3. **Challenge Period**: 24h window to dispute outcomes
4. **Stake Requirements**: Disputes require skin in the game

### User Security

1. **Non-Custodial**: Users always control funds
2. **Transparent Contracts**: All code open source
3. **Clear Risks**: Prominent disclaimers about gambling risks

---

## Go-to-Market

### Launch Strategy

**Week 1-2: Testnet**
- Deploy contracts to TON testnet
- Internal testing with test tokens
- Fix bugs, optimize gas

**Week 3-4: Closed Beta**
- Invite 100 users from community
- Real markets, small limits ($100 max)
- Gather feedback, iterate

**Month 2: Public Beta**
- Open to all, higher limits
- Marketing push in Telegram crypto channels
- Referral program launch

**Month 3+: Full Launch**
- Remove limits
- Add sports markets
- Mobile optimization

### Marketing Channels

| Channel | Strategy |
|---------|----------|
| **Telegram** | Crypto trading groups, TON community |
| **Twitter/X** | Crypto Twitter, prediction market discussions |
| **MemeSeal Users** | Cross-promote to existing user base |
| **Influencers** | Partner with crypto YouTubers/streamers |
| **Referrals** | 5% commission on referred volume |

---

## Competitive Advantages

| vs Polymarket | vs Telegram Casinos | vs Traditional Bookies |
|---------------|---------------------|------------------------|
| Telegram-native (not web) | Non-custodial (we don't hold funds) | P2P (better odds, 2% vs 10%) |
| TON (faster, cheaper) | Not the house (users trade with each other) | Crypto-native payments |
| Meme coin markets | Provably fair | No KYC required |
| Community-focused | Transparent on-chain | Global access |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Smart contract exploit | Medium | High | Audits, bug bounty, gradual rollout |
| Oracle manipulation | Low | High | Multiple sources, dispute mechanism |
| Regulatory action | Medium | High | Non-custodial structure, geo-blocking |
| Low liquidity | High | Medium | Market making incentives, referrals |
| Competition | Medium | Medium | Move fast, community moat |

---

## Next Steps

1. **Read**: [TECH-STACK.md](./TECH-STACK.md) for implementation details
2. **Read**: [LEGAL.md](./LEGAL.md) for regulatory structure
3. **Read**: [ROADMAP.md](./ROADMAP.md) for timeline

---

## Resources

### TON Development
- [TON Docs - Smart Contracts](https://docs.ton.org/v3/documentation/smart-contracts/overview)
- [Tact Language](https://tact-lang.org/)
- [STON.fi Contracts (Reference)](https://github.com/ston-fi/dex-core)

### Oracles
- [RedStone on TON](https://docs.ton.org/ecosystem/oracles/redstone)
- [RedStone TON Contracts](https://github.com/redstone-finance/redstone-oracles-monorepo/tree/main/packages/ton-connector/contracts)

### Prediction Markets
- [Polymarket Docs](https://docs.polymarket.com/)
- [UMA Optimistic Oracle](https://docs.uma.xyz/)

### Sports Data
- [The Odds API](https://the-odds-api.com/)
- [Sports Game Odds](https://sportsgameodds.com/)
