# MemeSeal Labs: Legal Structure & Compliance

> **Legal framework for MemeMarket (P2P prediction exchange) and MemeMart (hardware store)**

---

## Executive Summary

MemeMarket is structured as a **non-custodial, peer-to-peer exchange for event contracts**—not a gambling platform. MemeMart is a hardware store selling security tools. This document outlines the legal framework, regulatory landscape, and compliance strategy for both.

**Key Principles**:
1. We don't custody user funds (smart contracts do)
2. We don't set odds (market makers do)
3. We don't take sides on bets (neutral exchange)
4. We frame everything as "prediction markets" and "event contracts"
5. We geo-block US users initially (risk mitigation)

---

## The Legal Distinction: Event Contracts vs. Gambling

### Gambling (What We're NOT)

| Characteristic | Why It's Gambling |
|---------------|-------------------|
| Bet against the house | House has adverse interest |
| House sets odds | House controls risk |
| House profits from losses | Misaligned incentives |
| Entertainment purpose | Not information discovery |
| Luck-based outcomes | No skill component |

### Event Contracts (What We ARE)

| Characteristic | Why It's Event Contracts |
|---------------|--------------------------|
| Peer-to-peer trading | Users trade with each other |
| Market sets odds | Supply/demand pricing |
| Exchange earns fees | Neutral intermediary |
| Price discovery purpose | Information aggregation |
| Skill-based outcomes | Research, analysis, judgment |

---

## Regulatory Precedents

### Kalshi v. CFTC (2024-2025)

**The Case**:
- Kalshi sought to list election contracts
- CFTC denied, citing "gaming" concerns
- Kalshi sued, arguing federal preemption

**The Outcome**:
- Federal court ruled for Kalshi
- CFTC dropped appeal (May 2025)
- Election contracts now legal on registered exchanges

**Key Holding**:
> "Prediction markets are not gambling because they serve a price-discovery and information-aggregation function, distinguishing them from games of chance."

**Relevance to MemeMarket**:
- Courts recognize event contracts as derivatives
- CFTC jurisdiction preempts state gambling laws
- Non-custodial protocols may not even need registration

### Polymarket Settlement (2022)

**The Issue**:
- Polymarket operated without CFTC registration
- Offered unregulated derivatives to US persons

**The Resolution**:
- $1.4M civil penalty
- Agreed to wind down US operations
- Restructured as non-US entity
- Now operates with US geo-blocking

**Lesson for MemeMarket**:
- Geo-block US users from day one
- Don't offer derivatives to US persons
- Consider offshore legal entity

### Augur's Decentralization Strategy

**The Approach**:
- Augur is a fully decentralized protocol
- Forecast Foundation (developer) has zero control over:
  - Market creation
  - Market resolution
  - Fund custody
  - Trade execution

**Legal Position**:
> "If the developers have no control, they bear no responsibility. Users are responsible for compliance in their jurisdiction."

**Relevance to MemeMarket**:
- Non-custodial design shifts responsibility to users
- Protocol is infrastructure, not operator
- Decentralization is a legal shield

---

## Jurisdiction Analysis

### United States

**Risk Level: HIGH**

| Regulator | Concern | Mitigation |
|-----------|---------|------------|
| CFTC | Unregistered derivatives | Geo-block US users |
| SEC | Securities violations | Not offering tokens |
| FinCEN | Money transmission | Non-custodial |
| State AGs | State gambling laws | Geo-blocking |

**Strategy**: Complete US geo-blocking via IP + wallet screening

### European Union

**Risk Level: MEDIUM**

| Regulation | Concern | Mitigation |
|------------|---------|------------|
| MiCA | Crypto-asset regulation | Not issuing tokens |
| Gambling Directives | Country-specific | Non-custodial, P2P |
| GDPR | Data privacy | Standard compliance |

**Strategy**: Monitor MiCA implementation; most EU countries don't classify P2P prediction as gambling

### United Kingdom

**Risk Level: MEDIUM**

| Regulator | Concern | Mitigation |
|-----------|---------|------------|
| FCA | Financial promotions | Limited marketing |
| Gambling Commission | Gambling license | P2P exchange exemption |

**Strategy**: UK has precedent for prediction markets (Betfair exchange model)

### Asia (Singapore, Hong Kong)

**Risk Level: LOW-MEDIUM**

