# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0]

First packaged release. Reorganizes the original scripts into an installable package.

### Added

- `prediction-arb` command with `scan`, `run`, `report`, `match-debug`, `positions`, and
  `check-config` subcommands.
- Live Polymarket order placement through the official `py-clob-client` (optional `[trading]` extra).
- Ed25519 Kalshi API keys, and loading the key from a file (`KALSHI_PRIVATE_KEY_PATH`).
- Risk limits: `MAX_OPEN_POSITIONS`, no re-entry into held pairs, halt after a one-sided fill, and
  Polymarket minimum order size.
- Configurable thresholds, fee rates, Kalshi series, and file paths, with validation.
- Offline pytest suite; CI (lint, tests on Python 3.10–3.13, secret scanning, build), CodeQL, and
  Dependabot.
- Documentation: architecture, configuration reference, live-trading guide, security policy.

### Fixed

- Hedge legs are sized to the same contract count. Previously the Kalshi leg was sized in dollars
  and the Polymarket leg in shares, so positions were not actually hedged.
- Kalshi requests are signed with RSA-PSS/SHA-256 as the API requires (was PKCS#1 v1.5), and order
  IDs are read from the response's `order` object.
- Polymarket orders are signed. Previously they were posted unsigned and always failed, which in
  live mode left one-sided Kalshi exposure.
- Opportunities use executable ask prices instead of Polymarket mid prices.
- Fees follow each exchange's published formula and per-market Polymarket fee rates.
- The matcher rejects pairs from different leagues, years, or questions, and handles `®`/`™` in
  titles and season years such as `2025-26`.
- `MAX_DAYS_TO_RESOLUTION` is enforced, using Kalshi's expected resolution date.
- The bot no longer re-enters the same opportunity on every scan.

### Changed

- The live opportunities page is published to the `live-data` branch instead of being committed to
  `main` every 15 minutes, and its workflow no longer receives exchange credentials.
- Polymarket markets are fetched in order of 24-hour volume.

### Removed

- Ad-hoc debug scripts, which printed credential identifiers, and personal working notes.

### Security

- Tracebacks no longer include local variable values, which could have written private keys to
  the console and log file.
- API base URLs must be on the exchanges' own domains. Signed requests and Polymarket API
  credentials can no longer be redirected to another host by configuration, and Kalshi order
  requests do not follow redirects.
- Untrusted exchange data is validated: non-finite numbers and implausible fee rates are rejected.
- A crash in one order leg can no longer hide a fill on the other, and the bot halts if a live
  position cannot be recorded.
- The log file and positions database are created readable only by their owner, and a world-readable
  Kalshi key file triggers a warning.
- Bare URLs and @mentions in market titles are neutralized in the published report.
- The live-report workflow's write token is isolated from third-party code; CI audits dependencies
  (pip-audit) and workflows (zizmor); all actions, hooks, and the Docker base image are pinned.
