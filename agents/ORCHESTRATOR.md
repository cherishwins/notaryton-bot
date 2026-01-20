# Agent Orchestrator — Team Configurations

> Chain multiple agents together for complex tasks. Each agent contributes their domain expertise.

---

## How Orchestration Works

```
USER REQUEST
     ↓
┌─────────────────────────────┐
│    ORCHESTRATOR SELECTS     │
│    RELEVANT AGENTS          │
└─────────────────────────────┘
     ↓
┌─────────────┬─────────────┬─────────────┐
│   Agent 1   │   Agent 2   │   Agent 3   │
│   (Domain)  │   (Domain)  │   (Domain)  │
└─────────────┴─────────────┴─────────────┘
     ↓              ↓              ↓
┌─────────────────────────────────────────┐
│         SYNTHESIZE & EXECUTE            │
│    (Resolve conflicts, prioritize)      │
└─────────────────────────────────────────┘
     ↓
    OUTPUT
```

---

## Pre-Configured Teams

### 🚀 REVENUE_SPRINT
**Goal:** Ship monetization features fast

**Agents:**
1. **Patrick Collison (Payment)** — Lead on checkout flow
2. **Paul Graham (Backend)** — Keep it simple
3. **Guillermo Rauch (Frontend)** — Make it fast

**Conflict Resolution:**
- Payment > Performance > Features
- If Patrick and Paul disagree, Patrick wins (money matters)
- If Guillermo and Paul disagree, Paul wins (ship first)

**Use For:**
- Casino chips implementation
- Subscription flows
- Withdrawal features

---

### 📈 GROWTH_LOOP
**Goal:** Build viral mechanics and retention

**Agents:**
1. **Nikita Bier (Growth)** — Lead on mechanics
2. **Ansem (Culture)** — Lead on messaging
3. **Guillermo Rauch (Frontend)** — Make it shareable

**Conflict Resolution:**
- Virality > Polish > Features
- If Nikita and Ansem disagree, Nikita wins (data > vibes)
- If Nikita and Guillermo disagree, Nikita wins (growth > perf)

**Use For:**
- Lottery announcements
- Referral systems
- Social sharing
- Winner celebrations

---

### ⛓️ PROTOCOL_LAUNCH
**Goal:** Deploy smart contracts safely and efficiently

**Agents:**
1. **Anatoly Yakovenko (Protocol)** — Lead on contract design
2. **Paul Graham (Backend)** — Integration simplicity
3. **Patrick Collison (Payment)** — Transaction flows

