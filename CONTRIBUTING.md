# Contributing

Contributions are welcome. The highest-value open work is listed in [Known Limitations](README.md#known-limitations--roadmap).

## Setup

```bash
git clone https://github.com/skbariz/prediction-market-arbitrage
cd prediction-market-arbitrage
pip install -r requirements.txt
cp .env.example .env
# Fill in credentials (Kalshi required for order tests; Polymarket read-only needs none)
```

## Before submitting a PR

1. Run the offline tests: `python tests/smoke_test.py`
2. Run the live pipeline test: `python tests/live_test.py` (read-only, no credentials needed)
3. If you changed the matcher, run `python tests/debug_matching.py` and verify no real pairs were dropped

## Key areas

### Polymarket CLOB auth (most wanted)

`src/clients/polymarket.py` → `place_order()` has the payload structure but the `_auth_headers()` method returns stubs. It needs HMAC-SHA256 signing per the [Polymarket CLOB API docs](https://docs.polymarket.com/#authentication). The credential fields are already wired in `config/settings.py`.

### Improving match coverage

`src/core/matcher.py` → `_KALSHI_EXPANSIONS` maps Kalshi's generic league names to real names. Add entries here if you find markets that should match but don't. Run `python tests/debug_matching.py` to inspect scores for pairs below the threshold.

### Fee accuracy

`src/utils/fees.py` → Kalshi's fee rate is hardcoded at 7%. If you have access to Kalshi's fee schedule API or want to add tiered lookup logic, this is the place.

## Style

- No docstrings on obvious functions
- No inline comments on self-explanatory code
- Keep it minimal — don't add abstractions beyond what the task needs
