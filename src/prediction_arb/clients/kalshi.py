"""Kalshi Trade API v2 client.

Market data endpoints are public. Order placement requires an API key whose requests are signed
with the account's private key: RSA-PSS/SHA-256 for RSA keys or Ed25519 for Ed25519 keys, over
``timestamp_ms + METHOD + path`` (path without query string).
https://docs.kalshi.com/getting_started/api_keys
"""

from __future__ import annotations

import asyncio
import base64
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa

from prediction_arb.clients.http import get_json, new_session
from prediction_arb.config import Settings
from prediction_arb.log import logger
from prediction_arb.models import Market, MarketPrice, OrderResult, Platform, Side

_PAGE_LIMIT = 1000
_MAX_PAGES_PER_SERIES = 5

PrivateKey = rsa.RSAPrivateKey | ed25519.Ed25519PrivateKey


class KalshiAuthError(RuntimeError):
    pass


def load_private_key(settings: Settings) -> PrivateKey | None:
    if settings.kalshi_private_key_path:
        pem = Path(settings.kalshi_private_key_path).expanduser().read_bytes()
    elif settings.kalshi_private_key:
        pem = settings.kalshi_private_key.encode()
    else:
        return None
    try:
        key = serialization.load_pem_private_key(pem, password=None)
    except (ValueError, TypeError) as exc:
        # Never include key material in the error message.
        raise KalshiAuthError(
            "Kalshi private key could not be parsed as an unencrypted PEM"
        ) from exc
    if not isinstance(key, rsa.RSAPrivateKey | ed25519.Ed25519PrivateKey):
        raise KalshiAuthError("Kalshi private key must be an RSA or Ed25519 key")
    return key


