# Prediction Market Arbitrage Bot

A fully automated arbitrage scanner and execution engine for [Kalshi](https://kalshi.com) and [Polymarket](https://polymarket.com). It fetches live prices from both platforms every 30 seconds, identifies markets representing the same real-world event, and flags (or automatically places) opposing trades whenever the combined entry cost falls below $1.00 after fees — a guaranteed profit regardless of outcome.

> **Want to see current opportunities without running anything?**  
> → [LIVE_OPPORTUNITIES.md](LIVE_OPPORTUNITIES.md) — updated every 15 minutes by GitHub Actions.

---

## Table of Contents

1. [How Prediction Market Arbitrage Works](#how-prediction-market-arbitrage-works)
2. [Live Opportunities](#live-opportunities)
3. [Architecture](#architecture)
4. [Quick Start](#quick-start)
5. [Getting API Credentials](#getting-api-credentials)
6. [Configuration Reference](#configuration-reference)
7. [Running the Bot](#running-the-bot)
8. [Understanding the Output](#understanding-the-output)
9. [Design Decisions](#design-decisions)
10. [Known Limitations & Roadmap](#known-limitations--roadmap)
11. [Disclaimer](#disclaimer)
12. [License](#license)

---

## How Prediction Market Arbitrage Works

Prediction markets price binary outcomes between $0.00 and $1.00 (or 0¢–100¢). A "Yes" contract pays $1.00 if the event happens; a "No" contract pays $1.00 if it doesn't. Buying both legs on the same market always costs exactly $1.00 — no edge there.

**The arbitrage opportunity appears when the same event is priced differently across two platforms.**

```
Example:

  Kalshi:     "Will Team A win the championship?"   Yes @ $0.42
  Polymarket: "Will Team A win the championship?"    No @ $0.54

  Buy Yes on Kalshi:    $0.42
  Buy No on Polymarket: $0.54
  Total cost:           $0.96

  Payout (regardless of outcome): $1.00
  Gross profit:                    $0.04 (4.2%)
  After fees (~1.5%):              ~2.7% guaranteed return
```

This bot automates finding these gaps, verifying they exceed total fees + a minimum profit threshold, and (optionally) placing both legs simultaneously to lock in the return.

### The Math

```
net_profit_pct = (1.0 - yes_ask - no_ask) - fee_pct
```

Where `fee_pct` is the sum of Kalshi's tiered fee (conservative 7% of contract value) and Polymarket's 0.5% taker fee. An opportunity is only flagged when `net_profit_pct >= MIN_PROFIT_PCT` (default: 2%).

---

## Live Opportunities

[**→ View LIVE_OPPORTUNITIES.md**](LIVE_OPPORTUNITIES.md)

This file is regenerated every 15 minutes by a GitHub Actions workflow. It shows:
- Any current arbitrage opportunities with exact entry prices and expected profit
- All matched market pairs across both platforms with their price gaps

To get the live table working on your own fork, see [GitHub Actions Setup](#github-actions-setup) below.

---

## Architecture

```
predictionbot/
├── src/
│   ├── clients/
│   │   ├── kalshi.py          # RSA-signed async REST client
│   │   └── polymarket.py      # Gamma API client, parallel pagination
│   ├── core/
│   │   ├── matcher.py         # Fuzzy title matching with league name normalization
│   │   ├── detector.py        # Arb detection: checks both leg directions, applies fees
│   │   ├── executor.py        # Places both legs simultaneously via asyncio.gather
│   │   └── position_manager.py # SQLite persistence
│   ├── models/
│   │   ├── market.py          # Market, MarketPrice dataclasses
│   │   ├── opportunity.py     # ArbOpportunity dataclass
│   │   └── position.py        # Position dataclass
│   ├── risk/
│   │   └── manager.py         # Pre-trade guards (profit, match score, liquidity)
│   ├── utils/
│   │   ├── fees.py            # Fee models for each platform
│   │   └── logger.py          # Loguru setup (stdout + logs/bot.log)
│   └── main.py                # Main polling loop
├── config/
│   └── settings.py            # All settings loaded from .env
├── scripts/
│   ├── update_live_table.py   # Generates LIVE_OPPORTUNITIES.md (used by CI)
│   └── format_kalshi_key.py   # Converts multi-line PEM key to .env-compatible format
├── tests/
│   ├── live_test.py           # Full pipeline test against live APIs
│   ├── smoke_test.py          # Offline unit test with mock data
│   └── debug_matching.py      # Match score inspection tool
├── .github/
│   └── workflows/
│       └── scan.yml           # GitHub Actions: scan + update LIVE_OPPORTUNITIES.md
├── db/
│   └── schema.sql             # SQLite schema
├── .env.example               # Credential template
└── requirements.txt
```

### Data Flow

```
┌─────────────────┐    asyncio.gather    ┌──────────────────┐
│   KalshiClient  │ ──────────────────── │ PolymarketClient │
│ (12 series,     │                      │  (10 pages ×     │
│  ~400 markets)  │                      │   100 markets)   │
└────────┬────────┘                      └────────┬─────────┘
         │                                        │
         └──────────────────┬─────────────────────┘
                            ▼
                      matcher.py
                  (fuzzy title match,
                   Kalshi name expansion,
                   deduplication)
                            │
                            ▼
                      detector.py
                  (both leg directions,
                   fee deduction,
                   min profit filter)
                            │
                     ┌──────┴──────┐
                     │             │
               opportunities    no opps
                     │             │
               risk/manager.py    │
               (volume, score,     │
                position size)     │
                     │             │
               executor.py    log + sleep
               (both legs simultaneous)
                     │
               position_manager.py
               (SQLite persistence)
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- A [Kalshi account](https://kalshi.com) with API access enabled
- (For live trading) A [Polymarket account](https://polymarket.com) with a funded Polygon wallet

### Install

```bash
git clone https://github.com/skbariz/prediction-market-arbitrage
cd prediction-market-arbitrage
pip install -r requirements.txt
cp .env.example .env
```

### Verify it works (no credentials needed for read-only)

```bash
python tests/live_test.py
```

This fetches live market data from both platforms, runs the matcher and detector, and prints any current opportunities. **No credentials are required for this step** — both read APIs are public.

Expected output:
```
Live API Test — 2026-06-09 22:00 UTC

KALSHI — markets resolving within 7 days
============================================================
  Found 399 near-term markets

POLYMARKET — markets resolving within 7 days
============================================================
  Found 812 near-term markets

ARB PIPELINE — matching + detection
============================================================
  Matched pairs  : 4
  Arb opportunities found: 0

  No profitable arb found after fees — market is efficient right now.
```

---

## Getting API Credentials

### Kalshi

1. Go to [kalshi.com/profile/api](https://kalshi.com/profile/api)
2. Click **Generate Key Pair** — download the private key `.pem` file
3. Copy the **Key ID** (UUID format)
4. Place the `.pem` file somewhere safe and run the key formatter:

```bash
# Paste the raw contents of your .pem into .env as KALSHI_PRIVATE_KEY, then:
python scripts/format_kalshi_key.py
```

This collapses the multi-line PEM into the single-line format that `python-dotenv` requires.

5. Set `KALSHI_API_KEY_ID` in `.env` to your Key ID UUID.

**Note:** Kalshi credentials are only needed for **order placement**. Market scanning (read-only) works without any credentials.

### Polymarket

Polymarket market scanning requires **no credentials**. For live order execution:

1. Create a funded wallet on Polygon (MATIC network)
2. Log in to Polymarket and connect your wallet
3. Follow the [Polymarket CLOB API docs](https://docs.polymarket.com/#authentication) to generate API credentials
4. Set `POLY_PRIVATE_KEY`, `POLY_API_KEY`, `POLY_API_SECRET`, `POLY_PASSPHRASE` in `.env`

> ⚠️ **Note:** Polymarket live order execution requires HMAC signing of CLOB API requests. This is implemented in `src/clients/polymarket.py` but the auth signature generation is incomplete. Pull requests welcome — see [Known Limitations](#known-limitations--roadmap).

### GitHub Actions Setup

To get the [live opportunities table](LIVE_OPPORTUNITIES.md) auto-updating on your fork:

1. Fork this repo
2. Go to **Settings → Secrets and variables → Actions**
3. Add repository secrets:
   - `KALSHI_API_KEY_ID` — your Kalshi key ID UUID
   - `KALSHI_PRIVATE_KEY` — your single-line formatted private key
4. The workflow will run every 15 minutes and commit updates to `LIVE_OPPORTUNITIES.md`

> **Without Kalshi secrets:** The workflow still runs and updates Polymarket data. Kalshi markets show as 0 (unauthenticated requests return 401).

---

## Configuration Reference

All settings are loaded from `.env` via `config/settings.py`.

| Variable | Default | Description |
|----------|---------|-------------|
| `KALSHI_API_KEY_ID` | — | UUID from Kalshi API Access page |
| `KALSHI_PRIVATE_KEY` | — | RSA private key, single-line PEM format |
| `KALSHI_BASE_URL` | `https://api.elections.kalshi.com/trade-api/v2` | Kalshi API base URL |
| `POLY_PRIVATE_KEY` | — | Polygon wallet private key (live trading only) |
| `POLY_API_KEY` | — | Polymarket CLOB API key (live trading only) |
| `POLY_API_SECRET` | — | Polymarket CLOB API secret (live trading only) |
| `POLY_PASSPHRASE` | — | Polymarket CLOB passphrase (live trading only) |
| `MIN_PROFIT_PCT` | `0.02` | Minimum net profit % after fees to place a trade |
| `MAX_POSITION_USD` | `50.00` | Maximum USD per arb pair |
| `POLL_INTERVAL_SEC` | `30` | Seconds between market scans |
| `DRY_RUN` | `true` | When `true`, logs trades without executing them |
| `MAX_DAYS_TO_RESOLUTION` | `7` | Only consider markets resolving within N days (max 14) |

### Risk Parameters (hardcoded in `src/risk/manager.py`)

| Parameter | Value | Reason |
|-----------|-------|--------|
| `MIN_VOLUME_USD` | $100 | Ensures sufficient liquidity for order fills |
| `MIN_MATCH_SCORE` | 85/100 | Stricter than the scan threshold — prevents false matches at execution time |

---

## Running the Bot

### One-shot scan (recommended to start)

```bash
python tests/live_test.py
```

### Continuous polling loop

```bash
python src/main.py
```

The bot polls every `POLL_INTERVAL_SEC` seconds. With `DRY_RUN=true` (the default), it logs every detected opportunity but does not place any orders.

### Generate the live opportunities table

```bash
python scripts/update_live_table.py
```

Writes current scan results to `LIVE_OPPORTUNITIES.md`.

### Inspect match quality

```bash
python tests/debug_matching.py
```

Shows all market pairs scoring ≥ 70 (below the 80-point threshold), useful for tuning the matcher or finding new matchable series.

### Offline unit test

```bash
python tests/smoke_test.py
```

Runs the full pipeline against mock market data — no network required.

---

## Understanding the Output

```
17:22:23 | DEBUG | Polymarket: 812 open markets
17:22:23 | DEBUG | Kalshi: 399 open binary markets across 12 series
17:22:23 | INFO  | Fetching markets from both platforms...
17:22:23 | INFO  | Kalshi: 399 markets | Polymarket: 812 markets
17:22:23 | INFO  | Matched 4 market pairs
17:22:23 | INFO  | No arb opportunities this scan.
```

If an opportunity is found:

```
17:45:01 | INFO  | ARB FOUND | Will Carolina win the 2025-26 Stanley Cup | Kalshi yes@0.310 + Poly no@0.650 | Net profit: 3.42%
17:45:01 | INFO  | Executing arb: Kalshi yes@31¢ x161 | Poly no@0.6500 $50.00
17:45:01 | SUCCESS | Both legs placed | Kalshi:K-123456 Poly:P-789012 | Expected profit: $1.71
17:45:01 | INFO  | Position saved | id=1 status=open
```

Positions are stored in `db/positions.db` (SQLite). View them:

```bash
sqlite3 db/positions.db "SELECT * FROM positions;"
```

---

## Design Decisions

### Why RSA-SHA256 auth for Kalshi?

Kalshi's API uses RSA key-pair authentication rather than a simple API token. Each request must be signed with your private key, and the signature covers the timestamp + method + path to prevent replay attacks. The implementation in `src/clients/kalshi.py` signs the message with PKCS1v15 padding and sends three headers: `KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-SIGNATURE`, and `KALSHI-ACCESS-TIMESTAMP`.

### Why query Kalshi by series_ticker?

Kalshi's default `/markets` endpoint returns only sports parlays (`KXMV*` tickers) by default. Standard binary markets — NBA, NHL, economic, political — are only returned when you explicitly pass `series_ticker=KXNBA`, etc. The client queries all 12 known series in parallel with `asyncio.gather`.

### Why fuzzy matching with brand name expansion?

Kalshi uses generic names to avoid sports licensing fees: "Pro Basketball Finals" instead of "NBA Finals", "Stanley Cup Finals" instead of "NHL Stanley Cup", etc. Before fuzzy matching, `matcher.py` expands these to their real names so `fuzz.token_set_ratio` can find the Polymarket counterpart. Without this expansion, NBA Finals markets would score ~30/100 against each other and never match.

`token_set_ratio` is used instead of simple ratio because it handles word-order differences and extra words well — "Will the New York Knicks win the 2026 NBA Finals?" matches "New York Knicks NBA Finals 2026 winner?" correctly regardless of phrasing.

### Why deduplication in the matcher?

Without deduplication, a single Polymarket market can match multiple Kalshi contracts. For example, if four teams are in a tournament, all four Kalshi "Will [Team] win?" contracts can each score 80+ against the same Polymarket "Will [Team] win?" market for a different team — creating false cross-matches. The deduplication pass assigns each Polymarket market to at most the one Kalshi contract with the highest match score.

### Why 7% for the Kalshi fee estimate?

Kalshi's fee schedule is tiered by 30-day volume. The actual rate ranges from 3% to 7%. We use 7% (the highest tier) as a conservative estimate so the bot never enters a trade that looks profitable but isn't after real fees. Once you know your actual tier, update `fee_rate` in `src/utils/fees.py`.

### Why both leg directions?

For each matched pair, the detector checks:
- **Direction A:** Buy Yes on Kalshi + Buy No on Polymarket
- **Direction B:** Buy No on Kalshi + Buy Yes on Polymarket

Either direction can be profitable depending on which platform is mispricing which side.

### Why SQLite?

Single-file, zero-configuration, and appropriate for the trade volume this bot operates at. A prediction market arb bot at $50/position will realistically execute a few dozen trades per month at most. SQLite handles that easily and the database travels with the codebase.

### Why `DRY_RUN=true` as default?

Placing live trades on two platforms simultaneously is hard to undo. Dry run mode lets you observe the bot's behavior, verify match quality, and build confidence in the fee model before committing real capital. The first thing you should do is watch several days of dry-run logs to confirm opportunities are real before switching to live.

### Why `asyncio.gather` for both API calls?

Fetching Kalshi (12 parallel series requests) and Polymarket (10 parallel pagination requests) takes ~500ms each. Sequential fetching would take ~1s; parallel fetching takes ~500ms. More importantly, the two legs of an arb are placed with `asyncio.gather` so both orders hit the exchange within milliseconds of each other — reducing the window where one leg fills and the other doesn't.

---

## Known Limitations & Roadmap

### Current limitations

| Issue | Impact | Status |
|-------|--------|--------|
| Polymarket CLOB order auth (HMAC signing) not implemented | Live trading on Polymarket side doesn't work | In progress |
| Kalshi fee rate hardcoded at 7% (conservative) | May miss opportunities at lower fee tiers | Easy fix — update `src/utils/fees.py` |
| `MAX_DAYS_TO_RESOLUTION` filter exists but is not applied in clients | Could match long-dated markets | Re-enable by filtering in `get_markets()` |
| MLB World Series markets have no Polymarket counterpart (in-season) | ~30 Kalshi markets unmatched | Will work in October |
| BTC/ETH price range markets don't match Polymarket's milestone markets | Crypto price arb not covered | Needs custom alias rules in `matcher.py` |

### Roadmap

- [ ] Polymarket CLOB HMAC auth for live order placement
- [ ] Re-enable `MAX_DAYS_TO_RESOLUTION` filter in clients
- [ ] Tiered Kalshi fee lookup based on account volume
- [ ] Position closing logic (track open positions, close when market resolves)
- [ ] Slack/email alert when opportunity is found
- [ ] Web dashboard for position tracking
- [ ] Expand match coverage to crypto and political markets

---

## Disclaimer

This software is provided for **educational and research purposes only**.

- Prediction market trading carries real financial risk. You can lose money.
- Arbitrage opportunities can close before both legs fill, leaving you with an unhedged position.
- Fee structures, API behavior, and market rules can change without notice.
- Past opportunity frequency is not indicative of future results.
- **This is not financial advice.** Do your own due diligence before trading.

Always run with `DRY_RUN=true` first and fully understand the bot's behavior before enabling live execution.

---

## License

MIT License — see [LICENSE](LICENSE).
