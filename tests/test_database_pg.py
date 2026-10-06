"""
Postgres checks for the money SQL in database.py: what the in-memory fakes in
test_money_paths.py cannot prove (locking, conflict handling, the legacy lottery void).

Integration tests: they run only when TEST_DATABASE_URL points at a throwaway
Postgres, and they drop and recreate the tables they use. Never point it at a
real database.

    TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/notary pytest -m integration
"""

import asyncio
import collections
import os

import pytest

asyncpg = pytest.importorskip("asyncpg")

import database  # noqa: E402

os.environ.setdefault("BOT_TOKEN", "123456:TEST-placeholder-token")
import bot  # noqa: E402
from tests.test_money_paths import FAKE_TOKEN, Recorder, sign_init_data  # noqa: E402

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL is not set"),
]

TABLES = ["api_keys", "lottery_prizes", "ton_payments_processed", "lottery_entries",
          "casino_balances", "notarizations", "pending_payments", "bot_state"]


@pytest.fixture
async def pg(monkeypatch):
    monkeypatch.setenv("DATABASE_SSL", "disable")
    conn = await asyncpg.connect(URL)
    for table in TABLES:
        await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    await conn.execute("DROP TABLE IF EXISTS users CASCADE")
    await conn.close()
    db = database.Database()
    await db.connect(URL)
    yield db
    await db.disconnect()


async def test_reserve_withdrawal_pays_once_under_twenty_concurrent_calls(pg):
    await pg.execute("INSERT INTO users (user_id, referral_earnings, total_withdrawn) VALUES (1, 1.25, 0.25)")
    results = await asyncio.gather(*[pg.users.reserve_withdrawal(1, 0.05) for _ in range(20)])
    assert sorted(results, reverse=True)[:2] == [1.0, 0.0]
    assert await pg.fetchval("SELECT total_withdrawn FROM users WHERE user_id = 1") == 1.25


async def test_startup_does_not_void_legacy_entries(pg):
    await pg.execute("INSERT INTO users (user_id) VALUES (1), (7)")
    await pg.execute("INSERT INTO lottery_entries (user_id, amount_stars) VALUES (7, 25000), (1, 2500)")
    # Reconnect: the schema init runs again and must leave the pot alone.
    await pg.disconnect()
    await pg.connect(URL)
    assert await pg.fetchval("SELECT value FROM bot_state WHERE key = $1", database.LEGACY_LOTTERY_VOID_KEY) is None
    assert await pg.lottery.get_total_entries() == 2
    assert await pg.lottery.legacy_entries_voided() is False


async def test_void_legacy_entries_once_on_request(pg):
    await pg.execute("INSERT INTO users (user_id) VALUES (1), (7)")
    await pg.execute("INSERT INTO lottery_entries (user_id, amount_stars) VALUES (7, 25000), (1, 2500)")
    await pg.execute("INSERT INTO lottery_entries (user_id, amount_stars, draw_id) VALUES (7, 5, 123)")
    # Made after the call began (a clock ahead of the transaction's): left alone.
    await pg.execute("INSERT INTO lottery_entries (user_id, amount_stars, created_at) "
                     "VALUES (7, 3, LOCALTIMESTAMP + INTERVAL '1 minute')")

    first = await pg.lottery.void_legacy_entries()
    assert first["already_done"] is False and first["voided"] == 2
    assert await pg.lottery.legacy_entries_voided() is True
    assert await pg.lottery.get_total_entries() == 1
    assert await pg.fetchval("SELECT COUNT(*) FROM lottery_entries WHERE draw_id = $1",
                             database.VOID_DRAW_ID) == 2
    assert await pg.fetchval("SELECT COUNT(*) FROM lottery_entries WHERE user_id = 1 AND draw_id IS NULL") == 0
    assert await pg.fetchval("SELECT COUNT(*) FROM lottery_entries WHERE draw_id = 123") == 1

    # A real entry made after the void stays, and a rerun changes nothing.
    await pg.lottery.add_entry(7, 10)
    second = await pg.lottery.void_legacy_entries()
    assert second == {"already_done": True, "voided": 2, "at": first["at"], "chip_balances_cut": 0}
    assert await pg.lottery.get_total_entries() == 2


async def test_concurrent_void_calls_void_once(pg):
    await pg.execute("INSERT INTO users (user_id) VALUES (7)")
    await pg.execute("INSERT INTO lottery_entries (user_id, amount_stars) VALUES (7, 1), (7, 2), (7, 3)")
    results = await asyncio.gather(*[pg.lottery.void_legacy_entries() for _ in range(8)])
    assert sorted(r["already_done"] for r in results) == [False] + [True] * 7
    assert all(r["voided"] == 3 for r in results)


