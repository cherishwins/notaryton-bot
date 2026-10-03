"""
Tests for the FastAPI app in bot.py: pages render, webhooks and admin
endpoints fail closed, and Telegram registration never blocks startup.

Nothing here reaches Telegram, TON or the database: secrets are set on the
module per test, and the app runs without its startup hook.
"""

import asyncio
import os
import types

import pytest

# aiogram validates the token shape at import; any <digits>:<secret> works.
os.environ.setdefault("BOT_TOKEN", "123456:TEST-placeholder-token")

import bot  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client():
    # No `with`: the startup hook (DB, Telegram) does not run.
    return TestClient(bot.app, raise_server_exceptions=False)


@pytest.fixture
def secrets_unset(monkeypatch):
    for name in ("TELEGRAM_WEBHOOK_SECRET", "TONAPI_WEBHOOK_SECRET",
                 "TONCONSOLE_CASINO_SECRET", "TONCONSOLE_TOKENS_SECRET", "ADMIN_SECRET"):
        monkeypatch.setattr(bot, name, "")


# ========================
# Jinja pages
# ========================

@pytest.mark.unit
@pytest.mark.parametrize("path", [
    "/", "/verify", "/whitepaper", "/score", "/notaryton",
    "/memescan", "/memescan/litepaper",
])
def test_template_pages_render(client, path):
    """TemplateResponse(request, name, ...) works on current Starlette."""
    response = client.get(path)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# ========================
# Telegram webhook
# ========================

@pytest.mark.unit
def test_bot_token_is_not_the_webhook_path():
    assert bot.WEBHOOK_PATH == "/webhook/telegram"
    assert bot.BOT_TOKEN not in bot.WEBHOOK_PATH


@pytest.mark.unit
def test_telegram_webhook_rejects_missing_secret_header(client, monkeypatch):
    monkeypatch.setattr(bot, "TELEGRAM_WEBHOOK_SECRET", "s3cret")
    response = client.post(bot.WEBHOOK_PATH, json={"update_id": 1})
    assert response.status_code == 401


