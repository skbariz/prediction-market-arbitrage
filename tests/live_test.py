"""
Live API test — fetches real market data from Kalshi and Polymarket,
applies the resolution-date filter, runs matching + arb detection,
and prints a summary. No credentials required for read-only access.
"""
import sys
import asyncio
sys.path.insert(0, ".")

from datetime import datetime, timezone
from src.clients.kalshi import KalshiClient
from src.clients.polymarket import PolymarketClient
from src.core.matcher import match_markets
from src.core.detector import detect_opportunities
from config.settings import MAX_DAYS_TO_RESOLUTION


def fmt_time(dt):
    if dt is None:
        return "unknown"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


async def test_kalshi():
    print("\n" + "=" * 60)
    print(f"KALSHI — markets resolving within {MAX_DAYS_TO_RESOLUTION} days")
    print("=" * 60)
    async with KalshiClient() as client:
        markets = await client.get_markets(limit=200)

    if not markets:
        print("  No markets returned (API may require auth or no near-term markets found)")
        return markets

    print(f"  Found {len(markets)} near-term markets\n")
    for m in markets[:10]:
        print(f"  [{m.market_id}]")
        print(f"    Title    : {m.title}")
        print(f"    Closes   : {fmt_time(m.close_time)}")
        print(f"    Yes/No   : {m.price.yes:.3f} / {m.price.no:.3f}")
        print(f"    Volume   : ${m.volume_usd or 0:,.0f}")
        print()
    if len(markets) > 10:
        print(f"  ... and {len(markets) - 10} more")
    return markets


async def test_polymarket():
    print("\n" + "=" * 60)
    print(f"POLYMARKET — markets resolving within {MAX_DAYS_TO_RESOLUTION} days")
    print("=" * 60)
    async with PolymarketClient() as client:
        markets = await client.get_markets(pages=10)

    if not markets:
        print("  No markets returned (API may be unreachable or no near-term markets found)")
        return markets

    print(f"  Found {len(markets)} near-term markets\n")
    for m in markets[:10]:
        print(f"  [{m.market_id[:20]}...]")
        print(f"    Title    : {m.title}")
        print(f"    Closes   : {fmt_time(m.close_time)}")
        print(f"    Yes/No   : {m.price.yes:.3f} / {m.price.no:.3f}")
        print(f"    Volume   : ${m.volume_usd or 0:,.0f}")
        print()
    if len(markets) > 10:
        print(f"  ... and {len(markets) - 10} more")
    return markets


async def test_arb_pipeline(kalshi_markets, poly_markets):
    print("\n" + "=" * 60)
    print("ARB PIPELINE — matching + detection")
    print("=" * 60)

    if not kalshi_markets or not poly_markets:
        print("  Skipping — one or both platforms returned no markets")
        return

    pairs = match_markets(kalshi_markets, poly_markets)
    print(f"  Matched pairs  : {len(pairs)}")

    if pairs:
        print("\n  Top 5 matches by score:")
        for km, pm, score in pairs[:5]:
            print(f"    [{score:.0f}] K: {km.title[:45]}")
            print(f"         P: {pm.title[:45]}")

    opps = detect_opportunities(pairs)
    print(f"\n  Arb opportunities found: {len(opps)}")

    if opps:
        print()
        for o in opps:
            days_left = (o.kalshi_market.close_time - datetime.now(timezone.utc)).days if o.kalshi_market.close_time else "?"
            print(f"  *** OPPORTUNITY ***")
            print(f"    Market      : {o.kalshi_market.title[:55]}")
            print(f"    Resolves in : {days_left} days")
            print(f"    Kalshi      : {o.kalshi_side} @ {o.kalshi_entry:.4f}")
            print(f"    Polymarket  : {o.poly_side} @ {o.poly_entry:.4f}")
            print(f"    Gross cost  : {o.gross_cost:.4f}  (profit before fees: {(1-o.gross_cost)*100:.2f}%)")
            print(f"    Est. fees   : ${o.fees:.4f}")
            print(f"    Net profit  : {o.net_profit_pct*100:.2f}% = ${o.net_profit_usd:.4f} on $50 position")
            print(f"    Match score : {o.match_score:.1f}/100")
            print()
    else:
        print("  No profitable arb found after fees — market is efficient right now or match set is small.")


async def main():
    print(f"\nLive API Test — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Resolution window: {MAX_DAYS_TO_RESOLUTION} days")

    kalshi_markets = await test_kalshi()
    poly_markets = await test_polymarket()
    await test_arb_pipeline(kalshi_markets, poly_markets)

    print("\n" + "=" * 60)
    print("Done.")


asyncio.run(main())
