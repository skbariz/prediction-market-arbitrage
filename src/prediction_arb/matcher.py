"""Pairs Kalshi and Polymarket markets that describe the same real-world event.

Kalshi avoids league trademarks ("Pro Basketball Finals" instead of "NBA Finals"), so titles are
normalized to common names before fuzzy matching with RapidFuzz's ``token_set_ratio``, which is
robust to word order and extra words.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from rapidfuzz import fuzz

from prediction_arb.models import Market, MatchedPair

# Applied in order. Patterns run against lower-cased titles from both platforms.
KALSHI_EXPANSIONS: dict[str, str] = {
    r"\b(\d{2})\d{2}-(\d{2})\b": r"\1\2",  # season "2025-26" -> "2026"
    r"pro basketball finals": "nba finals",
    r"pro baseball championship": "mlb world series",
    r"pro football championship": "nfl super bowl",
    r"pro hockey championship": "nhl stanley cup",
    r"(?<!nhl )stanley cup(?: finals)?": "nhl stanley cup",
    r"pro soccer championship": "mls cup",
}
_EXPANSIONS = [(re.compile(p), r) for p, r in KALSHI_EXPANSIONS.items()]

# Titles that name different leagues or different years are never the same event, however
# similar the rest of the wording ("Will New York win the 2027 NBA Finals?" vs "... NFL ...").
_LEAGUES = {
    "nba": re.compile(r"\bnba\b"),
    "wnba": re.compile(r"\bwnba\b"),
    "nfl": re.compile(r"\bnfl\b|super bowl"),
    "nhl": re.compile(r"\bnhl\b|stanley cup"),
    "mlb": re.compile(r"\bmlb\b|world series"),
    "mls": re.compile(r"\bmls\b"),
    "ncaa": re.compile(r"\bncaa\b|march madness"),
}
_YEAR = re.compile(r"\b20\d{2}\b")
# Words that change which question is being asked. "Win the Stanley Cup" and "make the NHL
# playoffs" share most tokens but are different events, so a qualifier present in only one
# title rules the pair out.
_QUALIFIERS = {
    "playoffs": re.compile(r"\bplayoffs?\b|\bpostseason\b"),
    "conference": re.compile(
        r"\bconference\b|\b(?:eastern|western|afc|nfc|al|nl) (?:finals|championship|pennant)\b"
    ),
    "division": re.compile(r"\bdivision\b"),
    "mvp": re.compile(r"\bmvp\b|most valuable"),
    "draft": re.compile(r"\bdraft\b"),
    "nomination": re.compile(r"\bnominat"),
    "primary": re.compile(r"\bprimary\b"),
    "popular_vote": re.compile(r"popular vote"),
}


def normalize_title(title: str) -> str:
    text = title.lower().replace("®", "").replace("™", "")
    for pattern, replacement in _EXPANSIONS:
        text = pattern.sub(replacement, text)
    return text


@dataclass(frozen=True)
class _Prepared:
    text: str
    leagues: frozenset[str]
    years: frozenset[str]
    qualifiers: frozenset[str]

    @classmethod
    def of(cls, title: str) -> _Prepared:
        text = normalize_title(title)
        return cls(
            text,
            frozenset(name for name, rx in _LEAGUES.items() if rx.search(text)),
            frozenset(_YEAR.findall(text)),
            frozenset(name for name, rx in _QUALIFIERS.items() if rx.search(text)),
        )

    def compatible(self, other: _Prepared) -> bool:
        def conflict(a: frozenset[str], b: frozenset[str]) -> bool:
            return bool(a and b and a.isdisjoint(b))

        return not (
            conflict(self.leagues, other.leagues)
            or conflict(self.years, other.years)
            or self.qualifiers != other.qualifiers
        )


def _score(a: _Prepared, b: _Prepared, cutoff: float = 0.0) -> float:
    if not a.compatible(b):
        return 0.0
    return float(fuzz.token_set_ratio(a.text, b.text, score_cutoff=cutoff))


def score_titles(a: str, b: str) -> float:
    """Similarity of two titles (0-100); 0 when they name different leagues or years."""
    return _score(_Prepared.of(a), _Prepared.of(b))


def candidate_pairs(
    kalshi_markets: Iterable[Market],
    poly_markets: Iterable[Market],
    min_score: float,
) -> list[MatchedPair]:
    """Every Kalshi x Polymarket pair scoring at least ``min_score``, best first (not deduplicated)."""
    poly_prepared = [(pm, _Prepared.of(pm.title)) for pm in poly_markets]
    candidates: list[MatchedPair] = []
    for km in kalshi_markets:
        k_prep = _Prepared.of(km.title)
        for pm, p_prep in poly_prepared:
            score = _score(k_prep, p_prep, min_score)
            if score:
                candidates.append(MatchedPair(km, pm, score))
    candidates.sort(key=lambda p: p.score, reverse=True)
    return candidates


def match_markets(
    kalshi_markets: Iterable[Market],
    poly_markets: Iterable[Market],
    threshold: float = 80.0,
) -> list[MatchedPair]:
    """Return one-to-one pairs scoring at least ``threshold`` (0-100), best matches first.

    Each market appears in at most one pair. Without this, a single Polymarket market such as
    "Will Team A win?" can match every "Will Team X win?" contract in the same tournament.
    """
    candidates = candidate_pairs(kalshi_markets, poly_markets, threshold)
    used_kalshi: set[str] = set()
    used_poly: set[str] = set()
    pairs: list[MatchedPair] = []
    for pair in candidates:
        if pair.kalshi.market_id in used_kalshi or pair.polymarket.market_id in used_poly:
            continue
        used_kalshi.add(pair.kalshi.market_id)
        used_poly.add(pair.polymarket.market_id)
        pairs.append(pair)
    return pairs
