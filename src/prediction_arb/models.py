"""Plain data types shared by every component of the bot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Platform(str, Enum):
    KALSHI = "kalshi"
    POLYMARKET = "polymarket"


class Side(str, Enum):
    YES = "yes"
    NO = "no"


class PositionStatus(str, Enum):
    DRY_RUN = "dry_run"
    OPEN = "open"
    FAILED = "failed"
    UNHEDGED = "unhedged"
    CLOSED = "closed"


@dataclass(frozen=True)
class MarketPrice:
    """Best available ask price (the price you pay to buy) for each outcome, in dollars (0-1)."""

    yes: float
    no: float

    @classmethod
    def from_yes(cls, yes_price: float) -> MarketPrice:
        return cls(yes=yes_price, no=round(1.0 - yes_price, 6))

    def ask(self, side: Side) -> float:
        return self.yes if side is Side.YES else self.no


@dataclass(frozen=True)
class Market:
    platform: Platform
    market_id: str
    title: str
    price: MarketPrice
    resolves_at: datetime | None = None
    volume: float = 0.0
    is_active: bool = True
    # Polymarket-only fields required for order placement.
    yes_token_id: str | None = None
    no_token_id: str | None = None
    tick_size: float | None = None
    min_order_size: float | None = None
    neg_risk: bool = False
    fee_rate: float | None = None

    def token_id(self, side: Side) -> str | None:
        return self.yes_token_id if side is Side.YES else self.no_token_id

    def days_to_resolution(self, now: datetime | None = None) -> float | None:
        if self.resolves_at is None:
            return None
        now = now or datetime.now(timezone.utc)
        return (self.resolves_at - now).total_seconds() / 86400


@dataclass(frozen=True)
class MatchedPair:
    kalshi: Market
    polymarket: Market
    score: float


@dataclass(frozen=True)
class ArbOpportunity:
    """A fully-sized, fee-adjusted arbitrage between two matched markets.

    Buying ``contracts`` of ``kalshi_side`` on Kalshi and the same number of ``poly_side`` shares on
    Polymarket guarantees a payout of ``contracts * $1`` whichever way the event resolves.
    """

    pair: MatchedPair
    kalshi_side: Side
    poly_side: Side
    kalshi_price: float
    poly_price: float
    contracts: int
    kalshi_fee: float
    poly_fee: float

    @property
    def kalshi_market(self) -> Market:
        return self.pair.kalshi

    @property
    def poly_market(self) -> Market:
        return self.pair.polymarket

    @property
    def match_score(self) -> float:
        return self.pair.score

    @property
    def gross_cost_per_contract(self) -> float:
        return self.kalshi_price + self.poly_price

    @property
    def total_fees(self) -> float:
        return self.kalshi_fee + self.poly_fee

    @property
    def total_cost(self) -> float:
        return self.contracts * self.gross_cost_per_contract + self.total_fees

    @property
    def payout(self) -> float:
        return float(self.contracts)

    @property
    def net_profit_usd(self) -> float:
        return self.payout - self.total_cost

    @property
    def net_profit_pct(self) -> float:
        """Net profit as a fraction of capital deployed."""
        return self.net_profit_usd / self.total_cost if self.total_cost > 0 else 0.0

    @property
    def key(self) -> str:
        """Stable identifier used to avoid re-entering the same arb on consecutive scans."""
        return f"{self.kalshi_market.market_id}|{self.poly_market.market_id}"


@dataclass
class OrderResult:
    platform: Platform
    ok: bool
    order_id: str | None = None
    status: str = ""
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    opportunity: ArbOpportunity
    status: PositionStatus
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    kalshi_order: OrderResult | None = None
    poly_order: OrderResult | None = None
    id: int | None = None
