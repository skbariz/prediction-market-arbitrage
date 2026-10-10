# Security policy

## Supported versions

Security fixes are made on the latest release and the `main` branch.

## Reporting a vulnerability

**Please do not report security issues in public issues, discussions, or pull requests.**

Report privately through GitHub:
**Security → Advisories → [Report a vulnerability](https://github.com/skbariz/prediction-market-arbitrage/security/advisories/new)**
([how it works](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)).

Please include the affected version or commit, steps to reproduce, and the impact. You should get
an acknowledgement within 7 days. We will agree on a disclosure timeline with you and credit you in
the advisory unless you prefer otherwise.

Examples of in-scope issues:

- Credentials or key material being logged, persisted, or sent anywhere other than the exchange
  that issued them.
- Any way to trigger live orders without `DRY_RUN=false` **and** `--live`.
- Order-sizing or hedging logic that can create unintended or unhedged exposure.
- Injection through third-party market data (for example, into the generated Markdown report).
- Weaknesses in the GitHub Actions workflows (token scope, untrusted input).

## Handling your own credentials

This tool asks for credentials that control real money. To keep them safe:

- Keep secrets in `.env` (git-ignored) or your process manager's secret store. Never in code, issues,
  or screenshots. `prediction-arb check-config` prints `<set>` instead of secret values, so its
  output is safe to share when asking for help.
- Store the Kalshi private key as a file outside the repository (`KALSHI_PRIVATE_KEY_PATH`) with
  `chmod 600`.
- Use a dedicated Polymarket wallet that holds only your trading capital.
- `data/` (positions database) and `logs/` record your trading activity. They are git-ignored; keep
  them private.
- The published live-opportunities workflow uses only public market data. It does **not** need, and
  should not be given, any exchange credentials.
- Before committing, consider enabling the bundled pre-commit hooks (`pre-commit install`), which
  scan staged changes for secrets. CI also scans the full history with gitleaks.

### If a credential is exposed

1. **Revoke it immediately.** Delete the API key in Kalshi's account settings. For a Polymarket
   wallet key, move the funds to a new wallet; a leaked private key cannot be revoked.
2. Create new credentials and update your `.env`.
3. If the secret was committed, deleting the file is not enough, because it stays in git history and
   in any forks or clones. Treat it as permanently public, rotate it, and then optionally purge it
   from history with [`git filter-repo`](https://github.com/newren/git-filter-repo).
