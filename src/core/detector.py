from typing import List, Optional, Tuple
from src.models.market import Market
from src.models.opportunity import ArbOpportunity
from src.utils.fees import total_fees
from src.utils.logger import logger
from config.settings import MIN_PROFIT_PCT, MAX_POSITION_USD


def _check_pair(
    kalshi: Market,
    poly: Market,
    match_score: float,
) -> Optional[ArbOpportunity]:
    """
    Checks both leg directions for an arb opportunity between one matched pair.

    Direction A: buy Yes on Kalshi + buy No on Polymarket
    Direction B: buy No on Kalshi + buy Yes on Polymarket

    An opportunity exists when gross_cost + fees < 1.00 (i.e. guaranteed payout exceeds total outlay).
    """
    for k_side, k_price, p_side, p_price in [
        ("yes", kalshi.price.yes, "no",  poly.price.no),
        ("no",  kalshi.price.no,  "yes", poly.price.yes),
    ]:
        gross_cost = k_price + p_price
        if gross_cost >= 1.0:
            continue  # No raw arb even before fees

        fees = total_fees(k_price, p_price, MAX_POSITION_USD)
        fees_pct = fees / MAX_POSITION_USD
        net_profit_pct = (1.0 - gross_cost) - fees_pct

        if net_profit_pct >= MIN_PROFIT_PCT:
            return ArbOpportunity(
                kalshi_market=kalshi,
                poly_market=poly,
                kalshi_side=k_side,
                poly_side=p_side,
                kalshi_entry=k_price,
                poly_entry=p_price,
                gross_cost=round(gross_cost, 6),
                fees=round(fees, 6),
                net_profit_pct=round(net_profit_pct, 6),
                match_score=match_score,
            )
    return None


def detect_opportunities(
    matched_pairs: List[Tuple[Market, Market, float]],
) -> List[ArbOpportunity]:
    opportunities = []
    for kalshi, poly, score in matched_pairs:
        opp = _check_pair(kalshi, poly, score)
        if opp:
            logger.info(
                f"ARB FOUND | {kalshi.title[:50]} | "
                f"Kalshi {opp.kalshi_side}@{opp.kalshi_entry:.3f} + "
                f"Poly {opp.poly_side}@{opp.poly_entry:.3f} | "
                f"Net profit: {opp.net_profit_pct*100:.2f}%"
            )
            opportunities.append(opp)
    return opportunities
