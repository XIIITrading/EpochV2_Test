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
  - Health Score (0-10)
  - Composite Scores (long 0-7, short 0-7)

IMPORTANT: Core calculations import from the centralized 03_indicators
library to ensure consistency across all Epoch modules.

Version: 2.0.0
================================================================================
"""

from typing import List, Dict, Optional, NamedTuple
import numpy as np
import pandas as pd
import sys
from pathlib import Path

# =============================================================================
# IMPORT FROM LOCAL INDICATORS LIBRARY
# =============================================================================

# Add local indicators to path (self-contained in 03_backtest/processor/indicators)
_INDICATORS_PATH = Path(__file__).resolve().parent.parent.parent / "indicators"
if str(_INDICATORS_PATH) not in sys.path:
    sys.path.insert(0, str(_INDICATORS_PATH))

# Import configurations from centralized library using importlib to avoid local config collision
import importlib.util
_config_spec = importlib.util.spec_from_file_location("indicators_config", _INDICATORS_PATH / "config.py")
_indicators_config = importlib.util.module_from_spec(_config_spec)
_config_spec.loader.exec_module(_indicators_config)

# Extract config objects from centralized library
SMA_CONFIG = _indicators_config.SMA_CONFIG
VOLUME_ROC_CONFIG = _indicators_config.VOLUME_ROC_CONFIG
VOLUME_DELTA_CONFIG = _indicators_config.VOLUME_DELTA_CONFIG
CVD_CONFIG = _indicators_config.CVD_CONFIG
CANDLE_RANGE_CONFIG = _indicators_config.CANDLE_RANGE_CONFIG
SCORE_CONFIG = _indicators_config.SCORE_CONFIG

# Import calculation functions from centralized library
from core.candle_range import calculate_candle_range_pct, NORMAL_THRESHOLD as CANDLE_RANGE_NORMAL_THRESHOLD
from core.volume_delta import calculate_bar_delta
from core.scores import (
    calculate_long_score as _calc_long_score,
    calculate_short_score as _calc_short_score,
    CANDLE_RANGE_THRESHOLD,
    VOLUME_ROC_THRESHOLD,
    VOLUME_DELTA_MAGNITUDE_THRESHOLD,
    SMA_SPREAD_THRESHOLD,
)

# =============================================================================
# LOCAL CONFIG FROM MODULE (for DataFrame operations that need periods)
# =============================================================================

# Load local config using explicit path to avoid collision with 03_indicators config
_LOCAL_CONFIG_PATH = Path(__file__).resolve().parent / "config.py"
_local_config_spec = importlib.util.spec_from_file_location("local_config", _LOCAL_CONFIG_PATH)
_local_config = importlib.util.module_from_spec(_local_config_spec)
_local_config_spec.loader.exec_module(_local_config)

# Extract local config values
SMA_FAST_PERIOD = _local_config.SMA_FAST_PERIOD
SMA_SLOW_PERIOD = _local_config.SMA_SLOW_PERIOD
SMA_MOMENTUM_LOOKBACK = _local_config.SMA_MOMENTUM_LOOKBACK
SMA_WIDENING_THRESHOLD = _local_config.SMA_WIDENING_THRESHOLD
VOLUME_ROC_BASELINE_PERIOD = _local_config.VOLUME_ROC_BASELINE_PERIOD
VOLUME_DELTA_ROLLING_PERIOD = _local_config.VOLUME_DELTA_ROLLING_PERIOD
CVD_WINDOW = _local_config.CVD_WINDOW
HEALTH_VOL_ROC_THRESHOLD = _local_config.HEALTH_VOL_ROC_THRESHOLD
HEALTH_CVD_SLOPE_THRESHOLD = _local_config.HEALTH_CVD_SLOPE_THRESHOLD
HEALTH_SMA_SPREAD_THRESHOLD = _local_config.HEALTH_SMA_SPREAD_THRESHOLD
ATR_PERIOD = _local_config.ATR_PERIOD

# Import ATR calculation from centralized library
from core.atr import calculate_true_range


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

    # Health Score
    health_score: Optional[int]

    # Entry Qualifier Scores
    candle_range_pct: Optional[float]
    long_score: Optional[int]
    short_score: Optional[int]

    # Metadata
    bars_in_calculation: int


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _simple_moving_average(values: pd.Series, period: int) -> pd.Series:
    """Calculate simple moving average."""
    return values.rolling(window=period, min_periods=period).mean()


def _linear_regression_slope(values: np.ndarray) -> float:
    """Calculate slope of linear regression line through values."""
    n = len(values)
    if n < 2:
        return 0.0

    x = np.arange(n)
    y = np.array(values)

    x_mean = np.mean(x)
    y_mean = np.mean(y)

    numerator = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sum((x - x_mean) ** 2)

    if denominator == 0:
        return 0.0

    return numerator / denominator


def _calculate_bar_delta(row: pd.Series) -> float:
    """
    Estimate volume delta for a single bar using centralized calculation.

    Uses the 03_indicators library formula:
    position = (2 * (close - low) / bar_range) - 1
    delta = position * volume
    """
    open_price = float(row.get('open', 0))
    high = float(row.get('high', 0))
    low = float(row.get('low', 0))
    close = float(row.get('close', 0))
    volume = int(row.get('volume', 0))

    # Use centralized calculation
    result = calculate_bar_delta(open_price, high, low, close, volume)
    return result.bar_delta


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

    Core calculations delegate to the centralized 03_indicators library.
    """

    def __init__(self):
        """Initialize the indicator calculator."""
        pass

    def add_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add all indicator columns to the DataFrame.

        Args:
            df: DataFrame with columns: open, high, low, close, volume, vwap

        Returns:
            DataFrame with added indicator columns
        """
        if df.empty:
            return df

        df = df.copy()

        # Calculate VWAP (cumulative for the trading day)
        df = self._add_vwap(df)

        # Calculate SMAs
        df = self._add_sma(df)

        # Entry Qualifier Standard: SMA Config, Spread %, Price Position
        df = self._add_sma_config(df)
        df = self._add_sma_spread_pct(df)
        df = self._add_price_position(df)

        # Calculate SMA momentum
        df = self._add_sma_momentum(df)

        # Calculate Volume ROC
        df = self._add_volume_roc(df)

        # Calculate Volume Delta (raw + rolling)
        df = self._add_volume_delta(df)

        # Calculate CVD Slope
        df = self._add_cvd_slope(df)

        # Calculate Health Score
        df = self._add_health_score(df)

        # Calculate Entry Qualifier Indicators
        df = self._add_candle_range(df)
        df = self._add_composite_scores(df)

        # Calculate ATR (M1 timeframe)
        df = self._add_atr_m1(df)

        return df

    # =========================================================================
    # ENTRY QUALIFIER STANDARD INDICATORS (NEW in v2)
    # =========================================================================

    def _add_sma_config(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add sma_config column: BULL, BEAR, or FLAT.

        Entry Qualifier Standard:
        - BULL = SMA9 > SMA21 (fast above slow)
        - BEAR = SMA9 < SMA21 (fast below slow)
        - FLAT = SMA9 == SMA21 (equal)

        Reference: 02_dow_ai/entry_qualifier/calculations/sma_config.py
        """
        def get_config(row):
            sma9 = row.get('sma9')
            sma21 = row.get('sma21')
            if pd.isna(sma9) or pd.isna(sma21):
                return None
            if sma9 > sma21:
                return 'BULL'
            elif sma9 < sma21:
                return 'BEAR'
            else:
                return 'FLAT'

        df['sma_config'] = df.apply(get_config, axis=1)
        return df

    def _add_sma_spread_pct(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add sma_spread_pct column: abs(sma9 - sma21) / close * 100.

        Entry Qualifier Standard:
        - Measures SMA separation as percentage of price
        - Wide spread (>= 0.15%) indicates strong trend

        Reference: 02_dow_ai/entry_qualifier/calculations/sma_config.py
        """
        def get_spread_pct(row):
            sma9 = row.get('sma9')
            sma21 = row.get('sma21')
            close = row.get('close')
            if pd.isna(sma9) or pd.isna(sma21) or pd.isna(close) or close == 0:
                return None
            return abs(sma9 - sma21) / close * 100

        df['sma_spread_pct'] = df.apply(get_spread_pct, axis=1)
        return df

    def _add_price_position(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add price_position column: ABOVE, BTWN, or BELOW.

        Entry Qualifier Standard:
        - ABOVE = price > max(sma9, sma21)
        - BELOW = price < min(sma9, sma21)
        - BTWN  = price between the two SMAs

        Reference: 02_dow_ai/entry_qualifier/calculations/sma_config.py
        """
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
    # EXISTING INDICATORS (from v1, some modified)
    # =========================================================================

    def _add_vwap(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add calculated VWAP column (cumulative daily VWAP).

        Note: If 'vwap' column already exists from API, we still recalculate
        for consistency across the entire bar sequence.
        """
        # Calculate typical price
        df['_tp'] = (df['high'] + df['low'] + df['close']) / 3

        # Calculate TPV (typical price * volume)
        df['_tpv'] = df['_tp'] * df['volume']

        # Group by bar_date and calculate cumulative sums
        df['_cum_tpv'] = df.groupby('bar_date')['_tpv'].cumsum()
        df['_cum_vol'] = df.groupby('bar_date')['volume'].cumsum()

        # Calculate VWAP
        df['vwap_calc'] = df['_cum_tpv'] / df['_cum_vol'].replace(0, np.nan)

        # Clean up temp columns
        df = df.drop(columns=['_tp', '_tpv', '_cum_tpv', '_cum_vol'])

        return df

    def _add_sma(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add SMA9, SMA21, and SMA spread columns."""
        df['sma9'] = _simple_moving_average(df['close'], SMA_FAST_PERIOD)
        df['sma21'] = _simple_moving_average(df['close'], SMA_SLOW_PERIOD)
        df['sma_spread'] = df['sma9'] - df['sma21']

        return df

    def _add_sma_momentum(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add SMA momentum ratio and label columns."""
        # Get absolute spread
        df['_abs_spread'] = df['sma_spread'].abs()

        # Calculate spread from N bars ago
        df['_prev_spread'] = df['_abs_spread'].shift(SMA_MOMENTUM_LOOKBACK)

        # Calculate ratio
        df['sma_momentum_ratio'] = df['_abs_spread'] / df['_prev_spread'].replace(0, np.nan)

        # Cap ratio to prevent database overflow (max 9999.999999 for DECIMAL(10,6))
        df['sma_momentum_ratio'] = df['sma_momentum_ratio'].clip(upper=999.0)

        # Determine momentum label
        def get_momentum_label(ratio):
            if pd.isna(ratio):
                return None
            if ratio > SMA_WIDENING_THRESHOLD:
                return 'WIDENING'
            elif ratio < 1.0 / SMA_WIDENING_THRESHOLD:
                return 'NARROWING'
            else:
                return 'STABLE'

        df['sma_momentum_label'] = df['sma_momentum_ratio'].apply(get_momentum_label)

        # Clean up temp columns
        df = df.drop(columns=['_abs_spread', '_prev_spread'])

        return df

    def _add_volume_roc(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Volume ROC column."""
        # Calculate baseline average (previous N bars, excluding current)
        df['_vol_baseline'] = df['volume'].shift(1).rolling(
            window=VOLUME_ROC_BASELINE_PERIOD,
            min_periods=VOLUME_ROC_BASELINE_PERIOD
        ).mean()

        # Calculate ROC percentage (formula from 03_indicators)
        df['vol_roc'] = ((df['volume'] - df['_vol_baseline']) / df['_vol_baseline'].replace(0, np.nan)) * 100

        # Clean up
        df = df.drop(columns=['_vol_baseline'])

        return df

    def _add_volume_delta(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add Volume Delta columns (raw single-bar + rolling sum).

        v2 change: Now produces both vol_delta_raw and vol_delta_roll
        (v1 only produced the rolling sum as vol_delta).
        """
        # Calculate bar delta for each row using centralized calculation
        df['vol_delta_raw'] = df.apply(_calculate_bar_delta, axis=1)

        # Calculate rolling sum
        df['vol_delta_roll'] = df['vol_delta_raw'].rolling(
            window=VOLUME_DELTA_ROLLING_PERIOD,
            min_periods=VOLUME_DELTA_ROLLING_PERIOD
        ).sum()

        # Keep backward-compatible vol_delta alias for health score and composite scores
        df['vol_delta'] = df['vol_delta_roll']

        return df

    def _add_cvd_slope(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add CVD Slope column."""
        # Calculate bar delta for each row using centralized calculation
        df['_bar_delta'] = df.apply(_calculate_bar_delta, axis=1)

        # Calculate cumulative volume delta
        df['_cvd'] = df['_bar_delta'].cumsum()

        # Calculate slope over window
        def rolling_slope(series):
            if len(series) < CVD_WINDOW:
                return np.nan
            return _linear_regression_slope(series.values)

        df['_cvd_slope_raw'] = df['_cvd'].rolling(
            window=CVD_WINDOW,
            min_periods=CVD_WINDOW
        ).apply(rolling_slope, raw=False)

        # Normalize by average volume for interpretability
        df['_avg_vol'] = df['volume'].rolling(window=CVD_WINDOW, min_periods=CVD_WINDOW).mean()
        df['cvd_slope'] = df['_cvd_slope_raw'] / df['_avg_vol'].replace(0, np.nan)

        # Clean up
        df = df.drop(columns=['_bar_delta', '_cvd', '_cvd_slope_raw', '_avg_vol'])

        return df

    def _add_health_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add Health Score column (0-10 scale).

        Health score is direction-agnostic - it measures the "quality" of the
        indicator readings, not whether they align with a specific direction.

        Scoring criteria (2 points each, 10 total):
        1. Volume ROC > threshold (activity)
        2. SMA momentum is WIDENING (trend strength)
        3. CVD slope magnitude > threshold (order flow conviction)
        4. SMA spread is significant (trend clarity)
        5. VWAP relationship is clear (institutional interest)
        """
        def calculate_health(row):
            score = 0

            # 1. Volume ROC (2 points for elevated volume)
            vol_roc = row.get('vol_roc')
            if pd.notna(vol_roc) and vol_roc > HEALTH_VOL_ROC_THRESHOLD:
                score += 2

            # 2. SMA Momentum (2 points for widening)
            sma_momentum = row.get('sma_momentum_label')
            if sma_momentum == 'WIDENING':
                score += 2

            # 3. CVD Slope magnitude (2 points for strong slope)
            cvd_slope = row.get('cvd_slope')
            if pd.notna(cvd_slope) and abs(cvd_slope) > 0.001:
                score += 2

            # 4. SMA Spread significance (2 points)
            sma_spread = row.get('sma_spread')
            close = row.get('close', 1)
            if pd.notna(sma_spread) and pd.notna(close) and close > 0:
                spread_pct = abs(sma_spread) / close
                if spread_pct > 0.001:  # 0.1% spread
                    score += 2

            # 5. VWAP relationship clarity (2 points)
            vwap = row.get('vwap_calc')
            if pd.notna(vwap) and pd.notna(close) and close > 0:
                vwap_distance_pct = abs(close - vwap) / close
                if vwap_distance_pct > 0.001:  # 0.1% from VWAP
                    score += 2

            return score

        df['health_score'] = df.apply(calculate_health, axis=1)

        return df

    def _add_candle_range(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add candle_range_pct column using centralized calculation.

        Formula (from 03_indicators): (high - low) / close * 100
        Used as primary skip filter for absorption zones.
        """
        # Use centralized calculation via vectorized operation
        df['candle_range_pct'] = df.apply(
            lambda row: calculate_candle_range_pct(
                float(row['high']),
                float(row['low']),
                float(row['close'])
            ),
            axis=1
        )
        return df

    def _add_composite_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add long_score and short_score columns (0-7 scale).

        Uses thresholds from centralized 03_indicators library.

        Note: H1 structure is calculated separately in calculator.py.
        The scores here are partial (max 5 without H1).
        """
        def calculate_long_score(row):
            score = 0

            # Candle Range >= threshold: +2
            candle_range = row.get('candle_range_pct')
            if pd.notna(candle_range) and candle_range >= CANDLE_RANGE_THRESHOLD:
                score += 2

            # Vol ROC >= threshold: +1
            vol_roc = row.get('vol_roc')
            if pd.notna(vol_roc) and vol_roc >= VOLUME_ROC_THRESHOLD:
                score += 1

            # High magnitude Vol Delta: +1
            vol_delta = row.get('vol_delta')
            if pd.notna(vol_delta) and abs(vol_delta) > VOLUME_DELTA_MAGNITUDE_THRESHOLD:
                score += 1

            # Wide SMA spread: +1
            sma_spread = row.get('sma_spread')
            close = row.get('close', 1)
            if pd.notna(sma_spread) and pd.notna(close) and close > 0:
                spread_pct = abs(sma_spread) / close * 100
                if spread_pct >= SMA_SPREAD_THRESHOLD:
                    score += 1

            return score

        def calculate_short_score(row):
            score = 0

            # Candle Range >= threshold: +2
            candle_range = row.get('candle_range_pct')
            if pd.notna(candle_range) and candle_range >= CANDLE_RANGE_THRESHOLD:
                score += 2

            # Vol ROC >= threshold: +1
            vol_roc = row.get('vol_roc')
            if pd.notna(vol_roc) and vol_roc >= VOLUME_ROC_THRESHOLD:
                score += 1

            # Vol Delta POSITIVE (paradox - exhausted buyers): +1
            vol_delta = row.get('vol_delta')
            if pd.notna(vol_delta) and vol_delta > 0:
                score += 1

            # SMA BULLISH (paradox - catching failed rally): +1
            sma_spread = row.get('sma_spread')
            if pd.notna(sma_spread) and sma_spread > 0:  # SMA9 > SMA21 = bullish
                score += 1

            return score

        df['long_score'] = df.apply(calculate_long_score, axis=1)
        df['short_score'] = df.apply(calculate_short_score, axis=1)

        return df

    # =========================================================================
    # ATR (AVERAGE TRUE RANGE) - M1 TIMEFRAME
    # =========================================================================

    def _add_atr_m1(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add M1 ATR column (14-period by default).

        Formula (from centralized 03_indicators library):
          True Range = max(high - low, |high - prev_close|, |low - prev_close|)
          ATR = SMA of True Range over ATR_PERIOD bars

        Uses centralized calculate_true_range for the TR calculation,
        then pandas rolling for the SMA.

        Adds column: atr_m1
        """
        # Calculate True Range for each bar
        prev_close = df['close'].shift(1)
        df['_tr'] = df.apply(
            lambda row: calculate_true_range(
                float(row['high']),
                float(row['low']),
                float(prev_close.loc[row.name]) if pd.notna(prev_close.loc[row.name]) else float(row['low'])
            ),
            axis=1
        )

        # ATR = SMA of True Range over period
        df['atr_m1'] = df['_tr'].rolling(
            window=ATR_PERIOD,
            min_periods=ATR_PERIOD
        ).mean()

        # Clean up temp columns
        df = df.drop(columns=['_tr'])

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
            health_score=self._safe_int(row.get('health_score')),
            candle_range_pct=self._safe_float(row.get('candle_range_pct')),
            long_score=self._safe_int(row.get('long_score')),
            short_score=self._safe_int(row.get('short_score')),
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
