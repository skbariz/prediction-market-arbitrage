from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class MarketPrice:
    yes: float
    no: float

    @classmethod
    def from_yes(cls, yes_price: float) -> "MarketPrice":
        return cls(yes=yes_price, no=round(1.0 - yes_price, 6))


@dataclass
class Market:
    platform: str
    market_id: str
    title: str
    price: MarketPrice
    close_time: Optional[datetime] = None
    volume_usd: Optional[float] = None
    is_active: bool = True
    # Polymarket CLOB token IDs (needed for order placement)
    yes_token_id: Optional[str] = None
    no_token_id: Optional[str] = None