def sign_message(key: PrivateKey, message: bytes) -> str:
    if isinstance(key, ed25519.Ed25519PrivateKey):
        signature = key.sign(message)
    else:
        signature = key.sign(
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
    return base64.b64encode(signature).decode()


def _parse_time(value: Any) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def parse_market(raw: dict[str, Any], now: datetime | None = None) -> Market | None:
    """Convert one Kalshi ``/markets`` item into a :class:`Market`, or ``None`` if unusable."""
    now = now or datetime.now(timezone.utc)
    ticker = raw.get("ticker")
    raw_close = raw.get("close_time") or raw.get("expiration_time")
    yes_ask = raw.get("yes_ask_dollars")
    no_ask = raw.get("no_ask_dollars")
    if not ticker or not raw_close or yes_ask is None or no_ask is None:
        return None
    if raw.get("market_type", "binary") != "binary":
        return None
    try:
        close_time = _parse_time(raw_close)
        # close_time is a worst-case bound (e.g. "closes once a champion is declared, at the
        # latest in 2029"); expected_expiration_time is when the market should actually resolve.
        expected = raw.get("expected_expiration_time")
        resolves_at = _parse_time(expected) if expected else close_time
        price = MarketPrice(yes=float(yes_ask), no=float(no_ask))
        volume = float(raw.get("volume_fp") or raw.get("volume") or 0)
    except (TypeError, ValueError):
        logger.debug(f"Kalshi: skipping unparseable market {ticker}")
        return None
    if close_time <= now:
        return None
    return Market(
        platform=Platform.KALSHI,
        market_id=ticker,
        title=str(raw.get("title", "")),
        price=price,
        resolves_at=resolves_at,
        volume=volume,
        is_active=raw.get("status") == "active",
    )


class KalshiClient:
    def __init__(self, settings: Settings, session: aiohttp.ClientSession | None = None):
        self.settings = settings
        self.base_url = settings.kalshi_base_url
        self._base_path = urlparse(self.base_url).path.rstrip("/")
        self._session = session
        self._owns_session = session is None
        self._key = load_private_key(settings)

    async def __aenter__(self) -> KalshiClient:
        if self._session is None:
            self._session = new_session(self.settings.http_timeout_sec)
        return self

    def _require_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("use 'async with KalshiClient(settings)' before making requests")
        return self._session

    async def __aexit__(self, *_: object) -> None:
        if self._session and self._owns_session:
            await self._session.close()

    @property
    def can_trade(self) -> bool:
        return self._key is not None and bool(self.settings.kalshi_api_key_id)

    def auth_headers(self, method: str, endpoint: str) -> dict[str, str]:
        if not self.can_trade:
            return {}
        timestamp = str(int(time.time() * 1000))
        message = f"{timestamp}{method.upper()}{self._base_path}{endpoint}".encode()
        return {
            "KALSHI-ACCESS-KEY": self.settings.kalshi_api_key_id,
            "KALSHI-ACCESS-SIGNATURE": sign_message(self._key, message),  # type: ignore[arg-type]
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
        }

    async def _fetch_series(self, series: str) -> list[dict[str, Any]]:
        session = self._require_session()
        markets: list[dict[str, Any]] = []
        cursor = ""
        for _ in range(_MAX_PAGES_PER_SERIES):
            params: dict[str, Any] = {
                "series_ticker": series,
                "status": "open",
                "limit": _PAGE_LIMIT,
            }
            if cursor:
                params["cursor"] = cursor
            try:
                data = await get_json(session, f"{self.base_url}/markets", params=params)
            except Exception as exc:
                logger.warning(f"Kalshi: series {series} fetch failed: {exc}")
                break
            markets.extend(data.get("markets", []))
            cursor = data.get("cursor") or ""
            if not cursor:
                break
        return markets

    async def get_markets(self) -> list[Market]:
        batches = await asyncio.gather(
            *(self._fetch_series(s) for s in self.settings.kalshi_series)
        )
        now = datetime.now(timezone.utc)
        seen: set[str] = set()
        markets: list[Market] = []
        for raw in (m for batch in batches for m in batch):
            market = parse_market(raw, now)
            if market and market.market_id not in seen:
                seen.add(market.market_id)
                markets.append(market)
        logger.debug(
            f"Kalshi: {len(markets)} open binary markets across {len(self.settings.kalshi_series)} series"
        )
        return markets

    async def place_order(
        self, ticker: str, side: Side, price: float, contracts: int
    ) -> OrderResult:
        """Submit a fill-or-kill limit buy. Either the full size fills at ``price`` or nothing does."""
        session = self._require_session()
        if not self.can_trade:
            return OrderResult(Platform.KALSHI, ok=False, error="Kalshi credentials not configured")

        price_cents = round(price * 100)
        if not 1 <= price_cents <= 99:
            return OrderResult(Platform.KALSHI, ok=False, error=f"price {price} out of range")
        endpoint = "/portfolio/orders"
        payload = {
            "ticker": ticker,
            "client_order_id": str(uuid.uuid4()),
            "action": "buy",
            "side": side.value,
            "count": contracts,
            f"{side.value}_price": price_cents,
            "time_in_force": "fill_or_kill",
        }
        try:
            async with session.post(
                f"{self.base_url}{endpoint}",
                json=payload,
                headers=self.auth_headers("POST", endpoint),
            ) as resp:
                body = await resp.json(content_type=None)
                if resp.status not in (200, 201):
                    return OrderResult(
                        Platform.KALSHI,
                        ok=False,
                        status=str(resp.status),
                        error=str(body)[:300],
                        raw=body,
                    )
        except Exception as exc:
            return OrderResult(Platform.KALSHI, ok=False, error=f"{type(exc).__name__}: {exc}")

        order = body.get("order", {}) if isinstance(body, dict) else {}
        status = order.get("status", "")
        return OrderResult(
            Platform.KALSHI,
            ok=status == "executed",
            order_id=order.get("order_id"),
            status=status,
            error=None if status == "executed" else f"order not filled (status={status!r})",
            raw=body,
        )
