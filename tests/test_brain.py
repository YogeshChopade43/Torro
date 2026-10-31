import asyncio
from datetime import date

from torro.brain import Brain, build_system_prompt
from torro.config import Config
from torro.ledger import CostLedger


def cfg_for(tmp_path):
    return Config(
        anthropic_api_key="k", telegram_bot_token="t", telegram_owner_id=1,
        workspace=tmp_path / "ws", data_dir=tmp_path, chat_model="m", task_model="m",
        daily_budget_inr=100, usd_to_inr=100.0, approval_timeout_s=1, shell_allowlist=("ls",),
    )


async def yes(_):
    return True


sent = []


async def collect(text):
    sent.append(text)


def test_prompt_has_name_and_date():
    p = build_system_prompt("Call him Yogesh.", date(2026, 11, 1))
    assert p["preset"] == "claude_code" and "Yogesh" in p["append"] and "2026-11-01" in p["append"]


def test_start_task_refused_when_over_budget(tmp_path):
    led = CostLedger(tmp_path / "c.db", 100, 100.0)
    led.add(5)
    b = Brain(cfg_for(tmp_path), led, approver=yes, notify=collect)
    assert "Budget" in asyncio.run(b.start_task("research phones"))


def test_stop_cancels_tasks(tmp_path, monkeypatch):
    b = Brain(cfg_for(tmp_path), CostLedger(tmp_path / "c.db", 100, 100.0), yes, collect)
    monkeypatch.setattr(b, "_run_task", lambda d: asyncio.sleep(60))

    async def go():
        await b.start_task("x")
        await b.start_task("y")
        return await b.stop_everything()

    assert asyncio.run(go()) == 2


def test_chat_failure_reconnects(tmp_path, monkeypatch):
    b = Brain(cfg_for(tmp_path), CostLedger(tmp_path / "c.db", 100, 100.0), yes, collect)

    class DeadClient:
        async def query(self, _): raise RuntimeError("CLI died")
        async def disconnect(self): pass

    starts = []
    async def fake_start(): starts.append(1)
    b._client, b._chat_cost_seen = DeadClient(), 5.0
    monkeypatch.setattr(b, "start", fake_start)

    async def go():
        try:
            await b.chat("hi")
        except RuntimeError:
            pass
    asyncio.run(go())
    assert starts == [1] and b._chat_cost_seen == 0
