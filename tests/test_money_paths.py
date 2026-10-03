"""
Tests for the paths in bot.py that move value: the casino API, the lottery
draw, /withdraw, the TON payment poller, the notarize API and the MemeSeal
"pay with TON" seal.

Nothing here reaches Telegram, TON or the database. Each test swaps bot.db for
an in-memory fake, and every function that could send TON is replaced by a
recorder (or a raiser, to prove it is not called). Telegram initData is signed
here with a throwaway token, exactly as Telegram signs it.
"""

import asyncio
import hashlib
import hmac
import json
import os
import time
import types
from urllib.parse import urlencode

import pytest

os.environ.setdefault("BOT_TOKEN", "123456:TEST-placeholder-token")

import bot  # noqa: E402
from database import DrawResult  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pytoniq_core import Address, Builder, Cell  # noqa: E402
from pytoniq_core.tlb.account import AccountStatus  # noqa: E402
from pytoniq_core.tlb.block import CurrencyCollection  # noqa: E402
from pytoniq_core.tlb.transaction import (  # noqa: E402
    ExternalMsgInfo, InternalMsgInfo, MessageAny, Transaction,
)

FAKE_TOKEN = "654321:FAKE-token-for-tests-only"
OTHER_TOKEN = "999999:SOME-other-bot-token"
ALICE = 111111111
BOB = 222222222

# Throwaway addresses (zero and constant hashes), not real wallets.
SERVICE = Address((0, bytes(32)))
PAYER = Address((0, b"\x11" * 32))


# ========================
# Fakes
# ========================

class Recorder:
    """An async callable that records its calls, and optionally raises."""

    def __init__(self, result=None, exc=None):
        self.calls = []
        self.result = result
        self.exc = exc

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.exc:
            raise self.exc
        return self.result


class FakeCasino:
    def __init__(self, chips=None):
        self.chips = dict(chips or {})
        self.wins = []
        self.withdrawals = []

    async def deduct_chips(self, user_id, amount):
        have = self.chips.get(user_id)
        if have is None or have < amount:
            return (False, have or 0)
        self.chips[user_id] = have - amount
        return (True, self.chips[user_id])

    async def record_win(self, user_id, amount):
        self.wins.append((user_id, amount))
        self.chips[user_id] = self.chips.get(user_id, 0) + amount
        return self.chips[user_id]

    async def withdraw_chips(self, user_id, amount):
        self.withdrawals.append((user_id, amount))
        have = self.chips.get(user_id, 0)
        if have < amount:
            return (False, 0)
        self.chips[user_id] = have - amount
        return (True, self.chips[user_id])

    async def get_balance(self, user_id):
        return types.SimpleNamespace(
            chips=self.chips.get(user_id, 0), total_wagered=0, total_won=0,
            total_deposited=0, total_withdrawn=0)


class FakeLottery:
    def __init__(self, entries=None, legacy_voided=False):
        self.entries = list(entries or [])  # (user_id, amount_stars)
        self.prizes = []  # (draw_id, user_id, amount_ton, status)
        # Whether POST /admin/void-legacy-lottery has run (its bot_state key exists).
        self.legacy_voided = legacy_voided

    async def legacy_entries_voided(self):
        return self.legacy_voided

    async def record_prize(self, draw_id, user_id, amount_ton, status):
        self.prizes.append((draw_id, user_id, amount_ton, status))

    def prize_statuses(self):
        return [status for *_, status in self.prizes]

    async def add_entry(self, user_id, amount_stars=1):
        self.entries.append((user_id, amount_stars))

    async def count_user_entries(self, user_id, current_only=True):
        return sum(1 for uid, _ in self.entries if uid == user_id)

    async def get_total_entries(self, current_only=True):
        return len(self.entries)

    async def get_pot_size_stars(self):
        return int(sum(stars for _, stars in self.entries) * 0.2)

    async def get_pot_size_ton(self):
        return (await self.get_pot_size_stars()) * 0.001

    async def get_entry_stars(self, user_id=None):
        return sum(stars for uid, stars in self.entries if user_id is None or uid == user_id)

    async def pick_winner(self, draw_id):
        """Claims every open entry, as the real one does; the first entry wins."""
        if not self.entries:
            return None
        claimed, self.entries = self.entries, []
        self.drawn = getattr(self, "drawn", []) + claimed
        return DrawResult(winner_id=claimed[0][0], entries=len(claimed),
                          entry_stars=sum(stars for _, stars in claimed))


class FakeUsers:
    def __init__(self, users=None, language="en", paid=None, subscribers=()):
        self.users = dict(users or {})
        self.language = language
        self.calls = []
        self.paid = dict(paid or {})
        self.subscribers = set(subscribers)

    def _log(self, name, *args):
        self.calls.append((name,) + args)

    def names(self):
        return [c[0] for c in self.calls]

    async def get(self, user_id):
        self._log("get", user_id)
        return self.users.get(user_id)

    async def get_language(self, user_id):
        return self.language

    async def ensure_exists(self, user_id):
        self._log("ensure_exists", user_id)

    async def set_withdrawal_wallet(self, user_id, wallet):
        self._log("set_withdrawal_wallet", user_id, wallet)

    async def add_referral_earnings(self, user_id, amount):
        self._log("add_referral_earnings", user_id, amount)
        if user_id in self.users:
            self.users[user_id].referral_earnings += amount

    async def record_withdrawal(self, user_id, amount):
        self._log("record_withdrawal", user_id, amount)
        self.users[user_id].total_withdrawn += amount

    async def reserve_withdrawal(self, user_id, minimum):
        # Atomic in the fake as in Postgres: read and debit with no await between.
        self._log("reserve_withdrawal", user_id, minimum)
        user = self.users.get(user_id)
        available = user.available_balance if user else 0
        if available <= 0 or available < minimum:
            return 0.0
        user.total_withdrawn += available
        return available

    async def add_payment(self, user_id, amount):
        self._log("add_payment", user_id, amount)
        self.paid[user_id] = self.paid.get(user_id, 0.0) + amount

    async def deduct_payment(self, user_id, amount):
        # Conditional, as in Postgres: no debit below the amount.
        self._log("deduct_payment", user_id, amount)
        if self.paid.get(user_id, 0.0) < amount:
            return False
        self.paid[user_id] = self.paid[user_id] - amount
        return True

    async def get_total_paid(self, user_id):
        return self.paid.get(user_id, 0.0)

    async def has_active_subscription(self, user_id):
        return user_id in self.subscribers

    async def add_subscription(self, user_id, months=1):
        self._log("add_subscription", user_id, months)


def make_user(user_id, earnings=0.0, withdrawn=0.0, wallet=None, referred_by=None):
    from database import User
    return User(user_id=user_id, referral_earnings=earnings, total_withdrawn=withdrawn,
                withdrawal_wallet=wallet, referred_by=referred_by)


class Untouchable:
    """A db that fails the test if anything reads it."""

    def __getattr__(self, name):
        raise AssertionError(f"db.{name} was touched")


class StopLoop(BaseException):
    """Raised from a fake sleep to end a background task's while-True loop."""


# ========================
# initData
# ========================

def sign_init_data(user_id=ALICE, token=FAKE_TOKEN, auth_date=None, **extra):
    """initData as Telegram builds it: fields plus hash over the sorted fields."""
    fields = {
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps({"id": user_id, "first_name": "T", "language_code": "en"},
                           separators=(",", ":")),
        **extra,
    }
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields)).encode()
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check, hashlib.sha256).hexdigest()
    return urlencode(fields)


def auth(user_id=ALICE, **kwargs):
    return {"X-Telegram-Init-Data": sign_init_data(user_id, **kwargs)}


@pytest.fixture
def client():
    return TestClient(bot.app, raise_server_exceptions=False)


@pytest.fixture
def casino_on(monkeypatch):
    monkeypatch.setattr(bot, "CASINO_ENABLED", True, raising=False)
    monkeypatch.setattr(bot, "BOT_TOKEN", FAKE_TOKEN)
    monkeypatch.setattr(bot, "MEMESEAL_BOT_TOKEN", None)


@pytest.fixture
def no_ton(monkeypatch):
    """Any attempt to send TON fails the test."""
    async def forbidden(*args, **kwargs):
        raise AssertionError("tried to send TON")

    monkeypatch.setattr(bot, "send_payout_transaction", forbidden)
    monkeypatch.setattr(bot, "send_ton_transaction", forbidden)
    monkeypatch.setattr(bot, "LiteBalancer", Untouchable())
    monkeypatch.setattr(bot, "WalletV5R1", Untouchable())


class FakeTonPayments:
    """The processed-payments ledger: a key is claimed once."""

    def __init__(self):
        self.rows = {}
        self.memos = {}

    async def claim(self, tx_key, user_id, amount_nano):
        if tx_key in self.rows:
            return False
        self.rows[tx_key] = "claimed"
        return True

    async def record_uncredited(self, tx_key, amount_nano, memo, status):
        self.rows.setdefault(tx_key, status)
        self.memos[tx_key] = memo

    async def set_status(self, tx_key, status):
        self.rows[tx_key] = status


class FakeApiKeys:
    def __init__(self):
        self.keys = {}  # hash -> user_id
        self.used = []

    async def replace_for_user(self, user_id, key_hash):
        self.keys = {h: u for h, u in self.keys.items() if u != user_id}
        self.keys[key_hash] = user_id

    async def get(self, key_hash):
        user_id = self.keys.get(key_hash)
        return types.SimpleNamespace(user_id=user_id) if user_id else None

    async def record_usage(self, key_hash):
        self.used.append(key_hash)


