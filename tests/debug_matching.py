"""
Show the top scoring Kalshi/Polymarket title pairs just below the match threshold
to find out if we're missing real matches.
"""
import sys, asyncio
sys.path.insert(0, ".")

from rapidfuzz import fuzz
from src.clients.kalshi import KalshiClient
from src.clients.polymarket import PolymarketClient

async def main():
    async with KalshiClient() as kc, PolymarketClient() as pc:
        k_markets, p_markets = await asyncio.gather(kc.get_markets(), pc.get_markets(pages=10))

    print(f"Kalshi: {len(k_markets)} | Polymarket: {len(p_markets)}")

    # Score every pair, collect top 30 regardless of threshold
    scores = []
    for km in k_markets:
        for pm in p_markets:
            s = fuzz.token_set_ratio(km.title.lower(), pm.title.lower())
            if s >= 70:
                scores.append((s, km, pm))

    scores.sort(key=lambda x: x[0], reverse=True)

    print(f"\nAll pairs scoring >= 70 (total: {len(scores)}):\n")
    for s, km, pm in scores[:40]:
        print(f"  [{s:>3}] K: {km.title[:60]}")
        print(f"        P: {pm.title[:60]}")
        print()

asyncio.run(main())
