from prediction_arb import bot
from prediction_arb.detector import evaluate_pair
from prediction_arb.models import OrderResult, Platform
from prediction_arb.scanner import ScanResult
from tests.conftest import make_pair


class FilledTrader:
    def __init__(self, platform):
        self.platform = platform

    async def place_order(self, *args):
        return OrderResult(self.platform, ok=True, order_id="filled")


class BrokenStore:
    def active_pair_keys(self):
        return set()

    def save(self, position):
        raise OSError("disk full")


async def test_halts_when_a_live_position_cannot_be_recorded(settings, monkeypatch):
    from dataclasses import replace

    live = replace(settings, dry_run=False)
    pair = make_pair(0.40, 0.62, 0.57, 0.45)
    opp = evaluate_pair(pair, live)

    async def fake_scan(*_):
        return ScanResult([pair.kalshi], [pair.polymarket], [pair], [opp])

    monkeypatch.setattr(bot, "scan", fake_scan)
    halted = await bot.run_cycle(
        FilledTrader(Platform.KALSHI), FilledTrader(Platform.POLYMARKET), BrokenStore(), live
    )
    assert halted is True
