from prediction_arb.detector import evaluate_pair
from prediction_arb.models import OrderResult, Platform, Position, PositionStatus
from prediction_arb.storage import PositionStore
from tests.conftest import make_pair


def _position(settings, status):
    pair = make_pair(0.40, 0.62, 0.57, 0.45)
    opp = evaluate_pair(pair, settings)
    return Position(
        opportunity=opp,
        status=status,
        kalshi_order=OrderResult(Platform.KALSHI, ok=True, order_id="k1", raw={"order": {}}),
        poly_order=OrderResult(Platform.POLYMARKET, ok=False, error="rejected"),
    )


def test_save_and_list(settings, tmp_path):
    store = PositionStore(tmp_path / "nested" / "positions.db")
    store.init()
    position = _position(settings, PositionStatus.UNHEDGED)
    position_id = store.save(position)

    rows = store.list_positions()
    assert position.id == position_id == rows[0]["id"]
    assert rows[0]["status"] == "unhedged"
    assert rows[0]["contracts"] == position.opportunity.contracts


def test_active_pair_keys_only_include_live_exposure(settings, tmp_path):
    store = PositionStore(tmp_path / "positions.db")
    store.init()
    store.save(_position(settings, PositionStatus.FAILED))
    assert store.active_pair_keys() == set()

    open_position = _position(settings, PositionStatus.OPEN)
    store.save(open_position)
    assert store.active_pair_keys() == {open_position.opportunity.key}


def test_init_is_idempotent(tmp_path):
    store = PositionStore(tmp_path / "positions.db")
    store.init()
    store.init()
    assert store.list_positions() == []
