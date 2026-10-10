from dataclasses import replace
from datetime import datetime, timedelta, timezone

from prediction_arb.detector import evaluate_pair
from prediction_arb.models import MatchedPair
from prediction_arb.risk import evaluate
from tests.conftest import make_pair


def _opp(settings, **pair_kwargs):
    opp = evaluate_pair(make_pair(0.40, 0.62, 0.57, 0.45, **pair_kwargs), settings)
    assert opp is not None
    return opp


def test_approves_a_clean_opportunity(settings):
    decision = evaluate(_opp(settings), settings, set())
    assert decision.approved, decision.reasons


def test_rejects_low_match_score(settings):
    decision = evaluate(_opp(settings, score=82), settings, set())
    assert not decision.approved
    assert "match score" in decision.reasons[0]


def test_rejects_thin_volume(settings):
    decision = evaluate(_opp(settings, volume=10), settings, set())
    assert any("volume" in r for r in decision.reasons)


def test_rejects_long_dated_markets(settings):
    far = datetime.now(timezone.utc) + timedelta(days=400)
    decision = evaluate(_opp(settings, resolves_at=far), settings, set())
    assert any("resolves in" in r for r in decision.reasons)
    assert evaluate(
        _opp(settings, resolves_at=far), replace(settings, max_days_to_resolution=0), set()
    ).approved


def test_never_reenters_an_open_pair(settings):
    opp = _opp(settings)
    decision = evaluate(opp, settings, {opp.key})
    assert any("already open" in r for r in decision.reasons)


def test_caps_open_positions(settings):
    opp = _opp(settings)
    others = {f"other-{i}" for i in range(settings.max_open_positions)}
    assert any("MAX_OPEN_POSITIONS" in r for r in evaluate(opp, settings, others).reasons)


def test_rejects_below_polymarket_min_order_size(settings):
    opp = _opp(settings)
    poly = replace(opp.poly_market, min_order_size=opp.contracts + 1)
    opp = replace(opp, pair=MatchedPair(opp.kalshi_market, poly, opp.match_score))
    assert any("minimum order size" in r for r in evaluate(opp, settings, set()).reasons)


def test_rejects_inactive_markets(settings):
    opp = _opp(settings, is_active=False)
    assert any("not accepting orders" in r for r in evaluate(opp, settings, set()).reasons)
