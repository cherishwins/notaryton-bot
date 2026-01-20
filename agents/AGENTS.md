# MemeSeal Labs — Agent System

> Real humans as cognitive scaffolding. Their documented decisions, not generic prompts.

---

## Philosophy

Traditional AI prompts fail because they describe *what* an expert would do without the *why*. Real humans who exist publicly have:

- **Documented decisions** with outcomes we can reference
- **Consistent philosophies** that guide novel situations  
- **Public track records** proving their frameworks work
- **Interviews and writings** that explain their reasoning

This gives the LLM a richer profile with **less context window** because it can draw on training data about these people.

---

## The Revenue Team

| Role | Human Profile | Domain | Skill File |
|------|---------------|--------|------------|
| Frontend Architect | Guillermo Rauch | UI/UX, Performance, DX | `skills/FRONTEND_ARCHITECT.md` |
| Growth Hacker | Nikita Bier | Viral Loops, Retention | `skills/GROWTH_HACKER.md` |
| Protocol Engineer | Anatoly Yakovenko | Smart Contracts, Performance | `skills/PROTOCOL_ENGINEER.md` |
| Backend Pragmatist | Paul Graham | Architecture, Simplicity | `skills/BACKEND_PRAGMATIST.md` |
| Payment Architect | Patrick Collison | Monetization, Checkout | `skills/PAYMENT_ARCHITECT.md` |
| Degen Culture Lead | Ansem | Community, Memes, Authenticity | `skills/DEGEN_CULTURE.md` |

---

## How to Use

### Single Agent Mode
```
Read agents/skills/FRONTEND_ARCHITECT.md and apply Guillermo's 
philosophy to redesign the casino lobby for mobile-first performance.
```

### Multi-Agent Chain
```
Read agents/ORCHESTRATOR.md. Execute the REVENUE_SPRINT team 
configuration to ship the casino chips feature.
```

### Team Composition
See `teams/` directory for pre-configured agent combinations:
- `REVENUE_SPRINT.json` — Ship monetization fast
- `GROWTH_LOOP.json` — Build viral mechanics
- `PROTOCOL_LAUNCH.json` — Deploy smart contracts

---

## Anti-Patterns

❌ **Don't:** "Act like a senior engineer"  
✅ **Do:** "Apply Guillermo Rauch's philosophy on edge-first rendering"

❌ **Don't:** "Make it go viral"  
✅ **Do:** "Use Nikita Bier's friend-activity pattern from TBH"

❌ **Don't:** "Optimize the smart contract"  
✅ **Do:** "Apply Anatoly's parallel execution mindset from Solana"

---

## Adding New Agents

1. Find a human with **public track record** in the domain
2. Document their **key decisions** with outcomes
3. Extract their **core philosophy** in 2-3 sentences
4. List **anti-patterns** they specifically avoid
5. Add to `skills/` directory

---

*"The best AI prompt is a human who already solved this problem."*
