"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
M1 Indicator Bars v2 - Indicator Calculations
XIII Trading LLC
================================================================================

Direction-agnostic indicator calculation functions for M1 bars.
Calculates all Entry Qualifier standard indicators plus extended analysis.

Entry Qualifier Standard (from 02_dow_ai/entry_qualifier):
  - Candle Range %
  - Volume Delta (raw + rolling)
  - Volume ROC
  - SMA Config (BULL/BEAR/FLAT)
  - SMA Spread %
  - Price Position (ABOVE/BTWN/BELOW)

Extended Analysis:
  - VWAP (cumulative session)
  - SMA Momentum (WIDENING/NARROWING/STABLE)
  - CVD Slope (normalized)
  - ATR (True Range method)

DEPRECATED per SWH-6:
  - Health Score (was 0-10)
  - Composite Scores (was long 0-7, short 0-7)
  Scoring columns are retained as NULL to avoid schema changes.
  They will be removed in a future migration.

IMPORTANT: All calculations import from the canonical shared.indicators library.
No local indicator implementations.

Version: 3.0.0 (SWH-6 migration)
================================================================================
"""

from typing import List, Dict, Optional, NamedTuple
import numpy as np
import pandas as pd

# =============================================================================
# IMPORT FROM CANONICAL SHARED INDICATORS LIBRARY
# =============================================================================

from shared.indicators.config import CONFIG

# DataFrame wrappers (vectorized - preferred for DataFrame operations)
from shared.indicators.core.volume_delta import volume_delta_df, rolling_delta_df
from shared.indicators.core.volume_roc import volume_roc_df
from shared.indicators.core.cvd import cvd_slope_df
from shared.indicators.core.atr import atr_df
from shared.indicators.core.sma import sma_df, sma_spread_df
from shared.indicators.core.vwap import vwap_df
from shared.indicators.core.candle_range import candle_range_pct_df


# =============================================================================
# RESULT DATA STRUCTURES
# =============================================================================

class IndicatorSnapshot(NamedTuple):
    """Complete indicator snapshot for a single M1 bar."""
    # Price Indicators
    vwap: Optional[float]
    sma9: Optional[float]
    sma21: Optional[float]
    sma_config: Optional[str]           # BULL, BEAR, FLAT
    sma_spread_pct: Optional[float]     # abs(sma9-sma21)/close*100
    price_position: Optional[str]       # ABOVE, BTWN, BELOW
    sma_spread: Optional[float]
    sma_momentum_ratio: Optional[float]
    sma_momentum_label: Optional[str]

    # Volume Indicators
    vol_roc: Optional[float]
    vol_delta_raw: Optional[float]      # Single bar delta
    vol_delta_roll: Optional[float]     # 5-bar rolling sum
    cvd_slope: Optional[float]

    # Health Score (DEPRECATED - always None)
    health_score: Optional[int]

    # Entry Qualifier Scores
    candle_range_pct: Optional[float]
    long_score: Optional[int]           # DEPRECATED - always None
    short_score: Optional[int]          # DEPRECATED - always None

    # Metadata
    bars_in_calculation: int


# =============================================================================
# INDICATOR CALCULATION CLASS
# =============================================================================

class M1IndicatorCalculator:
    """
    Calculates direction-agnostic indicators for M1 bars.

    All indicators are calculated on a rolling basis to support
    calculating values at any bar in the sequence.

    Includes Entry Qualifier standard indicators (sma_config, sma_spread_pct,
    price_position) plus extended analysis (VWAP, SMA momentum, CVD slope, etc.)

    All calculations delegate to the canonical shared.indicators library (SWH-6).
    """

    def __init__(self):
        """Initialize the indicator calculator."""
        pass

    def add_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add all indicator columns to the DataFrame.

        Args:
            df: DataFrame with columns: open, high, low, close, volume, vwap
                Must also have 'bar_date' for daily VWAP reset.

        Returns:
            DataFrame with added indicator columns
        """
        if df.empty:
            return df

        df = df.copy()

        # Calculate VWAP (cumulative daily reset)
        df = self._add_vwap(df)

        # Calculate SMAs + config + spread + price position (all vectorized)
        df = self._add_sma_suite(df)

        # Calculate SMA momentum
        df = self._add_sma_momentum(df)

        # Calculate Volume ROC (vectorized)
        df = self._add_volume_roc(df)

        # Calculate Volume Delta - raw + rolling (vectorized)
        df = self._add_volume_delta(df)

        # Calculate CVD Slope (vectorized)
        df = self._add_cvd_slope(df)

        # Candle Range % (vectorized)
        df = self._add_candle_range(df)

        # ATR (vectorized)
        df = self._add_atr_m1(df)

        # DEPRECATED: Health score and composite scores (SWH-6)
        # Columns retained as NULL for backward compatibility
        df['health_score'] = np.nan
        df['long_score'] = np.nan
        df['short_score'] = np.nan

        return df

    # =========================================================================
    # VWAP
    # =========================================================================

    def _add_vwap(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add calculated VWAP column (cumulative daily VWAP).

        Uses shared.indicators.core.vwap.vwap_df with daily reset.
        """
        df['vwap_calc'] = vwap_df(df, reset_daily=True)
        return df

    # =========================================================================
    # SMA SUITE: SMA9, SMA21, config, spread_pct, price_position
    # =========================================================================

    def _add_sma_suite(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add all SMA-related columns using shared vectorized calculation.

        Adds: sma9, sma21, sma_spread, sma_config, sma_spread_pct, price_position
        """
        # Use shared sma_spread_df for sma9, sma21, spread, config, spread_pct
        sma_result = sma_spread_df(df)
        df['sma9'] = sma_result['sma9']
        df['sma21'] = sma_result['sma21']
        df['sma_spread'] = sma_result['sma_spread']
        df['sma_config'] = sma_result['sma_config']
        df['sma_spread_pct'] = sma_result['sma_spread_pct']

        # Handle NaN -> None for sma_config (string column)
        df['sma_config'] = df['sma_config'].where(
            df['sma9'].notna() & df['sma21'].notna(), other=None
        )

        # Price position: ABOVE, BTWN, BELOW
        def get_position(row):
            close = row.get('close')
            sma9 = row.get('sma9')
            sma21 = row.get('sma21')
            if pd.isna(sma9) or pd.isna(sma21) or pd.isna(close):
                return None
            higher = max(sma9, sma21)
            lower = min(sma9, sma21)
            if close > higher:
                return 'ABOVE'
            elif close < lower:
                return 'BELOW'
            else:
                return 'BTWN'

        df['price_position'] = df.apply(get_position, axis=1)
        return df

    # =========================================================================
    # SMA MOMENTUM
    # =========================================================================

    def _add_sma_momentum(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add SMA momentum ratio and label columns.

        Uses CONFIG.sma.momentum_lookback and CONFIG.sma.widening_threshold.
        """
        cfg = CONFIG.sma

        # Get absolute spread
        abs_spread = df['sma_spread'].abs()

        # Calculate spread from N bars ago
        prev_spread = abs_spread.shift(cfg.momentum_lookback)

        # Calculate ratio
        df['sma_momentum_ratio'] = abs_spread / prev_spread.replace(0, np.nan)

        # Cap ratio to prevent database overflow (max 9999.999999 for DECIMAL(10,6))
        df['sma_momentum_ratio'] = df['sma_momentum_ratio'].clip(upper=999.0)

        # Determine momentum label
        def get_momentum_label(ratio):
            if pd.isna(ratio):
                return None
            if ratio > cfg.widening_threshold:
                return 'WIDENING'
            elif ratio < 1.0 / cfg.widening_threshold:
                return 'NARROWING'
            else:
                return 'STABLE'

        df['sma_momentum_label'] = df['sma_momentum_ratio'].apply(get_momentum_label)

        return df

    # =========================================================================
    # VOLUME ROC
    # =========================================================================

    def _add_volume_roc(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add Volume ROC column using shared vectorized calculation.

        Uses shared.indicators.core.volume_roc.volume_roc_df.
        Output: percentage (0% = average, 30% = elevated, 50% = high).
        """
        df['vol_roc'] = volume_roc_df(df)
        return df

    # =========================================================================
    # VOLUME DELTA
    # =========================================================================

    def _add_volume_delta(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add Volume Delta columns (raw single-bar + rolling sum + normalized).

        Uses shared.indicators.core.volume_delta:
        - volume_delta_df() for per-bar delta
        - rolling_delta_df() for rolling sum

        v3 change: Added vol_delta_norm (roll / avg_volume) for cross-ticker comparability.
        """
        # Per-bar delta using shared vectorized calculation
        df['vol_delta_raw'] = volume_delta_df(df)

        # Rolling sum using shared vectorized calculation
        df['vol_delta_roll'] = rolling_delta_df(df)

        # Normalize by average volume for cross-ticker comparability
        period = CONFIG.volume_delta.rolling_period
        avg_vol = df['volume'].rolling(window=period, min_periods=period).mean()
        df['vol_delta_norm'] = df['vol_delta_roll'] / avg_vol.replace(0, np.nan)

        # Keep backward-compatible vol_delta alias
        df['vol_delta'] = df['vol_delta_roll']

        return df

    # =========================================================================
    # CVD SLOPE
    # =========================================================================

    def _add_cvd_slope(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add CVD Slope column using shared vectorized calculation.

        Uses shared.indicators.core.cvd.cvd_slope_df.
        Linear regression, normalized by CVD range x window, clamped [-2, 2].
        """
        df['cvd_slope'] = cvd_slope_df(df)
        return df

    # =========================================================================
    # CANDLE RANGE
    # =========================================================================

    def _add_candle_range(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add candle_range_pct column using shared vectorized calculation.

        Formula: (high - low) / close * 100
        Used as primary skip filter for absorption zones.
        """
        df['candle_range_pct'] = candle_range_pct_df(df)
        return df

    # =========================================================================
    # ATR (AVERAGE TRUE RANGE) - M1 TIMEFRAME
    # =========================================================================

    def _add_atr_m1(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add M1 ATR column using shared vectorized calculation.

        True Range = max(high - low, |high - prev_close|, |low - prev_close|)
        ATR = SMA of True Range over CONFIG.atr.period bars

        Uses shared.indicators.core.atr.atr_df.
        """
        df['atr_m1'] = atr_df(df)
        return df

    # =========================================================================
    # SNAPSHOT UTILITIES
    # =========================================================================

    def get_snapshot_at_index(self, df: pd.DataFrame, index: int) -> Optional[IndicatorSnapshot]:
        """
        Get indicator snapshot at a specific DataFrame index.

        Args:
            df: DataFrame with indicator columns already added
            index: Row index to get snapshot for

        Returns:
            IndicatorSnapshot or None if index is invalid
        """
        if index < 0 or index >= len(df):
            return None

        row = df.iloc[index]

        return IndicatorSnapshot(
            vwap=self._safe_float(row.get('vwap_calc')),
            sma9=self._safe_float(row.get('sma9')),
            sma21=self._safe_float(row.get('sma21')),
            sma_config=row.get('sma_config'),
            sma_spread_pct=self._safe_float(row.get('sma_spread_pct')),
            price_position=row.get('price_position'),
            sma_spread=self._safe_float(row.get('sma_spread')),
            sma_momentum_ratio=self._safe_float(row.get('sma_momentum_ratio')),
            sma_momentum_label=row.get('sma_momentum_label'),
            vol_roc=self._safe_float(row.get('vol_roc')),
            vol_delta_raw=self._safe_float(row.get('vol_delta_raw')),
            vol_delta_roll=self._safe_float(row.get('vol_delta_roll')),
            cvd_slope=self._safe_float(row.get('cvd_slope')),
            health_score=None,  # DEPRECATED per SWH-6
            candle_range_pct=self._safe_float(row.get('candle_range_pct')),
            long_score=None,    # DEPRECATED per SWH-6
            short_score=None,   # DEPRECATED per SWH-6
            bars_in_calculation=index + 1
        )

    def _safe_float(self, value) -> Optional[float]:
        """Convert value to float, returning None for NaN."""
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return None
        try:
            return round(float(value), 6)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value) -> Optional[int]:
        """Convert value to int, returning None for NaN."""
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
