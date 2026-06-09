def kalshi_fee(price: float, size_usd: float) -> float:
    """
    Kalshi charges a fee on each contract. The fee schedule is tiered;
    this uses a conservative flat estimate of 7% of the contract value
    (based on their published maker/taker fee caps).
    Adjust once you verify your actual tier.
    """
    fee_rate = 0.07
    return round(price * size_usd * fee_rate, 6)


def polymarket_fee(price: float, size_usd: float) -> float:
    """
    Polymarket charges 0% maker / 0.5% taker on the CLOB.
    We assume taker fills for conservatism.
    """
    fee_rate = 0.005
    return round(size_usd * fee_rate, 6)


def total_fees(kalshi_price: float, poly_price: float, size_usd: float) -> float:
    return kalshi_fee(kalshi_price, size_usd) + polymarket_fee(poly_price, size_usd)