def fake_db(monkeypatch, users=None, lottery=None, casino=None, bot_state=None,
            ton_payments=None, api_keys=None):
    ns = types.SimpleNamespace(
        users=users or FakeUsers(), lottery=lottery or FakeLottery(),
        casino=casino or FakeCasino(), bot_state=bot_state,
        ton_payments=ton_payments or FakeTonPayments(), api_keys=api_keys or FakeApiKeys())
    monkeypatch.setattr(bot, "db", ns)
    return ns


@pytest.mark.unit
def test_init_data_valid():
    user_id, reason = bot.validate_telegram_init_data(sign_init_data(), (FAKE_TOKEN,), 86400)
    assert (user_id, reason) == (ALICE, None)


@pytest.mark.unit
def test_init_data_signed_by_either_bot():
    data = sign_init_data(token=OTHER_TOKEN)
    assert bot.validate_telegram_init_data(data, (FAKE_TOKEN, OTHER_TOKEN), 86400) == (ALICE, None)
    assert bot.validate_telegram_init_data(data, (FAKE_TOKEN, None), 86400)[1] == "bad init data signature"


@pytest.mark.unit
def test_init_data_tampered_hash():
    data = sign_init_data()
    good_hash = data.rsplit("hash=", 1)[1]
    bad = data.replace(good_hash, ("0" if good_hash[0] != "0" else "1") + good_hash[1:])
    assert bot.validate_telegram_init_data(bad, (FAKE_TOKEN,), 86400) == (None, "bad init data signature")


@pytest.mark.unit
def test_init_data_tampered_user_id():
    """Swapping in another user's id breaks the signature."""
    data = sign_init_data(ALICE).replace(f"%22id%22%3A{ALICE}", f"%22id%22%3A{BOB}")
    assert str(BOB) in data
    assert bot.validate_telegram_init_data(data, (FAKE_TOKEN,), 86400) == (None, "bad init data signature")


@pytest.mark.unit
def test_init_data_wrong_bot_token():
    data = sign_init_data(token=OTHER_TOKEN)
    assert bot.validate_telegram_init_data(data, (FAKE_TOKEN,), 86400) == (None, "bad init data signature")


@pytest.mark.unit
def test_init_data_stale_auth_date():
    data = sign_init_data(auth_date=int(time.time()) - 86401)
    assert bot.validate_telegram_init_data(data, (FAKE_TOKEN,), 86400) == (None, "init data expired")
    assert bot.validate_telegram_init_data(data, (FAKE_TOKEN,), 90000) == (ALICE, None)


@pytest.mark.unit
def test_init_data_from_the_future_is_refused():
    data = sign_init_data(auth_date=int(time.time()) + 3600)
    assert bot.validate_telegram_init_data(data, (FAKE_TOKEN,), 86400) == (None, "malformed init data")


@pytest.mark.unit
def test_init_data_too_long_is_refused_before_parsing():
    data = sign_init_data(padding="x" * 9000)
    assert len(data) > bot.INIT_DATA_MAX_LENGTH
    assert bot.validate_telegram_init_data(data, (FAKE_TOKEN,), 86400) == (None, "malformed init data")


@pytest.mark.unit
@pytest.mark.parametrize("data,reason", [
    ("", "missing init data"),
    (None, "missing init data"),
    ("not a query string", "malformed init data"),
    ("auth_date=1&user=x", "malformed init data"),  # no hash
    ("a=1&a=2&hash=00", "malformed init data"),
])
def test_init_data_malformed(data, reason):
    assert bot.validate_telegram_init_data(data, (FAKE_TOKEN,), 86400) == (None, reason)


@pytest.mark.unit
@pytest.mark.parametrize("method,path", [
    ("post", "/api/v1/casino/bet"),
    ("post", "/api/v1/casino/buy-chips"),
    ("get", f"/api/v1/casino/balance/{ALICE}"),
    ("post", "/api/v1/casino/play"),
    ("post", "/api/v1/casino/withdraw"),
])
def test_casino_user_routes_require_init_data(client, casino_on, monkeypatch, method, path):
    monkeypatch.setattr(bot, "db", Untouchable())
    kwargs = {"json": {"user_id": ALICE, "amount": 10, "bet_amount": 10}} if method == "post" else {}
    for headers, reason in [
        ({}, "missing init data"),
        (auth(token=OTHER_TOKEN), "bad init data signature"),
        (auth(auth_date=int(time.time()) - 86401), "init data expired"),
    ]:
        response = getattr(client, method)(path, headers=headers, **kwargs)
        assert response.status_code == 401
        assert response.json() == {"success": False, "error": reason}


# ========================
# CASINO_ENABLED
# ========================

CASINO_ROUTES = [
    ("post", "/api/v1/casino/bet"),
    ("post", "/api/v1/casino/buy-chips"),
    ("get", f"/api/v1/casino/balance/{ALICE}"),
    ("post", "/api/v1/casino/play"),
    ("post", "/api/v1/casino/withdraw"),
    ("get", "/api/v1/casino/stats"),
    ("get", "/api/v1/casino/leaderboard"),
]


@pytest.mark.unit
@pytest.mark.parametrize("name", ["CASINO_ENABLED", "LOTTERY_AUTO_PAYOUT_ENABLED", "WITHDRAWALS_ENABLED"])
def test_money_switches_default_off(monkeypatch, name):
    """Read from a cleared environment, not from whatever .env the developer has."""
    monkeypatch.delenv(name, raising=False)
    assert bot._env_flag(name) is False


@pytest.mark.unit
@pytest.mark.parametrize("value,expected", [
    ("true", True), ("True", False), ("TRUE", False), ("1", False), ("yes", False),
    (" true", False), ("true ", False), ("", False), ("false", False),
])
def test_money_switch_only_the_literal_true_enables(monkeypatch, value, expected):
    monkeypatch.setenv("WITHDRAWALS_ENABLED", value)
    assert bot._env_flag("WITHDRAWALS_ENABLED") is expected


@pytest.mark.unit
@pytest.mark.parametrize("method,path", CASINO_ROUTES)
def test_casino_off_returns_503_before_anything(client, monkeypatch, method, path):
    monkeypatch.setattr(bot, "CASINO_ENABLED", False, raising=False)
    monkeypatch.setattr(bot, "BOT_TOKEN", FAKE_TOKEN)
    monkeypatch.setattr(bot, "db", Untouchable())
    kwargs = {"content": b"{not json"} if method == "post" else {}
    response = getattr(client, method)(path, headers=auth(), **kwargs)
    assert response.status_code == 503
    assert response.json() == {"error": "casino disabled"}


# ========================
# /bet and /play
# ========================

@pytest.mark.unit
def test_bet_cannot_enter_another_user_or_a_chosen_amount(client, casino_on, monkeypatch):
    """The old route entered any user_id with stars = amount * 1000 for free.

    The amount is in range, so this reaches the debit: ALICE has no chips,
    nothing is debited, and therefore nothing may be entered for anyone.
    """
    db = fake_db(monkeypatch, casino=FakeCasino({ALICE: 0, BOB: 500}))
    response = client.post("/api/v1/casino/bet", headers=auth(ALICE),
                           json={"user_id": BOB, "amount": 100, "game": "slots"})
    assert response.status_code == 200
    assert response.json() == {"success": False, "error": "Insufficient chips", "chips": 0}
    assert db.lottery.entries == []
    assert db.casino.chips == {ALICE: 0, BOB: 500}


@pytest.mark.unit
@pytest.mark.parametrize("path,body", [
    ("/api/v1/casino/bet", {"amount": 10}),
    ("/api/v1/casino/play", {"bet_amount": 10, "result": "lose"}),
])
def test_wager_without_the_chips_adds_no_entry(client, casino_on, monkeypatch, path, body):
    db = fake_db(monkeypatch, casino=FakeCasino({ALICE: 9}))
    response = client.post(path, headers=auth(ALICE), json=body)
    assert response.json()["success"] is False
    assert db.lottery.entries == []
    assert db.casino.chips == {ALICE: 9}


@pytest.mark.unit
@pytest.mark.parametrize("bet,entry", [(1, None), (4, None), (5, 1), (9, 1), (10, 2), (100, 20)])
def test_wager_entry_is_a_fifth_rounded_down(client, casino_on, monkeypatch, bet, entry):
    """A 1-chip bet used to round up to a 1-star entry: 100 tiny bets beat one big one."""
    db = fake_db(monkeypatch, casino=FakeCasino({ALICE: 1000}))
    response = client.post("/api/v1/casino/bet", headers=auth(ALICE), json={"amount": bet})
    assert response.json()["success"] is True
    assert db.casino.chips == {ALICE: 1000 - bet}
    assert db.lottery.entries == ([] if entry is None else [(ALICE, entry)])


@pytest.mark.unit
def test_split_wagers_feed_the_pot_like_one_wager(client, casino_on, monkeypatch):
    db = fake_db(monkeypatch, casino=FakeCasino({ALICE: 100, BOB: 100}))
    for _ in range(100):
        client.post("/api/v1/casino/bet", headers=auth(ALICE), json={"amount": 1})
    client.post("/api/v1/casino/bet", headers=auth(BOB), json={"amount": 100})
    stars = {uid: sum(s for u, s in db.lottery.entries if u == uid) for uid in (ALICE, BOB)}
    assert stars == {ALICE: 0, BOB: 20}


