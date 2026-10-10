"""Polymarket client.

Market discovery uses the public Gamma API. Order placement uses Polymarket's official
``py-clob-client`` SDK (install with ``pip install "prediction-arb[trading]"``), which handles the
EIP-712 order signing and L2 API authentication the CLOB requires.
https://docs.polymarket.com/developers/CLOB/introduction
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import aiohttp

from prediction_arb.clients.http import get_json, new_session
from prediction_arb.config import Settings
from prediction_arb.log import logger
from prediction_arb.models import Market, MarketPrice, OrderResult, Platform, Side

_PAGE_SIZE = 100


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _fee_rate(raw: dict[str, Any]) -> float | None:
    if raw.get("feesEnabled") is False:
        return 0.0
    schedule = raw.get("feeSchedule")
    if isinstance(schedule, dict):
        rate = schedule.get("rate")
        if isinstance(rate, int | float):
            return float(rate)
    return None


def parse_market(raw: dict[str, Any], now: datetime | None = None) -> Market | None:
    """Convert one Gamma ``/markets`` item into a :class:`Market`, or ``None`` if unusable.

    Prices are the best executable asks. Gamma's ``bestBid``/``bestAsk`` quote the first outcome's
    order book; buying the other outcome costs ``1 - bestBid``. Falls back to ``outcomePrices``
    (mid prices) when the book quotes are missing.
    """
    now = now or datetime.now(timezone.utc)
    condition_id = raw.get("conditionId")
    raw_close = raw.get("endDate") or raw.get("end_date_iso")
    if not condition_id or not raw_close:
        return None

    outcomes = [str(o).strip().lower() for o in _json_list(raw.get("outcomes"))]
    if sorted(outcomes) != ["no", "yes"]:
        return None
    yes_idx, no_idx = outcomes.index("yes"), outcomes.index("no")
    prices = _json_list(raw.get("outcomePrices"))
    tokens = _json_list(raw.get("clobTokenIds"))

    try:
        close_time = datetime.fromisoformat(str(raw_close).replace("Z", "+00:00"))
        mid = [float(p) for p in prices] if len(prices) == 2 else None
    except (TypeError, ValueError):
        return None
    if close_time <= now:
        return None

    best_ask = _positive_float(raw.get("bestAsk"))
    best_bid = _positive_float(raw.get("bestBid"))
    asks = [None, None]
    if best_ask is not None:
        asks[0] = best_ask
    if best_bid is not None:
        asks[1] = round(1.0 - best_bid, 6)
    for i in (0, 1):
        if asks[i] is None and mid is not None:
            asks[i] = mid[i]
    if asks[0] is None or asks[1] is None:
        return None

    return Market(
        platform=Platform.POLYMARKET,
        market_id=str(condition_id),
        title=str(raw.get("question", "")),
        price=MarketPrice(yes=asks[yes_idx], no=asks[no_idx]),
        resolves_at=close_time,
        volume=float(raw.get("volumeClob") or raw.get("volume") or 0),
        is_active=bool(raw.get("active"))
        and not raw.get("closed")
        and raw.get("acceptingOrders", True) is not False,
        yes_token_id=str(tokens[yes_idx]) if len(tokens) == 2 else None,
        no_token_id=str(tokens[no_idx]) if len(tokens) == 2 else None,
        tick_size=_positive_float(raw.get("orderPriceMinTickSize")),
        min_order_size=_positive_float(raw.get("orderMinSize")),
        neg_risk=bool(raw.get("negRisk")),
        fee_rate=_fee_rate(raw),
    )


class PolymarketClient:
    def __init__(self, settings: Settings, session: aiohttp.ClientSession | None = None):
        self.settings = settings
        self._session = session
        self._owns_session = session is None
        self._clob: Any = None

    async def __aenter__(self) -> PolymarketClient:
        if self._session is None:
            self._session = new_session(self.settings.http_timeout_sec)
        return self

    def _require_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("use 'async with PolymarketClient(settings)' before making requests")
        return self._session

    async def __aexit__(self, *_: object) -> None:
        if self._session and self._owns_session:
            await self._session.close()

    async def _fetch_page(self, offset: int) -> list[dict[str, Any]]:
        session = self._require_session()
        params = {
            "active": "true",
            "closed": "false",
            "limit": _PAGE_SIZE,
            "offset": offset,
            # Most-traded first, so the page budget covers the liquid markets worth arbitraging.
            "order": "volume24hr",
            "ascending": "false",
        }
        try:
            data = await get_json(session, f"{self.settings.poly_gamma_url}/markets", params=params)
        except Exception as exc:
            logger.warning(f"Polymarket: page offset={offset} fetch failed: {exc}")
            return []
        return data if isinstance(data, list) else data.get("data", [])

    async def get_markets(self) -> list[Market]:
        offsets = [i * _PAGE_SIZE for i in range(self.settings.poly_pages)]
        pages = await asyncio.gather(*(self._fetch_page(o) for o in offsets))
        now = datetime.now(timezone.utc)
        seen: set[str] = set()
        markets: list[Market] = []
        for raw in (m for page in pages for m in page):
            market = parse_market(raw, now)
            if market and market.market_id not in seen:
                seen.add(market.market_id)
                markets.append(market)
        logger.debug(f"Polymarket: {len(markets)} open binary markets")
        return markets

    def _clob_client(self) -> Any:
        if self._clob is not None:
            return self._clob
        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds
        except ImportError as exc:
            raise RuntimeError(
                'Live Polymarket trading requires the trading extra: pip install "prediction-arb[trading]"'
            ) from exc

        s = self.settings
        client = ClobClient(
            s.poly_clob_url,
            chain_id=s.poly_chain_id,
            key=s.poly_private_key,
            signature_type=s.poly_signature_type,
            funder=s.poly_funder_address or None,
        )
        if s.poly_api_key and s.poly_api_secret and s.poly_passphrase:
            client.set_api_creds(ApiCreds(s.poly_api_key, s.poly_api_secret, s.poly_passphrase))
        else:
            client.set_api_creds(client.create_or_derive_api_creds())
        self._clob = client
        return client

    @property
    def can_trade(self) -> bool:
        return self.settings.has_polymarket_credentials

    async def place_order(
        self, market: Market, side: Side, price: float, shares: int
    ) -> OrderResult:
        """Submit a fill-or-kill limit buy of ``shares`` outcome tokens at ``price``."""
        token_id = market.token_id(side)
        if not self.can_trade:
            return OrderResult(
                Platform.POLYMARKET, ok=False, error="Polymarket credentials not configured"
            )
        if not token_id:
            return OrderResult(Platform.POLYMARKET, ok=False, error="market has no CLOB token id")

        def _submit() -> dict[str, Any]:
            from py_clob_client.clob_types import OrderArgs, OrderType, PartialCreateOrderOptions
            from py_clob_client.order_builder.constants import BUY

            client = self._clob_client()
            options = PartialCreateOrderOptions(
                tick_size=f"{market.tick_size:g}" if market.tick_size else None,
                neg_risk=market.neg_risk,
            )
            order = client.create_order(
                OrderArgs(token_id=token_id, price=price, size=float(shares), side=BUY), options
            )
            return client.post_order(order, OrderType.FOK)

        try:
            resp = await asyncio.to_thread(_submit)
        except Exception as exc:
            return OrderResult(Platform.POLYMARKET, ok=False, error=f"{type(exc).__name__}: {exc}")

        ok = bool(resp.get("success")) and not resp.get("errorMsg")
        return OrderResult(
            Platform.POLYMARKET,
            ok=ok,
            order_id=resp.get("orderID"),
            status=str(resp.get("status", "")),
            error=None if ok else str(resp.get("errorMsg") or "order rejected"),
            raw=resp,
        )
