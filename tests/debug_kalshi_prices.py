"""Check raw price fields on Kalshi binary markets."""
import sys, asyncio, time, base64
sys.path.insert(0, ".")
import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from config.settings import KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY, KALSHI_BASE_URL

async def main():
    key = serialization.load_pem_private_key(KALSHI_PRIVATE_KEY.encode(), password=None)
    path = "/trade-api/v2/markets"
    ts = str(round(time.time() * 1000))
    msg = (ts + "GET" + path).encode()
    sig = base64.b64encode(key.sign(msg, padding.PKCS1v15(), hashes.SHA256())).decode()
    headers = {
        "KALSHI-ACCESS-KEY": KALSHI_API_KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": sig,
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{KALSHI_BASE_URL}/markets",
                               params={"series_ticker": "KXNBA", "status": "open", "limit": 5},
                               headers=headers) as r:
            data = await r.json()

    price_fields = ["yes_ask", "yes_bid", "no_ask", "no_bid", "last_price",
                    "previous_yes_ask", "previous_yes_bid", "open_interest"]
    import json
    for m in data.get("markets", []):
        print(f"\n[{m['ticker']}] {m.get('title','')}")
        print(json.dumps(m, indent=2))

asyncio.run(main())
