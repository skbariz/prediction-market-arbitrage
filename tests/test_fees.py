import pytest

from prediction_arb.fees import kalshi_fee, polymarket_fee


@pytest.mark.parametrize(
    ("price", "contracts", "expected"),
    [
        (0.50, 100, 1.75),
        (0.10, 100, 0.63),  # exact cent amount must not be rounded up by float error
        (0.50, 1, 0.02),  # 0.0175 rounds up to the next cent
        (0.99, 1, 0.01),
        (0.0, 100, 0.0),
    ],
)
def test_kalshi_fee_rounds_up_to_the_cent(price, contracts, expected):
    assert kalshi_fee(price, contracts) == expected


@pytest.mark.parametrize(
    ("price", "rate", "expected"),
    [
        # Values from the 100-share tables at https://docs.polymarket.com/trading/fees
        (0.50, 0.07, 1.75),
        (0.30, 0.05, 1.05),
        (0.45, 0.04, 0.99),
        (0.50, 0.0, 0.0),
    ],
)
def test_polymarket_fee_matches_published_tables(price, rate, expected):
    assert polymarket_fee(price, 100, rate) == pytest.approx(expected)


def test_fees_are_symmetric_around_half():
    assert kalshi_fee(0.3, 100) == kalshi_fee(0.7, 100)
    assert polymarket_fee(0.3, 100) == polymarket_fee(0.7, 100)


@pytest.mark.parametrize("price", [-0.1, 1.1])
def test_fee_rejects_invalid_price(price):
    with pytest.raises(ValueError):
        kalshi_fee(price, 1)
