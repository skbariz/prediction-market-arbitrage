import pytest

from prediction_arb.detector import evaluate_pair
from prediction_arb.executor import execute
from prediction_arb.models import OrderResult, Platform, PositionStatus
from tests.conftest import make_pair


class FakeTrader:
    def __init__(self, platform: Platform, ok: bool):
        self.platform = platform
        self.ok = ok
        self.calls: list[tuple] = []

    async def place_order(self, target, side, price, size):
        self.calls.append((target, side, price, size))
        return OrderResult(
            self.platform,
            ok=self.ok,
            order_id="order-1" if self.ok else None,
            error=None if self.ok else "rejected",
        )


@pytest.fixture
def opp(settings):
    return evaluate_pair(make_pair(0.40, 0.62, 0.57, 0.45), settings)


async def test_dry_run_places_no_orders(opp):
    kalshi, poly = FakeTrader(Platform.KALSHI, True), FakeTrader(Platform.POLYMARKET, True)
    position = await execute(opp, kalshi, poly, dry_run=True)
    assert position.status is PositionStatus.DRY_RUN
    assert kalshi.calls == [] and poly.calls == []


async def test_both_legs_use_the_same_contract_count(opp):
    kalshi, poly = FakeTrader(Platform.KALSHI, True), FakeTrader(Platform.POLYMARKET, True)
    position = await execute(opp, kalshi, poly, dry_run=False)

    assert position.status is PositionStatus.OPEN
    assert kalshi.calls == [(opp.kalshi_market.market_id, opp.kalshi_side, 0.40, opp.contracts)]
    assert poly.calls == [(opp.poly_market, opp.poly_side, 0.45, opp.contracts)]


@pytest.mark.parametrize(("k_ok", "p_ok"), [(True, False), (False, True)])
async def test_single_leg_fill_is_flagged_unhedged(opp, k_ok, p_ok):
    position = await execute(
        opp, FakeTrader(Platform.KALSHI, k_ok), FakeTrader(Platform.POLYMARKET, p_ok), dry_run=False
    )
    assert position.status is PositionStatus.UNHEDGED


async def test_no_fills_is_a_failed_position(opp):
    position = await execute(
        opp,
        FakeTrader(Platform.KALSHI, False),
        FakeTrader(Platform.POLYMARKET, False),
        dry_run=False,
    )
    assert position.status is PositionStatus.FAILED


class CrashingTrader:
    async def place_order(self, *args):
        raise RuntimeError("connection reset")


async def test_a_crashing_leg_does_not_hide_the_other_legs_fill(opp):
    position = await execute(
        opp, CrashingTrader(), FakeTrader(Platform.POLYMARKET, True), dry_run=False
    )
    assert position.status is PositionStatus.UNHEDGED
    assert "connection reset" in position.kalshi_order.error
    assert position.poly_order.ok
