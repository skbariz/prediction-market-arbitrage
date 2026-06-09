from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from src.models.opportunity import ArbOpportunity


@dataclass
class Position:
    created_at: datetime
    opportunity: ArbOpportunity
    size_usd: float
    id: Optional[int] = None
    kalshi_order_id: Optional[str] = None
    poly_order_id: Optional[str] = None
    status: str = "open"
    closed_at: Optional[datetime] = None
    actual_profit_usd: Optional[float] = None
