"""Exchange taker-fee models.

Both exchanges charge takers ``rate * contracts * price * (1 - price)``:

* Kalshi rounds the total up to the next cent. The general taker rate is 0.07; some markets
  are cheaper, so 0.07 is a conservative default (override with ``KALSHI_FEE_RATE``).
  https://kalshi.com/docs/kalshi-fee-schedule.pdf
* Polymarket publishes a per-market ``feeSchedule.rate`` (0 for fee-free markets) and rounds to
  5 decimal places. When a market does not report a rate, ``POLY_DEFAULT_FEE_RATE`` (0.07, the
  highest published category rate) is used. https://docs.polymarket.com/trading/fees
"""

from __future__ import annotations

import math


def _variance_term(price: float) -> float:
    if not 0.0 <= price <= 1.0:
        raise ValueError(f"price must be between 0 and 1, got {price}")
    return price * (1.0 - price)


def kalshi_fee(price: float, contracts: int, rate: float = 0.07) -> float:
    cents = rate * contracts * _variance_term(price) * 100
    # Round away float noise first so an exact cent amount is not bumped up a cent.
    return math.ceil(round(cents, 6)) / 100


def polymarket_fee(price: float, shares: float, rate: float = 0.07) -> float:
    return round(rate * shares * _variance_term(price), 5)