| Jurisdiction | Status |
|-------------|--------|
| Singapore | Generally permissive for crypto |
| Hong Kong | Licensed crypto trading allowed |
| Japan | Strict, may need to geo-block |

**Strategy**: Singapore-friendly structure; geo-block restrictive jurisdictions

### Telegram/TON Ecosystem

**Risk Level: LOW**

TON Foundation has explicitly positioned the ecosystem as global, decentralized, and censorship-resistant. Operating within Telegram Mini Apps provides:
- No specific jurisdiction
- Decentralized infrastructure
- Global user base
- Existing regulatory buffer

---

## Legal Entity Structure

### Recommended Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    SEALBET FOUNDATION                        │
│                   (Cayman Islands/BVI)                       │
│                                                              │
│  Purpose: Protocol development, treasury, governance         │
│  No: Custody, trading, market making                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          │                               │
          ▼                               ▼
┌─────────────────────┐       ┌─────────────────────┐
│   DEVELOPMENT CO    │       │    OPERATIONS CO    │
│   (Delaware LLC)    │       │   (Singapore PTE)   │
│                     │       │                     │
│ • Software dev      │       │ • Marketing         │
│ • Open source code  │       │ • Community         │
│ • Protocol research │       │ • Partnerships      │
└─────────────────────┘       └─────────────────────┘
```

### Why This Structure?

1. **Foundation (Cayman/BVI)**
   - Tax neutral
   - Flexible governance
   - No substance requirements
   - Protocol ownership

2. **Development Co (Delaware)**
   - US developer access
   - Clear employment law
   - Limited to software development
   - No user interaction

3. **Operations Co (Singapore)**
   - Crypto-friendly jurisdiction
   - Access to Asian markets
   - Clear regulatory framework
   - Marketing and BD

### Alternative: No Legal Entity

For maximum decentralization, operate as:
- Anonymous team
- Open-source protocol
- No official entity
- Community governance

**Pros**: Maximum legal protection (no entity to sue)
**Cons**: Harder to raise funds, hire, partner

---

## Compliance Implementation

### 1. Geo-Blocking (US)

**Technical Implementation**:

```typescript
// middleware/geo-block.ts

const BLOCKED_COUNTRIES = ['US', 'USA', 'United States'];

export async function geoBlockMiddleware(req: Request) {
  // 1. IP-based detection
  const ip = req.headers.get('x-forwarded-for') || req.ip;
  const geo = await getGeoFromIP(ip);

  if (BLOCKED_COUNTRIES.includes(geo.country)) {
    return new Response('Service not available in your region', {
      status: 451, // Unavailable For Legal Reasons
    });
  }

  // 2. Wallet screening (optional, for high-risk wallets)
  const walletAddress = req.headers.get('x-wallet-address');
  if (walletAddress) {
    const isUSWallet = await checkWalletJurisdiction(walletAddress);
    if (isUSWallet) {
      return new Response('Service not available', { status: 451 });
    }
  }

  return null; // Allow request
}
```

**User Agreement**:

```
By using MemeMarket, you represent and warrant that:

1. You are not a resident of, located in, or accessing this
   service from the United States of America.

2. You are not a US Person as defined under Regulation S of
   the US Securities Act.

3. You are of legal age in your jurisdiction to enter into
   binding agreements.

4. You understand that prediction markets involve risk and
   you may lose your entire investment.
