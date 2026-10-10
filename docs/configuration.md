# Configuration reference

`prediction-arb` reads settings from environment variables. On start-up it also loads a `.env` file
from the current directory (or the path given with `--env-file`). Variables already set in the
environment take precedence over the file.

Invalid values stop the program with a message that names the setting. Run
`prediction-arb check-config` to see the effective configuration; secrets and account identifiers
(key ID, funder address) are shown only as `<set>` or `<not set>`.

API base URLs are restricted to the exchanges' own domains. Authenticated requests carry signatures
and, for Polymarket, the API key and passphrase, so sending them to any other host would expose your
account. A `.env` file that points them elsewhere is rejected at start-up.

## Mode

| Variable | Default | Description |
|---|---|---|
| `DRY_RUN` | `true` | `true`: log what would be traded and place no orders. `false`: allow live orders (also requires `run --live`). |

## Strategy and risk

| Variable | Default | Description |
|---|---|---|
| `MIN_PROFIT_PCT` | `0.02` | Minimum net profit as a fraction of capital deployed, after fees. `0.02` = 2%. |
| `MAX_POSITION_USD` | `50` | All-in budget per arbitrage: both legs plus fees. Contract count is the largest that fits. |
| `MAX_OPEN_POSITIONS` | `5` | Positions with status `open` or `unhedged` count toward this limit. |
| `MAX_DAYS_TO_RESOLUTION` | `14` | Skip trades on markets expected to resolve later than this. `0` disables the check. |
| `MATCH_SCORE_THRESHOLD` | `80` | Minimum title similarity (0–100) for two markets to be treated as a pair at all. |
| `EXECUTION_MIN_MATCH_SCORE` | `85` | Stricter similarity required before a pair is traded. |
| `MIN_VOLUME` | `100` | Minimum traded volume on each market (contracts on Kalshi, USDC on Polymarket). |
| `POLL_INTERVAL_SEC` | `30` | Seconds between scans in `run` mode. Minimum `5`. |

## Fees

| Variable | Default | Description |
|---|---|---|
| `KALSHI_FEE_RATE` | `0.07` | Coefficient in Kalshi's taker fee `ceil(rate × C × P × (1 − P))`. 0.07 is the general rate; some markets are lower. |
| `POLY_DEFAULT_FEE_RATE` | `0.07` | Used only when a Polymarket market does not publish its own `feeSchedule.rate`. 0.07 is the highest published category rate. |

## Kalshi

Market data is public. These are needed only for live order placement.

| Variable | Default | Description |
|---|---|---|
| `KALSHI_API_KEY_ID` | — | The API key ID shown when you create a key at <https://kalshi.com/account/profile>. |
| `KALSHI_PRIVATE_KEY_PATH` | — | **Recommended.** Path to the private key `.pem` file downloaded with the key. `~` is expanded. |
| `KALSHI_PRIVATE_KEY` | — | Alternative for CI/containers: the PEM contents on one line, with line breaks written as `\n`. |
| `KALSHI_BASE_URL` | `https://api.elections.kalshi.com/trade-api/v2` | Use `https://demo-api.kalshi.co/trade-api/v2` for Kalshi's [demo environment](https://docs.kalshi.com/getting_started/demo_env). Must be an `https://` URL on `kalshi.com` or `kalshi.co`. |
| `KALSHI_SERIES` | `KXNBA,KXNHL,KXMLB,KXNFL,KXBTC,KXETH,KXECON,KXPRES,KXGOV,KXWORLD,KXTECH,KXSCI` | Comma-separated Kalshi series tickers to scan. |

RSA keys are signed with RSA-PSS/SHA-256 and Ed25519 keys with Ed25519, as Kalshi requires. The key
must be unencrypted PEM. Keep the file outside the repository and readable only by you
(`chmod 600 kalshi.pem`).

## Polymarket

Market data is public. These are needed only for live order placement, which also requires
`pip install "prediction-arb[trading]"`.

| Variable | Default | Description |
|---|---|---|
| `POLY_PRIVATE_KEY` | — | Private key (`0x…`) of the wallet that signs orders. Use a dedicated wallet. |
| `POLY_SIGNATURE_TYPE` | `0` | `0` = an externally owned wallet that holds the funds itself; `1` = Polymarket email/Magic account; `2` = browser-wallet proxy (e.g. MetaMask connected to polymarket.com). |
| `POLY_FUNDER_ADDRESS` | — | Address that holds your funds. Required for signature types `1` and `2` (it is the proxy wallet address shown on your Polymarket profile). |
| `POLY_API_KEY`, `POLY_API_SECRET`, `POLY_PASSPHRASE` | — | Optional. CLOB API credentials. When unset they are derived from `POLY_PRIVATE_KEY` on first use. |
| `POLY_PAGES` | `20` | Number of 100-market pages to fetch, ordered by 24-hour volume (1–50). |
| `POLY_CLOB_URL` | `https://clob.polymarket.com` | CLOB API base URL. Must be an `https://` URL on `polymarket.com`. |
| `POLY_GAMMA_URL` | `https://gamma-api.polymarket.com` | Market-data API base URL. Must be an `https://` URL on `polymarket.com`. |
| `POLY_CHAIN_ID` | `137` | Polygon mainnet. |

## Runtime

| Variable | Default | Description |
|---|---|---|
| `DB_PATH` | `data/positions.db` | SQLite database for positions and orders. Created on first `run`. |
| `LOG_FILE` | `logs/bot.log` | Debug-level log file used by `run` (rotated at 10 MB, kept 7 days). Empty disables it. |
| `LOG_LEVEL` | `INFO` | Console log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `HTTP_TIMEOUT_SEC` | `20` | Total timeout per HTTP request. Failed requests are retried with exponential backoff. |

The database and log files contain your trading activity. Both are git-ignored; keep them private.
