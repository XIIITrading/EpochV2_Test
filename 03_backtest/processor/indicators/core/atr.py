"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 03: SHARED INDICATORS
Average True Range (ATR) Calculations
XIII Trading LLC
================================================================================

Formula:
    True Range = max(high - low, |high - prev_close|, |low - prev_close|)
    ATR = Simple Moving Average of True Range over N periods

Standard period: 14

Health Factor: Higher ATR indicates greater volatility/range for stop placement.

================================================================================
"""

from typing import List, Optional, Any
import sys
from pathlib import Path

# Add parent to path for relative imports within shared library
_LIB_DIR = Path(__file__).parent.parent
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from _internal import ATR_CONFIG, ATRResult, get_high, get_low, get_close


# =============================================================================
# DEFAULT PERIOD
# =============================================================================

DEFAULT_ATR_PERIOD = ATR_CONFIG["period"]  # 14


# =============================================================================
# CORE CALCULATIONS
# =============================================================================

def calculate_true_range(
    high: float,
    low: float,
    prev_close: float
) -> float:
    """
    Calculate True Range for a single bar.

    True Range = max(high - low, |high - prev_close|, |low - prev_close|)

    Args:
        high: Bar high price
        low: Bar low price
        prev_close: Previous bar's close price

    Returns:
        True Range value (always >= 0)
    """
    return max(
        high - low,
        abs(high - prev_close),
        abs(low - prev_close)
    )


def calculate_atr(
    bars: List[Any],
    period: int = None,
    up_to_index: Optional[int] = None
) -> ATRResult:
    """
    Calculate ATR from a list of bar dicts/objects.

    Uses Simple Moving Average of True Range over the specified period.
    Requires at least period + 1 bars (need prev_close for first TR).

    Args:
        bars: List of bar data (dict or object with high, low, close)
        period: ATR period (default: 14 from config)
        up_to_index: Calculate up to this index (inclusive), default all

    Returns:
        ATRResult with atr value, last true_range, and period used
    """
    period = period or DEFAULT_ATR_PERIOD

    if not bars or len(bars) < 2:
        return ATRResult(atr=None, true_range=None, period=period)

    end_index = up_to_index if up_to_index is not None else len(bars) - 1
    end_index = min(end_index, len(bars) - 1)

    if end_index < 1:
        return ATRResult(atr=None, true_range=None, period=period)

    # Calculate True Range for each bar (starting from index 1)
    true_ranges = []
    for i in range(1, end_index + 1):
        high = get_high(bars[i], 0.0)
        low = get_low(bars[i], 0.0)
        prev_close = get_close(bars[i - 1], 0.0)

        tr = calculate_true_range(high, low, prev_close)
        true_ranges.append(tr)

    if len(true_ranges) < period:
        # Not enough data for full ATR, return last TR but no ATR
        return ATRResult(
            atr=None,
            true_range=true_ranges[-1] if true_ranges else None,
            period=period
        )

    # ATR = SMA of the last `period` True Range values
    atr_value = sum(true_ranges[-period:]) / period

    return ATRResult(
        atr=atr_value,
        true_range=true_ranges[-1],
        period=period
    )


def calculate_atr_series(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = None
) -> List[Optional[float]]:
    """
    Calculate ATR for a series of price data (for pandas/vectorized use).

    Returns a list of ATR values aligned with the input arrays.
    First `period` values will be None (insufficient data for calculation).

    Args:
        highs: List of high prices
        lows: List of low prices
        closes: List of close prices
        period: ATR period (default: 14 from config)

    Returns:
        List of ATR values (same length as input, None for warmup period)
    """
    period = period or DEFAULT_ATR_PERIOD
    n = len(highs)

    if n < 2:
        return [None] * n

    # Calculate True Range series (index 0 has no prev_close, so TR is None)
    true_ranges = [None]  # First bar has no previous close
    for i in range(1, n):
        tr = calculate_true_range(highs[i], lows[i], closes[i - 1])
        true_ranges.append(tr)

    # Calculate ATR as rolling SMA of True Range
    atr_values = [None] * n

    for i in range(period, n):
        # Sum the last `period` true ranges (starting from index 1)
        window = true_ranges[i - period + 1:i + 1]
        if None in window:
            atr_values[i] = None
        else:
            atr_values[i] = sum(window) / period

    return atr_values
