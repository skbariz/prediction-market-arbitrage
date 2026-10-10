"""Finds fee-adjusted arbitrage in matched market pairs.

For each pair two hedges are possible, and each pays exactly $1 per contract whatever happens:

* buy YES on Kalshi + buy NO on Polymarket
* buy NO on Kalshi + buy YES on Polymarket

The hedge is profitable when ``contracts * $1`` exceeds the combined cost of both legs plus
taker fees. Both legs are sized to the *same number of contracts*; sizing by dollar amount would
leave the position partially unhedged.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from prediction_arb.config import Settings
from prediction_arb.fees import kalshi_fee, polymarket_fee
from prediction_arb.models import ArbOpportunity, MatchedPair, Side

_DIRECTIONS = ((Side.YES, Side.NO), (Side.NO, Side.YES))


def _size_hedge(
    k_price: float, p_price: float, k_rate: float, p_rate: float, budget: float
) -> tuple[int, float, float]:
    """Largest contract count whose all-in cost fits ``budget``, with the fees at that size."""
    per_contract = (
        k_price + p_price + k_rate * k_price * (1 - k_price) + p_rate * p_price * (1 - p_price)
    )
    contracts = math.floor(budget / per_contract)
    while contracts > 0:
        k_fee = kalshi_fee(k_price, contracts, k_rate)
        p_fee = polymarket_fee(p_price, contracts, p_rate)
        if contracts * (k_price + p_price) + k_fee + p_fee <= budget:
            return contracts, k_fee, p_fee
        contracts -= 1
    return 0, 0.0, 0.0


def evaluate_pair(pair: MatchedPair, settings: Settings) -> ArbOpportunity | None:
    """Return the most profitable hedge for ``pair`` that clears ``MIN_PROFIT_PCT``, if any."""
    poly_rate = (
        pair.polymarket.fee_rate
        if pair.polymarket.fee_rate is not None
        else settings.poly_default_fee_rate
    )
    best: ArbOpportunity | None = None
    for k_side, p_side in _DIRECTIONS:
        k_price = pair.kalshi.price.ask(k_side)
        p_price = pair.polymarket.price.ask(p_side)
        if not (0 < k_price < 1 and 0 < p_price < 1) or k_price + p_price >= 1:
            continue
        contracts, k_fee, p_fee = _size_hedge(
            k_price, p_price, settings.kalshi_fee_rate, poly_rate, settings.max_position_usd
        )
        if contracts == 0:
            continue
        opp = ArbOpportunity(
            pair=pair,
            kalshi_side=k_side,
            poly_side=p_side,
            kalshi_price=k_price,
            poly_price=p_price,
            contracts=contracts,
            kalshi_fee=k_fee,
            poly_fee=p_fee,
        )
        if opp.net_profit_pct >= settings.min_profit_pct and (
            best is None or opp.net_profit_pct > best.net_profit_pct
        ):
            best = opp
    return best


def detect_opportunities(pairs: Iterable[MatchedPair], settings: Settings) -> list[ArbOpportunity]:
    opportunities = [opp for pair in pairs if (opp := evaluate_pair(pair, settings))]
    opportunities.sort(key=lambda o: o.net_profit_pct, reverse=True)
    return opportunities
