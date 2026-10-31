from datetime import date

import pytest

from torro.ledger import CostLedger


def ledger(tmp_path, day=date(2026, 11, 1)):
    d = {"v": day}
    return CostLedger(tmp_path / "c.db", 100, 100.0, today=lambda: d["v"]), d


def test_thresholds(tmp_path):
    l, _ = ledger(tmp_path)
    assert l.status() == "ok"
    l.add(0.79)
    assert l.status() == "ok"
    l.add(0.01)
    assert l.status() == "warn"
    l.add(0.20)
    assert l.status() == "over" and l.remaining_usd() == 0


def test_resets_next_day_and_persists(tmp_path):
    l, d = ledger(tmp_path)
    l.add(1.0)
    d["v"] = date(2026, 11, 2)
    assert l.spent_today_inr() == 0
    d["v"] = date(2026, 11, 1)
    l2 = CostLedger(tmp_path / "c.db", 100, 100.0, today=lambda: d["v"])
    assert l2.spent_today_inr() == pytest.approx(100.0)
