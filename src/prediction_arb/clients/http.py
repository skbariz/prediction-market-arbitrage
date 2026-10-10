"""Shared HTTP helpers: session construction and retrying JSON GETs."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from prediction_arb import __version__

USER_AGENT = (
    f"prediction-arb/{__version__} (+https://github.com/skbariz/prediction-market-arbitrage)"
)
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class HttpError(RuntimeError):
    def __init__(self, status: int, url: str, body: str = ""):
        super().__init__(f"HTTP {status} from {url}: {body[:200]}")
        self.status = status


def new_session(timeout_sec: float) -> aiohttp.ClientSession:
    return aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout_sec),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )


async def get_json(
    session: aiohttp.ClientSession,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    retries: int = 3,
    backoff_sec: float = 1.0,
) -> Any:
    for attempt in range(retries + 1):
        try:
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                body = await resp.text()
                if resp.status not in _RETRYABLE_STATUS or attempt == retries:
                    raise HttpError(resp.status, url, body)
        except (aiohttp.ClientConnectionError, asyncio.TimeoutError):
            if attempt == retries:
                raise
        await asyncio.sleep(backoff_sec * 2**attempt)
    raise AssertionError("unreachable")
