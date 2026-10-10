# Live trading guide

> [!CAUTION]
> Live mode places real orders with real money on two exchanges. Read this whole page first. Run in
> dry-run mode for several days, then start with a small `MAX_POSITION_USD`.

## 1. Check eligibility

Kalshi and Polymarket each restrict who may trade, by jurisdiction. Confirm you are allowed to use
both platforms and their APIs under their terms of service and your local laws. This software does
not check eligibility for you.

## 2. Install the trading extra

```bash
pip install -e ".[trading]"
```

This adds Polymarket's official [`py-clob-client`](https://github.com/Polymarket/py-clob-client),
which signs orders (EIP-712) and authenticates with the order book.

## 3. Kalshi credentials

1. Log in to Kalshi, open **Account → Profile → API Keys**
   (<https://kalshi.com/account/profile>), and create a key.
2. Save the downloaded private key outside this repository, for example
   `~/.config/prediction-arb/kalshi.pem`, and run `chmod 600` on it. Kalshi shows the private key
   only once.
3. In `.env`, set `KALSHI_API_KEY_ID` to the key ID and `KALSHI_PRIVATE_KEY_PATH` to the file path.

To rehearse without real money, point `KALSHI_BASE_URL` at Kalshi's
[demo environment](https://docs.kalshi.com/getting_started/demo_env) with a demo-account key.
Polymarket has no equivalent test environment.

## 4. Polymarket credentials

1. Use a **dedicated wallet** that holds only the funds you intend to trade with.
2. Fund it with USDC on Polygon through Polymarket, and complete Polymarket's one-time trading setup
   (token approvals) by placing a trade on polymarket.com.
3. In `.env`, set:
   - `POLY_PRIVATE_KEY`: the wallet's private key.
   - `POLY_SIGNATURE_TYPE`: `0` if the key's own address holds the funds, `1` for an email/Magic
     account, `2` for a browser wallet (e.g. MetaMask) connected to polymarket.com.
   - `POLY_FUNDER_ADDRESS`: for types `1` and `2`, the proxy wallet address shown on your Polymarket
     profile.

API credentials are derived from the private key automatically on first use.

## 5. Verify, then start

```bash
prediction-arb check-config     # expect "Live trading: ready"
prediction-arb run              # dry run: watch what it would trade
```

When you are satisfied, set `DRY_RUN=false` and start with the explicit confirmation flag:

```bash
prediction-arb run --live
```

## How orders are placed

For each approved opportunity the bot submits both legs **concurrently** as **fill-or-kill limit
buys** at the quoted ask, for the **same number of contracts**:

- *Fill-or-kill* means a leg either fills completely at that price or not at all, so partial fills
  cannot happen.
- *Same contract count* is what makes the hedge pay a fixed `contracts × $1`.

The outcome is recorded in `DB_PATH`:

| Status | Meaning | What the bot does |
|---|---|---|
| `open` | Both legs filled. The payout is locked in. | Never re-enters that pair; counts toward `MAX_OPEN_POSITIONS`. |
| `failed` | Neither leg filled. No exposure. | Carries on. |
| `unhedged` | One leg filled and the other did not. **You hold a directional position.** | Logs a `CRITICAL` message and **stops**. |

### If the bot halts with an unhedged position

1. Run `prediction-arb positions --status unhedged` to see the details.
2. On the exchange where the leg filled, either sell it, or buy the missing leg manually on the
   other exchange if the combined price still works.
3. Once resolved, update the record so the pair no longer counts as open:

   ```bash
   sqlite3 data/positions.db "UPDATE positions SET status='closed' WHERE id=<ID>;"
   ```

4. Restart the bot.

## Operating checklist

- Read both markets' resolution rules before trusting a pair. Similar titles can still resolve
  differently.
- Keep `EXECUTION_MIN_MATCH_SCORE` at 85 or higher, and review pairs with `prediction-arb scan`.
- Keep only the capital you are prepared to lose on each exchange.
- Run the bot under a process supervisor (systemd, Docker `--restart=on-failure`) and alert on
  `CRITICAL` log lines.
- Keep the machine, `.env`, key files, `data/`, and `logs/` private. Rotate keys immediately if you
  suspect exposure (see [SECURITY.md](../SECURITY.md)).
