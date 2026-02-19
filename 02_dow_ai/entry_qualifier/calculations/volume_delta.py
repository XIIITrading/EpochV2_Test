"""
Volume Delta Calculations - Thin Adapter
Epoch Trading System - XIII Trading LLC

Delegates to shared.indicators.core.volume_delta (canonical implementation).
Preserves dict-based return format for backward compatibility with data_worker.

SWH-6: Single source of truth - shared.indicators
"""
from typing import List, Optional

from shared.indicators.core.volume_delta import (
    calculate_bar_delta as _shared_bar_delta,
)


def calculate_bar_delta(
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float
) -> float:
    """
    Estimate volume delta for a single bar using bar position method.

    Delegates to shared.indicators.core.volume_delta.calculate_bar_delta.

    Returns:
        Estimated net volume (positive = buying, negative = selling)
    """
    result = _shared_bar_delta(open_price, high, low, close, int(volume))
    return result.bar_delta


def calculate_rolling_delta(
    raw_deltas: List[float],
    period: int = 5
) -> Optional[float]:
    """
    Calculate rolling sum of bar deltas.

    Args:
        raw_deltas: List of raw volume delta values
        period: Number of bars for rolling sum

    Returns:
        Sum of last N bar deltas, or None if insufficient data
    """
    if len(raw_deltas) < period:
        return None

    return sum(raw_deltas[-period:])


def calculate_all_deltas(
    bars: List[dict],
    roll_period: int = 5
) -> List[dict]:
    """
    Calculate raw and rolling deltas for all bars.

    Args:
        bars: List of bar dictionaries with o, h, l, c, v keys
        roll_period: Period for rolling delta calculation

    Returns:
        List of dicts with 'raw_delta' and 'roll_delta' keys
    """
    results = []
    raw_deltas = []

    for bar in bars:
        raw_delta = calculate_bar_delta(
            open_price=bar.get('open', bar.get('o', 0)),
            high=bar.get('high', bar.get('h', 0)),
            low=bar.get('low', bar.get('l', 0)),
            close=bar.get('close', bar.get('c', 0)),
            volume=bar.get('volume', bar.get('v', 0))
        )
        raw_deltas.append(raw_delta)

        roll_delta = calculate_rolling_delta(raw_deltas, roll_period)

        results.append({
            'raw_delta': raw_delta,
            'roll_delta': roll_delta
        })

    return results