@pytest.mark.unit
def test_bet_enters_only_debited_chips_for_the_authenticated_user(client, casino_on, monkeypatch):
    db = fake_db(monkeypatch, casino=FakeCasino({ALICE: 50}))
    response = client.post("/api/v1/casino/bet", headers=auth(ALICE),
                           json={"user_id": BOB, "amount": 10})
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert db.casino.chips == {ALICE: 40}
    assert db.lottery.entries == [(ALICE, 2)]


@pytest.mark.unit
@pytest.mark.parametrize("amount", [0.5, "10", True, -1, 0, None])
def test_bet_rejects_non_chip_amounts(client, casino_on, monkeypatch, amount):
    db = fake_db(monkeypatch, casino=FakeCasino({ALICE: 50}))
    response = client.post("/api/v1/casino/bet", headers=auth(ALICE), json={"amount": amount})
    assert response.status_code == 400
    assert db.lottery.entries == [] and db.casino.chips == {ALICE: 50}


@pytest.mark.unit
def test_play_cannot_credit_a_client_payout(client, casino_on, monkeypatch):
    db = fake_db(monkeypatch, casino=FakeCasino({ALICE: 10}))
    response = client.post("/api/v1/casino/play", headers=auth(ALICE), json={
        "user_id": ALICE, "bet_amount": 10, "game": "slots", "result": "win", "payout": 1_000_000})
    assert response.status_code == 501
    assert db.casino.wins == []
    assert db.casino.chips == {ALICE: 10}
    assert db.lottery.entries == []


@pytest.mark.unit
def test_play_refuses_any_payout_even_on_a_loss(client, casino_on, monkeypatch):
    db = fake_db(monkeypatch, casino=FakeCasino({ALICE: 10}))
    response = client.post("/api/v1/casino/play", headers=auth(ALICE), json={
        "bet_amount": 10, "result": "lose", "payout": 5})
    assert response.status_code == 501
    assert db.casino.chips == {ALICE: 10} and db.casino.wins == []
    assert db.lottery.entries == []


@pytest.mark.unit
def test_play_debits_the_authenticated_user_only(client, casino_on, monkeypatch):
    db = fake_db(monkeypatch, casino=FakeCasino({ALICE: 10, BOB: 100}))
    response = client.post("/api/v1/casino/play", headers=auth(ALICE), json={
        "user_id": BOB, "bet_amount": 10, "result": "lose"})
    assert response.json()["success"] is True
    assert db.casino.chips == {ALICE: 0, BOB: 100}
    assert db.lottery.entries == [(ALICE, 2)]
    assert db.casino.wins == []


@pytest.mark.unit
def test_balance_of_another_user_is_forbidden(client, casino_on, monkeypatch):
    fake_db(monkeypatch, casino=FakeCasino({ALICE: 7, BOB: 99}))
    assert client.get(f"/api/v1/casino/balance/{BOB}", headers=auth(ALICE)).status_code == 403
    response = client.get(f"/api/v1/casino/balance/{ALICE}", headers=auth(ALICE))
    assert response.status_code == 200
    assert response.json()["chips"] == 7


@pytest.mark.unit
def test_buy_chips_invoices_the_authenticated_user(client, casino_on, monkeypatch):
    fake_db(monkeypatch)
    create = Recorder(result="https://t.me/$invoice")
    monkeypatch.setattr(bot, "memeseal_bot", None)
    monkeypatch.setattr(bot, "bot", types.SimpleNamespace(create_invoice_link=create))
    response = client.post("/api/v1/casino/buy-chips", headers=auth(ALICE),
                           json={"user_id": BOB, "amount": 100})
    assert response.json()["invoice_url"] == "https://t.me/$invoice"
    assert create.calls[0][1]["payload"].startswith(f"casino_chips_{ALICE}_100_")


# ========================
# Withdrawals
# ========================

@pytest.mark.unit
def test_casino_withdraw_paused_and_touches_no_chips(client, casino_on, monkeypatch, no_ton):
    monkeypatch.setattr(bot, "WITHDRAWALS_ENABLED", False, raising=False)
    db = fake_db(monkeypatch, casino=FakeCasino({ALICE: 500}))
    response = client.post("/api/v1/casino/withdraw", headers=auth(ALICE),
                           json={"user_id": ALICE, "amount": 500, "wallet": SERVICE.to_str()})
    assert response.status_code == 503
    assert response.json()["error"] == "withdrawals paused"
    assert db.casino.withdrawals == [] and db.casino.chips == {ALICE: 500}


def withdraw_message(user_id, text):
    answer = Recorder()
    message = types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=user_id, language_code="ru"),
        text=text, answer=answer)
    return message, answer


@pytest.mark.unit
async def test_withdraw_command_paused_saves_no_wallet(monkeypatch, no_ton):
    monkeypatch.setattr(bot, "WITHDRAWALS_ENABLED", False, raising=False)
    users = FakeUsers({ALICE: make_user(ALICE, earnings=1.0)}, language="ru")
    fake_db(monkeypatch, users=users)
    bot.user_languages.pop(ALICE, None)
    send = Recorder()
    monkeypatch.setattr(bot, "send_payout_transaction", send)
    message, answer = withdraw_message(ALICE, f"/withdraw {PAYER.to_str()}")

    await bot.cmd_withdraw(message)

    assert send.calls == []
    assert "set_withdrawal_wallet" not in users.names()
    assert "reserve_withdrawal" not in users.names()
    assert "record_withdrawal" not in users.names()
    assert answer.calls[0][0][0] == bot.TRANSLATIONS["ru"]["withdraw_paused"]
    bot.user_languages.pop(ALICE, None)


@pytest.mark.unit
async def test_withdraw_command_cannot_pay_twice_concurrently(monkeypatch):
    monkeypatch.setattr(bot, "WITHDRAWALS_ENABLED", True, raising=False)
    users = FakeUsers({ALICE: make_user(ALICE, earnings=1.0, wallet=PAYER.to_str())})
    fake_db(monkeypatch, users=users)
    sent = []

    async def send_payout_transaction(destination, amount_ton, memo=""):
        sent.append(amount_ton)
        await asyncio.sleep(0)  # let the other command run mid-send

    monkeypatch.setattr(bot, "send_payout_transaction", send_payout_transaction)
    first, _ = withdraw_message(ALICE, "/withdraw")
    second, _ = withdraw_message(ALICE, "/withdraw")

    await asyncio.gather(bot.cmd_withdraw(first), bot.cmd_withdraw(second))

    assert sent == [1.0]
    assert users.users[ALICE].total_withdrawn == 1.0


@pytest.mark.unit
async def test_withdraw_failure_does_not_echo_the_error(monkeypatch):
    monkeypatch.setattr(bot, "WITHDRAWALS_ENABLED", True, raising=False)
    users = FakeUsers({ALICE: make_user(ALICE, earnings=1.0, wallet=PAYER.to_str())})
    fake_db(monkeypatch, users=users)
    monkeypatch.setattr(bot, "send_payout_transaction",
                        Recorder(exc=RuntimeError("liteserver secret-ish detail")))
    bot.user_languages.pop(ALICE, None)
    message, answer = withdraw_message(ALICE, "/withdraw")

    await bot.cmd_withdraw(message)

    reply = answer.calls[0][0][0]
    assert "secret-ish" not in reply
    assert reply == bot.TRANSLATIONS["en"]["withdraw_failed"].format(amount="1.0000")
    # Held, not refunded: the send may have reached the chain.
    assert users.users[ALICE].total_withdrawn == 1.0
    bot.user_languages.pop(ALICE, None)


# ========================
# /withdraw reservation (database.py)
# ========================

class InterleavingConn:
    """A connection where both callers read before either one writes.

    It applies the reservation UPDATE only if its WHERE still holds, the way
    Postgres re-checks a WHERE after waiting on a concurrent UPDATE. If the
    guard is dropped from the SQL, both reservations go through.
    """

    GUARD = "COALESCE(referral_earnings, 0) - COALESCE(total_withdrawn, 0) >= $2"

    def __init__(self, row, readers):
        self.row = row
        self.readers = readers
        self.read = 0
        self.both_read = asyncio.Event()

    async def fetchrow(self, query, user_id):
        self.read += 1
        if self.read >= self.readers:
            self.both_read.set()
        await self.both_read.wait()
        return {"available": self.row["earnings"] - self.row["withdrawn"]}

    async def fetchval(self, query, user_id, amount):
        assert query.lstrip().startswith("UPDATE users")
        if self.GUARD in query and self.row["earnings"] - self.row["withdrawn"] < amount:
            return None
        self.row["withdrawn"] += amount
        return user_id


class OneConnPool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


@pytest.mark.unit
async def test_reserve_withdrawal_pays_a_balance_once_under_concurrency():
    from database import UserRepository
    conn = InterleavingConn({"earnings": 1.0, "withdrawn": 0.0}, readers=2)
    repo = UserRepository(OneConnPool(conn))

    results = await asyncio.gather(repo.reserve_withdrawal(ALICE, 0.05), repo.reserve_withdrawal(ALICE, 0.05))

    assert sorted(results) == [0.0, 1.0]
    assert conn.row["withdrawn"] == 1.0


@pytest.mark.unit
async def test_reserve_withdrawal_respects_the_minimum():
    from database import UserRepository
    conn = InterleavingConn({"earnings": 0.04, "withdrawn": 0.0}, readers=1)
    assert await UserRepository(OneConnPool(conn)).reserve_withdrawal(ALICE, 0.05) == 0.0
    assert conn.row["withdrawn"] == 0.0


# ========================
# Lottery draw
# ========================

