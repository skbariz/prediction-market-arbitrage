"""
Debug raw API responses to identify correct field names and endpoints.
"""
import sys
import asyncio
import json
from datetime import datetime, timezone, timedelta
sys.path.insert(0, ".")

import aiohttp


async def debug_polymarket_gamma():
    """Polymarket Gamma API supports active/date filtering."""
    print("\n=== POLYMARKET GAMMA API (active markets, next 7 days) ===")
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=7)
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        "active": "true",
        "closed": "false",
        "end_date_min": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_date_max": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 5,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            print(f"Status: {resp.status}")
            if resp.status != 200:
                print(await resp.text())
                return
            data = await resp.json()

    markets = data if isinstance(data, list) else data.get("data", [])
    print(f"Returned {len(markets)} markets")
    if markets:
        m = markets[0]
        print(f"\nFirst market keys: {list(m.keys())}")
        date_fields = {k: v for k, v in m.items() if any(x in k.lower() for x in ["date", "time", "end", "expir", "close", "resolv"])}
        print(f"\nDate fields: {json.dumps(date_fields, indent=2, default=str)}")
        token_fields = {k: v for k, v in m.items() if any(x in k.lower() for x in ["token", "condition", "clob", "outcome", "price"])}
        print(f"\nToken/price fields: {json.dumps(token_fields, indent=2, default=str)}")
        print(f"\nSample title: {m.get('question') or m.get('title')}")


async def debug_polymarket_clob_paginate():
    """Check if CLOB /markets supports active filter param."""
    print("\n=== POLYMARKET CLOB — with active=true param ===")
    url = "https://clob.polymarket.com/markets"
    params = {"limit": 5, "active": "true"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            print(f"Status: {resp.status}")
            if resp.status != 200:
                print(await resp.text())
                return
            data = await resp.json()

    markets = data.get("data", [])
    print(f"Returned {len(markets)} markets")
    if markets:
        m = markets[0]
        closed = m.get("closed")
        active = m.get("active")
        end_date = m.get("end_date_iso")
        print(f"First market: active={active}, closed={closed}, end_date={end_date}")
        print(f"Title: {m.get('question', '')[:60]}")


async def debug_kalshi_auth():
    print("\n=== KALSHI — auth status ===")
    print("Kalshi requires an API key for all endpoints.")
    print("Get yours at: https://kalshi.com/account/api-access")
    print("Set KALSHI_API_KEY and KALSHI_API_KEY_ID in your .env file.")


async def main():
    await debug_polymarket_gamma()
    await debug_polymarket_clob_paginate()
    await debug_kalshi_auth()

asyncio.run(main())
