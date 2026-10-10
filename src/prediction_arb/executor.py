"""Places both legs of an arbitrage at the same time."""

from __future__ import annotations

import asyncio
from typing import Protocol

from prediction_arb.log import logger
from prediction_arb.models import (
    ArbOpportunity,
    Market,
    OrderResult,
    Platform,
    Position,
    PositionStatus,
    Side,
)


class KalshiTrader(Protocol):
    async def place_order(
        self, ticker: str, side: Side, price: float, contracts: int
    ) -> OrderResult: ...


class PolymarketTrader(Protocol):
    async def place_order(
        self, market: Market, side: Side, price: float, shares: int
    ) -> OrderResult: ...


def _as_result(outcome: OrderResult | BaseException, platform: Platform) -> OrderResult:
    if isinstance(outcome, OrderResult):
        return outcome
    if not isinstance(outcome, Exception):
        raise outcome
    return OrderResult(platform, ok=False, error=f"{type(outcome).__name__}: {outcome}")


def describe(opp: ArbOpportunity) -> str:
    return (
        f"{opp.kalshi_market.title[:60]} | {opp.contracts} contracts | "
        f"Kalshi {opp.kalshi_side.value.upper()} @ {opp.kalshi_price:.3f} + "
        f"Polymarket {opp.poly_side.value.upper()} @ {opp.poly_price:.3f} | "
        f"cost ${opp.total_cost:,.2f} (fees ${opp.total_fees:.2f}) | "
        f"profit ${opp.net_profit_usd:,.2f} ({opp.net_profit_pct:.2%})"
    )


async def execute(
    opp: ArbOpportunity,
    kalshi: KalshiTrader,
    poly: PolymarketTrader,
    *,
    dry_run: bool,
) -> Position:
    """Submit both legs as fill-or-kill orders.

    Fill-or-kill means each leg either fills completely at the quoted price or not at all, which
    rules out partial fills. It cannot rule out one leg filling while the other is rejected; such
    positions are returned with status ``UNHEDGED`` and must be resolved manually.
    """
    if dry_run:
        logger.info(f"[DRY RUN] would execute: {describe(opp)}")
        return Position(opportunity=opp, status=PositionStatus.DRY_RUN)

    logger.info(f"Executing: {describe(opp)}")
    # return_exceptions keeps one leg's crash from hiding the other leg's fill.
    k_raw, p_raw = await asyncio.gather(
        kalshi.place_order(
            opp.kalshi_market.market_id, opp.kalshi_side, opp.kalshi_price, opp.contracts
        ),
        poly.place_order(opp.poly_market, opp.poly_side, opp.poly_price, opp.contracts),
        return_exceptions=True,
    )
    k_result = _as_result(k_raw, Platform.KALSHI)
    p_result = _as_result(p_raw, Platform.POLYMARKET)

    if k_result.ok and p_result.ok:
        status = PositionStatus.OPEN
        logger.success(
            f"Both legs filled | Kalshi {k_result.order_id} | Polymarket {p_result.order_id} | "
            f"expected profit ${opp.net_profit_usd:,.2f}"
        )
    elif k_result.ok or p_result.ok:
        status = PositionStatus.UNHEDGED
        filled = k_result if k_result.ok else p_result
        failed = p_result if k_result.ok else k_result
        logger.critical(
            f"UNHEDGED POSITION: {filled.platform.value} leg filled ({filled.order_id}) but "
            f"{failed.platform.value} leg failed: {failed.error}. Manual action required."
        )
    else:
        status = PositionStatus.FAILED
        logger.warning(
            f"Neither leg filled (no exposure) | Kalshi: {k_result.error} | "
            f"Polymarket: {p_result.error}"
        )

    return Position(opportunity=opp, status=status, kalshi_order=k_result, poly_order=p_result)