class FrozenDatetime(bot.datetime):
    frozen = None

    @classmethod
    def now(cls, tz=None):
        return cls.frozen


async def run_one_draw(monkeypatch):
    """Drive run_sunday_lottery_draw through exactly one draw."""
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) > 1:
            raise StopLoop()

    monkeypatch.setattr(bot, "_sleep", fake_sleep)
    with pytest.raises(StopLoop):
        await bot.run_sunday_lottery_draw()
    return sleeps


@pytest.fixture
def draw_world(monkeypatch):
    users = FakeUsers({ALICE: make_user(ALICE, wallet=PAYER.to_str())}, language="zh")
    # pot: 1000 stars = 1.0 TON. The legacy void has run (draws need it).
    lottery = FakeLottery([(ALICE, 5000)], legacy_voided=True)
    fake_db(monkeypatch, users=users, lottery=lottery)
    dms = []

    async def send_message(chat_id, text, **kwargs):
        dms.append((chat_id, text))

    monkeypatch.setattr(bot, "memeseal_bot", None)
    monkeypatch.setattr(bot, "bot", types.SimpleNamespace(send_message=send_message))
    monkeypatch.setattr(bot.social_poster, "post_lottery_winner", Recorder())
    bot.user_languages.pop(ALICE, None)
    yield users, lottery, dms
    bot.user_languages.pop(ALICE, None)


@pytest.mark.unit
async def test_draw_with_payout_off_sends_no_ton_and_holds_the_prize(monkeypatch, draw_world, no_ton):
    users, lottery, dms = draw_world
    monkeypatch.setattr(bot, "LOTTERY_AUTO_PAYOUT_ENABLED", False, raising=False)
    # A recorder, not a raiser: the old code caught a failed send and fell
    # back to crediting, which would hide that it tried.
    send = Recorder()
    monkeypatch.setattr(bot, "send_payout_transaction", send)

    await run_one_draw(monkeypatch)

    assert send.calls == []
    assert lottery.prize_statuses() == ["held"]
    assert lottery.prizes[0][1:3] == (ALICE, 1.0)
    # Never the /withdraw balance.
    assert "add_referral_earnings" not in users.names()
    texts = [text for _, text in dms]
    assert bot.TRANSLATIONS["zh"]["lottery_payout_paused"].format(amount="1.0000") in texts


@pytest.mark.unit
async def test_prize_is_not_withdrawable_with_only_withdrawals_on(monkeypatch, draw_world):
    """A forged or unbacked pot must not cash out through /withdraw."""
    users, lottery, dms = draw_world
    monkeypatch.setattr(bot, "LOTTERY_AUTO_PAYOUT_ENABLED", False, raising=False)
    monkeypatch.setattr(bot, "WITHDRAWALS_ENABLED", True, raising=False)
    send = Recorder()
    monkeypatch.setattr(bot, "send_payout_transaction", send)

    await bot.execute_lottery_draw()
    message, answer = withdraw_message(ALICE, "/withdraw")
    await bot.cmd_withdraw(message)

    assert send.calls == []
    assert users.users[ALICE].available_balance == 0
    assert "Minimum Withdrawal" in answer.calls[0][0][0]


@pytest.mark.unit
async def test_draw_with_payout_on_sends_to_saved_wallet(monkeypatch, draw_world):
    users, lottery, dms = draw_world
    monkeypatch.setattr(bot, "LOTTERY_AUTO_PAYOUT_ENABLED", True, raising=False)
    lottery.legacy_voided = True
    send = Recorder()
    monkeypatch.setattr(bot, "send_payout_transaction", send)

    await run_one_draw(monkeypatch)

    assert send.calls[0][0][:2] == (PAYER.to_str(), 1.0)
    assert lottery.prize_statuses() == ["sending", "paid"]
    assert "add_referral_earnings" not in users.names()


@pytest.mark.unit
async def test_draw_payout_that_raises_is_held_for_review_not_credited(monkeypatch, draw_world):
    """The send may have reached the chain before raising: crediting would pay twice."""
    users, lottery, dms = draw_world
    monkeypatch.setattr(bot, "LOTTERY_AUTO_PAYOUT_ENABLED", True, raising=False)
    lottery.legacy_voided = True
    send = Recorder(exc=RuntimeError("liteserver closed"))
    monkeypatch.setattr(bot, "send_payout_transaction", send)

    await bot.execute_lottery_draw()

    assert len(send.calls) == 1
    assert lottery.prize_statuses() == ["sending", "review"]
    assert "add_referral_earnings" not in users.names()
    texts = [text for _, text in dms]
    assert bot.TRANSLATIONS["zh"]["lottery_payout_review"].format(amount="1.0000") in texts


@pytest.mark.unit
async def test_draw_payout_on_without_wallet_holds_the_prize(monkeypatch, draw_world, no_ton):
    users, lottery, dms = draw_world
    users.users[ALICE].withdrawal_wallet = None
    monkeypatch.setattr(bot, "LOTTERY_AUTO_PAYOUT_ENABLED", True, raising=False)
    lottery.legacy_voided = True

    await bot.execute_lottery_draw()

    assert lottery.prize_statuses() == ["held"]
    assert "add_referral_earnings" not in users.names()


@pytest.mark.unit
@pytest.mark.parametrize("payout_on", [True, False])
async def test_no_draw_runs_until_the_legacy_entries_are_voided(
        monkeypatch, draw_world, capsys, payout_on):
    """Drawing the legacy pot would promise (and announce) a possibly forged prize.

    And the void would then find nothing to void: the entries would be gone
    into a 'held' prize nobody can tell apart from an honest one.
    """
    users, lottery, dms = draw_world
    lottery.legacy_voided = False
    monkeypatch.setattr(bot, "LOTTERY_AUTO_PAYOUT_ENABLED", payout_on, raising=False)
    send = Recorder()
    monkeypatch.setattr(bot, "send_payout_transaction", send)
    monkeypatch.setattr(bot, "send_ton_transaction", Recorder())

    assert await bot.execute_lottery_draw() is None

    assert send.calls == []
    assert lottery.prizes == []
    assert lottery.entries == [(ALICE, 5000)]  # still in the pot, for the void
    assert dms == []
    assert bot.social_poster.post_lottery_winner.calls == []
    out = capsys.readouterr().out
    assert "LOTTERY DRAW SKIPPED" in out
    assert "/admin/void-legacy-lottery" in out


@pytest.mark.unit
async def test_no_draw_runs_when_the_void_record_cannot_be_read(monkeypatch, draw_world):
    """A database error reading the void record counts as "not voided"."""
    users, lottery, dms = draw_world
    monkeypatch.setattr(bot, "LOTTERY_AUTO_PAYOUT_ENABLED", True, raising=False)

    async def broken():
        raise ConnectionError("db down")

    monkeypatch.setattr(lottery, "legacy_entries_voided", broken)
    send = Recorder()
    monkeypatch.setattr(bot, "send_payout_transaction", send)

    await bot.execute_lottery_draw()

    assert send.calls == []
    assert lottery.prizes == []
    assert lottery.entries == [(ALICE, 5000)]


@pytest.mark.unit
async def test_prize_is_what_the_draw_claimed_not_the_pot_read_before(monkeypatch, draw_world, no_ton):
    """An entry bought between a pot read and the claim used to be drawn but not paid."""
    users, lottery, dms = draw_world
    monkeypatch.setattr(bot, "LOTTERY_AUTO_PAYOUT_ENABLED", False, raising=False)
    real_pick = lottery.pick_winner

    async def pick_after_a_late_entry(draw_id):
        lottery.entries.append((BOB, 5000))  # bought mid-draw
        return await real_pick(draw_id)

    monkeypatch.setattr(lottery, "pick_winner", pick_after_a_late_entry)

    await bot.execute_lottery_draw()

    # Both entries were claimed (10000 stars), so the prize is 2000 stars = 2.0 TON.
    assert lottery.entries == []
    assert lottery.prizes[0][1:4] == (ALICE, 2.0, "held")


@pytest.mark.unit
async def test_draw_with_payout_on_and_legacy_voided_takes_the_send_path(monkeypatch, draw_world):
    users, lottery, dms = draw_world
    monkeypatch.setattr(bot, "LOTTERY_AUTO_PAYOUT_ENABLED", True, raising=False)
    lottery.legacy_voided = True
    send = Recorder()
    monkeypatch.setattr(bot, "send_payout_transaction", send)

    await bot.execute_lottery_draw()

    assert len(send.calls) == 1
    assert send.calls[0][0][:2] == (PAYER.to_str(), 1.0)
    assert lottery.prize_statuses() == ["sending", "paid"]


@pytest.mark.unit
@pytest.mark.parametrize("now,expected", [
    ("2026-10-04 00:00:00", "2026-10-11 00:00:00"),  # exactly at the draw
    ("2026-10-04 00:00:05", "2026-10-11 00:00:00"),  # just after it, still hour 0
    ("2026-10-04 00:59:59", "2026-10-11 00:00:00"),
    ("2026-10-03 23:59:59", "2026-10-04 00:00:00"),  # Saturday night
    ("2026-10-05 12:00:00", "2026-10-11 00:00:00"),  # Monday
])
def test_next_draw_is_strictly_in_the_future(now, expected):
    from datetime import timezone
    fmt = "%Y-%m-%d %H:%M:%S"
    now = bot.datetime.strptime(now, fmt).replace(tzinfo=timezone.utc)
    assert bot.next_lottery_draw_after(now) == bot.datetime.strptime(expected, fmt).replace(tzinfo=timezone.utc)


