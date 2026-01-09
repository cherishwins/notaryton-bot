# Codebase Audit Report - January 2026

> Full audit of notaryton-bot codebase, infrastructure, and documentation.

---

## Executive Summary

**Overall Health:** GOOD with critical security fix needed

| Area | Status | Priority Issues |
|------|--------|-----------------|
| **Security** | CRITICAL | Hardcoded API keys in config.py |
| **Code Quality** | GOOD | bot.py is monolithic (4,700+ lines) |
| **Database** | GOOD | Race conditions in withdrawals |
| **Testing** | NEEDS WORK | SQLite tests vs PostgreSQL production |
| **Documentation** | EXCELLENT | Comprehensive docs structure |
| **Infrastructure** | GOOD | All repos properly configured |

---

## CRITICAL ISSUES (Fix Immediately)

### 1. Hardcoded API Keys in config.py

**Location:** config.py lines 85-86

```python
# CURRENT (BAD)
TONAPI_CASINO_KEY = os.getenv("TONAPI_CASINO_KEY", "AGVIA46VSFGJTSQAAAAA4AD4B3BPP6HY77QUOGTUFUTRNCUR35XJLMDOXBTDTC4VBE7QBNY")
TONAPI_TOKENS_KEY = os.getenv("TONAPI_TOKENS_KEY", "AGVIA46VNGVZOYYAAAAB7HTFXTMRIDNKFV3UAKX4M2AVQ7JZIDFPR5ISHSZKMEWNAVCHVNI")
```

**Impact:** API keys exposed in git history. Anyone with repo access can use these keys.

**Fix:** Remove hardcoded fallbacks:
```python
TONAPI_CASINO_KEY = os.getenv("TONAPI_CASINO_KEY", "")
TONAPI_TOKENS_KEY = os.getenv("TONAPI_TOKENS_KEY", "")
```

**Action Required:** Rotate these API keys at tonconsole.com after fixing code.

---

### 2. Race Condition in Withdrawal System

**Location:** database.py lines 329-361

**Issue:** Withdrawal operations lack transaction isolation. Concurrent requests could withdraw more than available balance.

**Fix:** Use atomic UPDATE with WHERE clause:
```sql
UPDATE users
SET total_withdrawn = total_withdrawn + $2
WHERE user_id = $1
  AND (referral_earnings - total_withdrawn) >= $2
RETURNING total_withdrawn;
```

---

### 3. Race Conditions in In-Memory Dictionaries

**Location:** bot.py lines 177-178, 191

```python
pending_files = {}  # Not thread-safe
pending_ton_payments = {}  # Not thread-safe
payment_memo_lookup = {}  # Not thread-safe
```

**Impact:** Multiple webhook handlers can run concurrently in FastAPI, causing data corruption.

**Fix:** Use `asyncio.Lock()` or move to database/Redis storage.

---

## HIGH PRIORITY ISSUES

### 4. Lottery pick_winner() Missing Transaction Wrapper

**Location:** database.py lines 583-609

The lottery draw performs 3 separate operations without a transaction. If process crashes mid-draw, you could have orphaned data.

**Fix:** Wrap in explicit transaction:
```python
async with conn.transaction():
    # all lottery operations
```

---

### 5. bot.py is Monolithic (4,776 lines)

**Recommendation:** Extract into feature modules:
```
handlers/
├── notarization.py
├── subscription.py
├── referral.py
├── lottery.py
├── memescan.py
└── admin.py
```

---

### 6. Config Duplication Between config.py and bot.py

bot.py duplicates environment variable loading (lines 37-62) instead of importing from config.py.

**Fix:** Import all config from config.py:
```python
from config import (BOT_TOKEN, MEMESEAL_BOT_TOKEN, ...)
```

---

### 7. Missing Database Indexes

Add these indexes for performance:
```sql
-- Compound index for lottery queries
CREATE INDEX idx_lottery_entries_user_draw ON lottery_entries(user_id, draw_id);

-- Partial index for current lottery
CREATE INDEX idx_lottery_entries_current ON lottery_entries(user_id) WHERE draw_id IS NULL;

-- Holder snapshots compound index
CREATE INDEX idx_holder_snapshots_token_time ON holder_snapshots(token_address, snapshot_at DESC);
```

---

## MEDIUM PRIORITY ISSUES

### 8. Test Coverage Gaps

**Current State:**
- 3 test files, ~50 tests
- Uses SQLite fixtures but production uses PostgreSQL
- Tests don't cover actual bot handlers or database.py repository classes
- No coverage metrics

**Recommendations:**
1. Add pytest-cov for coverage reporting
2. Create PostgreSQL test fixtures (use testcontainers or similar)
3. Add integration tests for actual handlers
4. Target 70%+ coverage

---

### 9. Error Handling: Bare Except Clauses

**Found at:** Lines 660, 673, 686, 723, 843, 866, 902+ in bot.py

