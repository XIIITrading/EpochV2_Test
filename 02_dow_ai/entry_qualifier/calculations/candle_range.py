"""
Candle Range Calculations - Thin Adapter
Epoch Trading System - XIII Trading LLC

Delegates to shared.indicators.core.candle_range (canonical implementation).
Preserves dict-based return format for backward compatibility with data_worker.

SWH-6: Single source of truth - shared.indicators
"""
from typing import List

from shared.indicators.core.candle_range import (
    calculate_candle_range_pct as _shared_candle_range_pct,
    is_absorption_zone as _shared_is_absorption,
    get_range_classification,
)
from shared.indicators.config import CONFIG


# Re-export thresholds from canonical config (for backward compatibility)
ABSORPTION_THRESHOLD = CONFIG.candle_range.absorption_threshold / 100  # 0.0012
NORMAL_THRESHOLD = CONFIG.candle_range.normal_threshold / 100          # 0.0015
HIGH_THRESHOLD = CONFIG.candle_range.high_threshold / 100              # 0.0020


def calculate_candle_range_pct(high: float, low: float, close: float) -> float:
    """
    Calculate candle range as percentage of price.

    Formula: (high - low) / close * 100

    Delegates to shared.indicators.core.candle_range.calculate_candle_range_pct.
    """
    return _shared_candle_range_pct(high, low, close)


def is_absorption_zone(candle_range_pct: float) -> bool:
    """
    Check if candle range indicates absorption zone (should skip).

    Delegates to shared.indicators.core.candle_range.is_absorption_zone.
    """
    return _shared_is_absorption(candle_range_pct)


def calculate_all_candle_ranges(bars: List[dict]) -> List[dict]:
    """
    Calculate candle range percentage for all bars.

    Args:
        bars: List of bar dictionaries with h, l, c keys

    Returns:
        List of dicts with 'candle_range_pct' and 'is_absorption' keys
    """
    results = []

    for bar in bars:
        high = bar.get('high', bar.get('h', 0))
        low = bar.get('low', bar.get('l', 0))
        close = bar.get('close', bar.get('c', 0))

        pct = calculate_candle_range_pct(high, low, close)

        results.append({
            'candle_range_pct': pct,
            'is_absorption': is_absorption_zone(pct)
        })

    return results