@pytest.mark.unit
async def test_draw_loop_never_draws_twice_in_one_night(monkeypatch):
    """Frozen at Sunday 00:00:05: the old loop slept a negative time and drew again at once."""
    from datetime import timezone
    FrozenDatetime.frozen = bot.datetime(2026, 10, 4, 0, 0, 5, tzinfo=timezone.utc)
    monkeypatch.setattr(bot, "datetime", FrozenDatetime)
    draws = Recorder()
    monkeypatch.setattr(bot, "execute_lottery_draw", draws)
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) >= 3:
            raise StopLoop()

    monkeypatch.setattr(bot, "_sleep", fake_sleep)
    with pytest.raises(StopLoop):
        await bot.run_sunday_lottery_draw()

    assert all(seconds > 0 for seconds in sleeps)
    # The clock never moved, yet each wake schedules the following Sunday.
    assert sleeps[1] - sleeps[0] == 7 * 86400
    assert len(draws.calls) == 2


# ========================
# TON payment poller
# ========================

def text_body(text):
    return Builder().store_uint(0, 32).store_snake_string(text).end_cell()


def internal(src, nano, body, bounced=False):
    """A real internal message, round-tripped through its BoC encoding as a liteserver returns it."""
    info = InternalMsgInfo(ihr_disabled=True, bounce=False, bounced=bounced, src=src, dest=SERVICE,
                           value=CurrencyCollection(nano), ihr_fee=0, fwd_fee=0,
                           created_lt=1, created_at=1)
    msg = MessageAny(info=info, init=None, body=body)
    return MessageAny.deserialize(msg.serialize().begin_parse())


def external(body=None):
    return MessageAny(info=ExternalMsgInfo(None, SERVICE, 0), init=None, body=body or Cell.empty())


def tx(lt, in_msg, prev_lt=0):
    """A real Transaction. Fields the poller never reads (state_update,
    description) are None: the parser only reads lt and in_msg."""
    return Transaction(account_addr=bytes(32), lt=lt, prev_trans_hash=bytes(32), prev_trans_lt=prev_lt,
                       now=0, outmsg_cnt=0, orig_status=AccountStatus("active"),
                       end_status=AccountStatus("active"), in_msg=in_msg, out_msgs=[],
                       total_fees=CurrencyCollection(0), state_update=None, description=None,
                       cell=Cell.empty())


@pytest.mark.unit
def test_parse_payment_reads_amount_and_comment():
    payment = bot.parse_incoming_payment(tx(5, internal(PAYER, 150_000_000, text_body("123456789"))), SERVICE)
    amount, memo, src = payment
    assert amount == 150_000_000
    assert memo == "123456789"
    assert src == PAYER
    assert bot.memo_user_id(memo) == 123456789


@pytest.mark.unit
def test_parse_payment_long_comment_spanning_cells():
    comment = "x" * 200 + "-tail"
    _, memo, _ = bot.parse_incoming_payment(tx(5, internal(PAYER, 1, text_body(comment))), SERVICE)
    assert memo == comment


@pytest.mark.unit
@pytest.mark.parametrize("service", [
    SERVICE,
    SERVICE.to_str(),
    SERVICE.to_str(is_bounceable=False),
    SERVICE.to_str(is_user_friendly=False),
])
def test_parse_payment_skips_self_transfers(service):
    """Our seals are self-transfers whose comment an API caller can choose."""
    seal = tx(5, internal(SERVICE, 150_000_000, text_body("NotaryTON:424242:abcdef012345")))
    assert bot.parse_incoming_payment(seal, service) is None


@pytest.mark.unit
def test_parse_payment_skips_external_and_bounced_and_empty():
    assert bot.parse_incoming_payment(tx(5, external()), SERVICE) is None
    assert bot.parse_incoming_payment(tx(5, internal(PAYER, 9, text_body("1"), bounced=True)), SERVICE) is None
    assert bot.parse_incoming_payment(tx(5, None), SERVICE) is None


@pytest.mark.unit
def test_parse_payment_non_text_body_has_no_comment():
    jetton_notify = Builder().store_uint(0x7362D09C, 32).store_uint(123456789, 64).end_cell()
    short = Builder().store_uint(0, 8).end_cell()
    for body in (jetton_notify, short, Cell.empty()):
        amount, memo, _ = bot.parse_incoming_payment(tx(5, internal(PAYER, 7, body)), SERVICE)
        assert (amount, memo) == (7, "")


@pytest.mark.unit
@pytest.mark.parametrize("memo,expected", [
    ("123456789", 123456789),
    (" 42 ", 42),
    ("MemeSeal:abc123def4567890", None),
    ("NotaryTON:424242:abcdef012345", None),
    ("SEAL-AB12", None),
    ("", None),
    ("0", None),
    ("9" * 25, None),
])
def test_memo_user_id_is_the_whole_comment(memo, expected):
    assert bot.memo_user_id(memo) == expected


class FakeBalancer:
    """A liteserver: newest first, stopping at to_lt as pytoniq does."""
    transactions = []
    calls = []
    error = None

    @classmethod
    def from_mainnet_config(cls, trust_level=1):
        return cls()

    async def start_up(self):
        pass

    async def get_transactions(self, address, count, from_lt=None, from_hash=None, to_lt=0):
        FakeBalancer.calls.append({"count": count, "to_lt": to_lt})
        if FakeBalancer.error:
            raise FakeBalancer.error
        if not self.transactions:
            # pytoniq indexes the first page's last element: an account with
            # no transactions at all raises IndexError, it does not return [].
            raise IndexError("list index out of range")
        newest_first = sorted(self.transactions, key=lambda t: t.lt, reverse=True)
        return [t for t in newest_first if t.lt > to_lt][:count]

    async def raw_get_account_state(self, address):
        FakeBalancer.calls.append({"account_state": True})
        if not self.transactions:
            return None, None  # pytoniq: an account with no history
        last = max(t.lt for t in self.transactions)
        return object(), types.SimpleNamespace(last_trans_lt=last)

    async def close_all(self):
        pass


class ExplodingTx:
    lt = 6

    @property
    def in_msg(self):
        raise RuntimeError("corrupt message")


class FakeState:
    def __init__(self, values=None, get_errors=0):
        self.values = dict(values or {})
        self.get_errors = get_errors
        self.deleted = []

    async def get(self, key):
        if self.get_errors:
            self.get_errors -= 1
            raise ConnectionError("pool timeout")
        return self.values.get(key)

    async def set(self, key, value):
        self.values[key] = value

    async def delete(self, key):
        self.deleted.append(key)


@pytest.fixture
def poller_world(monkeypatch, no_ton):
    """A poller wired to fakes. Returns (users, state, ledger, waits)."""
    users = FakeUsers({123456789: make_user(123456789, referred_by=555)})
    state = FakeState({bot.TON_POLLER_LT_KEY: "4"})
    db = fake_db(monkeypatch, users=users, bot_state=state)
    FakeBalancer.transactions = []
    FakeBalancer.calls = []
    FakeBalancer.error = None
    monkeypatch.setattr(bot, "LiteBalancer", FakeBalancer)
    monkeypatch.setattr(bot, "SERVICE_TON_WALLET", SERVICE.to_str())
    dms = Recorder()
    monkeypatch.setattr(bot, "bot", types.SimpleNamespace(send_message=dms))
    monkeypatch.setattr(bot, "memeseal_bot", None)
    bot.user_languages.pop(123456789, None)
    waits = []

    async def wait_or_stop(seconds):
        waits.append(seconds)
        if len(waits) >= world.polls:
            raise StopLoop()

    world = types.SimpleNamespace(users=users, state=state, db=db, waits=waits, dms=dms, polls=1)
    monkeypatch.setattr(bot, "_wait_for_poll", wait_or_stop)
    monkeypatch.setattr(bot, "_sleep", wait_or_stop)
    yield world
    bot.user_languages.pop(123456789, None)


async def run_poller():
    with pytest.raises(StopLoop):
        await bot.poll_wallet_for_payments()


def payer_credits(users):
    return [c for c in users.calls if c[0] in ("add_payment", "add_subscription")]


@pytest.mark.unit
async def test_poller_credits_real_payment_and_ignores_self_seals(poller_world):
    FakeBalancer.transactions = [
        tx(7, internal(PAYER, 150_000_000, text_body("123456789"))),
        ExplodingTx(),
        tx(5, internal(SERVICE, 150_000_000, text_body("NotaryTON:424242:abcdef012345"))),
        tx(8, external(text_body("987654321"))),
    ]
    await run_poller()

    users = poller_world.users
    assert payer_credits(users) == [("add_payment", 123456789, 0.15)]
    assert not any(424242 in c or 987654321 in c for c in users.calls)
    assert poller_world.state.values[bot.TON_POLLER_LT_KEY] == "8"
    assert poller_world.db.ton_payments.rows == {bot.ton_tx_key(SERVICE, 7): "credited"}
    assert FakeBalancer.calls[0] == {"count": bot.TON_POLL_MAX_TXS, "to_lt": 4}


@pytest.mark.unit
async def test_poller_credits_payer_before_referrer(poller_world):
    FakeBalancer.transactions = [tx(7, internal(PAYER, 300_000_000, text_body("123456789")))]
    await run_poller()
    names = [c[0] for c in poller_world.users.calls if c[0] in ("add_subscription", "add_referral_earnings")]
    assert names == ["add_subscription", "add_referral_earnings"]
    assert ("add_referral_earnings", 555, 0.015) in poller_world.users.calls
    assert poller_world.db.lottery.entries == [(123456789, 20)]


