import asyncio, aiohttp, sys
sys.path.insert(0, ".")

async def main():
    async with aiohttp.ClientSession() as s:
        # Try offset-based pagination
        for offset in [0, 100, 200]:
            async with s.get("https://gamma-api.polymarket.com/markets",
                             params={"active": "true", "closed": "false",
                                     "limit": 100, "offset": offset}) as r:
                data = await r.json()
                items = data if isinstance(data, list) else data.get("data", [])
                first = items[0].get("question", "")[:50] if items else "empty"
                print(f"offset={offset} -> {len(items)} markets | first: {first}")

        # Also try order param to sort by volume desc for best matching candidates
        async with s.get("https://gamma-api.polymarket.com/markets",
                         params={"active": "true", "closed": "false",
                                 "limit": 100, "offset": 0,
                                 "order": "volume", "ascending": "false"}) as r:
            data = await r.json()
            items = data if isinstance(data, list) else data.get("data", [])
            print(f"\norder=volume desc -> {len(items)} markets")
            for m in items[:5]:
                print(f"  {m.get('question','')[:60]}  vol={m.get('volumeClob',0):.0f}")

asyncio.run(main())
