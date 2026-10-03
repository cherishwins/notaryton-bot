"""
The legacy lottery void: an operator decision, never a startup migration.

POST /admin/void-legacy-lottery voids every undrawn entry made before the
call, once, and records it in bot_state. Startup never does it, because it
voids tickets honest users bought with Stars along with the forged ones.

The repository code under test is the real LotteryRepository; only the pool
is fake: an in-memory model of the two tables it touches, answering the exact
statements the repository sends. tests/test_database_pg.py runs the same
paths against a real Postgres when TEST_DATABASE_URL is set.
"""

import json
import os
import types
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("BOT_TOKEN", "123456:TEST-placeholder-token")

import bot  # noqa: E402
import database  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

PATH = "/admin/void-legacy-lottery"
SECRET = "s3cret-for-tests"
HOUSE = 1
ALICE = 111111111


# ========================
# A fake pool over two in-memory tables
# ========================

class FakeLotteryTables:
    """bot_state, lottery_entries and casino_balances, enough for void_legacy_entries."""

    def __init__(self):
        self.bot_state = {}
        self.entries = []  # dicts: id, user_id, amount_stars, draw_id, created_at
        self.casino = {}   # user_id -> {"chips", "total_won"}
        self.now = datetime(2026, 10, 3, 12, 0, 0)
        self.statements = []

    def add_entry(self, user_id, amount_stars, draw_id=None, created_at=None):
        self.entries.append({"id": len(self.entries) + 1, "user_id": user_id,
                             "amount_stars": amount_stars, "draw_id": draw_id,
                             "created_at": created_at or self.now - timedelta(days=3)})

    def undrawn(self):
        return [e for e in self.entries if e["draw_id"] is None]


class FakeConn:
    def __init__(self, tables):
        self.t = tables

    def transaction(self):
        return _Nothing()

    async def execute(self, sql, *args):
        self.t.statements.append(" ".join(sql.split()))
        if sql.startswith("LOCK TABLE bot_state"):
            return "LOCK TABLE"
        if sql.startswith("UPDATE bot_state SET value = $2 WHERE key = $1"):
            key, value = args
            assert key in self.t.bot_state
            self.t.bot_state[key] = value
            return "UPDATE 1"
        if "INSERT INTO bot_state" in sql:
            key, value = args
            if key in self.t.bot_state:
                raise AssertionError("duplicate bot_state key: the void ran twice")
            self.t.bot_state[key] = value
            return "INSERT 0 1"
        raise AssertionError(f"unexpected statement: {sql}")

    async def fetchval(self, sql, *args):
        self.t.statements.append(" ".join(sql.split()))
        if "SELECT value FROM bot_state WHERE key = $1" in sql:
            return self.t.bot_state.get(args[0])
        if "UPDATE lottery_entries SET draw_id = $1" in sql:
            assert "draw_id IS NULL" in sql and "created_at <= LOCALTIMESTAMP" in sql
            count = 0
            for e in self.t.entries:
                if e["draw_id"] is None and (e["created_at"] is None or e["created_at"] <= self.t.now):
                    e["draw_id"] = args[0]
                    count += 1
            return count
        if "UPDATE casino_balances" in sql:
            assert "GREATEST(0, chips - total_won)" in sql
            assert "WHERE total_won > 0 AND chips > 0" in sql
            count = 0
            for row in self.t.casino.values():
                if row["total_won"] > 0 and row["chips"] > 0:
                    row["chips"] = max(0, row["chips"] - row["total_won"])
                    count += 1
            return count
        raise AssertionError(f"unexpected query: {sql}")


class _Nothing:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakePool:
    def __init__(self, tables):
        self.tables = tables

    def acquire(self):
        conn = FakeConn(self.tables)

        class _Acquire:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return _Acquire()


@pytest.fixture
def tables():
    t = FakeLotteryTables()
    t.add_entry(ALICE, 25000)                       # bought with Stars, or forged: no way to tell
    t.add_entry(HOUSE, 2500)                        # unbacked /admin/seed-lottery house entry
    t.add_entry(ALICE, 5, draw_id=123)              # already drawn: untouched
    t.add_entry(ALICE, 10, created_at=t.now + timedelta(seconds=1))  # made after the call began
    t.casino[ALICE] = {"chips": 2_000_000_010, "total_won": 2_000_000_000}  # forged "wins"
    t.casino[HOUSE] = {"chips": 40, "total_won": 0}                         # bought, never won
    return t


@pytest.fixture
def lottery(tables):
    return database.LotteryRepository(FakePool(tables))


@pytest.fixture
def client(monkeypatch, lottery):
    # No `with`: the startup hook (DB, Telegram) does not run.
    monkeypatch.setattr(bot, "db", types.SimpleNamespace(lottery=lottery))
    monkeypatch.setattr(bot, "ADMIN_SECRET", SECRET)
    return TestClient(bot.app, raise_server_exceptions=False)


# ========================
# Endpoint auth
# ========================

@pytest.mark.unit
def test_void_requires_the_admin_header(client, tables):
    assert client.post(PATH).status_code == 401
    assert client.post(PATH, headers={"X-Admin-Secret": "wrong"}).status_code == 401
    # Not accepted in the query string either.
    assert client.post(PATH, params={"secret": SECRET}).status_code == 401
    assert tables.bot_state == {}
    assert len(tables.undrawn()) == 3


@pytest.mark.unit
@pytest.mark.parametrize("given", ["", "memeseal-admin-2024", SECRET])
def test_void_is_disabled_while_admin_secret_is_unset(client, monkeypatch, tables, given):
    monkeypatch.setattr(bot, "ADMIN_SECRET", "")
    assert client.post(PATH, headers={"X-Admin-Secret": given}).status_code == 401
    assert tables.bot_state == {}
    assert len(tables.undrawn()) == 3


