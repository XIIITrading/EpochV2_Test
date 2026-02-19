"""
SMA Configuration Calculations - Thin Adapter
Epoch Trading System - XIII Trading LLC

Delegates to shared.indicators.core.sma (canonical implementation).
Preserves dict-based return format + enum types for backward compatibility.

SWH-6: Single source of truth - shared.indicators
"""
from typing import List, Optional
from enum import Enum

from shared.indicators.core.sma import (
    calculate_sma as _shared_calc_sma,
    calculate_sma_spread_pct as _shared_spread_pct,
    get_sma_config_str as _shared_sma_config,
    get_price_position as _shared_price_position,
    is_wide_spread as _shared_is_wide,
)
from shared.indicators.config import CONFIG


class SMAConfig(Enum):
    """SMA configuration states."""
    BULLISH = "B+"     # SMA9 > SMA21
    BEARISH = "B-"     # SMA9 < SMA21
    NEUTRAL = "N"      # SMA9 == SMA21 (rare)


class PricePosition(Enum):
    """Price position relative to SMAs."""
    ABOVE_BOTH = "ABOVE"
    BETWEEN = "BTWN"
    BELOW_BOTH = "BELOW"


# Re-export threshold from canonical config
WIDE_SPREAD_THRESHOLD = CONFIG.sma.wide_spread_threshold  # 0.15


# Mapping from shared string labels to local enums
_CONFIG_MAP = {"BULL": SMAConfig.BULLISH, "BEAR": SMAConfig.BEARISH, "FLAT": SMAConfig.NEUTRAL}
_POSITION_MAP = {"ABOVE": PricePosition.ABOVE_BOTH, "BELOW": PricePosition.BELOW_BOTH, "BTWN": PricePosition.BETWEEN}


def calculate_sma(prices: List[float], period: int) -> Optional[float]:
    """Calculate Simple Moving Average."""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def calculate_sma_spread_pct(sma9: float, sma21: float, price: float) -> float:
    """Calculate spread between SMA9 and SMA21 as percentage of price."""
    return _shared_spread_pct(sma9, sma21, price)


def get_sma_config(sma9: float, sma21: float) -> SMAConfig:
    """Determine SMA configuration. Returns SMAConfig enum."""
    label = _shared_sma_config(sma9, sma21)
    return _CONFIG_MAP.get(label, SMAConfig.NEUTRAL)


def get_price_position(price: float, sma9: float, sma21: float) -> PricePosition:
    """Determine price position relative to SMAs. Returns PricePosition enum."""
    label = _shared_price_position(price, sma9, sma21)
    return _POSITION_MAP.get(label, PricePosition.BETWEEN)


def is_wide_spread(spread_pct: float) -> bool:
    """Check if SMA spread indicates strong trend."""
    return _shared_is_wide(spread_pct)


def format_sma_display(config: SMAConfig, spread_pct: float) -> str:
    """Format SMA config and spread for display."""
    return f"{config.value} {spread_pct:.2f}%"


def calculate_all_sma_configs(
    bars: List[dict],
    sma_short: int = 9,
    sma_long: int = 21
) -> List[dict]:
    """
    Calculate SMA configuration for all bars.

    Args:
        bars: List of bar dictionaries with 'close' or 'c' key
        sma_short: Short SMA period (default 9)
        sma_long: Long SMA period (default 21)

    Returns:
        List of dicts with SMA-related values
    """
    results = []
    closes = []

    for i, bar in enumerate(bars):
        close = bar.get('close', bar.get('c', 0))
        closes.append(close)

        if i < sma_long - 1:
            results.append({
                'sma9': None,
                'sma21': None,
                'sma_config': None,
                'sma_spread_pct': None,
                'price_position': None,
                'sma_display': None
            })
        else:
            sma9 = calculate_sma(closes, sma_short)
            sma21 = calculate_sma(closes, sma_long)

            if sma9 is not None and sma21 is not None:
                config = get_sma_config(sma9, sma21)
                spread_pct = calculate_sma_spread_pct(sma9, sma21, close)
                position = get_price_position(close, sma9, sma21)
                display = format_sma_display(config, spread_pct)

                results.append({
                    'sma9': sma9,
                    'sma21': sma21,
                    'sma_config': config,
                    'sma_spread_pct': spread_pct,
                    'price_position': position,
                    'sma_display': display
                })
            else:
                results.append({
                    'sma9': None,
                    'sma21': None,
                    'sma_config': None,
                    'sma_spread_pct': None,
                    'price_position': None,
                    'sma_display': None
                })

    return results
