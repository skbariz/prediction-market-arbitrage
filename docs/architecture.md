# Architecture

## Data flow

```text
              ┌──────────────────────┐        ┌──────────────────────────┐
              │ KalshiClient         │        │ PolymarketClient         │
              │ GET /markets per     │        │ Gamma GET /markets,      │
              │ series (paginated)   │        │ by 24h volume (parallel) │
              └──────────┬───────────┘        └────────────┬─────────────┘
                         └──────────── asyncio.gather ─────┘
                                           │  list[Market]
                                           ▼
                                  matcher.match_markets
                       normalize → league/year/qualifier guards →
                       fuzzy score → one-to-one assignment
                                           │  list[MatchedPair]
                                           ▼
                                detector.detect_opportunities
                       both directions → equal-contract sizing →
                       exchange fees → MIN_PROFIT_PCT filter
                                           │  list[ArbOpportunity]
                ┌──────────────────────────┼──────────────────────────┐
                ▼                          ▼                          ▼
          report.render_markdown      cli scan (print)        bot.run_cycle
                                                                     │
                                                         risk.evaluate (per opp)
                                                                     │
                                                       executor.execute (both legs,
                                                       fill-or-kill, concurrent)
                                                                     │
                                                         storage.PositionStore
```

`scanner.scan` is the shared fetch → match → detect step used by `scan`, `report`, and `run`.

## Modules

| Module | Responsibility |
|---|---|
| `config.py` | Immutable `Settings` built from the environment, with validation. Secrets are excluded from `repr`. |
| `models.py` | Plain dataclasses. `ArbOpportunity` derives cost, payout, and profit from contract count, prices, and fees, so those numbers can never disagree. |
| `clients/` | Exchange I/O only. `parse_market` functions are pure, so they are tested without the network. |
| `matcher.py` | Pure function from two market lists to pairs. |
| `detector.py` | Pure function from pairs to sized opportunities. |
| `fees.py` | Exchange fee formulas, with sources. |
| `risk.py` | Pure function returning approval plus human-readable reasons. |
| `executor.py` | Talks to the clients through small `Protocol`s, so tests use fakes. |
| `bot.py` | Orchestration and the halt-on-unhedged policy. |
| `storage.py` | SQLite. The schema ships inside the package. |

## Design decisions

**Equal contract counts, not equal dollars.** A YES + NO hedge pays `$1 × contracts` only if both legs
hold the same number of contracts. `detector._size_hedge` finds the largest count whose total cost,
including fees, fits within `MAX_POSITION_USD`.

**Ask prices, not mid prices.** Polymarket's `outcomePrices` are mid-market prices that you cannot
actually buy at. The client uses `bestAsk` for the first outcome and `1 − bestBid` for the other,
falling back to mid prices only when the book is empty. Kalshi provides `yes_ask_dollars` and
`no_ask_dollars` directly.

**Fee model.** Both exchanges charge takers `rate × contracts × price × (1 − price)`. Kalshi rounds up
to the cent. Polymarket publishes a rate per market (`feeSchedule.rate`, or `feesEnabled: false`);
when one is missing, the highest published category rate is assumed.

**Matching guards.** RapidFuzz's `token_set_ratio` scores a title 100 when its words are a subset of
the other's, which makes it good at "New York" vs "New York Knicks", but it also accepts
"New York … NBA Finals" vs "New York Giants … NFL" and "win the Stanley Cup" vs "make the playoffs".
Before scoring, titles are tagged with leagues, years, and qualifiers (playoffs, conference, MVP, …),
and pairs whose tags conflict are rejected. Each market is then used in at most one pair, best score
first.

**Kalshi series queries.** Kalshi's unfiltered `/markets` listing is dominated by multivariate
parlay markets (`KXMV…`). Standard binary markets are fetched by series ticker instead
(`KALSHI_SERIES`).

**Resolution date.** Kalshi's `close_time` is a worst-case bound (for example, "closes once a
champion is declared, at the latest in 2029"). `expected_expiration_time` is used for
`MAX_DAYS_TO_RESOLUTION`, because capital is locked until settlement.

**Fail-safe execution.** Fill-or-kill on both legs prevents partial fills. Positions with exposure
are never re-entered, and the loop stops at the first one-sided fill, because continuing could
compound an unhedged position.

**Two gates for live mode.** `DRY_RUN=false` alone is not enough: `run --live` is also required, so a
stray environment variable cannot start real trading.

**Live page on its own branch.** The scheduled report is force-pushed to `live-data` as a single
commit. `main` keeps a clean, human-only history, and pull requests never conflict with automated
commits.
