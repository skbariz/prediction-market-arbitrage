from dataclasses import dataclass
from src.models.market import Market


@dataclass
class ArbOpportunity:
    kalshi_market: Market
    poly_market: Market
    kalshi_side: str
    poly_side: str
    kalshi_entry: float
    poly_entry: float
    gross_cost: float
    fees: float
    net_profit_pct: float
    match_score: float

    @property
    def net_profit_usd(self) -> float:
        from config.settings import MAX_POSITION_USD
        return round(self.net_profit_pct * MAX_POSITION_USD, 4)
