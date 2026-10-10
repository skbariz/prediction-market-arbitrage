# Contributing

Thanks for helping improve `prediction-arb`. Bug reports, matcher improvements, documentation, and
features from the [roadmap](README.md#limitations-and-roadmap) are all welcome.

## Development setup

```bash
git clone https://github.com/skbariz/prediction-market-arbitrage.git
cd prediction-market-arbitrage
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install        # optional: lint and secret-scan before each commit (pip install pre-commit)
```

No credentials are needed for development. The test suite is fully offline, and `prediction-arb
scan` uses public market data.

## Before opening a pull request

```bash
ruff format .
ruff check .
pytest
```

- Add or update tests for any behaviour change. Trading logic (sizing, fees, risk, execution) must
  be covered by tests.
- If you change the matcher, run `prediction-arb match-debug` and `prediction-arb scan`, and confirm
  in the PR that no genuine pairs were lost and no false pairs were added.
- Update the docs (`README.md`, `docs/`) and add a line under **Unreleased** in `CHANGELOG.md`.
- Keep pull requests focused: one logical change per PR.

## Guidelines

- **Safety first.** Changes must never make it easier to start live trading by accident, or to end
  up with unhedged exposure. Dry run stays the default.
- **Never commit secrets,** including in tests: generate throwaway keys in the test itself (see
  `tests/test_kalshi.py`).
- **Keep I/O at the edges.** Parsing, matching, detection, and risk checks are pure functions. Keep
  them that way so they stay easy to test.
- Follow the existing style: type hints, small modules, and docstrings or comments that explain *why*
  rather than *what*.
- Cite sources (exchange docs) when encoding exchange rules such as fees or API formats.

## Areas that need help

- **Matcher coverage** (`src/prediction_arb/matcher.py`): new normalization rules, and guards for
  categories beyond championship markets.
- **Position lifecycle:** detecting settlement and recording realized P&L.
- **Order-book depth:** checking available size at the quoted price before sizing a trade.
- **Alerts:** notifying (Slack, email, webhook) when an opportunity appears.

## Reporting bugs and requesting features

Use the [issue templates](https://github.com/skbariz/prediction-market-arbitrage/issues/new/choose).
For security problems, follow [SECURITY.md](SECURITY.md) instead of opening an issue.

By participating you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md). Contributions are
licensed under the [MIT License](LICENSE).
