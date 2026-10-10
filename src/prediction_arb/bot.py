"""The polling loop: scan, risk-check, execute, persist, sleep."""

from __future__ import annotations

import asyncio

from prediction_arb import executor, risk
from prediction_arb.clients.kalshi import KalshiClient
from prediction_arb.clients.polymarket import PolymarketClient
from prediction_arb.config import Settings
from prediction_arb.log import logger
from prediction_arb.models import PositionStatus
from prediction_arb.scanner import scan
from prediction_arb.storage import PositionStore

EXIT_OK = 0
EXIT_HALTED = 2


async def run_cycle(
    kalshi: KalshiClient, poly: PolymarketClient, store: PositionStore, settings: Settings
) -> bool:
    """Run one scan-and-trade cycle. Returns ``True`` if trading must halt."""
    result = await scan(kalshi, poly, settings)
    logger.info(
        f"Kalshi {len(result.kalshi_markets)} markets | Polymarket {len(result.poly_markets)} "
        f"markets | {len(result.pairs)} matched pairs | {len(result.opportunities)} opportunities"
    )

    active_keys = store.active_pair_keys()
    for opp in result.opportunities:
        decision = risk.evaluate(opp, settings, active_keys)
        if not decision.approved:
            logger.info(f"Skipped: {executor.describe(opp)} | {'; '.join(decision.reasons)}")
            continue

        position = await executor.execute(opp, kalshi, poly, dry_run=settings.dry_run)
        if position.status is PositionStatus.DRY_RUN:
            continue
        store.save(position)
        logger.info(f"Position {position.id} saved with status {position.status.value}")
        if position.status in (PositionStatus.OPEN, PositionStatus.UNHEDGED):
            active_keys.add(opp.key)
        if position.status is PositionStatus.UNHEDGED:
            logger.critical("Halting: resolve the unhedged position before restarting the bot.")
            return True
    return False


async def run(settings: Settings, *, once: bool = False) -> int:
    store = PositionStore(settings.db_path)
    store.init()
    mode = "DRY RUN" if settings.dry_run else "LIVE TRADING"
    logger.info(
        f"Starting [{mode}] | max ${settings.max_position_usd:,.2f}/trade | "
        f"min profit {settings.min_profit_pct:.2%} | polling every {settings.poll_interval_sec}s"
    )

    async with KalshiClient(settings) as kalshi, PolymarketClient(settings) as poly:
        while True:
            try:
                if await run_cycle(kalshi, poly, store, settings):
                    return EXIT_HALTED
            except Exception:
                logger.exception("Scan cycle failed; retrying next interval")
            if once:
                return EXIT_OK
            await asyncio.sleep(settings.poll_interval_sec)
