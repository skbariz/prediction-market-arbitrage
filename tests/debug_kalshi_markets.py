"""
Explore Kalshi's market categories and series to find standard binary markets.
"""
import sys, asyncio
sys.path.insert(0, ".")

from src.clients.kalshi import KalshiClient

async def main():
    async with KalshiClient() as client:
        # Fetch a large batch and inspect what series/categories exist
        import aiohttp, time, base64
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from config.settings import KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY, KALSHI_BASE_URL

        key = serialization.load_pem_private_key(KALSHI_PRIVATE_KEY.encode(), password=None)
        path = "/trade-api/v2/markets"
        url = f"{KALSHI_BASE_URL}/markets"

        ts = str(round(time.time() * 1000))
        msg = (ts + "GET" + path).encode()
        sig = base64.b64encode(key.sign(msg, padding.PKCS1v15(), hashes.SHA256())).decode()
        headers = {
            "KALSHI-ACCESS-KEY": KALSHI_API_KEY_ID,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "KALSHI-ACCESS-TIMESTAMP": ts,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params={"limit": 1000, "status": "open"}, headers=headers) as r:
                data = await r.json()

        markets = data.get("markets", [])
        print(f"Total markets returned: {len(markets)}")

        # Tally by series prefix
        from collections import Counter
        series = Counter()
        for m in markets:
            ticker = m.get("ticker", "")
            prefix = ticker.split("-")[0] if "-" in ticker else ticker[:10]
            series[prefix] += 1

        print("\nMarket series (top 30):")
        for s, count in series.most_common(30):
            print(f"  {s:<45} {count}")

        # Show non-KXMV markets
        standard = [m for m in markets if not m["ticker"].startswith("KXMV") and not m["ticker"].startswith("KXMVE")]
        print(f"\nNon-parlay markets: {len(standard)}")
        for m in standard[:20]:
            print(f"  [{m['ticker']}]  {m.get('title','')[:70]}")

asyncio.run(main())
