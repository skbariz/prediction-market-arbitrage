import re
from typing import List, Tuple
from rapidfuzz import fuzz
from src.models.market import Market
from config.settings import MATCH_SCORE_THRESHOLD

# Kalshi uses generic branded names to avoid licensing; these map them to real league names
# so fuzzy matching can find pairs against Polymarket's standard terminology.
_KALSHI_EXPANSIONS = {
    r"pro basketball finals": "NBA Finals",
    r"pro baseball championship": "MLB World Series",
    r"pro football championship": "NFL Super Bowl",
    r"pro hockey championship": "NHL Stanley Cup",
    r"stanley cup finals": "NHL Stanley Cup",
    r"2025-26 stanley cup": "2026 NHL Stanley Cup",
    r"pro soccer championship": "MLS Cup",
}


def _normalize(title: str) -> str:
    t = title.lower()
    for pattern, replacement in _KALSHI_EXPANSIONS.items():
        t = re.sub(pattern, replacement.lower(), t)
    return t


def match_markets(
    kalshi_markets: List[Market],
    poly_markets: List[Market],
) -> List[Tuple[Market, Market, float]]:
    """
    Returns (kalshi_market, poly_market, score) pairs scoring >= threshold.
    Kalshi titles are normalized to real league names before matching.
    """
    poly_normalized = [(pm, _normalize(pm.title)) for pm in poly_markets]

    pairs = []
    for km in kalshi_markets:
        k_norm = _normalize(km.title)
        for pm, p_norm in poly_normalized:
            score = fuzz.token_set_ratio(k_norm, p_norm)
            if score >= MATCH_SCORE_THRESHOLD:
                pairs.append((km, pm, float(score)))

    pairs.sort(key=lambda x: x[2], reverse=True)

    # Each Polymarket market can only be the best match for one Kalshi market.
    # Without this, cross-matches appear (e.g. "NYK no" paired with "SAS yes").
    used_poly = set()
    deduped = []
    for km, pm, score in pairs:
        if pm.market_id not in used_poly:
            used_poly.add(pm.market_id)
            deduped.append((km, pm, score))

    return deduped
