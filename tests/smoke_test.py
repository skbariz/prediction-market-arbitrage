import sys
sys.path.insert(0, ".")

from datetime import datetime, timezone, timedelta
from rapidfuzz import fuzz
from src.models.market import Market, MarketPrice
from src.core.matcher import match_markets
from src.core.detector import detect_opportunities

# --- Fuzzy match score check ---
title_k = "Who will win the 2026 Senate election in Ohio?"
title_p = "Will Democrats win the Ohio Senate seat in 2026?"
score = fuzz.token_set_ratio(title_k.lower(), title_p.lower())
print(f"Fuzzy match score (different phrasing): {score:.1f}")

# --- Arb detection with close_time within 7 days ---
now = datetime.now(timezone.utc)
close_soon = now + timedelta(days=5)

k = [Market("kalshi", "ELECTION-OH-2026", "Ohio Senate 2026 election",
            MarketPrice(yes=0.42, no=0.58), close_time=close_soon, volume_usd=5000)]
p = [Market("polymarket", "abc123", "Ohio Senate election 2026",
            MarketPrice(yes=0.63, no=0.37), close_time=close_soon, volume_usd=8000)]

pairs = match_markets(k, p)
print(f"Matched pairs: {len(pairs)}, score={pairs[0][2]:.1f}" if pairs else "No pairs matched")

opps = detect_opportunities(pairs)
if opps:
    o = opps[0]
    days_left = (close_soon - now).days
    print(f"Opportunity: Kalshi {o.kalshi_side}@{o.kalshi_entry} + Poly {o.poly_side}@{o.poly_entry}")
    print(f"Gross cost: {o.gross_cost:.4f} | Fees: {o.fees:.4f} | Net profit: {o.net_profit_pct*100:.2f}% = ${o.net_profit_usd:.4f}")
    print(f"Resolves in: {days_left} days (within 7-day window)")
else:
    print("No opportunity detected")
