"""
Entry Qualifier Calculations Module

All indicator calculations delegate to shared.indicators (canonical).
This module provides backward-compatible dict-based wrappers.

SWH-6: Single source of truth - shared.indicators
"""
from calculations.volume_delta import calculate_all_deltas, calculate_bar_delta
from calculations.candle_range import (
    calculate_all_candle_ranges,
    calculate_candle_range_pct,
    is_absorption_zone,
    ABSORPTION_THRESHOLD,
    NORMAL_THRESHOLD
)
from calculations.volume_roc import (
    calculate_all_volume_roc,
    calculate_volume_roc,
    is_elevated_volume,
    ELEVATED_THRESHOLD,
    HIGH_THRESHOLD
)
from calculations.sma_config import (
    calculate_all_sma_configs,
    SMAConfig,
    PricePosition,
    WIDE_SPREAD_THRESHOLD
)
from calculations.h1_structure import (
    calculate_structure_for_bars,
    MarketStructure,
    H1StructureCache,
    StructureCache
)