@pytest.mark.unit
def test_telegram_webhook_rejects_wrong_secret_header(client, monkeypatch):
    monkeypatch.setattr(bot, "TELEGRAM_WEBHOOK_SECRET", "s3cret")
    response = client.post(bot.WEBHOOK_PATH, json={"update_id": 1},
                           headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"})
    assert response.status_code == 401


@pytest.mark.unit
def test_telegram_webhook_rejects_everything_when_secret_unset(client, secrets_unset):
    response = client.post(bot.WEBHOOK_PATH, json={"update_id": 1},
                           headers={"X-Telegram-Bot-Api-Secret-Token": ""})
    assert response.status_code == 401


@pytest.mark.unit
def test_telegram_webhook_accepts_matching_secret(client, monkeypatch):
    fed = []

    async def feed_update(tg_bot, update):
        fed.append(update.update_id)

    monkeypatch.setattr(bot, "TELEGRAM_WEBHOOK_SECRET", "s3cret")
    monkeypatch.setattr(bot.dp, "feed_update", feed_update)
    response = client.post(bot.WEBHOOK_PATH, json={"update_id": 7},
                           headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"})
    assert response.status_code == 200
    assert fed == [7]


# ========================
# TonAPI / TonConsole webhooks
# ========================

@pytest.mark.unit
@pytest.mark.parametrize("path", ["/webhook/tonapi", "/webhook/casino", "/webhook/tokens"])
def test_contract_webhooks_reject_when_secret_unset(client, secrets_unset, path):
    """An unsigned forged payment must never be processed."""
    response = client.post(path, json={"event_type": "transaction", "transactions": []})
    assert response.status_code == 503
    assert response.json()["ok"] is False


@pytest.mark.unit
@pytest.mark.parametrize("path,secret_name,header", [
    ("/webhook/tonapi", "TONAPI_WEBHOOK_SECRET", "X-TonAPI-Signature"),
    ("/webhook/casino", "TONCONSOLE_CASINO_SECRET", "X-Signature"),
    ("/webhook/tokens", "TONCONSOLE_TOKENS_SECRET", "X-Signature"),
])
def test_contract_webhooks_reject_bad_signature(client, monkeypatch, path, secret_name, header):
    monkeypatch.setattr(bot, secret_name, "s3cret")
    for headers in ({}, {header: "0" * 64}):
        response = client.post(path, json={"event_type": "transaction", "transactions": []},
                               headers=headers)
        assert response.status_code == 401


# ========================
# Admin endpoints
# ========================

ADMIN_CALLS = [
    ("/admin/seed-lottery", {"amount_stars": 1}),
    ("/admin/import-ton-labels", {}),
    ("/admin/void-legacy-lottery", {}),
    ("/api/v1/kols/seed", {}),
]


@pytest.mark.unit
@pytest.mark.parametrize("path,params", ADMIN_CALLS)
def test_admin_disabled_when_secret_unset(client, secrets_unset, path, params):
    # The old hardcoded default must not work either.
    response = client.post(path, params={**params, "secret": "memeseal-admin-2024"},
                           headers={"X-Admin-Secret": "memeseal-admin-2024"})
    assert response.status_code == 401


@pytest.mark.unit
@pytest.mark.parametrize("path,params", ADMIN_CALLS)
def test_admin_rejects_secret_in_query_or_wrong_header(client, monkeypatch, path, params):
    monkeypatch.setattr(bot, "ADMIN_SECRET", "s3cret")
    assert client.post(path, params={**params, "secret": "s3cret"}).status_code == 401
    assert client.post(path, params=params, headers={"X-Admin-Secret": "nope"}).status_code == 401


# ========================
# Startup
# ========================

class FlakyBot:
    """Stands in for aiogram's Bot: fails `failures` times, then accepts."""

    token = "123456:TEST-placeholder-token"

    def __init__(self, failures):
        self.failures = failures
        self.calls = []

    async def set_webhook(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if len(self.calls) <= self.failures:
            raise RuntimeError(f"cannot reach https://api.telegram.org/bot{self.token}/setWebhook")
        return True


@pytest.mark.unit
async def test_register_webhook_retries_with_backoff(monkeypatch, capsys):
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(bot.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(bot, "TELEGRAM_WEBHOOK_SECRET", "s3cret")
    tg = FlakyBot(failures=3)

    await bot.register_webhook(tg, bot.WEBHOOK_PATH, "NotaryTON")

    assert len(tg.calls) == 4
    assert sleeps == [5, 10, 20]
    url, kwargs = tg.calls[-1]
    assert url == f"{bot.WEBHOOK_URL}/webhook/telegram"
    assert kwargs["secret_token"] == "s3cret"
    assert kwargs["drop_pending_updates"] is False
    out = capsys.readouterr().out
    assert tg.token not in out
    assert "registered" in out


@pytest.mark.unit
async def test_startup_does_not_wait_for_telegram_or_poll_without_wallet(monkeypatch, tmp_path, capsys):
    """on_startup returns at once; registration and polling are background tasks."""
    started = []

    def create_task(coro):
        started.append(coro.__qualname__)
        coro.close()

    async def noop(*args, **kwargs):
        return None

    async def unreachable(*args, **kwargs):
        raise RuntimeError("Telegram unreachable")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bot, "asyncio", types.SimpleNamespace(create_task=create_task))
    monkeypatch.setattr(bot.db, "connect", noop)
    monkeypatch.setattr(bot.social_poster, "initialize", lambda: None)
    monkeypatch.setattr(bot, "bot", types.SimpleNamespace(get_me=unreachable, set_webhook=unreachable))
    monkeypatch.setattr(bot, "memeseal_bot", None)
    monkeypatch.setattr(bot, "memescan_bot", None)
    monkeypatch.setattr(bot, "GROUP_IDS", [])
    monkeypatch.setattr(bot, "TELEGRAM_WEBHOOK_SECRET", "s3cret")
    monkeypatch.setattr(bot, "SERVICE_TON_WALLET", None)

    await bot.on_startup()

    assert "register_webhook" in started
    assert "poll_wallet_for_payments" not in started
    assert "SERVICE_TON_WALLET is not set" in capsys.readouterr().out


@pytest.mark.unit
async def test_startup_completes_while_telegram_hangs(monkeypatch, tmp_path):
    """A Telegram that accepts and never answers must not hold up startup."""
    started = []

    def create_task(coro):
        started.append(coro.__qualname__)
        coro.close()

    async def noop(*args, **kwargs):
        return None

    async def hang(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bot, "asyncio", types.SimpleNamespace(create_task=create_task))
    monkeypatch.setattr(bot.db, "connect", noop)
    monkeypatch.setattr(bot.social_poster, "initialize", lambda: None)
    hung = types.SimpleNamespace(get_me=hang, send_message=hang, set_webhook=hang)
    monkeypatch.setattr(bot, "bot", hung)
    monkeypatch.setattr(bot, "memeseal_bot", hung)
    monkeypatch.setattr(bot, "memescan_bot", None)
    monkeypatch.setattr(bot, "GROUP_IDS", ["-1001", "-1002"])
    monkeypatch.setattr(bot, "TELEGRAM_WEBHOOK_SECRET", "s3cret")

    await asyncio.wait_for(bot.on_startup(), timeout=2)

    assert "announce_bots" in started
    assert "register_webhook" in started


@pytest.mark.unit
async def test_announce_bots_sets_usernames_and_announces(monkeypatch):
    sent = []

    async def get_me():
        return types.SimpleNamespace(username="NotaryTest_bot")

    async def get_ms():
        return types.SimpleNamespace(username="MemeSealTest_bot")

    async def send_message(chat_id, text):
        sent.append(chat_id)

    monkeypatch.setattr(bot, "BOT_USERNAME", "NotaryTON_bot")
    monkeypatch.setattr(bot, "MEMESEAL_USERNAME", "MemeSealTON_bot")
    monkeypatch.setattr(bot, "bot", types.SimpleNamespace(get_me=get_me, send_message=send_message))
    monkeypatch.setattr(bot, "memeseal_bot", types.SimpleNamespace(get_me=get_ms))
    monkeypatch.setattr(bot, "GROUP_IDS", ["-1001", " "])

    await bot.announce_bots()

    assert bot.BOT_USERNAME == "NotaryTest_bot"
    assert bot.MEMESEAL_USERNAME == "MemeSealTest_bot"
    assert sent == ["-1001"]
