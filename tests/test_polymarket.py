import json
from datetime import datetime, timedelta, timezone

import pytest

from prediction_arb.clients.polymarket import PolymarketClient, parse_market
from prediction_arb.config import Settings
from prediction_arb.models import Platform, Side
from tests.conftest import make_market

RAW_MARKET = {
    "conditionId": "0xabc",
    "question": "Will New York Knicks win the 2027 NBA Finals?",
    "endDate": "2099-07-01T00:00:00Z",
    "outcomes": json.dumps(["Yes", "No"]),
    "outcomePrices": json.dumps(["0.125", "0.875"]),
    "clobTokenIds": json.dumps(["111", "222"]),
    "bestAsk": 0.13,
    "bestBid": 0.12,
    "volumeClob": 2500000.5,
    "active": True,
    "closed": False,
    "acceptingOrders": True,
    "orderPriceMinTickSize": 0.001,
    "orderMinSize": 5,
    "negRisk": True,
    "feesEnabled": True,
    "feeSchedule": {"exponent": 1, "rate": 0.05, "takerOnly": True},
}


def test_parse_market_uses_executable_book_prices():
    market = parse_market(RAW_MARKET)
    assert market.price.yes == 0.13  # best ask
    assert market.price.no == 0.88  # 1 - best bid
    assert (market.yes_token_id, market.no_token_id) == ("111", "222")
    assert market.tick_size == 0.001
    assert market.min_order_size == 5
    assert market.neg_risk is True
    assert market.fee_rate == 0.05
    assert market.is_active


def test_parse_market_falls_back_to_mid_prices():
    market = parse_market({**RAW_MARKET, "bestAsk": None, "bestBid": None})
    assert (market.price.yes, market.price.no) == (0.125, 0.875)


def test_parse_market_handles_reversed_outcomes():
    raw = {
        **RAW_MARKET,
        "outcomes": json.dumps(["No", "Yes"]),
        "outcomePrices": json.dumps(["0.875", "0.125"]),
        "clobTokenIds": json.dumps(["222", "111"]),
        "bestAsk": None,
        "bestBid": None,
    }
    market = parse_market(raw)
    assert (market.price.yes, market.price.no) == (0.125, 0.875)
    assert (market.yes_token_id, market.no_token_id) == ("111", "222")


def test_fee_free_markets_report_zero_rate():
    assert parse_market({**RAW_MARKET, "feesEnabled": False}).fee_rate == 0.0
    assert parse_market({**RAW_MARKET, "feeSchedule": None}).fee_rate is None


@pytest.mark.parametrize(
    "override",
    [
        {"outcomes": json.dumps(["Lakers", "Celtics"])},
        {"endDate": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()},
        {"conditionId": None},
        {"outcomes": "not json"},
    ],
)
def test_parse_market_skips_unusable(override):
    assert parse_market({**RAW_MARKET, **override}) is None


def test_not_accepting_orders_is_inactive():
    assert not parse_market({**RAW_MARKET, "acceptingOrders": False}).is_active


async def test_place_order_without_credentials_fails_safely():
    market = make_market(Platform.POLYMARKET, "0xabc", "t", 0.5, 0.5)
    async with PolymarketClient(Settings()) as client:
        result = await client.place_order(market, Side.YES, 0.5, 10)
    assert not result.ok
    assert "credentials" in result.error


@pytest.mark.parametrize("rate", [-0.5, 5, "nan", "inf"])
def test_implausible_fee_rates_fall_back_to_default(rate):
    raw = {**RAW_MARKET, "feeSchedule": {"rate": rate}}
    assert parse_market(raw).fee_rate is None


@pytest.mark.parametrize("field", ["bestAsk", "bestBid"])
def test_non_finite_quotes_are_ignored(field):
    market = parse_market({**RAW_MARKET, field: "inf"})
    assert market is not None
    assert all(0 < p < 1 for p in (market.price.yes, market.price.no))


def test_garbage_volume_does_not_break_parsing():
    assert parse_market({**RAW_MARKET, "volumeClob": "lots"}).volume == 0.0
