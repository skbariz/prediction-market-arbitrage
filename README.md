# Prediction Market Arbitrage

[![CI](https://github.com/skbariz/prediction-market-arbitrage/actions/workflows/ci.yml/badge.svg)](https://github.com/skbariz/prediction-market-arbitrage/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

`prediction-arb` scans [Kalshi](https://kalshi.com) and [Polymarket](https://polymarket.com) for the
same real-world event priced differently on each exchange, and flags — or, if you explicitly enable
it, trades — hedges that pay out more than they cost after fees, whatever the outcome.

- **Read-only by default.** Scanning uses public market data and needs no account or API key.
- **Fee-aware.** Uses each exchange's published taker-fee formula and per-market fee rates.
- **Hedge-correct.** Both legs buy the same number of contracts, so the payout is fixed.
- **Fail-safe live mode.** Fill-or-kill orders, position limits, no re-entry, and an automatic halt
  if a trade is ever left one-sided.

> **See current opportunities without installing anything:**
> [LIVE_OPPORTUNITIES.md](https://github.com/skbariz/prediction-market-arbitrage/blob/live-data/LIVE_OPPORTUNITIES.md),
> refreshed every 15 minutes by GitHub Actions.

> [!WARNING]
> This is experimental software that can place real-money orders. It is provided for educational
> and research purposes, with no warranty. Read the [disclaimer](#disclaimer) before using it.

---

## Contents

- [How it works](#how-it-works)
- [Quick start](#quick-start)
- [Commands](#commands)
- [Configuration](#configuration)
- [Live trading](#live-trading)
- [Publishing the live opportunities page](#publishing-the-live-opportunities-page)
- [Project layout](#project-layout)
- [Development](#development)
- [Limitations and roadmap](#limitations-and-roadmap)
- [Security](#security)
- [Disclaimer](#disclaimer)
- [License](#license)

---

## How it works

A binary prediction-market contract pays **$1** if its outcome happens and **$0** if not. Owning one
YES and one NO contract on the same event therefore always pays exactly $1. If the same event trades
on two exchanges, you can buy YES on one and NO on the other; when the two prices plus fees add up to
less than $1, the difference is locked in regardless of the result.

```text
Kalshi:      "Will New York win the 2027 Pro Basketball Finals?"   YES ask $0.40
Polymarket:  "Will New York Knicks win the 2027 NBA Finals?"        NO  ask $0.45

Buy 56 Kalshi YES  @ $0.40 = $22.40   + fee $0.95
Buy 56 Poly   NO   @ $0.45 = $25.20   + fee $0.97
                      total = $49.52
Payout (either outcome) = 56 × $1 = $56.00   →   profit $6.48 (13.1% on capital)
```

Each scan runs this pipeline:

1. **Fetch** open markets from both exchanges concurrently.
2. **Match** markets that describe the same event. Kalshi avoids league trademarks ("Pro Basketball
   Finals"), so titles are normalized ("NBA Finals") and compared with fuzzy matching. Pairs that name
   different leagues, years, or questions ("win the Stanley Cup" vs "make the playoffs") are rejected.
3. **Detect** profitable hedges in both directions (Kalshi YES + Polymarket NO, and the reverse),
   using best **ask** prices and sizing both legs to the same contract count within your budget.
4. **Risk-check** each opportunity: match confidence, liquidity, time to resolution, minimum order
   size, open-position limits, and whether that pair is already held.
5. **Execute** both legs at the same time as fill-or-kill orders (live mode only) and record the
   result in a local SQLite database.

Fees use each exchange's published formula, `fee = rate × contracts × price × (1 − price)`, with
Kalshi's rounded up to the cent. See [`fees.py`](src/prediction_arb/fees.py) for sources.

## Quick start

Requires Python 3.10 or newer.

```bash
git clone https://github.com/skbariz/prediction-market-arbitrage.git
cd prediction-market-arbitrage
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e .

prediction-arb scan
```

Example output:

```text
Kalshi: 407 markets | Polymarket: 888 markets | Matched pairs: 23

Top 10 matched pairs:
  [100] K: Will New York win the 2027 Pro Basketball Finals?
        P: Will New York Knicks win the 2027 NBA Finals?
        YES ask  Kalshi 0.090 | Polymarket 0.130
  ...

Opportunities after fees (min 2.00%): 1
  * Will New York win the 2027 Pro Basketball Finals? | 51 contracts | Kalshi YES @ 0.090 +
    Polymarket NO @ 0.880 | cost $49.93 (fees $0.46) | profit $1.07 (2.14%)
```

No configuration is needed for scanning. To change thresholds, copy the template and edit it:

```bash
cp .env.example .env
```

## Commands

| Command | What it does |
|---|---|
| `prediction-arb scan` | One read-only scan; prints matched pairs and opportunities. |
| `prediction-arb run` | Continuous loop: scan, risk-check, execute (dry run by default), sleep. |
| `prediction-arb run --once` | A single loop iteration, useful for cron or testing. |
| `prediction-arb report -o FILE` | Writes a Markdown report (what the live page is built from). |
| `prediction-arb match-debug` | Shows near-miss title matches, for tuning the matcher. |
| `prediction-arb positions` | Lists positions recorded in the local database. |
| `prediction-arb check-config` | Validates configuration and credentials without network access. Secrets are masked. |

Global options: `--env-file PATH` (default `.env`), `-v/--verbose`, `--version`.
`python -m prediction_arb` works the same as `prediction-arb`.

## Configuration

All settings are environment variables, optionally loaded from a `.env` file. Every setting has a
safe default; the most important ones are:

| Variable | Default | Meaning |
|---|---|---|
| `DRY_RUN` | `true` | When `true`, opportunities are logged but no orders are placed. |
| `MIN_PROFIT_PCT` | `0.02` | Minimum net return on capital after fees. |
| `MAX_POSITION_USD` | `50` | All-in budget per arbitrage (both legs plus fees). |
| `MAX_OPEN_POSITIONS` | `5` | No new positions beyond this many. |
| `MAX_DAYS_TO_RESOLUTION` | `14` | Only trade markets resolving within N days (`0` = no limit). |
| `EXECUTION_MIN_MATCH_SCORE` | `85` | Title-match confidence (0–100) required to trade. |
| `POLL_INTERVAL_SEC` | `30` | Seconds between scans. |

The full reference, including credentials, fee overrides, and Kalshi series selection, is in
[docs/configuration.md](docs/configuration.md).

## Live trading

Live trading is off unless **all** of the following are true, so it cannot be switched on by
accident:

1. `DRY_RUN=false` is set.
2. The `--live` flag is passed to `prediction-arb run`.
3. Kalshi and Polymarket credentials are configured.
4. The Polymarket SDK is installed: `pip install -e ".[trading]"`.

```bash
prediction-arb check-config           # confirms everything is in place
prediction-arb run --live
```

Read [docs/live-trading.md](docs/live-trading.md) first. It covers getting API keys, wallet setup,
what happens when one leg fails, and an operational checklist.

## Publishing the live opportunities page

[`live-opportunities.yml`](.github/workflows/live-opportunities.yml) runs `prediction-arb report`
every 15 minutes and force-pushes the result to the `live-data` branch as a single commit, so `main`
never collects automated commits. It uses only public market data and needs no secrets. On a fork,
enable Actions and the workflow will publish to your fork's `live-data` branch. Disable it under
**Actions → Live opportunities → ⋯ → Disable workflow**.

## Project layout

```text
src/prediction_arb/
├── cli.py              Command-line entry point
├── config.py           Settings loaded and validated from the environment
├── models.py           Market, MatchedPair, ArbOpportunity, Position, OrderResult
├── clients/
│   ├── http.py         Shared session, timeouts, retries
│   ├── kalshi.py       Kalshi market data and signed order placement
│   └── polymarket.py   Gamma market data and CLOB order placement (via py-clob-client)
├── scanner.py          Fetch → match → detect
├── matcher.py          Title normalization and fuzzy matching
├── detector.py         Hedge sizing and fee-adjusted profit
├── fees.py             Exchange fee formulas
├── risk.py             Pre-trade checks
├── executor.py         Concurrent two-leg execution
├── bot.py              Polling loop
├── storage.py          SQLite persistence (schema.sql)
└── report.py           Markdown report rendering
tests/                  Offline pytest suite (no network, no credentials)
docs/                   Architecture, configuration, and live-trading guides
```

See [docs/architecture.md](docs/architecture.md) for the data flow and design decisions.

## Development

```bash
pip install -e ".[dev]"
pytest                  # offline test suite
ruff check . && ruff format --check .
```

Optional: `pip install pre-commit && pre-commit install` to lint and scan for secrets before each
commit. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Limitations and roadmap

- **Execution risk.** Both legs are sent together as fill-or-kill orders, but one can still fill
  while the other is rejected. The bot halts when this happens; unwinding is manual.
- **No position lifecycle.** Positions are recorded when opened; settlement and P&L tracking are
  not implemented yet.
- **Matching is heuristic.** It works well for championship-style markets (NBA, NHL, MLB, NFL).
  Other categories may need new rules in `matcher.py`; use `prediction-arb match-debug` to tune.
- **Rule differences.** Two markets can look identical but resolve differently (sources, dates,
  edge cases). Always read both markets' rules before trading.
- **Coverage.** Kalshi is queried by series (`KALSHI_SERIES`) and Polymarket by 24-hour volume
  (`POLY_PAGES` × 100 markets), so not every market on either exchange is scanned.

Roadmap ideas, all open to contributors: settlement tracking and realized P&L, automatic unwinding of
one-sided fills, order-book depth checks before sizing, alerts (Slack, email, webhooks), and broader
market coverage.

## Security

Never commit `.env` files or private keys. Both are git-ignored, and CI runs a secret scan on every
push. To report a vulnerability, follow [SECURITY.md](SECURITY.md); please do not open a public
issue.

## Disclaimer

This software is provided for **educational and research purposes only** and is **not financial
advice**. Prediction-market trading carries real risk of loss: quotes move in milliseconds, one leg
of a hedge can fail, exchanges can change fees, rules, or APIs without notice, and markets that look
identical can resolve differently. Access to Kalshi and Polymarket is restricted in some
jurisdictions; you are responsible for complying with each platform's terms and your local laws.
Always run in dry-run mode first, start small, and never trade money you cannot afford to lose. The
authors accept no liability for any losses.

## License

[MIT](LICENSE)
