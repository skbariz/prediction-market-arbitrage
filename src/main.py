import asyncio
from src.clients.kalshi import KalshiClient
from src.clients.polymarket import PolymarketClient
from src.core.matcher import match_markets
from src.core.detector import detect_opportunities
from src.core.executor import execute_arb
from src.core.position_manager import init_db, save_position
from src.risk.manager import approve
from src.utils.logger import logger
from config.settings import POLL_INTERVAL_SEC, DRY_RUN


async def scan_and_trade():
    async with KalshiClient() as kalshi, PolymarketClient() as poly:
        logger.info("Fetching markets from both platforms...")
        kalshi_markets, poly_markets = await asyncio.gather(
            kalshi.get_markets(),
            poly.get_markets(),
        )
        logger.info(f"Kalshi: {len(kalshi_markets)} markets | Polymarket: {len(poly_markets)} markets")

        pairs = match_markets(kalshi_markets, poly_markets)
        logger.info(f"Matched {len(pairs)} market pairs")

        opportunities = detect_opportunities(pairs)
        if not opportunities:
            logger.info("No arb opportunities this scan.")
            return

        for opp in opportunities:
            if not approve(opp):
                continue

            position = await execute_arb(opp, kalshi, poly)
            row_id = save_position(position)
            logger.info(f"Position saved | id={row_id} status={position.status}")


async def main():
    mode = "DRY RUN" if DRY_RUN else "LIVE TRADING"
    logger.info(f"=== Prediction Market Arb Bot starting [{mode}] ===")
    init_db()

    while True:
        try:
            await scan_and_trade()
        except Exception as e:
            logger.error(f"Scan error: {e}")
        await asyncio.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    asyncio.run(main())
