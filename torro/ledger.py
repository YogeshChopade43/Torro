import sqlite3
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Literal

BudgetStatus = Literal["ok", "warn", "over"]
WARN_AT = 0.8


class CostLedger:
    """Claude spend per day, persisted in SQLite."""

    def __init__(self, db_path: Path, daily_budget_inr: float, usd_to_inr: float,
                 today: Callable[[], date] = date.today):
        self.budget_inr = daily_budget_inr
        self.usd_to_inr = usd_to_inr
        self.today = today
        self.db = sqlite3.connect(db_path)
        self.db.execute("CREATE TABLE IF NOT EXISTS costs (day TEXT, usd REAL)")

    def add(self, usd: float) -> None:
        with self.db:
            self.db.execute("INSERT INTO costs VALUES (?, ?)", (self.today().isoformat(), usd))

    def spent_today_inr(self) -> float:
        (usd,) = self.db.execute(
            "SELECT COALESCE(SUM(usd), 0) FROM costs WHERE day = ?", (self.today().isoformat(),)
        ).fetchone()
        return usd * self.usd_to_inr

    def status(self) -> BudgetStatus:
        # Round away float noise so exactly 80% / 100% hit the threshold.
        frac = round(self.spent_today_inr() / self.budget_inr, 9)
        return "over" if frac >= 1 else "warn" if frac >= WARN_AT else "ok"

    def remaining_usd(self) -> float:
        return max(0.0, (self.budget_inr - self.spent_today_inr()) / self.usd_to_inr)
