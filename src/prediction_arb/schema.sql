CREATE TABLE IF NOT EXISTS positions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at          TEXT    NOT NULL,
    pair_key            TEXT    NOT NULL,
    title               TEXT    NOT NULL,
    kalshi_market_id    TEXT    NOT NULL,
    poly_market_id      TEXT    NOT NULL,
    kalshi_side         TEXT    NOT NULL CHECK (kalshi_side IN ('yes', 'no')),
    poly_side           TEXT    NOT NULL CHECK (poly_side IN ('yes', 'no')),
    kalshi_price        REAL    NOT NULL,
    poly_price          REAL    NOT NULL,
    contracts           INTEGER NOT NULL,
    total_cost_usd      REAL    NOT NULL,
    fees_usd            REAL    NOT NULL,
    expected_profit_usd REAL    NOT NULL,
    match_score         REAL    NOT NULL,
    status              TEXT    NOT NULL,  -- dry_run | open | failed | unhedged | closed
    closed_at           TEXT,
    actual_profit_usd   REAL
);

CREATE INDEX IF NOT EXISTS idx_positions_status ON positions (status);
CREATE INDEX IF NOT EXISTS idx_positions_pair_key ON positions (pair_key);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id  INTEGER NOT NULL REFERENCES positions (id),
    created_at   TEXT    NOT NULL,
    platform     TEXT    NOT NULL CHECK (platform IN ('kalshi', 'polymarket')),
    ok           INTEGER NOT NULL,
    order_id     TEXT,
    status       TEXT,
    error        TEXT,
    raw_response TEXT
);