@pytest.mark.unit
async def test_poller_never_credits_the_same_transaction_twice(poller_world):
    """A restart that re-reads the window (LT lost, rewound, or a second worker) credits nothing new."""
    FakeBalancer.transactions = [tx(7, internal(PAYER, 300_000_000, text_body("123456789")))]
    await run_poller()
    poller_world.waits.clear()
    poller_world.state.values[bot.TON_POLLER_LT_KEY] = "4"  # rewound
    await run_poller()

    assert payer_credits(poller_world.users) == [("add_subscription", 123456789, 1)]
    assert [c for c in poller_world.users.calls if c[0] == "add_referral_earnings"] == [
        ("add_referral_earnings", 555, 0.015)]


@pytest.mark.unit
async def test_poller_does_not_start_from_zero_when_the_lt_cannot_load(poller_world):
    """Old code fell back to LT 0 on a DB error and re-credited the recent history."""
    poller_world.state.get_errors = 2
    poller_world.state.values[bot.TON_POLLER_LT_KEY] = "7"
    poller_world.polls = 3  # two retry sleeps, then one poll
    FakeBalancer.transactions = [
        tx(6, internal(PAYER, 300_000_000, text_body("123456789"))),
        tx(7, internal(PAYER, 150_000_000, text_body("123456789"))),
    ]
    await run_poller()

    assert payer_credits(poller_world.users) == []
    assert poller_world.waits[:2] == [5, 10]
    assert FakeBalancer.calls[0]["to_lt"] == 7


@pytest.mark.unit
async def test_poller_first_run_anchors_at_newest_and_credits_nothing(poller_world):
    del poller_world.state.values[bot.TON_POLLER_LT_KEY]
    FakeBalancer.transactions = [
        tx(6, internal(PAYER, 300_000_000, text_body("123456789"))),
        tx(9, internal(PAYER, 150_000_000, text_body("123456789"))),
    ]
    await run_poller()

    assert payer_credits(poller_world.users) == []
    assert poller_world.state.values[bot.TON_POLLER_LT_KEY] == "9"


@pytest.mark.unit
async def test_poller_keeps_its_lt_on_a_stale_liteserver(poller_world):
    FakeBalancer.error = RuntimeError("lt not in db")
    await run_poller()

    assert poller_world.state.deleted == []
    assert poller_world.state.values[bot.TON_POLLER_LT_KEY] == "4"
    assert payer_credits(poller_world.users) == []


@pytest.mark.unit
async def test_poller_pages_back_past_a_busy_window(poller_world):
    """Seals add two transactions each; ten of them must not hide a payment."""
    seals = [tx(lt, internal(SERVICE, 150_000_000, text_body(f"MemeSeal:{lt:016d}"))) for lt in range(6, 26)]
    FakeBalancer.transactions = [tx(5, internal(PAYER, 150_000_000, text_body("123456789")))] + seals
    await run_poller()

    assert payer_credits(poller_world.users) == [("add_payment", 123456789, 0.15)]
    assert poller_world.state.values[bot.TON_POLLER_LT_KEY] == "25"


@pytest.mark.unit
async def test_poller_small_payment_does_not_promise_a_seal(poller_world):
    poller_world.users.language = "ru"
    FakeBalancer.transactions = [tx(7, internal(PAYER, 50_000_000, text_body("123456789")))]
    await run_poller()

    text = poller_world.dms.calls[0][0][1]
    assert text == bot.TRANSLATIONS["ru"]["ton_payment_short"].format(
        amount="0.0500", balance="0.0500", price="0.15", short="0.1000", memo=123456789)
    assert "`123456789`" in text  # the memo the top-up must carry


@pytest.mark.unit
async def test_failed_credit_is_recorded_for_review(poller_world, monkeypatch):
    async def broken(user_id, months=1):
        raise RuntimeError("db down")

    monkeypatch.setattr(poller_world.users, "add_subscription", broken)
    FakeBalancer.transactions = [tx(7, internal(PAYER, 300_000_000, text_body("123456789")))]
    await run_poller()

    assert poller_world.db.ton_payments.rows == {bot.ton_tx_key(SERVICE, 7): "failed"}
    # The payer's credit failed first, so no commission was paid for it.
    assert [c for c in poller_world.users.calls if c[0] == "add_referral_earnings"] == []
    assert poller_world.state.values[bot.TON_POLLER_LT_KEY] == "7"


# ========================
# TonAPI webhook
# ========================

@pytest.mark.unit
def test_tonapi_webhook_wakes_the_poller_and_credits_nothing(client, monkeypatch):
    """It used to credit from its own body: a second credit of every payment, and
    self-seals credited to whatever number their comment held."""
    monkeypatch.setattr(bot, "TONAPI_WEBHOOK_SECRET", "s3cret")
    monkeypatch.setattr(bot, "db", Untouchable())
    bot._payment_poll_wakeup.clear()
    body = json.dumps({"event_type": "transaction", "transactions": [{
        "account": {"address": SERVICE.to_str(is_user_friendly=False)},
        "in_msg": {"value": 150_000_000, "msg_data": {"@type": "msg.dataText", "text": "NotaryTON:424242:ab"}},
    }]}).encode()
    signature = hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()

    response = client.post("/webhook/tonapi", content=body, headers={"X-TonAPI-Signature": signature})

    assert response.json() == {"ok": True, "queued": True}
    assert bot._payment_poll_wakeup.is_set()
    bot._payment_poll_wakeup.clear()


# ========================
# Notarize API
# ========================

@pytest.fixture
def api_world(monkeypatch):
    users = FakeUsers(subscribers={ALICE})
    db = fake_db(monkeypatch, users=users)
    sends = Recorder()
    monkeypatch.setattr(bot, "send_ton_transaction", sends)
    monkeypatch.setattr(bot, "get_contract_code_from_tx", Recorder(result=b"code"))
    monkeypatch.setattr(bot, "log_notarization", Recorder())
    monkeypatch.setattr(bot, "_api_seal_times", {})
    monkeypatch.setattr(bot, "API_SEALS_PER_HOUR", 3)
    return types.SimpleNamespace(db=db, sends=sends)


@pytest.mark.unit
def test_notarize_api_refuses_a_telegram_id_as_key(client, api_world):
    """Ids are public: any subscriber's id used to make the wallet pay fees on demand."""
    response = client.post("/api/v1/notarize", json={"api_key": str(ALICE), "contract_address": "EQ"})
    assert response.status_code == 401
    assert response.json() == {"success": False, "error": "invalid api key"}
    assert api_world.sends.calls == []


@pytest.mark.unit
async def test_notarize_api_with_issued_key_is_rate_limited(client, api_world):
    key = await bot.issue_api_key(ALICE)
    assert key.startswith("nt_") and str(ALICE) not in key
    assert key not in api_world.db.api_keys.keys  # only the hash is stored

    codes = [client.post("/api/v1/notarize", json={"api_key": key, "contract_address": "EQ"}).status_code
             for _ in range(5)]

    assert codes == [200, 200, 200, 429, 429]
    assert len(api_world.sends.calls) == 3


@pytest.mark.unit
async def test_batch_over_budget_is_refused_whole(client, api_world):
    key = await bot.issue_api_key(ALICE)
    contracts = [{"address": f"EQ{i}"} for i in range(2)]
    first = client.post("/api/v1/batch", json={"api_key": key, "contracts": contracts})
    second = client.post("/api/v1/batch", json={"api_key": key, "contracts": contracts})
    assert (first.status_code, second.status_code) == (200, 429)
    assert len(api_world.sends.calls) == 2  # the second batch sent nothing


@pytest.mark.unit
async def test_batch_larger_than_the_hourly_budget_is_a_400_not_a_429(client, api_world):
    """A 429 says "wait", and waiting never lets a batch above the budget through."""
    key = await bot.issue_api_key(ALICE)
    contracts = [{"address": f"EQ{i}"} for i in range(4)]  # budget is 3
    response = client.post("/api/v1/batch", json={"api_key": key, "contracts": contracts})
    assert response.status_code == 400
    assert response.json() == {"success": False, "error": "batch larger than hourly budget",
                               "limit_per_hour": 3}
    assert api_world.sends.calls == []
    # Nothing was taken from the budget: a batch that fits still goes through.
    ok = client.post("/api/v1/batch", json={"api_key": key, "contracts": contracts[:3]})
    assert ok.status_code == 200


@pytest.mark.unit
async def test_reissued_key_revokes_the_old_one(client, api_world):
    old = await bot.issue_api_key(ALICE)
    await bot.issue_api_key(ALICE)
    response = client.post("/api/v1/notarize", json={"api_key": old, "contract_address": "EQ"})
    assert response.status_code == 401


# ========================
# MemeSeal "pay with TON" seal
# ========================

def tap(user_id=ALICE):
    sent = Recorder()
    edited = Recorder()
    callback = types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=user_id), answer=Recorder(),
        message=types.SimpleNamespace(answer=sent, edit_text=edited))
    return callback, sent, edited


class SealStarter:
    """Stands in for background_seal_*: records the call, returns a no-op coroutine."""

    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)

        async def noop():
            pass
        return noop()


@pytest.fixture
def seal_world(monkeypatch):
    started = SealStarter()
    monkeypatch.setattr(bot, "background_seal_ton", started, raising=False)
    monkeypatch.setattr(bot, "background_seal_stars", started, raising=False)
    monkeypatch.setattr(bot, "_spawn", lambda coro: coro.close())
    monkeypatch.setattr(bot, "pending_files", {ALICE: {"file_id": "f", "file_type": "document", "timestamp": 0}})
    bot.user_languages.pop(ALICE, None)
    yield started
    bot.user_languages.pop(ALICE, None)