```

### 2. Terms of Service

**Key Provisions**:

1. **Service Description**
   > MemeMarket operates a non-custodial, peer-to-peer exchange for
   > event contracts on the TON blockchain. MemeMarket does not
   > custody user funds, set market odds, or take positions in
   > any market.

2. **User Responsibility**
   > Users are solely responsible for ensuring their use of
   > MemeMarket complies with applicable laws in their jurisdiction.

3. **No Gambling**
   > MemeMarket is not a gambling platform. Event contracts are
   > financial instruments that allow users to express views on
   > future outcomes through peer-to-peer trading.

4. **Risk Disclosure**
   > Trading event contracts involves substantial risk. Users
   > may lose their entire investment. Past performance does
   > not guarantee future results.

5. **Dispute Resolution**
   > All disputes shall be resolved through binding arbitration
   > in Singapore under ICC rules.

### 3. Marketing Guidelines

**DO**:
- "Prediction markets"
- "Event contracts"
- "Price discovery"
- "Information markets"
- "Forecast exchange"
- "Research and analysis"

**DON'T**:
- "Betting"
- "Gambling"
- "Wagering"
- "Casino"
- "House edge"
- "Odds" (use "prices" instead)

**Example Compliant Copy**:

> **Before**: "Bet on whether Bitcoin will hit $100K!"
>
> **After**: "Trade event contracts on Bitcoin price milestones.
> Express your market view through peer-to-peer trading."

### 4. KYC/AML (Optional)

For MVP, no KYC required (non-custodial, P2P).

If implementing KYC later:
- Use third-party provider (Jumio, Onfido)
- Tiered approach (higher limits = more verification)
- Sanctions screening (OFAC, EU lists)

---

## Risk Assessment

### Legal Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| US enforcement | Medium | High | Geo-blocking |
| Classified as gambling | Low | High | Event contract framing |
| License requirement | Low | Medium | Non-custodial design |
| User lawsuits | Low | Low | ToS, risk disclosure |

### Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Oracle failure | Medium | High | Multi-source, disputes |
| Smart contract bug | Low | Critical | Audits, insurance |
| Market manipulation | Medium | Medium | Monitoring, limits |

### Reputational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Associated with gambling | Medium | Medium | Clear messaging |
| Scam accusations | Low | High | Transparency |
| Regulatory attention | Medium | Medium | Proactive compliance |

---

## Regulatory Monitoring

### Sources to Track

1. **CFTC**
   - Enforcement actions
   - Rule proposals
   - No-action letters

2. **International**
   - MiCA implementation (EU)
   - MAS guidance (Singapore)
   - FSRA updates (ADGM)

3. **Industry**
   - Blockchain Association updates
   - DeFi Legal Defense Fund
   - Prediction Market Council (if formed)

### Response Plan

If regulatory contact occurs:

1. **Initial Contact**
   - Document all communications
   - Do not make admissions
   - Engage legal counsel immediately

2. **Information Request**
   - Respond within deadlines
   - Provide only requested information
   - Protect user data appropriately

3. **Enforcement Threat**
   - Assess jurisdiction and authority
   - Consider geographic restrictions
   - Evaluate compliance options

4. **Settlement Negotiation**
   - Professional legal representation
   - Preserve optionality
   - Protect user funds

---

## Legal Checklist

### Before Launch

- [ ] Terms of Service drafted and reviewed
- [ ] Privacy Policy drafted
- [ ] Risk disclosures implemented
- [ ] Geo-blocking technical implementation
- [ ] User agreement on sign-up
- [ ] Marketing guidelines documented
- [ ] Legal entity structure decided
- [ ] Regulatory counsel engaged

### At Launch

- [ ] Geo-blocking active and tested
- [ ] ToS acceptance required
- [ ] Risk disclosures displayed
- [ ] "Event contracts" language used
- [ ] No US marketing channels

### Ongoing

- [ ] Monitor regulatory developments
- [ ] Update ToS as needed
- [ ] Review geo-blocking effectiveness
- [ ] Document compliance efforts
- [ ] Annual legal review

---

## Legal Resources

### Law Firms Experienced in Prediction Markets

1. **Anderson Kill** (US) - Represented Kalshi
2. **Latham & Watkins** (Global) - Polymarket advisors
3. **Debevoise & Plimpton** (US) - CFTC expertise
4. **Dentons** (Global) - Blockchain regulatory

### Industry Groups

1. **Blockchain Association** - Policy advocacy
2. **DeFi Education Fund** - Legal defense
3. **Coin Center** - Research and policy

### Key Documents to Reference

1. Kalshi v. CFTC opinions
2. CFTC event contract guidance
3. Polymarket settlement agreement
4. Augur legal analysis memos
5. MiCA regulation text

---

## Summary

MemeMarket's legal strategy rests on three pillars:

1. **Structure**: Non-custodial, P2P, neutral exchange
2. **Framing**: Event contracts, price discovery, information markets
3. **Compliance**: Geo-blocking, clear ToS, risk disclosures

This positions MemeMarket as infrastructure—not an operator—following the path blazed by Polymarket, Kalshi, and Augur.

---

## Disclaimer

*This document is for informational purposes only and does not constitute legal advice. MemeMarket should engage qualified legal counsel in all relevant jurisdictions before launching.*

---

## Next Document

Continue to [CONTRACTS.md](./CONTRACTS.md) for smart contract specifications.

---

*"Structure determines strategy. Strategy determines survival."*
