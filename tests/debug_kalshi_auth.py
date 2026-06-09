"""
Debug Kalshi auth by printing the full 401 response body and
testing different signature formats.
"""
import sys, time, base64, asyncio
sys.path.insert(0, ".")

import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from config.settings import KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY, KALSHI_BASE_URL

BASE = "https://api.elections.kalshi.com"
PATH = "/trade-api/v2/markets"

def load_key():
    return serialization.load_pem_private_key(KALSHI_PRIVATE_KEY.encode(), password=None)

def sign(private_key, method, path, timestamp):
    msg = (timestamp + method.upper() + path).encode("utf-8")
    sig = private_key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()

async def try_request(label, headers):
    url = BASE + PATH + "?limit=1&status=open"
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=headers) as r:
            body = await r.text()
            print(f"\n[{label}] status={r.status}")
            print(f"  Response: {body[:300]}")

async def main():
    print(f"Key ID : {KALSHI_API_KEY_ID}")
    print(f"Key loaded: {bool(KALSHI_PRIVATE_KEY)}")

    key = load_key()
    ts = str(round(time.time() * 1000))

    # Format 1: headers KALSHI-ACCESS-KEY / SIGNATURE / TIMESTAMP
    sig = sign(key, "GET", PATH, ts)
    await try_request("KALSHI-ACCESS headers", {
        "KALSHI-ACCESS-KEY": KALSHI_API_KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": sig,
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "Content-Type": "application/json",
    })

    # Format 2: some versions use seconds not milliseconds
    ts_sec = str(round(time.time()))
    sig2 = sign(key, "GET", PATH, ts_sec)
    await try_request("seconds timestamp", {
        "KALSHI-ACCESS-KEY": KALSHI_API_KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": sig2,
        "KALSHI-ACCESS-TIMESTAMP": ts_sec,
        "Content-Type": "application/json",
    })

asyncio.run(main())
