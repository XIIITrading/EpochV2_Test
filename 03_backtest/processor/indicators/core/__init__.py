"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 03: SHARED INDICATORS
Core Indicator Calculations
XIII Trading LLC
================================================================================

Core indicator modules:
- candle_range: Candle Range % calculations (EPCH v1.0)
- vwap: Volume Weighted Average Price
- sma: Simple Moving Averages (SMA9/SMA21, spread, momentum)
- volume_delta: Bar delta and rolling delta calculations
- volume_roc: Volume Rate of Change
- cvd: Cumulative Volume Delta slope
- scores: Composite LONG/SHORT scores (EPCH v1.0)

================================================================================
"""

# Candle Range (EPCH v1.0)
from .candle_range import (
    calculate_candle_range_pct,
    calculate_candle_range_from_bar,
    is_absorption_zone,
    get_range_classification,
    is_candle_range_healthy,
    calculate_all_candle_ranges,
)

from .vwap import calculate_vwap, calculate_vwap_metrics, is_vwap_healthy

# SMA (with EPCH v1.0 spread_pct functions)
from .sma import (
    calculate_sma,
    calculate_sma_spread,
    calculate_sma_momentum,
    is_sma_alignment_healthy,
    is_sma_momentum_healthy,
    calculate_sma_spread_pct,
    is_wide_spread,
    get_sma_config_str,
    get_price_position,
    format_sma_display,
)

from .volume_delta import calculate_bar_delta, calculate_bar_delta_from_bar, calculate_rolling_delta, is_volume_delta_healthy

# Volume ROC (with EPCH v1.0 elevated/high functions)
from .volume_roc import (
    calculate_volume_roc,
    classify_volume_roc,
    is_volume_roc_healthy,
    is_elevated_volume,
    is_high_volume,
)

from .cvd import calculate_cvd_slope, classify_cvd_trend, is_cvd_healthy

# Composite Scores (EPCH v1.0)
from .scores import (
    calculate_long_score,
    calculate_short_score,
    calculate_scores,
    calculate_all_scores,
)

# ATR (Average True Range)
from .atr import calculate_true_range, calculate_atr, calculate_atr_series

__all__ = [
    # Candle Range (EPCH v1.0)
    "calculate_candle_range_pct",
    "calculate_candle_range_from_bar",
    "is_absorption_zone",
    "get_range_classification",
    "is_candle_range_healthy",
    "calculate_all_candle_ranges",
    # VWAP
    "calculate_vwap",
    "calculate_vwap_metrics",
    "is_vwap_healthy",
    # SMA
    "calculate_sma",
    "calculate_sma_spread",
    "calculate_sma_momentum",
    "is_sma_alignment_healthy",
    "is_sma_momentum_healthy",
    "calculate_sma_spread_pct",
    "is_wide_spread",
    "get_sma_config_str",
    "get_price_position",
    "format_sma_display",
    # Volume Delta
    "calculate_bar_delta",
    "calculate_bar_delta_from_bar",
    "calculate_rolling_delta",
    "is_volume_delta_healthy",
    # Volume ROC
    "calculate_volume_roc",
    "classify_volume_roc",
    "is_volume_roc_healthy",
    "is_elevated_volume",
    "is_high_volume",
    # CVD
    "calculate_cvd_slope",
    "classify_cvd_trend",
    "is_cvd_healthy",
    # Composite Scores (EPCH v1.0)
    "calculate_long_score",
    "calculate_short_score",
    "calculate_scores",
    "calculate_all_scores",
    # ATR (Average True Range)
    "calculate_true_range",
    "calculate_atr",
    "calculate_atr_series",
]
