"""Command-line interface: ``prediction-arb <command>``."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import importlib.util
import sys
from dataclasses import fields
from pathlib import Path

from prediction_arb import __version__, bot
from prediction_arb.clients.kalshi import KalshiAuthError, KalshiClient, load_private_key
from prediction_arb.clients.polymarket import PolymarketClient
from prediction_arb.config import ConfigError, Settings
from prediction_arb.executor import describe
from prediction_arb.log import configure_logging, logger
from prediction_arb.matcher import candidate_pairs
from prediction_arb.models import Market
from prediction_arb.report import render_markdown
from prediction_arb.scanner import ScanResult, scan
from prediction_arb.storage import PositionStore


async def _scan_once(settings: Settings) -> ScanResult:
    async with KalshiClient(settings) as kalshi, PolymarketClient(settings) as poly:
        return await scan(kalshi, poly, settings)


def cmd_scan(settings: Settings, args: argparse.Namespace) -> int:
    result = asyncio.run(_scan_once(settings))
    print(
        f"Kalshi: {len(result.kalshi_markets)} markets | "
        f"Polymarket: {len(result.poly_markets)} markets | "
        f"Matched pairs: {len(result.pairs)}"
    )
    if result.pairs:
        print(f"\nTop {min(args.limit, len(result.pairs))} matched pairs:")
        for pair in result.pairs[: args.limit]:
            print(f"  [{pair.score:>3.0f}] K: {pair.kalshi.title[:70]}")
            print(f"        P: {pair.polymarket.title[:70]}")
            print(
                f"        YES ask  Kalshi {pair.kalshi.price.yes:.3f} | "
                f"Polymarket {pair.polymarket.price.yes:.3f}"
            )
    print(
        f"\nOpportunities after fees (min {settings.min_profit_pct:.2%}): {len(result.opportunities)}"
    )
    for opp in result.opportunities:
        print(f"  * {describe(opp)}")
    return 0


def cmd_run(settings: Settings, args: argparse.Namespace) -> int:
    if not settings.dry_run:
        problems = settings.live_trading_problems()
        if importlib.util.find_spec("py_clob_client") is None:
            problems.append(
                'py-clob-client is not installed: pip install "prediction-arb[trading]"'
            )
        if not args.live:
            problems.append("DRY_RUN=false also requires the --live flag to confirm real trading")
        if problems:
            print(
                "Refusing to start live trading:\n  - " + "\n  - ".join(problems), file=sys.stderr
            )
            return 1
    elif args.live:
        print("--live was given but DRY_RUN is true; running in dry-run mode.", file=sys.stderr)

    with contextlib.suppress(KeyboardInterrupt):
        return asyncio.run(bot.run(settings, once=args.once))
    logger.info("Stopped by user")
    return 0


def cmd_report(settings: Settings, args: argparse.Namespace) -> int:
    result = asyncio.run(_scan_once(settings))
    markdown = render_markdown(result, settings)
    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(markdown)
    return 0


def cmd_match_debug(settings: Settings, args: argparse.Namespace) -> int:
    async def fetch() -> tuple[list[Market], list[Market]]:
        async with KalshiClient(settings) as kalshi, PolymarketClient(settings) as poly:
            return await asyncio.gather(kalshi.get_markets(), poly.get_markets())

    kalshi_markets, poly_markets = asyncio.run(fetch())
    candidates = candidate_pairs(kalshi_markets, poly_markets, args.min_score)
    print(f"Kalshi: {len(kalshi_markets)} | Polymarket: {len(poly_markets)}")
    print(
        f"Candidate pairs scoring >= {args.min_score:g} (match threshold is "
        f"{settings.match_score_threshold:g}): {len(candidates)}\n"
    )
    for pair in candidates[: args.limit]:
        marker = "match" if pair.score >= settings.match_score_threshold else "below"
        print(f"  [{pair.score:>5.1f} {marker}] K: {pair.kalshi.title[:70]}")
        print(f"                 P: {pair.polymarket.title[:70]}")
    return 0


def cmd_positions(settings: Settings, args: argparse.Namespace) -> int:
    store = PositionStore(settings.db_path)
    if not store.db_path.exists():
        print(f"No database at {store.db_path} yet.")
        return 0
    rows = store.list_positions(status=args.status, limit=args.limit)
    if not rows:
        print("No positions recorded.")
    for r in rows:
        print(
            f"#{r['id']:<4} {r['created_at'][:19]}  {r['status']:<9} {r['contracts']:>5} x  "
            f"K {r['kalshi_side']}@{r['kalshi_price']:.3f} + P {r['poly_side']}@{r['poly_price']:.3f}  "
            f"exp. ${r['expected_profit_usd']:.2f}  {r['title'][:50]}"
        )
    return 0


def cmd_check_config(settings: Settings, args: argparse.Namespace) -> int:
    print(f"prediction-arb {__version__}\n")
    for f in fields(settings):
        value = getattr(settings, f.name)
        if not f.repr:
            value = "<set>" if value else "<not set>"
        print(f"  {f.name:<28} {value}")

    print()
    try:
        key = load_private_key(settings)
        print(
            f"Kalshi private key: {'loaded (' + type(key).__name__ + ')' if key else 'not configured'}"
        )
    except (KalshiAuthError, OSError) as exc:
        print(f"Kalshi private key: ERROR - {exc}")
        return 1

    problems = settings.live_trading_problems()
    if importlib.util.find_spec("py_clob_client") is None:
        problems.append('py-clob-client not installed (pip install "prediction-arb[trading]")')
    if problems:
        print("Live trading: not ready\n  - " + "\n  - ".join(problems))
    else:
        print("Live trading: ready (requires DRY_RUN=false and --live)")
    print(f"Mode: {'DRY RUN' if settings.dry_run else 'LIVE'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prediction-arb",
        description="Find (and optionally trade) arbitrage between Kalshi and Polymarket.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--env-file", default=".env", help="dotenv file to load (default: .env)")
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    p = sub.add_parser("scan", help="run one read-only scan and print results")
    p.add_argument("--limit", type=int, default=10, help="matched pairs to show (default: 10)")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("run", help="run the continuous scan/trade loop")
    p.add_argument("--once", action="store_true", help="run a single cycle and exit")
    p.add_argument("--live", action="store_true", help="confirm live trading (with DRY_RUN=false)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("report", help="write a Markdown report of current opportunities")
    p.add_argument("-o", "--output", help="output file (default: stdout)")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("match-debug", help="show near-miss title matches for tuning the matcher")
    p.add_argument(
        "--min-score", type=float, default=70.0, help="lowest score to show (default: 70)"
    )
    p.add_argument("--limit", type=int, default=40, help="pairs to show (default: 40)")
    p.set_defaults(func=cmd_match_debug)

    p = sub.add_parser("positions", help="list positions recorded in the local database")
    p.add_argument("--status", help="filter by status (open, unhedged, failed, closed)")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_positions)

    p = sub.add_parser("check-config", help="validate configuration without touching the network")
    p.set_defaults(func=cmd_check_config)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = Settings.from_env(args.env_file)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 1
    log_file = settings.log_file if args.command == "run" else ""
    configure_logging("DEBUG" if args.verbose else settings.log_level, log_file)
    try:
        return args.func(settings, args)
    except KalshiAuthError as exc:
        print(f"Kalshi credential error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
