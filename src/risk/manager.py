from src.models.opportunity import ArbOpportunity
from src.utils.logger import logger
from config.settings import MIN_PROFIT_PCT, MAX_POSITION_USD

MIN_VOLUME_USD = 100.0   # Both markets must have at least this much volume
MIN_MATCH_SCORE = 85.0   # Stricter threshold at execution time


def approve(opp: ArbOpportunity) -> bool:
    """Returns True only if the opportunity passes all pre-trade guards."""

    if opp.net_profit_pct < MIN_PROFIT_PCT:
        logger.warning(f"Risk: profit {opp.net_profit_pct*100:.2f}% below minimum {MIN_PROFIT_PCT*100:.0f}%")
        return False

    if opp.match_score < MIN_MATCH_SCORE:
        logger.warning(f"Risk: match score {opp.match_score:.1f} below execution threshold {MIN_MATCH_SCORE}")
        return False

    k_vol = opp.kalshi_market.volume_usd or 0
    p_vol = opp.poly_market.volume_usd or 0
    if k_vol < MIN_VOLUME_USD or p_vol < MIN_VOLUME_USD:
        logger.warning(
            f"Risk: insufficient volume — Kalshi ${k_vol:.0f}, Poly ${p_vol:.0f} "
            f"(min ${MIN_VOLUME_USD:.0f})"
        )
        return False

    if MAX_POSITION_USD <= 0:
        logger.warning("Risk: MAX_POSITION_USD is zero or negative")
        return False

    return True
