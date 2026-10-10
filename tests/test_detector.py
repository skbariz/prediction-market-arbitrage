from dataclasses import replace

import pytest

from prediction_arb.detector import detect_opportunities, evaluate_pair
from prediction_arb.fees import kalshi_fee, polymarket_fee
from prediction_arb.models import Side
from tests.conftest import make_pair


def test_finds_arb_and_sizes_both_legs_equally(settings):
    pair = make_pair(k_yes=0.40, k_no=0.62, p_yes=0.57, p_no=0.45)
    opp = evaluate_pair(pair, settings)

    assert opp is not None
    assert (opp.kalshi_side, opp.poly_side) == (Side.YES, Side.NO)
    assert (opp.kalshi_price, opp.poly_price) == (0.40, 0.45)
    assert opp.contracts == 56
    assert opp.kalshi_fee == kalshi_fee(0.40, 56)
    assert opp.poly_fee == polymarket_fee(0.45, 56)
    assert opp.total_cost <= settings.max_position_usd
    assert opp.payout == 56
    assert opp.net_profit_usd == pytest.approx(opp.payout - opp.total_cost)
    assert opp.net_profit_pct > settings.min_profit_pct


def test_checks_the_other_direction(settings):
    pair = make_pair(k_yes=0.62, k_no=0.40, p_yes=0.45, p_no=0.57)
    opp = evaluate_pair(pair, settings)
    assert opp is not None
    assert (opp.kalshi_side, opp.poly_side) == (Side.NO, Side.YES)


def test_no_arb_when_combined_cost_is_at_least_one_dollar(settings):
    assert evaluate_pair(make_pair(0.50, 0.51, 0.49, 0.50), settings) is None


def test_fees_can_eliminate_a_thin_gross_edge(settings):
    # 0.49 + 0.50 = 0.99 leaves 1% gross, less than fees near 50/50.
    assert evaluate_pair(make_pair(0.49, 0.52, 0.49, 0.50), settings) is None


def test_market_fee_rate_is_used_when_reported(settings):
    default = evaluate_pair(make_pair(0.40, 0.62, 0.57, 0.45), settings)
    fee_free = evaluate_pair(make_pair(0.40, 0.62, 0.57, 0.45, poly_fee_rate=0.0), settings)
    assert fee_free.poly_fee == 0
    assert fee_free.net_profit_usd > default.net_profit_usd


def test_min_profit_threshold(settings):
    pair = make_pair(0.40, 0.62, 0.57, 0.45)
    assert evaluate_pair(pair, replace(settings, min_profit_pct=0.5)) is None


def test_ignores_unquoted_prices(settings):
    assert evaluate_pair(make_pair(0.0, 1.0, 1.0, 0.0), settings) is None


def test_position_too_small_for_one_contract(settings):
    assert (
        evaluate_pair(make_pair(0.40, 0.62, 0.57, 0.45), replace(settings, max_position_usd=0.5))
        is None
    )


def test_detect_opportunities_sorts_by_profit(settings):
    thin = make_pair(0.45, 0.57, 0.55, 0.47)
    fat = make_pair(0.30, 0.72, 0.65, 0.40)
    opps = detect_opportunities([thin, fat], settings)
    assert [o.kalshi_price for o in opps] == [0.30, 0.45]
