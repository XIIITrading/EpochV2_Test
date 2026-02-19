"""
Volume ROC Calculations - Thin Adapter
Epoch Trading System - XIII Trading LLC

Delegates to shared.indicators.core.volume_roc (canonical implementation).
Preserves dict-based return format for backward compatibility with data_worker.

SWH-6: Single source of truth - shared.indicators
"""
from typing import List, Optional

from shared.indicators.core.volume_roc import (
    is_elevated_volume as _shared_is_elevated,
    is_high_volume as _shared_is_high,
)
from shared.indicators.config import CONFIG


# Re-export thresholds from canonical config
DEFAULT_LOOKBACK = CONFIG.volume_roc.baseline_period       # 20
ELEVATED_THRESHOLD = CONFIG.volume_roc.elevated_threshold  # 30
HIGH_THRESHOLD = CONFIG.volume_roc.high_threshold          # 50


def calculate_volume_roc(current_volume: float, avg_volume: float) -> float:
    """
    Calculate volume rate of change as percentage.

    Formula: ((current - avg) / avg) * 100
    """
    if avg_volume <= 0:
        return 0.0
    return ((current_volume - avg_volume) / avg_volume) * 100


def calculate_volume_average(volumes: List[float], period: int = DEFAULT_LOOKBACK) -> Optional[float]:
    """Calculate simple moving average of volume."""
    if len(volumes) < period:
        return None
    return sum(volumes[-period:]) / period


def is_elevated_volume(volume_roc: float) -> bool:
    """Check if volume ROC indicates elevated volume (>=30%)."""
    return _shared_is_elevated(volume_roc)


def is_high_volume(volume_roc: float) -> bool:
    """Check if volume ROC indicates high volume (>=50%)."""
    return _shared_is_high(volume_roc)


def calculate_all_volume_roc(
    bars: List[dict],
    lookback: int = DEFAULT_LOOKBACK
) -> List[dict]:
    """
    Calculate volume ROC for all bars.

    Args:
        bars: List of bar dictionaries with 'volume' or 'v' key
        lookback: Lookback period for average calculation

    Returns:
        List of dicts with 'volume_roc' and 'is_elevated' keys
    """
    results = []
    volumes = []

    for i, bar in enumerate(bars):
        volume = bar.get('volume', bar.get('v', 0))
        volumes.append(volume)

        if i < lookback:
            results.append({
                'volume_roc': None,
                'is_elevated': False
            })
        else:
            # Average of previous 'lookback' bars (not including current)
            prev_volumes = volumes[i - lookback:i]
            avg_volume = sum(prev_volumes) / lookback

            volume_roc = calculate_volume_roc(volume, avg_volume)

            results.append({
                'volume_roc': volume_roc,
                'is_elevated': is_elevated_volume(volume_roc)
            })

    return results
