CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    kalshi_market_id TEXT NOT NULL,
    poly_market_id TEXT NOT NULL,
    kalshi_side TEXT NOT NULL,       -- 'yes' or 'no'
    poly_side TEXT NOT NULL,
    kalshi_price REAL NOT NULL,
    poly_price REAL NOT NULL,
    size_usd REAL NOT NULL,
    expected_profit_usd REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',  -- open | closed | failed
    closed_at TEXT,
    actual_profit_usd REAL
);

CREATE TABLE IF NOT EXISTS trade_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER REFERENCES positions(id),
    timestamp TEXT NOT NULL,
    platform TEXT NOT NULL,          -- 'kalshi' or 'polymarket'
    market_id TEXT NOT NULL,
    side TEXT NOT NULL,
    price REAL NOT NULL,
    size REAL NOT NULL,
    order_id TEXT,
    status TEXT NOT NULL,            -- submitted | filled | failed
    raw_response TEXT
);
