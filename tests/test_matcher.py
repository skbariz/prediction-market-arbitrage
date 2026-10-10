import pytest

from prediction_arb.matcher import match_markets, normalize_title, score_titles
from prediction_arb.models import Platform
from tests.conftest import make_market


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Will Boston win the 2027 Pro Basketball Finals?", "will boston win the 2027 nba finals?"),
        ("2025-26 Stanley Cup® Finals", "2026 nhl stanley cup"),
        ("Pro Baseball Championship", "mlb world series"),
        ("NHL Stanley Cup", "nhl stanley cup"),
    ],
)
def test_normalize_title(title, expected):
    assert normalize_title(title) == expected


def test_kalshi_generic_names_match_polymarket_league_names():
    score = score_titles(
        "Will New York win the 2027 Pro Basketball Finals?",
        "Will New York Knicks win the 2027 NBA Finals?",
    )
    assert score == 100


@pytest.mark.parametrize(
    ("kalshi", "poly"),
    [
        # different leagues
        (
            "Will New York win the 2027 Pro Basketball Finals?",
            "Will the New York Giants win the 2027 NFL league championship?",
        ),
        # different years
        (
            "Will Tampa Bay win the 2026 Pro Baseball Championship?",
            "Will the Tampa Bay Rays win the 2027 World Series?",
        ),
        # different question about the same team
        (
            "Will New York Rangers win the 2026-27 Stanley Cup® Finals?",
            "Will the New York Rangers make the 2026-27 NHL Playoffs?",
        ),
    ],
)
def test_incompatible_titles_score_zero(kalshi, poly):
    assert score_titles(kalshi, poly) == 0


def test_match_markets_is_one_to_one_and_best_first():
    kalshi = [
        make_market(
            Platform.KALSHI, "K-NYK", "Will New York win the 2027 Pro Basketball Finals?", 0.1, 0.9
        ),
        make_market(
            Platform.KALSHI, "K-BOS", "Will Boston win the 2027 Pro Basketball Finals?", 0.2, 0.8
        ),
    ]
    poly = [
        make_market(
            Platform.POLYMARKET, "P-NYK", "Will New York Knicks win the 2027 NBA Finals?", 0.1, 0.9
        ),
        make_market(
            Platform.POLYMARKET, "P-BOS", "Will Boston Celtics win the 2027 NBA Finals?", 0.2, 0.8
        ),
        make_market(Platform.POLYMARKET, "P-X", "Will it rain in Paris tomorrow?", 0.5, 0.5),
    ]
    pairs = match_markets(kalshi, poly, threshold=80)

    assert {(p.kalshi.market_id, p.polymarket.market_id) for p in pairs} == {
        ("K-NYK", "P-NYK"),
        ("K-BOS", "P-BOS"),
    }
    assert [p.score for p in pairs] == sorted((p.score for p in pairs), reverse=True)


def test_match_markets_respects_threshold():
    kalshi = [
        make_market(
            Platform.KALSHI, "K", "Will Boston win the 2027 Pro Basketball Finals?", 0.2, 0.8
        )
    ]
    poly = [make_market(Platform.POLYMARKET, "P", "Boston weather forecast", 0.5, 0.5)]
    assert match_markets(kalshi, poly, threshold=80) == []
