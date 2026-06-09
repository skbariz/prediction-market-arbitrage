# Prediction Market Arbitrage Bot — Summary

**Last updated:** 2026-06-09  
**Status:** Both APIs connected and live. Arb detection working. Live trade execution not yet enabled.

---

## What It Does

Scans Kalshi and Polymarket simultaneously for the same binary prediction market. When both sides of an outcome can be purchased across the two platforms for a combined cost below $1.00 (minus fees), it places opposing trades to lock in a guaranteed profit regardless of the outcome.

**Example:** If Kalshi prices "Yes" at $0.40 and Polymarket prices "No" at $0.45, buying both costs $0.85 and pays out $1.00 — a guaranteed 15% return before fees.

---

## Project Structure

```
predictionbot/
├── src/
│   ├── clients/
│   │   ├── kalshi.py          # RSA-signed REST client — fetches markets by series_ticker
│   │   └── polymarket.py      # Gamma API client — 10-page parallel offset pagination
│   ├── core/
│   │   ├── matcher.py         # Fuzzy title matching with Kalshi→real league name normalization
│   │   ├── detector.py        # Checks both leg directions, deducts fees, filters by MIN_PROFIT_PCT
│   │   ├── executor.py        # Places both legs simultaneously via asyncio.gather
│   │   └── position_manager.py # SQLite persistence for positions and trade log
│   ├── models/
│   │   ├── market.py          # Market, MarketPrice dataclasses
│   │   ├── opportunity.py     # ArbOpportunity dataclass
│   │   └── position.py        # Position dataclass
│   ├── risk/
│   │   └── manager.py         # Pre-trade guards: min profit, match score, liquidity
│   ├── utils/
│   │   ├── fees.py            # Kalshi (7% conservative) + Polymarket (0.5% taker) fee models
│   │   └── logger.py          # Loguru setup — stdout + logs/bot.log
│   └── main.py                # Main polling loop
├── config/
│   └── settings.py            # All settings loaded from .env
├── tests/
│   ├── live_test.py           # Full pipeline test against live APIs
│   ├── smoke_test.py          # Offline unit test with mock data
│   ├── debug_kalshi_auth.py   # Auth debugging
│   └── debug_matching.py      # Match score inspection
├── db/
│   └── schema.sql             # SQLite schema for positions + trade_log tables
├── .env                       # Credentials (never commit)
├── .env.example               # Template
└── requirements.txt
```

---

## How to Run

```
cd C:\Users\bariz\Downloads\predictionbot
python tests\live_test.py        # one-shot scan + report
python src\main.py               # continuous polling loop
```

---

## Configuration (.env)

| Setting | Default | Description |
|---|---|---|
| `KALSHI_API_KEY_ID` | — | UUID from Kalshi API Access page |
| `KALSHI_PRIVATE_KEY` | — | RSA private key (single-line, `\n` escaped) |
| `MIN_PROFIT_PCT` | `0.02` | Minimum net profit % to fire a trade |
| `MAX_POSITION_USD` | `50.00` | Max USD per arb pair |
| `POLL_INTERVAL_SEC` | `10` | Seconds between scans |
| `DRY_RUN` | `true` | Set `false` to enable live execution |
| `MAX_DAYS_TO_RESOLUTION` | `7` | Resolution window filter (hard cap 14) — currently disabled in clients |

---

## API Details

### Kalshi
- **Endpoint:** `https://api.elections.kalshi.com/trade-api/v2`
- **Auth:** RSA-SHA256 — sign `{timestamp_ms}{METHOD}{path}`, send via `KALSHI-ACCESS-*` headers
- **Price fields:** `yes_ask_dollars` / `no_ask_dollars` (already 0.0–1.0)
- **Critical:** Default sort returns only sports parlays. Must filter by `series_ticker`.
- **Active series:** KXNBA, KXNHL, KXMLB, KXNFL, KXBTC, KXETH, KXECON, KXPRES, KXGOV, KXWORLD, KXTECH, KXSCI
- Kalshi avoids league branding: "Pro Basketball Finals" = NBA Finals, "Pro Baseball Championship" = MLB World Series

### Polymarket
- **Market discovery:** `https://gamma-api.polymarket.com/markets` with `active=true&closed=false`
- **Pagination:** `offset` param, 100 per page (hard cap), fetched in parallel
- **Price fields:** `outcomePrices` and `outcomes` are JSON strings, index-matched
- **Order execution:** `https://clob.polymarket.com` — HMAC auth, not yet implemented
- No auth needed for read-only fetching

---

## Scan Log

### 2026-06-09 — Scan #1

**Kalshi markets:** 399 | **Polymarket markets:** 812 | **Matched pairs:** 4 | **Arb opportunities:** 0

| Market | Match Score | Kalshi Yes | Poly Yes | Gap | Arb? |
|---|---|---|---|---|---|
| SAS NBA Finals | 100 | 0.380 | 0.378 | 0.2¢ | No |
| NYK NBA Finals | 100 | 0.630 | 0.625 | 0.5¢ | No |
| VGK Stanley Cup | 97 | 0.620 | 0.618 | 0.2¢ | No |
| CAR Stanley Cup | 97 | 0.390 | 0.375 | 1.5¢ | No |

Markets are efficient. Largest gap is CAR at 1.5¢ — need ~9–10¢ to clear fees + 2% min profit threshold.

---

### 2026-06-08 — Initial Setup

**Kalshi markets:** 397 | **Polymarket markets:** ~818 | **Matched pairs:** 4 | **Arb opportunities:** 0

| Market | Kalshi Yes | Poly Yes | Gap | Arb? |
|---|---|---|---|---|
| NYK NBA Finals | 0.780 | 0.780 | 0¢ | No |
| SAS NBA Finals | 0.230 | 0.220 | 1¢ | No |
| VGK Stanley Cup | 0.640 | 0.623 | 1.7¢ | No |
| CAR Stanley Cup | 0.380 | 0.375 | 0.5¢ | No |

First successful end-to-end run. Both APIs live. No arb found.

---

---

## Known Issues / Next Steps

1. **Polymarket live execution** — HMAC signing for CLOB orders not implemented. `place_order()` in `polymarket.py` has the payload structure but no auth. Needs `POLY_PRIVATE_KEY` (Polygon wallet) and HMAC signature logic.
2. **Resolution window filter** — `MAX_DAYS_TO_RESOLUTION` was disabled during debugging to expand the match universe. Should be re-enabled for production to avoid holding long-dated positions.
3. **MLB matching** — Kalshi has 30 MLB team markets but Polymarket has no corresponding World Series markets yet (season is ongoing). Will become relevant in October.
4. **BTC/ETH price ranges** — Kalshi has daily BTC/ETH range markets with no Polymarket equivalent. Could be matched against Polymarket's BTC price milestone markets with a custom alias.
5. **Fee model** — Kalshi fee rate hardcoded at 7% (conservative). Should be verified against your actual account tier in Kalshi's fee schedule and updated in `src/utils/fees.py`.