@pytest.mark.unit
async def test_pay_with_ton_without_a_credit_does_not_seal(monkeypatch, seal_world, no_ton):
    users = FakeUsers()
    fake_db(monkeypatch, users=users)
    callback, sent, _ = tap()

    await bot.memeseal_ton_single(callback)

    assert seal_world.calls == []
    assert "deduct_payment" not in users.names()
    assert ALICE in bot.pending_files  # kept for when the payment lands
    text = sent.calls[0][0][0]
    assert text == bot.TRANSLATIONS["en"]["ton_seal_need_payment"].format(
        price="0.15", wallet=bot.SERVICE_TON_WALLET, memo=ALICE)


@pytest.mark.unit
async def test_pay_with_ton_with_a_credit_seals_once_and_charges(monkeypatch, seal_world):
    users = FakeUsers(paid={ALICE: 0.15})
    fake_db(monkeypatch, users=users)
    first, _, _ = tap()
    second, second_sent, _ = tap()

    await bot.memeseal_ton_single(first)
    await bot.memeseal_ton_single(second)

    assert len(seal_world.calls) == 1
    assert users.paid[ALICE] == 0.0
    assert ALICE not in bot.pending_files


@pytest.mark.unit
async def test_retry_of_an_unpaid_file_does_not_seal(monkeypatch, seal_world):
    fake_db(monkeypatch, users=FakeUsers())
    callback, sent, _ = tap()

    await bot.memeseal_retry_seal(callback)

    assert seal_world.calls == []
    assert sent.calls[0][0][0] == bot.TRANSLATIONS["en"]["seal_retry_unpaid"]
    assert ALICE in bot.pending_files


@pytest.mark.unit
async def test_retry_of_a_paid_file_seals_without_charging(monkeypatch, seal_world):
    users = FakeUsers()
    fake_db(monkeypatch, users=users)
    bot.pending_files[ALICE]["paid"] = True
    callback, _, _ = tap()

    await bot.memeseal_retry_seal(callback)

    assert len(seal_world.calls) == 1
    assert "deduct_payment" not in users.names()


# ========================
# Casino Mini App entry points
# ========================

@pytest.mark.unit
async def test_casino_command_says_paused_when_off(monkeypatch):
    monkeypatch.setattr(bot, "CASINO_ENABLED", False)
    fake_db(monkeypatch, users=FakeUsers(language="zh"))
    bot.user_languages.pop(ALICE, None)
    message, answer = withdraw_message(ALICE, "/casino")
    await bot.memeseal_casino(message)
    assert answer.calls[0][0][0] == bot.TRANSLATIONS["zh"]["casino_paused"]
    assert "reply_markup" not in answer.calls[0][1]
    bot.user_languages.pop(ALICE, None)


@pytest.mark.unit
@pytest.mark.parametrize("lang", ["en", "ru", "zh"])
def test_new_messages_exist_in_every_language(lang):
    keys = ["withdraw_paused", "withdraw_failed", "lottery_payout_paused", "lottery_prize_held",
            "lottery_payout_review", "casino_paused", "ton_payment_credited", "ton_payment_short",
            "ton_seal_need_payment", "ton_paid_button", "seal_retry_unpaid", "api_requires_sub",
            "api_key_issued"]
    assert set(keys) <= set(bot.TRANSLATIONS[lang])
    assert bot.TRANSLATIONS[lang]["api_key_issued"].format(key="nt_x", url="https://x").count("{hash}") == 1


# ========================
# Payment poller: nothing durable, nothing skipped
# ========================

class BlipTonPayments(FakeTonPayments):
    """The ledger refuses the first write (pool timeout), then works."""

    def __init__(self, failures=1):
        super().__init__()
        self.failures = failures

    async def claim(self, tx_key, user_id, amount_nano):
        if self.failures:
            self.failures -= 1
            raise ConnectionError("pool timeout")
        return await super().claim(tx_key, user_id, amount_nano)


@pytest.mark.unit
async def test_poller_does_not_pass_a_payment_it_could_not_record(poller_world):
    """A claim that raised used to advance the LT: the payment was skipped forever, unrecorded."""
    poller_world.db.ton_payments = BlipTonPayments()
    FakeBalancer.transactions = [tx(7, internal(PAYER, 150_000_000, text_body("123456789")))]
    poller_world.polls = 2
    await run_poller()

    # First poll: the claim failed and the LT stayed; second poll read it again.
    assert [c["to_lt"] for c in FakeBalancer.calls if "to_lt" in c] == [4, 4]
    assert payer_credits(poller_world.users) == [("add_payment", 123456789, 0.15)]
    assert poller_world.db.ton_payments.rows == {bot.ton_tx_key(SERVICE, 7): "credited"}
    assert poller_world.state.values[bot.TON_POLLER_LT_KEY] == "7"


@pytest.mark.unit
async def test_poller_records_ton_it_cannot_credit(poller_world):
    """A wrong memo or dust used to leave nothing but a log line."""
    FakeBalancer.transactions = [
        tx(6, internal(PAYER, 150_000_000, text_body("@alice"))),
        tx(7, internal(PAYER, 1_000_000, text_body("123456789"))),
    ]
    await run_poller()

    ledger = poller_world.db.ton_payments
    assert ledger.rows == {bot.ton_tx_key(SERVICE, 6): "unmatched",
                           bot.ton_tx_key(SERVICE, 7): "unmatched"}
    assert ledger.memos[bot.ton_tx_key(SERVICE, 6)] == "@alice"
    assert payer_credits(poller_world.users) == []
    assert poller_world.state.values[bot.TON_POLLER_LT_KEY] == "7"


@pytest.mark.unit
async def test_poller_records_a_skipped_range_durably(poller_world, monkeypatch):
    monkeypatch.setattr(bot, "TON_POLL_MAX_TXS", 4)
    seals = [tx(lt, internal(SERVICE, 1, text_body("MemeSeal:x")), prev_lt=lt - 1) for lt in range(10, 16)]
    FakeBalancer.transactions = seals
    await run_poller()

    gaps = [k for k in poller_world.state.values if k.startswith(bot.TON_POLLER_GAP_PREFIX)]
    assert gaps == [f"{bot.TON_POLLER_GAP_PREFIX}4:11"]


@pytest.mark.unit
async def test_payer_credited_then_a_later_step_fails_is_partial_not_failed(poller_world, monkeypatch):
    """'failed' tells a reviewer to credit by hand: it must not be used once the payer has been credited."""
    async def broken(user_id, amount_stars=1):
        raise RuntimeError("db down")

    monkeypatch.setattr(poller_world.db.lottery, "add_entry", broken)
    FakeBalancer.transactions = [tx(7, internal(PAYER, 150_000_000, text_body("123456789")))]
    await run_poller()

    assert payer_credits(poller_world.users) == [("add_payment", 123456789, 0.15)]
    assert poller_world.db.ton_payments.rows == {bot.ton_tx_key(SERVICE, 7): "partial"}


@pytest.mark.unit
async def test_a_credit_whose_final_status_write_fails_says_payer_credited(poller_world, monkeypatch, capsys):
    ledger = poller_world.db.ton_payments
    real_set = ledger.set_status

    async def set_status(tx_key, status):
        if status == "credited":
            raise ConnectionError("pool timeout")
        await real_set(tx_key, status)

    monkeypatch.setattr(ledger, "set_status", set_status)
    FakeBalancer.transactions = [tx(7, internal(PAYER, 150_000_000, text_body("123456789")))]
    await run_poller()

    assert ledger.rows == {bot.ton_tx_key(SERVICE, 7): "payer_credited"}
    out = capsys.readouterr().out
    assert "credited in full" in out and "needs manual review" not in out


@pytest.mark.unit
async def test_first_anchor_on_an_empty_wallet_is_zero_and_credits_the_first_payment(poller_world):
    """pytoniq raises IndexError on an empty history; the anchor comes from the account state."""
    del poller_world.state.values[bot.TON_POLLER_LT_KEY]
    poller_world.polls = 2
    await run_poller()  # nothing on the wallet yet
    assert poller_world.state.values[bot.TON_POLLER_LT_KEY] == "0"

    FakeBalancer.transactions = [tx(3, internal(PAYER, 150_000_000, text_body("123456789")))]
    poller_world.waits.clear()
    await run_poller()
    assert payer_credits(poller_world.users) == [("add_payment", 123456789, 0.15)]


@pytest.mark.unit
async def test_first_anchor_records_recent_payments_for_reconciliation(poller_world):
    del poller_world.state.values[bot.TON_POLLER_LT_KEY]
    FakeBalancer.transactions = [
        tx(6, internal(PAYER, 300_000_000, text_body("123456789"))),
        tx(8, internal(SERVICE, 150_000_000, text_body("MemeSeal:abc"))),
        tx(9, internal(PAYER, 150_000_000, text_body("123456789"))),
    ]
    await run_poller()

    assert payer_credits(poller_world.users) == []
    assert poller_world.state.values[bot.TON_POLLER_LT_KEY] == "9"
    assert poller_world.db.ton_payments.rows == {bot.ton_tx_key(SERVICE, 6): "precutover",
                                                 bot.ton_tx_key(SERVICE, 9): "precutover"}


# ========================
# One credit, one seal
# ========================

