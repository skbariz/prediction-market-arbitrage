"""SQLite persistence for positions and the orders submitted for them."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any

from prediction_arb.models import Position, PositionStatus

_ACTIVE_STATUSES = (PositionStatus.OPEN.value, PositionStatus.UNHEDGED.value)


class PositionStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        self.db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not self.db_path.exists():
            # Trade history is private; SQLite gives its journal files the same permissions.
            os.close(os.open(self.db_path, os.O_CREAT | os.O_WRONLY, 0o600))
        schema = resources.files("prediction_arb").joinpath("schema.sql").read_text()
        with closing(self._connect()) as conn, conn:
            conn.executescript(schema)

    def save(self, position: Position) -> int:
        opp = position.opportunity
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                """INSERT INTO positions (
                       created_at, pair_key, title, kalshi_market_id, poly_market_id,
                       kalshi_side, poly_side, kalshi_price, poly_price, contracts,
                       total_cost_usd, fees_usd, expected_profit_usd, match_score, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    position.created_at.isoformat(),
                    opp.key,
                    opp.kalshi_market.title,
                    opp.kalshi_market.market_id,
                    opp.poly_market.market_id,
                    opp.kalshi_side.value,
                    opp.poly_side.value,
                    opp.kalshi_price,
                    opp.poly_price,
                    opp.contracts,
                    round(opp.total_cost, 6),
                    round(opp.total_fees, 6),
                    round(opp.net_profit_usd, 6),
                    opp.match_score,
                    position.status.value,
                ),
            )
            position_id = int(cur.lastrowid or 0)
            now = datetime.now(timezone.utc).isoformat()
            for order in (position.kalshi_order, position.poly_order):
                if order is None:
                    continue
                conn.execute(
                    """INSERT INTO orders (position_id, created_at, platform, ok, order_id,
                                           status, error, raw_response)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        position_id,
                        now,
                        order.platform.value,
                        int(order.ok),
                        order.order_id,
                        order.status,
                        order.error,
                        json.dumps(order.raw, default=str),
                    ),
                )
        position.id = position_id
        return position_id

    def active_pair_keys(self) -> set[str]:
        """Pairs with live exposure (open or unhedged). These are never re-entered automatically."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT DISTINCT pair_key FROM positions WHERE status IN (?, ?)", _ACTIVE_STATUSES
            ).fetchall()
        return {row["pair_key"] for row in rows}

    def list_positions(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = "SELECT * FROM positions"
        params: tuple[Any, ...] = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY id DESC LIMIT ?"
        with closing(self._connect()) as conn:
            rows = conn.execute(query, (*params, limit)).fetchall()
        return [dict(row) for row in rows]