# ========================
# What it does
# ========================

@pytest.mark.unit
def test_void_takes_undrawn_entries_made_before_the_call_out_of_the_pot(client, tables):
    response = client.post(PATH, headers={"X-Admin-Secret": SECRET})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True and body["already_done"] is False
    assert body["voided"] == 2
    assert body["at"].endswith("Z")

    by_id = {e["id"]: e for e in tables.entries}
    assert by_id[1]["draw_id"] == database.VOID_DRAW_ID          # user's entry
    assert by_id[2]["draw_id"] == database.VOID_DRAW_ID          # house user 1
    assert by_id[3]["draw_id"] == 123                            # drawn before: untouched
    assert by_id[4]["draw_id"] is None                           # made after the call: stays

    record = json.loads(tables.bot_state[database.LEGACY_LOTTERY_VOID_KEY])
    assert record == {"voided": 2, "at": body["at"], "chip_balances_cut": 1}
    assert body["chip_balances_cut"] == 1


@pytest.mark.unit
def test_void_takes_back_chips_minted_by_claimed_wins(client, tables):
    """Forged chips wagered after the void would make fresh, unvoided lottery entries."""
    client.post(PATH, headers={"X-Admin-Secret": SECRET})
    assert tables.casino[ALICE]["chips"] == 10   # what deposits alone explain
    assert tables.casino[HOUSE]["chips"] == 40   # never claimed a win: untouched


@pytest.mark.unit
def test_second_call_reports_already_done_and_changes_nothing(client, tables):
    first = client.post(PATH, headers={"X-Admin-Secret": SECRET}).json()
    tables.add_entry(ALICE, 7)  # an entry bought after the first void
    tables.now += timedelta(days=1)
    before = [dict(e) for e in tables.entries]
    record = dict(tables.bot_state)
    tables.statements.clear()

    second = client.post(PATH, headers={"X-Admin-Secret": SECRET})

    assert second.status_code == 200
    assert second.json() == {"ok": True, "already_done": True, "voided": first["voided"],
                             "at": first["at"], "chip_balances_cut": 1}
    assert tables.entries == before
    assert tables.bot_state == record
    assert not any("UPDATE" in s or "INSERT" in s for s in tables.statements)


@pytest.mark.unit
async def test_legacy_entries_voided_follows_the_record(lottery):
    assert await lottery.legacy_entries_voided() is False
    await lottery.void_legacy_entries()
    assert await lottery.legacy_entries_voided() is True


@pytest.mark.unit
async def test_a_record_left_by_the_old_startup_migration_counts_as_done(lottery, tables):
    tables.bot_state[database.LEGACY_LOTTERY_VOID_KEY] = "2026-09-30T00:00:00Z UPDATE 41"
    result = await lottery.void_legacy_entries()
    # The entries are not voided again, but the chip step, which that void
    # never ran, runs once and is recorded.
    assert result == {"already_done": True, "voided": 41, "at": "2026-09-30T00:00:00Z",
                      "chip_balances_cut": 1}
    assert len(tables.undrawn()) == 3
    assert tables.casino[ALICE]["chips"] == 10
    tables.casino[ALICE]["chips"] = 500  # bought later: a rerun must not cut it again
    again = await lottery.void_legacy_entries()
    assert again == result
    assert tables.casino[ALICE]["chips"] == 500


# ========================
# Startup never voids
# ========================

class RecordingSchemaConn:
    def __init__(self):
        self.statements = []

    async def execute(self, sql, *args):
        self.statements.append(" ".join(sql.split()))
        return "OK"

    def transaction(self):
        return _Nothing()

    async def fetchval(self, sql, *args):
        self.statements.append(" ".join(sql.split()))
        return None


@pytest.mark.unit
async def test_schema_init_on_startup_does_not_void_lottery_entries():
    conn = RecordingSchemaConn()

    class Pool:
        def acquire(self):
            class _A:
                async def __aenter__(self_inner):
                    return conn

                async def __aexit__(self_inner, *exc):
                    return False
            return _A()

    db = database.Database()
    db._pool = Pool()
    await db._init_schema()

    assert conn.statements, "schema init ran no statements"
    touching = [s for s in conn.statements
                if s.startswith("UPDATE lottery_entries") or "LOCK TABLE bot_state" in s
                or (s.startswith("INSERT INTO bot_state"))]
    assert touching == []
    assert not hasattr(database.Database, "_void_legacy_lottery_entries")


@pytest.mark.unit
async def test_startup_with_auto_payout_on_and_no_void_warns(monkeypatch, tmp_path, capsys):
    calls = []

    async def noop(*args, **kwargs):
        return None

    async def voided():
        return False

    async def void_legacy_entries():
        calls.append("void")

    def create_task(coro):
        coro.close()

    fake_lottery = types.SimpleNamespace(legacy_entries_voided=voided,
                                         void_legacy_entries=void_legacy_entries)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bot, "db", types.SimpleNamespace(connect=noop, lottery=fake_lottery))
    monkeypatch.setattr(bot, "asyncio", types.SimpleNamespace(create_task=create_task))
    monkeypatch.setattr(bot.social_poster, "initialize", lambda: None)
    monkeypatch.setattr(bot, "TELEGRAM_WEBHOOK_SECRET", "")
    monkeypatch.setattr(bot, "SERVICE_TON_WALLET", None)
    monkeypatch.setattr(bot, "LOTTERY_AUTO_PAYOUT_ENABLED", True, raising=False)

    await bot.on_startup()

    assert calls == []
    assert "POST /admin/void-legacy-lottery has never run" in capsys.readouterr().out
