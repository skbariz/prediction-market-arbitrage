import asyncio
import aiohttp
import json as _json
from datetime import datetime, timezone
from typing import List, Optional
from src.models.market import Market, MarketPrice
from src.utils.logger import logger
from config import settings

GAMMA_URL = "https://gamma-api.polymarket.com"


class PolymarketClient:
    def __init__(self):
        self.clob_url = settings.POLY_CLOB_URL
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *_):
        if self._session:
            await self._session.close()

    def _auth_headers(self) -> dict:
        return {
            "POLY_ADDRESS": settings.POLY_API_KEY,
            "POLY_SIGNATURE": "",
            "POLY_TIMESTAMP": "",
            "POLY_NONCE": "",
            "Content-Type": "application/json",
        }

    async def _fetch_page(self, offset: int) -> list:
        url = f"{GAMMA_URL}/markets"
        params = {"active": "true", "closed": "false", "limit": 100, "offset": offset}
        try:
            async with self._session.get(url, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data if isinstance(data, list) else data.get("data", [])
        except Exception as e:
            logger.warning(f"Polymarket page offset={offset} failed: {e}")
            return []

    async def get_markets(self, pages: int = 10) -> List[Market]:
        """
        Fetches up to `pages * 100` active markets using parallel offset pagination.
        Default of 10 pages = up to 1000 markets.
        """
        now = datetime.now(timezone.utc)
        offsets = [i * 100 for i in range(pages)]
        results = await asyncio.gather(*[self._fetch_page(o) for o in offsets])
        raw_markets = [m for page in results for m in page]
        # Deduplicate by conditionId
        seen = set()
        deduped = []
        for m in raw_markets:
            cid = m.get("conditionId")
            if cid and cid not in seen:
                seen.add(cid)
                deduped.append(m)
        raw_markets = deduped
        markets = []
        for m in raw_markets:
            try:
                raw_close = m.get("endDate") or m.get("end_date_iso")
                if not raw_close:
                    continue
                close_time = datetime.fromisoformat(raw_close.replace("Z", "+00:00"))
                if close_time <= now:
                    continue

                outcomes = _json.loads(m.get("outcomes", "[]"))
                prices_raw = _json.loads(m.get("outcomePrices", "[]"))
                token_ids = _json.loads(m.get("clobTokenIds", "[]"))

                if not outcomes or not prices_raw:
                    continue

                yes_idx = next((i for i, o in enumerate(outcomes) if o.lower() == "yes"), None)
                no_idx = next((i for i, o in enumerate(outcomes) if o.lower() == "no"), None)
                if yes_idx is None or no_idx is None:
                    continue

                yes_price = float(prices_raw[yes_idx])
                yes_token_id = token_ids[yes_idx] if yes_idx < len(token_ids) else None
                no_token_id = token_ids[no_idx] if no_idx < len(token_ids) else None

                markets.append(Market(
                    platform="polymarket",
                    market_id=m["conditionId"],
                    title=m.get("question", ""),
                    price=MarketPrice.from_yes(yes_price),
                    close_time=close_time,
                    volume_usd=float(m.get("volumeClob") or m.get("volume") or 0),
                    is_active=bool(m.get("active")) and not bool(m.get("closed")),
                    yes_token_id=yes_token_id,
                    no_token_id=no_token_id,
                ))
            except Exception as e:
                logger.warning(f"Polymarket market parse error: {e} — {m.get('conditionId')}")

        logger.debug(f"Polymarket: {len(markets)} open markets")
        return markets

    async def place_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size_usd: float,
        dry_run: bool = True,
    ) -> dict:
        if dry_run:
            logger.info(f"[DRY RUN] Polymarket order: {token_id} {side} @ {price:.4f} ${size_usd:.2f}")
            return {"status": "dry_run", "order_id": "DRY-POLY"}

        url = f"{self.clob_url}/order"
        payload = {
            "tokenID": token_id,
            "price": price,
            "side": side.upper(),
            "size": size_usd,
            "orderType": "GTC",
        }
        headers = self._auth_headers()
        try:
            async with self._session.post(url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                return await resp.json()
        except Exception as e:
            logger.error(f"Polymarket place_order failed: {e}")
            return {"status": "failed", "error": str(e)}
