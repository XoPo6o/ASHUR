"""Conservative OHLCV-based execution-cost model for historical spot research.

This is a liquidity/volatility proxy, NOT a reconstruction of historical bid/ask
quotes or order-book market impact. Inputs must be known before the simulated fill:
use the previous completed candle's ATR and dollar volume.
"""
from __future__ import annotations

from math import isfinite, sqrt


DEFAULT_SPREAD_BPS = 4.0          # full quoted spread; charge half on each side
DEFAULT_BASE_SLIPPAGE_BPS = 1.0
DEFAULT_VOLATILITY_IMPACT = 0.10
DEFAULT_MAX_IMPACT_BPS = 50.0
DEFAULT_MAX_PARTICIPATION = 0.02  # order notional / previous candle dollar volume


def participation_rate(order_notional: float, reference_dollar_volume: float) -> float:
    """Estimate order size as a fraction of the last completed candle's dollar volume."""
    if not isfinite(order_notional) or order_notional < 0:
        raise ValueError("order_notional must be finite and non-negative")
    if not isfinite(reference_dollar_volume) or reference_dollar_volume <= 0:
        return float("inf")
    return order_notional / reference_dollar_volume


def adverse_cost_bps(
    atr_pct: float,
    reference_dollar_volume: float,
    order_notional: float,
    *,
    spread_bps: float = DEFAULT_SPREAD_BPS,
    base_slippage_bps: float = DEFAULT_BASE_SLIPPAGE_BPS,
    volatility_impact: float = DEFAULT_VOLATILITY_IMPACT,
    max_impact_bps: float = DEFAULT_MAX_IMPACT_BPS,
) -> float:
    """Return one-way adverse cost: half-spread + base slip + volatility/size impact."""
    values = (spread_bps, base_slippage_bps, volatility_impact, max_impact_bps)
    if any(not isfinite(v) or v < 0 for v in values):
        raise ValueError("execution cost parameters must be finite and non-negative")
    if not isfinite(atr_pct) or atr_pct < 0:
        raise ValueError("atr_pct must be finite and non-negative")
    participation = participation_rate(order_notional, reference_dollar_volume)
    if not isfinite(participation):
        return spread_bps / 2 + base_slippage_bps + max_impact_bps
    impact = min(max_impact_bps, atr_pct * 10_000 * volatility_impact * sqrt(participation))
    return spread_bps / 2 + base_slippage_bps + impact



def adverse_cost_components_bps(
    atr_pct: float,
    reference_dollar_volume: float,
    order_notional: float,
    *,
    spread_bps: float = DEFAULT_SPREAD_BPS,
    base_slippage_bps: float = DEFAULT_BASE_SLIPPAGE_BPS,
    volatility_impact: float = DEFAULT_VOLATILITY_IMPACT,
    max_impact_bps: float = DEFAULT_MAX_IMPACT_BPS,
) -> dict[str, float]:
    """Return one-way spread, base-slippage and market-impact components in bps."""
    total = adverse_cost_bps(
        atr_pct, reference_dollar_volume, order_notional,
        spread_bps=spread_bps,
        base_slippage_bps=base_slippage_bps,
        volatility_impact=volatility_impact,
        max_impact_bps=max_impact_bps,
    )
    participation = participation_rate(order_notional, reference_dollar_volume)
    impact = max(0.0, total - spread_bps / 2 - base_slippage_bps)
    return {
        "spread_bps": spread_bps / 2,
        "base_slippage_bps": base_slippage_bps,
        "market_impact_bps": impact,
        "total_bps": total,
    }


def fill_price(
    reference_price: float,
    side: str,
    atr_pct: float,
    reference_dollar_volume: float,
    order_notional: float,
    **cost_parameters: float,
) -> float:
    """Apply adverse one-way execution cost to a reference price."""
    if not isfinite(reference_price) or reference_price <= 0:
        raise ValueError("reference_price must be finite and positive")
    cost = adverse_cost_bps(
        atr_pct, reference_dollar_volume, order_notional, **cost_parameters
    ) / 10_000
    if side == "buy":
        return reference_price * (1 + cost)
    if side == "sell":
        return reference_price * (1 - cost)
    raise ValueError("side must be 'buy' or 'sell'")


def within_participation_limit(
    order_notional: float,
    reference_dollar_volume: float,
    max_participation: float = DEFAULT_MAX_PARTICIPATION,
) -> bool:
    if not isfinite(max_participation) or max_participation <= 0:
        raise ValueError("max_participation must be finite and positive")
    return participation_rate(order_notional, reference_dollar_volume) <= max_participation
