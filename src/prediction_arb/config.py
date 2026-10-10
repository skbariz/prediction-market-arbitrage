"""Runtime configuration loaded from environment variables (and an optional ``.env`` file).

Every setting has a safe default. Secrets are excluded from ``repr`` so a ``Settings`` object
can be logged without leaking credentials.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_KALSHI_SERIES = (
    "KXNBA",
    "KXNHL",
    "KXMLB",
    "KXNFL",
    "KXBTC",
    "KXETH",
    "KXECON",
    "KXPRES",
    "KXGOV",
    "KXWORLD",
    "KXTECH",
    "KXSCI",
)


class ConfigError(ValueError):
    """Raised when the environment contains an invalid or inconsistent configuration."""


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _get_bool(name: str, default: bool) -> bool:
    raw = _get(name, "true" if default else "false").lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be true or false, got {raw!r}")


def _get_float(name: str, default: float) -> float:
    raw = _get(name, str(default))
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


def _get_int(name: str, default: int) -> int:
    raw = _get(name, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _get_list(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = _get(name)
    if not raw:
        return default
    return tuple(item.strip().upper() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    # Kalshi
    kalshi_api_key_id: str = ""
    kalshi_private_key: str = field(default="", repr=False)
    kalshi_private_key_path: str = ""
    kalshi_base_url: str = "https://api.elections.kalshi.com/trade-api/v2"
    kalshi_series: tuple[str, ...] = DEFAULT_KALSHI_SERIES
    kalshi_fee_rate: float = 0.07

    # Polymarket
    poly_private_key: str = field(default="", repr=False)
    poly_funder_address: str = ""
    poly_signature_type: int = 0
    poly_api_key: str = field(default="", repr=False)
    poly_api_secret: str = field(default="", repr=False)
    poly_passphrase: str = field(default="", repr=False)
    poly_clob_url: str = "https://clob.polymarket.com"
    poly_gamma_url: str = "https://gamma-api.polymarket.com"
    poly_chain_id: int = 137
    poly_pages: int = 20
    poly_default_fee_rate: float = 0.07

    # Strategy and risk
    dry_run: bool = True
    min_profit_pct: float = 0.02
    max_position_usd: float = 50.0
    max_open_positions: int = 5
    poll_interval_sec: int = 30
    match_score_threshold: float = 80.0
    execution_min_match_score: float = 85.0
    min_volume: float = 100.0
    max_days_to_resolution: int = 14

    # Runtime
    db_path: str = "data/positions.db"
    log_file: str = "logs/bot.log"
    log_level: str = "INFO"
    http_timeout_sec: float = 20.0

    @classmethod
    def from_env(cls, env_file: str | os.PathLike[str] | None = ".env") -> Settings:
        if env_file and Path(env_file).is_file():
            load_dotenv(env_file, override=False)

        settings = cls(
            kalshi_api_key_id=_get("KALSHI_API_KEY_ID"),
            kalshi_private_key=_get("KALSHI_PRIVATE_KEY").replace("\\n", "\n"),
            kalshi_private_key_path=_get("KALSHI_PRIVATE_KEY_PATH"),
            kalshi_base_url=_get("KALSHI_BASE_URL", cls.kalshi_base_url).rstrip("/"),
            kalshi_series=_get_list("KALSHI_SERIES", DEFAULT_KALSHI_SERIES),
            kalshi_fee_rate=_get_float("KALSHI_FEE_RATE", cls.kalshi_fee_rate),
            poly_private_key=_get("POLY_PRIVATE_KEY"),
            poly_funder_address=_get("POLY_FUNDER_ADDRESS"),
            poly_signature_type=_get_int("POLY_SIGNATURE_TYPE", cls.poly_signature_type),
            poly_api_key=_get("POLY_API_KEY"),
            poly_api_secret=_get("POLY_API_SECRET"),
            poly_passphrase=_get("POLY_PASSPHRASE"),
            poly_clob_url=_get("POLY_CLOB_URL", cls.poly_clob_url).rstrip("/"),
            poly_gamma_url=_get("POLY_GAMMA_URL", cls.poly_gamma_url).rstrip("/"),
            poly_chain_id=_get_int("POLY_CHAIN_ID", cls.poly_chain_id),
            poly_pages=_get_int("POLY_PAGES", cls.poly_pages),
            poly_default_fee_rate=_get_float("POLY_DEFAULT_FEE_RATE", cls.poly_default_fee_rate),
            dry_run=_get_bool("DRY_RUN", True),
            min_profit_pct=_get_float("MIN_PROFIT_PCT", cls.min_profit_pct),
            max_position_usd=_get_float("MAX_POSITION_USD", cls.max_position_usd),
            max_open_positions=_get_int("MAX_OPEN_POSITIONS", cls.max_open_positions),
            poll_interval_sec=_get_int("POLL_INTERVAL_SEC", cls.poll_interval_sec),
            match_score_threshold=_get_float("MATCH_SCORE_THRESHOLD", cls.match_score_threshold),
            execution_min_match_score=_get_float(
                "EXECUTION_MIN_MATCH_SCORE", cls.execution_min_match_score
            ),
            min_volume=_get_float("MIN_VOLUME", cls.min_volume),
            max_days_to_resolution=_get_int("MAX_DAYS_TO_RESOLUTION", cls.max_days_to_resolution),
            db_path=_get("DB_PATH", cls.db_path),
            log_file=_get("LOG_FILE", cls.log_file),
            log_level=_get("LOG_LEVEL", cls.log_level).upper(),
            http_timeout_sec=_get_float("HTTP_TIMEOUT_SEC", cls.http_timeout_sec),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        errors: list[str] = []
        if not 0 <= self.min_profit_pct < 1:
            errors.append("MIN_PROFIT_PCT must be between 0 and 1 (e.g. 0.02 for 2%)")
        if self.max_position_usd <= 0:
            errors.append("MAX_POSITION_USD must be greater than 0")
        if self.max_open_positions < 1:
            errors.append("MAX_OPEN_POSITIONS must be at least 1")
        if self.poll_interval_sec < 5:
            errors.append("POLL_INTERVAL_SEC must be at least 5 to respect API rate limits")
        if not 0 <= self.match_score_threshold <= 100:
            errors.append("MATCH_SCORE_THRESHOLD must be between 0 and 100")
        if not 0 <= self.execution_min_match_score <= 100:
            errors.append("EXECUTION_MIN_MATCH_SCORE must be between 0 and 100")
        if self.max_days_to_resolution < 0:
            errors.append("MAX_DAYS_TO_RESOLUTION must be 0 (no limit) or a positive integer")
        if not 1 <= self.poly_pages <= 50:
            errors.append("POLY_PAGES must be between 1 and 50")
        if self.poly_signature_type not in (0, 1, 2):
            errors.append(
                "POLY_SIGNATURE_TYPE must be 0 (EOA), 1 (email/Magic), or 2 (browser proxy)"
            )
        for name in ("kalshi_base_url", "poly_clob_url", "poly_gamma_url"):
            if not getattr(self, name).startswith("https://"):
                errors.append(f"{name.upper()} must use https://")
        if errors:
            raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(errors))

    @property
    def has_kalshi_credentials(self) -> bool:
        return bool(
            self.kalshi_api_key_id and (self.kalshi_private_key or self.kalshi_private_key_path)
        )

    @property
    def has_polymarket_credentials(self) -> bool:
        return bool(self.poly_private_key)

    def live_trading_problems(self) -> list[str]:
        """Return the reasons live trading cannot start (empty when ready)."""
        problems = []
        if not self.has_kalshi_credentials:
            problems.append(
                "Kalshi credentials missing: set KALSHI_API_KEY_ID and "
                "KALSHI_PRIVATE_KEY_PATH (or KALSHI_PRIVATE_KEY)"
            )
        if not self.has_polymarket_credentials:
            problems.append("Polymarket credentials missing: set POLY_PRIVATE_KEY")
        if self.poly_signature_type in (1, 2) and not self.poly_funder_address:
            problems.append("POLY_FUNDER_ADDRESS is required when POLY_SIGNATURE_TYPE is 1 or 2")
        return problems
