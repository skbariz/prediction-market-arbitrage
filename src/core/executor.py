import asyncio
from datetime import datetime
from src.models.opportunity import ArbOpportunity
from src.models.position import Position
from src.clients.kalshi import KalshiClient
from src.clients.polymarket import PolymarketClient
from src.utils.logger import logger
from config.settings import MAX_POSITION_USD, DRY_RUN


async def execute_arb(
    opp: ArbOpportunity,
    kalshi: KalshiClient,
    poly: PolymarketClient,
) -> Position:
    """
    Places both legs simultaneously. If either leg fails the position is marked
    'failed' so the position manager can handle the unhedged exposure.
    """
    # Scale contract count for Kalshi (contracts are $0.01 each)
    kalshi_price_cents = round(opp.kalshi_entry * 100)
    contract_count = round(MAX_POSITION_USD / (opp.kalshi_entry))

    position = Position(
        created_at=datetime.utcnow(),
        opportunity=opp,
        size_usd=MAX_POSITION_USD,
    )

    logger.info(
        f"Executing arb: Kalshi {opp.kalshi_side}@{kalshi_price_cents}¢ x{contract_count} | "
        f"Poly {opp.poly_side}@{opp.poly_entry:.4f} ${MAX_POSITION_USD:.2f}"
    )

    k_result, p_result = await asyncio.gather(
        kalshi.place_order(
            market_id=opp.kalshi_market.market_id,
            side=opp.kalshi_side,
            price_cents=kalshi_price_cents,
            count=contract_count,
            dry_run=DRY_RUN,
        ),
        poly.place_order(
            token_id=(opp.poly_market.yes_token_id if opp.poly_side == "yes"
                      else opp.poly_market.no_token_id),
            side=opp.poly_side,
            price=opp.poly_entry,
            size_usd=MAX_POSITION_USD,
            dry_run=DRY_RUN,
        ),
    )

    k_ok = k_result.get("status") not in ("failed",)
    p_ok = p_result.get("status") not in ("failed",)

    if k_ok and p_ok:
        position.kalshi_order_id = k_result.get("order_id")
        position.poly_order_id = p_result.get("order_id")
        position.status = "open"
        logger.success(
            f"Both legs placed | Kalshi:{position.kalshi_order_id} Poly:{position.poly_order_id} | "
            f"Expected profit: ${opp.net_profit_usd:.4f}"
        )
    else:
        position.status = "failed"
        logger.error(
            f"Leg failure — Kalshi:{k_result.get('status')} Poly:{p_result.get('status')} — "
            "MANUAL REVIEW REQUIRED for unhedged exposure"
        )

    return position