```python
# BAD
except:
    pass

# GOOD
except Exception as e:
    print(f"Error: {e}")
```

Bare except catches `KeyboardInterrupt`, `SystemExit`, making debugging impossible.

---

### 10. Logging Infrastructure

Currently uses `print()` statements throughout.

**Recommendation:** Use Python `logging` module with structured logs:
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

---

### 11. File Cleanup in Exception Paths

**Location:** bot.py lines 1843-1876

Downloaded files may not be cleaned up if exceptions occur.

**Fix:** Use try/finally:
```python
file_path = None
try:
    # download and process
finally:
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
```

---

### 12. Missing Type Hints

Many functions lack type hints. Add return type hints throughout:
```python
# Before
async def cleanup_pending_payments():

# After
async def cleanup_pending_payments() -> None:
```

---

## LOW PRIORITY ISSUES

### 13. Code Duplication: Notification Logic

Bot notification pattern repeated 10+ times. Extract to helper:
```python
async def notify_user(user_id: int, message: str) -> bool:
    for bot_instance in [memeseal_bot, bot]:
        if bot_instance:
            try:
                await bot_instance.send_message(user_id, message)
                return True
            except Exception:
                continue
    return False
```

---

### 14. TODO Comments in Code

**Location:** Lines 3006-3010, 3053-3057

Placeholder webhook handlers with TODOs. Either implement or create GitHub issues.

---

### 15. N+1 Query in Lottery Stats

**Location:** Lines 1372-1378

Multiple separate queries for lottery stats. Combine into single query in database layer.

---

## UTILITY MODULES REVIEW

### utils/i18n.py - GOOD
- Clean translations for EN/RU/ZH
- Proper string formatting with kwargs
- User language cache works well

**Issue:** Uses module-level dict `user_languages = {}`. Consider persisting to database.

### utils/hashing.py - EXCELLENT
- Clean SHA-256 implementation
- Proper chunked file reading (4KB blocks)
- Type hints present

### utils/memo.py - GOOD
- Clean memo generation
- Has cleanup function

**Issue:** Same as bot.py - in-memory `payment_memo_lookup` dict is not thread-safe. This is duplicated from bot.py.

---

## DOCUMENTATION REVIEW

### Existing Docs (20 files in docs/)

| Doc | Status | Notes |
|-----|--------|-------|
| MASTER.md | EXCELLENT | Central reference |
| API.md | GOOD | API documentation |
| DATABASE.md | GOOD | Schema reference |
| ENV-VARS.md | EXISTS | Needs review |
| ROADMAP.md | EXISTS | Feature timeline |
| INVENTORY.md | EXISTS | Asset list |
| STRATEGY.md | EXISTS | Business model |
| ARCHITECTURE.md | EXISTS | Technical design |
| DEPLOYMENT.md | EXISTS | Deploy guide |

### START_HERE.md - EXCELLENT
Quick context file for session initialization.

### Missing/Outdated
- [ ] Update MASTER.md with KOL tracker status
- [ ] Add SECURITY.md for security practices
- [ ] Add CONTRIBUTING.md if open-sourcing

---

## INFRASTRUCTURE STATUS

### Related Repos (via MCP jpanda)

| Repo | Status | Notes |
|------|--------|-------|
| notaryton-bot | OK | Main backend, 1 commit ahead of remote |
| memeseal-casino | OK | All checks pass |
| memescan-astro | OK | All checks pass |

### Git Status
- Branch: main
- 1 commit ahead of origin (need to push)

---

## RECOMMENDED ACTION PLAN

### Immediate (This Week)
1. **FIX** hardcoded API keys in config.py
2. **ROTATE** TonAPI keys at tonconsole.com
3. **PUSH** pending commit to origin
4. **ADD** asyncio.Lock for in-memory dicts

### Short Term (This Month)
5. Wrap lottery pick_winner() in transaction
6. Add CHECK constraint for withdrawals
7. Add missing database indexes
8. Replace bare except clauses

### Medium Term (This Quarter)
9. Extract bot.py into feature modules
10. Add PostgreSQL test fixtures
11. Implement proper logging
12. Add test coverage metrics (target 70%)

### Nice to Have
13. Add Redis for distributed state
14. Implement Alembic for migrations
15. Add SECURITY.md documentation

---

## FILES REVIEWED

- bot.py (4,776 lines)
- database.py (1,532 lines)
- config.py (97 lines)
- utils/i18n.py (80 lines)
- utils/hashing.py (20 lines)
- utils/memo.py (45 lines)
- tests/conftest.py (151 lines)
- tests/test_handlers.py (129 lines)
- tests/test_database.py (166 lines)
- tests/test_api.py (117 lines)
- START_HERE.md
- docs/MASTER.md
- 20 documentation files

---

*Audit conducted: January 8, 2026*
*Next audit recommended: March 2026*