@pytest.fixture
def document_world(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    seals = []

    async def slow_seal(comment, amount_ton=0.005, retries=3):
        seals.append(comment)
        await asyncio.sleep(0.01)  # a real seal takes seconds

    async def get_file(file_id):
        return types.SimpleNamespace(file_path=file_id)

    async def download_file(src, dst):
        with open(dst, "w") as f:
            f.write(src)

    monkeypatch.setattr(bot, "send_ton_transaction", slow_seal)
    monkeypatch.setattr(bot, "log_notarization", Recorder())
    monkeypatch.setattr(bot, "bot", types.SimpleNamespace(get_file=get_file, download_file=download_file))
    return seals


def document_message(i, user_id=ALICE):
    return types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=user_id),
        document=types.SimpleNamespace(file_id=f"file{i}", file_name=f"f{i}.txt"),
        answer=Recorder())


@pytest.mark.unit
async def test_one_credit_buys_one_seal_under_concurrent_uploads(monkeypatch, document_world):
    """Each upload used to pass the balance check before any of them debited."""
    users = FakeUsers(paid={ALICE: bot.TON_SINGLE_SEAL})
    fake_db(monkeypatch, users=users)

    await asyncio.gather(*[bot.handle_document(document_message(i)) for i in range(5)])

    assert len(document_world) == 1
    assert users.paid[ALICE] == 0.0


@pytest.mark.unit
async def test_a_seal_that_fails_before_sending_gives_the_credit_back(monkeypatch, document_world):
    users = FakeUsers(paid={ALICE: bot.TON_SINGLE_SEAL})
    fake_db(monkeypatch, users=users)
    monkeypatch.setattr(bot, "send_ton_transaction", Recorder(exc=RuntimeError("liteserver down")))

    await bot.handle_document(document_message(1))

    assert users.paid[ALICE] == pytest.approx(bot.TON_SINGLE_SEAL)


# ========================
# MemeSeal "pay with TON": the paths a paying user takes
# ========================

@pytest.mark.unit
async def test_paid_button_after_the_file_expired_does_not_ask_for_payment_again(monkeypatch, seal_world):
    users = FakeUsers(paid={ALICE: 0.15})
    fake_db(monkeypatch, users=users)
    bot.pending_files.clear()  # the cleanup task expired the file
    callback, sent, _ = tap()

    await bot.memeseal_ton_single(callback)

    assert sent.calls[0][0][0] == bot.TRANSLATIONS["en"]["ton_credit_send_file"]
    assert users.paid[ALICE] == 0.15  # nothing charged without a file


@pytest.mark.unit
async def test_unpaid_tap_keeps_the_file_fresh_and_a_second_tap_says_not_yet(monkeypatch, seal_world):
    fake_db(monkeypatch, users=FakeUsers())
    first, first_sent, _ = tap()
    await bot.memeseal_ton_single(first)
    assert bot.pending_files[ALICE]["timestamp"] > time.time() - 5  # outlives the credit delay

    second, second_sent, _ = tap()
    await bot.memeseal_ton_single(second)

    assert len(first_sent.calls) == 1   # the instructions, once
    assert second_sent.calls == []      # not a second payment request
    assert second.answer.calls == [((bot.TRANSLATIONS["en"]["ton_not_credited_yet"],), {"show_alert": True})]
    assert ALICE in bot.pending_files
    assert seal_world.calls == []


@pytest.mark.unit
async def test_ton_button_on_a_stars_paid_file_seals_without_charging(monkeypatch, seal_world):
    users = FakeUsers(paid={ALICE: 0.15})
    fake_db(monkeypatch, users=users)
    bot.pending_files[ALICE]["paid"] = True  # Stars invoice paid, the seal failed
    callback, _, _ = tap()

    await bot.memeseal_ton_single(callback)

    assert len(seal_world.calls) == 1
    assert seal_world.calls[0]["file_info"]["paid"] is True
    assert "deduct_payment" not in users.names()
    assert users.paid[ALICE] == 0.15


@pytest.mark.unit
async def test_ton_button_on_a_stars_paid_file_without_credit_keeps_it_paid(monkeypatch, seal_world):
    fake_db(monkeypatch, users=FakeUsers())
    bot.pending_files[ALICE]["paid"] = True
    callback, sent, _ = tap()

    await bot.memeseal_ton_single(callback)

    assert len(seal_world.calls) == 1
    assert seal_world.calls[0]["file_info"]["paid"] is True
    assert not any(c[0][0] == bot.TRANSLATIONS["en"]["ton_seal_need_payment"].format(
        price="0.15", wallet=bot.SERVICE_TON_WALLET, memo=ALICE) for c in sent.calls)


# ========================
# Stars payments for chips
# ========================

def pre_checkout(payload, user_id=ALICE):
    return types.SimpleNamespace(invoice_payload=payload, from_user=types.SimpleNamespace(id=user_id),
                                 answer=Recorder())


@pytest.mark.unit
async def test_chip_payment_is_declined_while_the_casino_is_off(monkeypatch):
    monkeypatch.setattr(bot, "CASINO_ENABLED", False)
    fake_db(monkeypatch, users=FakeUsers(language="ru"))
    bot.user_languages.pop(ALICE, None)
    query = pre_checkout(f"casino_chips_{ALICE}_100_1")

    await bot.answer_pre_checkout(query)

    assert query.answer.calls == [((), {"ok": False, "error_message":
                                        bot.TRANSLATIONS["ru"]["casino_paused_checkout"]})]
    bot.user_languages.pop(ALICE, None)


@pytest.mark.unit
@pytest.mark.parametrize("payload,casino", [(f"casino_chips_{ALICE}_100_1", True),
                                            (f"single_{ALICE}", False), ("ms_sub_1", False)])
async def test_other_payments_are_approved(monkeypatch, payload, casino):
    monkeypatch.setattr(bot, "CASINO_ENABLED", casino)
    query = pre_checkout(payload)
    await bot.answer_pre_checkout(query)
    assert query.answer.calls == [((), {"ok": True})]


class ChipCasino(FakeCasino):
    async def add_chips(self, user_id, amount):
        self.chips[user_id] = self.chips.get(user_id, 0) + amount
        return self.chips[user_id]


@pytest.mark.unit
async def test_memeseal_chip_payment_credits_chips_not_a_seal(monkeypatch):
    """Chip invoices are issued by MemeSeal, whose handler used to sell a seal credit instead."""
    users = FakeUsers()
    casino = ChipCasino()
    db = fake_db(monkeypatch, users=users, casino=casino)
    message = types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=ALICE), answer=Recorder(),
        successful_payment=types.SimpleNamespace(invoice_payload=f"casino_chips_{ALICE}_100_1",
                                                 total_amount=100))

    await bot.memeseal_payment_success(message)

    assert casino.chips[ALICE] == 110  # 100 bought, 10% bonus
    assert "add_payment" not in users.names()
    assert db.lottery.entries == []    # wagers make entries, not purchases


# ========================
# Odds, referral link
# ========================

@pytest.mark.unit
async def test_odds_follow_stars_like_the_draw(monkeypatch):
    lottery = FakeLottery([(ALICE, 20)] + [(BOB, 1)] * 20)
    fake_db(monkeypatch, lottery=lottery)
    # One 20-star entry against twenty 1-star entries: even odds, not 1 in 21.
    assert await bot.lottery_win_chance(ALICE) == pytest.approx(50.0)
    fake_db(monkeypatch, lottery=FakeLottery())
    assert await bot.lottery_win_chance(ALICE) == 0.0


@pytest.mark.unit
@pytest.mark.parametrize("subscribed", [True, False])
async def test_memeseal_api_shows_the_referral_link(monkeypatch, subscribed):
    fake_db(monkeypatch, users=FakeUsers(subscribers={ALICE} if subscribed else ()))
    bot.user_languages.pop(ALICE, None)
    message, answer = withdraw_message(ALICE, "/api")

    await bot.memeseal_api(message)

    text = answer.calls[0][0][0]
    assert f"https://t.me/{bot.BOT_USERNAME}?start=REF{ALICE}" in text
    assert ("nt_" in text) is subscribed


@pytest.mark.unit
@pytest.mark.parametrize("lang", ["en", "ru", "zh"])
def test_review_messages_exist_in_every_language(lang):
    keys = ["ton_credit_send_file", "ton_not_credited_yet", "casino_paused_checkout",
            "referral_link_line"]
    assert set(keys) <= set(bot.TRANSLATIONS[lang])
    assert "{memo}" in bot.TRANSLATIONS[lang]["ton_payment_short"]
    assert "{url}" in bot.TRANSLATIONS[lang]["referral_link_line"]


@pytest.mark.unit
async def test_api_command_issues_a_key_to_a_subscriber(monkeypatch):
    """localized(user_id, key, **fields) clashed with api_key_issued's {key} field: /api raised."""
    fake_db(monkeypatch, users=FakeUsers(subscribers={ALICE}))
    bot.user_languages.pop(ALICE, None)
    message, answer = withdraw_message(ALICE, "/api")

    await bot.cmd_api(message)

    assert "`nt_" in answer.calls[0][0][0]


@pytest.mark.unit
def test_public_copy_matches_the_api_and_the_poller():
    """The homepage told developers to send their Telegram id; the TON flows promised ~1 minute."""
    import inspect
    from pathlib import Path
    landing = (Path(bot.__file__).parent / "templates" / "landing.html").read_text()
    assert "your_telegram_id" not in landing and '"api_key": "nt_' in landing
    source = inspect.getsource(bot)
    assert "~1 minute" not in source
    assert bot.TON_POLL_INTERVAL <= 180  # "within about 3 minutes" stays true
