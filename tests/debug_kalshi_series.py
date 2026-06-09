"""
Test Kalshi API with series_ticker filters and alternate base URLs
to locate standard binary markets (NBA Finals, elections, etc.)
"""
import sys, asyncio, time, base64
sys.path.insert(0, ".")

import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from config.settings import KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY

def make_headers(method, path, base="https://api.elections.kalshi.com"):
    key = serialization.load_pem_private_key(KALSHI_PRIVATE_KEY.encode(), password=None)
    ts = str(round(time.time() * 1000))
    msg = (ts + method.upper() + path).encode()
    sig = base64.b64encode(key.sign(msg, padding.PKCS1v15(), hashes.SHA256())).decode()
    return {
        "KALSHI-ACCESS-KEY": KALSHI_API_KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": sig,
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }

async def fetch(session, base, path, params=None):
    url = base + path
    headers = make_headers("GET", path, base)
    async with session.get(url, params=params or {}, headers=headers) as r:
        return r.status, await r.json() if r.status == 200 else await r.text()

async def main():
    async with aiohttp.ClientSession() as session:

        # Try series_ticker filters on elections API
        series_to_try = ["KXNBA", "KXNHL", "KXMLB", "KXNFL", "KXPRES", "KXBTC", "KXECON"]
        print("=== series_ticker filter on elections API ===")
        for s in series_to_try:
            status, data = await fetch(session, "https://api.elections.kalshi.com",
                                        "/trade-api/v2/markets",
                                        {"series_ticker": s, "status": "open", "limit": 5})
            count = len(data.get("markets", [])) if isinstance(data, dict) else 0
            print(f"  {s}: status={status}, markets={count}")
            if count:
                for m in data["markets"][:2]:
                    print(f"    [{m['ticker']}] {m.get('title','')[:60]}")

        # Try the trading API directly (maybe it still serves some markets)
        print("\n=== trading-api.kalshi.com direct ===")
        status, data = await fetch(session, "https://trading-api.kalshi.com",
                                    "/trade-api/v2/markets",
                                    {"status": "open", "limit": 5})
        print(f"  status={status}, response={str(data)[:200]}")

        # Try the newer kalshi.com API
        print("\n=== api.kalshi.com ===")
        for path in ["/trade-api/v2/markets", "/v1/markets"]:
            status, data = await fetch(session, "https://api.kalshi.com", path,
                                        {"status": "open", "limit": 5})
            count = len(data.get("markets", [])) if isinstance(data, dict) else 0
            print(f"  {path}: status={status}, markets={count}")
            if count:
                for m in data["markets"][:2]:
                    print(f"    [{m['ticker']}] {m.get('title','')[:60]}")

asyncio.run(main())
