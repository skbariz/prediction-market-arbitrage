"""Pre-trade checks. An opportunity is executed only if every check passes."""

from __future__ import annotations

from dataclasses import dataclass, field

from prediction_arb.config import Settings
from prediction_arb.models import ArbOpportunity


@dataclass
class RiskDecision:
    approved: bool
    reasons: list[str] = field(default_factory=list)


def evaluate(
    opp: ArbOpportunity,
    settings: Settings,
    open_position_keys: set[str],
) -> RiskDecision:
    reasons: list[str] = []
    k, p = opp.kalshi_market, opp.poly_market

    if opp.net_profit_pct < settings.min_profit_pct:
        reasons.append(
            f"net profit {opp.net_profit_pct:.2%} below minimum {settings.min_profit_pct:.2%}"
        )
    if opp.match_score < settings.execution_min_match_score:
        reasons.append(
            f"match score {opp.match_score:.0f} below execution minimum "
            f"{settings.execution_min_match_score:.0f}"
        )
    if k.volume < settings.min_volume or p.volume < settings.min_volume:
        reasons.append(
            f"insufficient volume (Kalshi {k.volume:,.0f}, Polymarket {p.volume:,.0f}, "
            f"minimum {settings.min_volume:,.0f})"
        )
    if settings.max_days_to_resolution:
        days = k.days_to_resolution()
        if days is None or days > settings.max_days_to_resolution:
            reasons.append(
                f"resolves in {'unknown' if days is None else f'{days:.0f}'} days "
                f"(limit {settings.max_days_to_resolution})"
            )
    if not (k.is_active and p.is_active):
        reasons.append("one or both markets are not accepting orders")
    if not p.token_id(opp.poly_side):
        reasons.append("Polymarket market has no order-book token id")
    if p.min_order_size and opp.contracts < p.min_order_size:
        reasons.append(
            f"{opp.contracts} contracts is below Polymarket minimum order size {p.min_order_size:g}"
        )
    if opp.key in open_position_keys:
        reasons.append("a position on this pair is already open")
    elif len(open_position_keys) >= settings.max_open_positions:
        reasons.append(f"MAX_OPEN_POSITIONS ({settings.max_open_positions}) reached")

    return RiskDecision(approved=not reasons, reasons=reasons)
