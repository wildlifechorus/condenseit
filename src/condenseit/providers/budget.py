"""OpenRouter spend tracking."""

from __future__ import annotations

import threading
from datetime import UTC, date, datetime

from condenseit.store.database import ContentStore


class BudgetTracker:
    def __init__(
        self,
        store: ContentStore,
        daily_limit: float,
        monthly_limit: float,
        digest_run_id: str = "",
    ) -> None:
        self.store = store
        self.daily_limit = daily_limit
        self.monthly_limit = monthly_limit
        self.digest_run_id = digest_run_id
        # Serialize all DB access so concurrent summarizer workers don't
        # trigger sqlite3.InterfaceError (SQLITE_MISUSE) on the shared conn.
        self._lock = threading.Lock()

    @property
    def today_spend(self) -> float:
        today = date.today().isoformat()
        with self._lock:
            row = self.store.db.execute(
                "SELECT COALESCE(SUM(amount_usd), 0) FROM spending WHERE recorded_at >= ?",
                [today],
            ).fetchone()
        return float(row[0])

    @property
    def month_spend(self) -> float:
        month_start = date.today().replace(day=1).isoformat()
        with self._lock:
            row = self.store.db.execute(
                "SELECT COALESCE(SUM(amount_usd), 0) FROM spending WHERE recorded_at >= ?",
                [month_start],
            ).fetchone()
        return float(row[0])

    def can_spend(self) -> bool:
        return (
            self.today_spend < self.daily_limit
            and self.month_spend < self.monthly_limit
        )

    def record_spend(self, amount: float, model: str = "", tokens: int = 0) -> None:
        with self._lock:
            self.store.db["spending"].insert(
                {
                    "amount_usd": amount,
                    "model": model,
                    "tokens": tokens,
                    "recorded_at": datetime.now(UTC).isoformat(),
                    "digest_run_id": self.digest_run_id,
                },
            )
