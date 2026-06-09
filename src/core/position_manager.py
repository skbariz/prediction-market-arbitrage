import sqlite3
import json
from datetime import datetime
from typing import List
from src.models.position import Position
from src.utils.logger import logger

DB_PATH = "db/positions.db"


def init_db():
    with open("db/schema.sql") as f:
        schema = f.read()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(schema)
    conn.commit()
    conn.close()


def save_position(pos: Position) -> int:
    opp = pos.opportunity
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO positions
           (created_at, kalshi_market_id, poly_market_id, kalshi_side, poly_side,
            kalshi_price, poly_price, size_usd, expected_profit_usd, status)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            pos.created_at.isoformat(),
            opp.kalshi_market.market_id,
            opp.poly_market.market_id,
            opp.kalshi_side,
            opp.poly_side,
            opp.kalshi_entry,
            opp.poly_entry,
            pos.size_usd,
            opp.net_profit_usd,
            pos.status,
        ),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def log_trade(position_id: int, platform: str, market_id: str, side: str,
              price: float, size: float, order_id: str, status: str, raw: dict):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO trade_log
           (position_id, timestamp, platform, market_id, side, price, size, order_id, status, raw_response)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            position_id,
            datetime.utcnow().isoformat(),
            platform, market_id, side, price, size, order_id, status,
            json.dumps(raw),
        ),
    )
    conn.commit()
    conn.close()


def get_open_positions() -> List[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM positions WHERE status='open'").fetchall()
    conn.close()
    return [dict(r) for r in rows]
