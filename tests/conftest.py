from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from prediction_arb.config import Settings
from prediction_arb.models import Market, MarketPrice, MatchedPair, Platform

ENV_VARS = [
    "KALSHI_API_KEY_ID",
    "KALSHI_PRIVATE_KEY",
    "KALSHI_PRIVATE_KEY_PATH",
    "KALSHI_BASE_URL",
    "KALSHI_SERIES",
    "KALSHI_FEE_RATE",
    "POLY_PRIVATE_KEY",
    "POLY_FUNDER_ADDRESS",
    "POLY_SIGNATURE_TYPE",
    "POLY_API_KEY",
    "POLY_API_SECRET",
    "POLY_PASSPHRASE",
    "POLY_CLOB_URL",
    "POLY_GAMMA_URL",
    "POLY_CHAIN_ID",
    "POLY_PAGES",
    "POLY_DEFAULT_FEE_RATE",
    "DRY_RUN",
    "MIN_PROFIT_PCT",
    "MAX_POSITION_USD",
    "MAX_OPEN_POSITIONS",
    "POLL_INTERVAL_SEC",
    "MATCH_SCORE_THRESHOLD",
    "EXECUTION_MIN_MATCH_SCORE",
    "MIN_VOLUME",
    "MAX_DAYS_TO_RESOLUTION",
    "DB_PATH",
    "LOG_FILE",
    "LOG_LEVEL",
    "HTTP_TIMEOUT_SEC",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's real environment (and any credentials in it) out of every test."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(db_path=str(tmp_path / "positions.db"), log_file="")


@pytest.fixture
def soon() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=3)


def make_market(
    platform: Platform,
    market_id: str,
    title: str,
    yes: float,
    no: float,
    *,
    resolves_at: datetime | None = None,
    volume: float = 10_000,
    **extra,
) -> Market:
    if platform is Platform.POLYMARKET:
        extra.setdefault("yes_token_id", f"{market_id}-yes")
        extra.setdefault("no_token_id", f"{market_id}-no")
        extra.setdefault("min_order_size", 5)
    return Market(
        platform=platform,
        market_id=market_id,
        title=title,
        price=MarketPrice(yes=yes, no=no),
        resolves_at=resolves_at or datetime.now(timezone.utc) + timedelta(days=3),
        volume=volume,
        **extra,
    )


def make_pair(
    k_yes: float,
    k_no: float,
    p_yes: float,
    p_no: float,
    *,
    score: float = 100.0,
    poly_fee_rate: float | None = None,
    **kalshi_extra,
) -> MatchedPair:
    kalshi = make_market(
        Platform.KALSHI, "KXNBA-27-NYK", "Will New York win the 2027 Pro Basketball Finals?",
        k_yes, k_no, **kalshi_extra,
    )  # fmt: skip
    poly = make_market(
        Platform.POLYMARKET, "0xknicks", "Will New York Knicks win the 2027 NBA Finals?",
        p_yes, p_no, fee_rate=poly_fee_rate,
    )  # fmt: skip
    return MatchedPair(kalshi, poly, score)