**Conflict Resolution:**
- Security > Performance > Simplicity
- If Anatoly and Paul disagree, Anatoly wins (contracts are forever)
- If Anatoly and Patrick disagree, Anatoly wins (can't fix deployed contracts)

**Use For:**
- SealBet market contracts
- Casino payout contracts
- Escrow systems

---

### 🎨 BRAND_VOICE
**Goal:** Create consistent degen-authentic messaging

**Agents:**
1. **Ansem (Culture)** — Lead on tone and language
2. **Nikita Bier (Growth)** — Ensure shareability
3. **Patrick Collison (Payment)** — Keep trust signals

**Conflict Resolution:**
- Authenticity > Virality > Trust
- If Ansem and Nikita disagree, Ansem wins (culture > hacks)
- If Ansem and Patrick disagree, balance both (can't lose trust OR vibes)

**Use For:**
- Bot messages
- Announcements
- Error messages
- Marketing copy

---

### 🏗️ FULL_STACK_FEATURE
**Goal:** Build complete features end-to-end

**Agents:**
1. **Paul Graham (Backend)** — Architecture decisions
2. **Guillermo Rauch (Frontend)** — UI implementation
3. **Patrick Collison (Payment)** — If involves money
4. **Nikita Bier (Growth)** — If needs viral component
5. **Ansem (Culture)** — If user-facing copy

**Conflict Resolution:**
- By layer: Backend → API → Frontend → Copy
- Upstream decisions constrain downstream

**Use For:**
- Major new features
- Complete user flows
- Product redesigns

---

## Orchestration Syntax

### Single Agent
```
READ agents/skills/PAYMENT_ARCHITECT.md
APPLY Patrick Collison's philosophy to: [task description]
```

### Multi-Agent (Sequential)
```
TEAM: REVENUE_SPRINT

STEP 1 (Patrick - Payment):
Design the checkout flow for casino chips

STEP 2 (Paul - Backend):
Implement the simplest backend that supports this flow

STEP 3 (Guillermo - Frontend):
Build the UI with loading states and instant feedback
```

### Multi-Agent (Parallel)
```
TEAM: GROWTH_LOOP

PARALLEL:
- Nikita: Design the viral sharing mechanic
- Ansem: Write the announcement copy
- Guillermo: Prototype the share card UI

SYNTHESIZE:
Combine outputs, resolve any conflicts per team rules
```

---

## Conflict Resolution Matrix

When agents disagree, use this hierarchy:

| Domain | Highest Authority | Reasoning |
|--------|-------------------|-----------|
| Security | Anatoly | Can't undo deployed contracts |
| Payment | Patrick | Money flow is critical path |
| Virality | Nikita | Data-driven > opinion |
| Culture | Ansem | Authenticity can't be faked |
| Performance | Guillermo | Users feel latency |
| Simplicity | Paul | Ship > perfect |

### Decision Framework
```
1. Is this a security decision? → Anatoly wins
2. Does this affect revenue? → Patrick wins
3. Is this user-facing copy? → Ansem wins
4. Is this about growth mechanics? → Nikita wins
5. Is this about UI/UX? → Guillermo wins
6. Is this about architecture? → Paul wins
```

---

## Example: Casino Chips Feature

### Orchestration Plan
```
TEAM: REVENUE_SPRINT
FEATURE: Buy chips with Telegram Stars

PHASE 1: Design (Patrick leads)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Patrick's requirements:
- One-tap purchase from game screen
- Clear price display before action
- Instant feedback on payment
- Graceful failure handling
- Multiple price tiers with anchoring

PHASE 2: Backend (Paul leads)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Paul's requirements:
- Single endpoint: POST /api/v1/casino/buy-chips
- Direct database update (no abstraction layers)
- Webhook handler for payment confirmation
- Return invoice URL, nothing fancy

PHASE 3: Frontend (Guillermo leads)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Guillermo's requirements:
- Skeleton loader while invoice generates
- Optimistic balance update on success
- Error boundary for payment failures
- Under 100ms to show purchase options

PHASE 4: Copy (Ansem consulted)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ansem's requirements:
- "Buy Chips" not "Purchase Credits"
- Show "50 ⭐ → 50 Chips" not "$2.50"
- Success: "LET'S GO 🐸 Chips loaded!"
- Failure: "Rekt by the payment gods. Try again."
```

---

## Quick Reference Commands

### Revenue Features
```
Invoke REVENUE_SPRINT team.
Patrick leads. Paul simplifies. Guillermo polishes.
Task: [describe feature]
```

### Growth Features
```
Invoke GROWTH_LOOP team.
Nikita leads. Ansem vibes. Guillermo ships.
Task: [describe feature]
```

### Smart Contracts
```
Invoke PROTOCOL_LAUNCH team.
Anatoly leads. Paul integrates. Patrick flows.
Task: [describe contract]
```

### Copy/Messaging
```
Invoke BRAND_VOICE team.
Ansem leads. Nikita shares. Patrick trusts.
Task: [describe message]
```

---

## Adding New Teams

1. **Define Goal** — What does this team ship?
2. **Select Agents** — Who has relevant expertise?
3. **Assign Lead** — Who makes final calls?
4. **Document Conflicts** — How to resolve disagreements?
5. **Add to this file** — Keep teams documented

---

## Metrics Per Team

### REVENUE_SPRINT
- Checkout completion rate
- Time to first purchase
- Payment failure rate

### GROWTH_LOOP
- Viral coefficient
- Share rate
- D1/D7/D30 retention

### PROTOCOL_LAUNCH
- Gas costs
- Transaction success rate
- Settlement time

### BRAND_VOICE
- Engagement rate
- Sentiment score
- Meme spread

---

*"A team of specialists beats a generalist every time—if they're orchestrated correctly."*