async def test_pick_winner_is_weighted_by_stars_not_rows(pg):
    await pg.execute("INSERT INTO users (user_id) VALUES (1), (2)")
    wins = collections.Counter()
    for draw in range(300):
        for _ in range(9):
            await pg.lottery.add_entry(1, 1)   # nine 1-star rows
        await pg.lottery.add_entry(2, 91)      # one 91-star row
        wins[(await pg.lottery.pick_winner(draw + 1)).winner_id] += 1
    # By rows user 1 would win ~90%; by stars ~9%.
    assert wins[1] < 60
    assert await pg.lottery.get_total_entries() == 0
    assert await pg.fetchval("SELECT COUNT(*) FROM lottery_entries WHERE won") == 300


async def test_pick_winner_with_no_weight_returns_entries_to_the_pot(pg):
    await pg.execute("INSERT INTO users (user_id) VALUES (1)")
    await pg.lottery.add_entry(1, 0)
    assert await pg.lottery.pick_winner(5) is None
    assert await pg.lottery.get_total_entries() == 1


async def test_ton_payment_claim_is_once(pg):
    claims = await asyncio.gather(*[pg.ton_payments.claim("0:ab:7", 42, 150_000_000) for _ in range(10)])
    assert claims.count(True) == 1
    await pg.ton_payments.set_status("0:ab:7", "credited")
    assert await pg.fetchval("SELECT status FROM ton_payments_processed") == "credited"


async def test_prize_ledger_records_status_changes_per_draw(pg):
    await pg.lottery.record_prize(9, 7, 1.5, "sending")
    await pg.lottery.record_prize(9, 7, 1.5, "review")
    rows = await pg.fetch("SELECT draw_id, user_id, amount_ton, status FROM lottery_prizes")
    assert [(r["draw_id"], r["user_id"], float(r["amount_ton"]), r["status"]) for r in rows] == [
        (9, 7, 1.5, "review")]
    # Never touches the /withdraw balance.
    assert await pg.fetchval("SELECT COUNT(*) FROM users") == 0


async def test_api_key_replace_revokes_the_old_key(pg):
    await pg.api_keys.replace_for_user(5, "a" * 64)
    await pg.api_keys.replace_for_user(5, "b" * 64)
    assert await pg.api_keys.get("a" * 64) is None
    assert (await pg.api_keys.get("b" * 64)).user_id == 5


# ========================
# Round 2 review: the money invariants, in SQL
# ========================

