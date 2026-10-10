"""One scan: fetch both platforms concurrently, match markets, and detect opportunities."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from prediction_arb.clients.kalshi import KalshiClient
from prediction_arb.clients.polymarket import PolymarketClient
from prediction_arb.config import Settings
from prediction_arb.detector import detect_opportunities
from prediction_arb.matcher import match_markets
from prediction_arb.models import ArbOpportunity, Market, MatchedPair


@dataclass
class ScanResult:
    kalshi_markets: list[Market]
    poly_markets: list[Market]
    pairs: list[MatchedPair]
    opportunities: list[ArbOpportunity]


async def scan(kalshi: KalshiClient, poly: PolymarketClient, settings: Settings) -> ScanResult:
    kalshi_markets, poly_markets = await asyncio.gather(kalshi.get_markets(), poly.get_markets())
    pairs = match_markets(kalshi_markets, poly_markets, settings.match_score_threshold)
    opportunities = detect_opportunities(pairs, settings)
    return ScanResult(kalshi_markets, poly_markets, pairs, opportunities)
