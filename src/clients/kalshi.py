import time
import base64
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from src.models.market import Market, MarketPrice
from src.utils.logger import logger
from config import settings


class KalshiClient:
    def __init__(self):
        self.base_url = settings.KALSHI_BASE_URL
        self._session: Optional[aiohttp.ClientSession] = None
        self._private_key = self._load_private_key()

    def _load_private_key(self):
        raw = settings.KALSHI_PRIVATE_KEY.strip()
        if not raw:
            return None
        try:
            return serialization.load_pem_private_key(raw.encode(), password=None)
        except Exception as e:
            logger.error(f"Kalshi: failed to load private key: {e}")
            return None

    def _sign_headers(self, method: str, path: str) -> dict:
        if not self._private_key or not settings.KALSHI_API_KEY_ID:
            return {}
        timestamp = str(round(time.time() * 1000))
        msg = (timestamp + method.upper() + path).encode("utf-8")
        sig = self._private_key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
        return {
            "KALSHI-ACCESS-KEY": settings.KALSHI_API_KEY_ID,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json",
        }

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *_):
        if self._session:
            await self._session.close()

    # Series that have standard binary markets matchable against Polymarket.
    # The default API sort returns only sports parlays (KXMV*), so we query each series explicitly.
    SERIES = ["KXNBA", "KXNHL", "KXMLB", "KXNFL", "KXBTC", "KXETH", "KXECON",
              "KXPRES", "KXGOV", "KXWORLD", "KXTECH", "KXSCI"]

    async def _fetch_series(self, series: str) -> list:
        path = "/trade-api/v2/markets"
        url = f"{self.base_url}/markets"
        params = {"series_ticker": series, "status": "open", "limit": 200}
        headers = self._sign_headers("GET", path)
        try:
            async with self._session.get(url, params=params, headers=headers) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data.get("markets", [])
        except Exception as e:
            logger.warning(f"Kalshi series {series} failed: {e}")
            return []

    async def get_markets(self, limit: int = 200) -> List[Market]:
        now = datetime.now(timezone.utc)

        results = await asyncio.gather(*[self._fetch_series(s) for s in self.SERIES])
        raw = [m for batch in results for m in batch]

        seen = set()
        markets = []
        for m in raw:
            ticker = m.get("ticker", "")
            if ticker in seen:
                continue
            seen.add(ticker)
            try:
                raw_close = m.get("close_time") or m.get("expiration_time")
                if not raw_close:
                    continue
                close_time = datetime.fromisoformat(raw_close.replace("Z", "+00:00"))
                if close_time <= now:
                    continue

                # New API returns prices in dollars (0.00–1.00) via _dollars fields
                yes_ask = m.get("yes_ask_dollars")
                no_ask = m.get("no_ask_dollars")
                if yes_ask is None or no_ask is None:
                    continue
                markets.append(Market(
                    platform="kalshi",
                    market_id=ticker,
                    title=m.get("title", ""),
                    price=MarketPrice(yes=float(yes_ask), no=float(no_ask)),
                    close_time=close_time,
                    volume_usd=float(m.get("volume_fp") or m.get("volume_24h_fp") or 0),
                    is_active=m.get("status") == "active",
                ))
            except Exception as e:
                logger.warning(f"Kalshi market parse error: {e} — {ticker}")

        logger.debug(f"Kalshi: {len(markets)} open binary markets across {len(self.SERIES)} series")
        return markets

    async def place_order(
        self,
        market_id: str,
        side: str,
        price_cents: int,
        count: int,
        dry_run: bool = True,
    ) -> dict:
        if dry_run:
            logger.info(f"[DRY RUN] Kalshi order: {market_id} {side} @ {price_cents}¢ x{count}")
            return {"status": "dry_run", "order_id": "DRY-KALSHI"}

        path = "/trade-api/v2/portfolio/orders"
        url = f"{self.base_url}/portfolio/orders"
        payload = {
            "ticker": market_id,
            "action": "buy",
            "side": side,
            "type": "limit",
            "yes_price": price_cents if side == "yes" else 100 - price_cents,
            "count": count,
        }
        headers = self._sign_headers("POST", path)
        try:
            async with self._session.post(url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                return await resp.json()
        except Exception as e:
            logger.error(f"Kalshi place_order failed: {e}")
            return {"status": "failed", "error": str(e)}