def _post(path, headers, body):
    from starlette.requests import Request

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {"type": "http", "method": "POST", "path": path, "query_string": b"",
             "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
    return Request(scope, receive)


def _quiet(monkeypatch):
    import types
    monkeypatch.setattr(bot, "bot", types.SimpleNamespace(send_message=Recorder()))
    monkeypatch.setattr(bot, "memeseal_bot", None)
    monkeypatch.setattr(bot, "social_poster", types.SimpleNamespace(post_lottery_winner=Recorder()))


async def test_forged_legacy_chips_cannot_be_wagered_into_a_prize_after_the_void(pg, monkeypatch):
    """Pre-Round-1 /casino/play minted chips from a client "payout"; wagered after the void they made the pot."""
    import json
    wallet = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c"  # throwaway zero address
    await pg.users.ensure_exists(7)
    await pg.users.set_withdrawal_wallet(7, wallet)
    await pg.casino.add_chips(7, 10)                   # 10 Stars really paid
    await pg.casino.record_win(7, 2_000_000_000)       # the forged "win"
    await pg.lottery.add_entry(7, 99999)               # a forged legacy entry

    result = await pg.lottery.void_legacy_entries()
    assert result["voided"] == 1 and result["chip_balances_cut"] == 1
    assert await pg.fetchval("SELECT chips FROM casino_balances WHERE user_id = 7") == 10

    monkeypatch.setattr(bot, "db", pg)
    monkeypatch.setattr(bot, "CASINO_ENABLED", True)
    monkeypatch.setattr(bot, "LOTTERY_ENABLED", True)
    monkeypatch.setattr(bot, "LOTTERY_AUTO_PAYOUT_ENABLED", True)
    monkeypatch.setattr(bot, "BOT_TOKEN", FAKE_TOKEN)
    monkeypatch.setattr(bot, "MEMESEAL_BOT_TOKEN", None)
    bet = _post("/api/v1/casino/bet", {"X-Telegram-Init-Data": sign_init_data(7)},
                json.dumps({"amount": 1_000_000, "game": "slots"}).encode())
    assert (await bot.api_casino_bet(bet))["success"] is False   # the forged chips are gone

    _quiet(monkeypatch)
    sent = Recorder()
    monkeypatch.setattr(bot, "send_payout_transaction", sent)
    await bot.execute_lottery_draw()
    assert sent.calls == []


async def test_same_second_draws_claim_once_and_hand_back_nothing_of_the_other(pg):
    for uid in (21, 22, 23):
        await pg.users.ensure_exists(uid)
        await pg.lottery.add_entry(uid, 1000)
    draw_id = 1_791_000_000
    a, b = await asyncio.gather(pg.lottery.pick_winner(draw_id), pg.lottery.pick_winner(draw_id))

    assert (a is None) != (b is None)
    result = a or b
    assert (result.entries, result.entry_stars) == (3, 3000)
    # The losing draw used to run its "hand back" over the shared draw_id and
    # reopen the winner's entries, so the same pot was paid again next week.
    assert await pg.fetchval("SELECT COUNT(*) FROM lottery_entries WHERE draw_id = $1", draw_id) == 3
    assert await pg.lottery.get_total_entries() == 0


async def test_a_draw_id_that_already_ran_does_not_draw_again(pg):
    await pg.users.ensure_exists(21)
    await pg.lottery.add_entry(21, 1000)
    assert (await pg.lottery.pick_winner(5)).winner_id == 21
    await pg.lottery.add_entry(21, 1000)  # bought after that draw
    assert await pg.lottery.pick_winner(5) is None
    assert await pg.lottery.get_total_entries() == 1


async def test_draw_prize_is_what_it_claimed_including_a_mid_draw_entry(pg, monkeypatch):
    for uid in (51, 52):
        await pg.users.ensure_exists(uid)
    await pg.lottery.void_legacy_entries()
    await pg.lottery.add_entry(51, 100)
    monkeypatch.setattr(bot, "db", pg)
    monkeypatch.setattr(bot, "LOTTERY_ENABLED", True)
    monkeypatch.setattr(bot, "LOTTERY_AUTO_PAYOUT_ENABLED", False)
    _quiet(monkeypatch)
    real_pick = pg.lottery.pick_winner

    async def pick_after_purchase(draw_id):
        await pg.lottery.add_entry(52, 5000)  # lands between the entry count and the claim
        return await real_pick(draw_id)

    monkeypatch.setattr(pg.lottery, "pick_winner", pick_after_purchase)
    await bot.execute_lottery_draw()

    claimed = await pg.fetchval("SELECT SUM(amount_stars) FROM lottery_entries WHERE draw_id > 0")
    prize = await pg.fetchval("SELECT amount_ton FROM lottery_prizes")
    assert claimed == 5100
    assert float(prize) == pytest.approx(5100 * 0.2 * 0.001)


async def test_no_draw_before_the_void_leaves_the_legacy_pot_for_it(pg, monkeypatch):
    await pg.users.ensure_exists(7)
    await pg.lottery.add_entry(7, 500000)  # forged
    monkeypatch.setattr(bot, "db", pg)
    monkeypatch.setattr(bot, "LOTTERY_ENABLED", True)
    monkeypatch.setattr(bot, "LOTTERY_AUTO_PAYOUT_ENABLED", False)
    _quiet(monkeypatch)

    assert await bot.execute_lottery_draw() is None
    assert await pg.fetchval("SELECT COUNT(*) FROM lottery_prizes") == 0
    assert (await pg.lottery.void_legacy_entries())["voided"] == 1


async def test_one_seal_credit_is_taken_once_under_concurrency(pg):
    await pg.users.add_payment(41, 0.15)
    taken = await asyncio.gather(*[pg.users.deduct_payment(41, 0.15) for _ in range(5)])
    assert taken.count(True) == 1
    assert await pg.users.get_total_paid(41) == 0.0
    assert await pg.users.deduct_payment(41, 0.15) is False


async def test_uncredited_ton_is_recorded_with_its_memo_and_never_overwrites(pg):
    await pg.ton_payments.record_uncredited("0:ab:6", 150_000_000, "@alice", "unmatched")
    assert await pg.ton_payments.claim("0:ab:7", 42, 150_000_000) is True
    await pg.ton_payments.record_uncredited("0:ab:7", 150_000_000, "42", "precutover")
    rows = {r["tx_key"]: (r["status"], r["memo"], r["user_id"])
            for r in await pg.fetch("SELECT tx_key, status, memo, user_id FROM ton_payments_processed")}
    assert rows == {"0:ab:6": ("unmatched", "@alice", None), "0:ab:7": ("claimed", None, 42)}
