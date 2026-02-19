"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
M1 Indicator Bars v2 - Calculator
XIII Trading LLC
================================================================================

Core calculator that computes all M1 indicator bars for a single ticker-date.
Combines M1 bar reading from m1_bars_2, indicator calculations, and structure
detection.

Key difference from v1: Reads M1 bars from m1_bars_2 database table instead
of fetching from Polygon API. No M1Fetcher needed.

Produces direction-agnostic bars for the full extended session
(prior day 16:00 ET to trade day 16:00 ET).

Version: 2.0.0
================================================================================
"""

from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Any
import logging
import pandas as pd
import numpy as np
import psycopg2

# Use explicit path imports to avoid collisions with 03_indicators modules
import importlib.util
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent

# Load local config
_config_spec = importlib.util.spec_from_file_location("local_config", _MODULE_DIR / "config.py")
_config = importlib.util.module_from_spec(_config_spec)
_config_spec.loader.exec_module(_config)
DB_CONFIG = _config.DB_CONFIG
M1_BARS_TABLE = _config.M1_BARS_TABLE
CALCULATION_VERSION = _config.CALCULATION_VERSION

# Load local indicators (already handles its own path issues)
_indicators_spec = importlib.util.spec_from_file_location("indicators", _MODULE_DIR / "indicators.py")
_indicators_mod = importlib.util.module_from_spec(_indicators_spec)
_indicators_spec.loader.exec_module(_indicators_mod)
M1IndicatorCalculator = _indicators_mod.M1IndicatorCalculator

# Load local structure
_structure_spec = importlib.util.spec_from_file_location("local_structure", _MODULE_DIR / "structure.py")
_structure_mod = importlib.util.module_from_spec(_structure_spec)
_structure_spec.loader.exec_module(_structure_mod)
StructureAnalyzer = _structure_mod.StructureAnalyzer
StructureResult = _structure_mod.StructureResult


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class M1IndicatorBarResult:
    """Complete M1 indicator bar result for database insertion."""
    # Primary Key
    ticker: str
    bar_date: date
    bar_time: time

    # OHLCV
    open: float
    high: float
    low: float
    close: float
    volume: int

    # Entry Qualifier Standard Indicators
    candle_range_pct: Optional[float]
    vol_delta_raw: Optional[float]
    vol_delta_roll: Optional[float]
    vol_delta_norm: Optional[float]
    vol_roc: Optional[float]
    sma9: Optional[float]
    sma21: Optional[float]
    sma_config: Optional[str]
    sma_spread_pct: Optional[float]
    price_position: Optional[str]

    # Extended Indicators
    vwap: Optional[float]
    sma_spread: Optional[float]
    sma_momentum_ratio: Optional[float]
    sma_momentum_label: Optional[str]
    cvd_slope: Optional[float]

    # Multi-TF Structure
    h4_structure: Optional[str]
    h1_structure: Optional[str]
    m15_structure: Optional[str]
    m5_structure: Optional[str]
    m1_structure: Optional[str]

    # Composite Scores
    health_score: Optional[int]
    long_score: Optional[int]
    short_score: Optional[int]

    # ATR (Average True Range, 14-period)
    atr_m1: Optional[float] = None
    atr_m5: Optional[float] = None
    atr_m15: Optional[float] = None

    # Metadata
    bars_in_calculation: int = 0


# =============================================================================
# MAIN CALCULATOR CLASS
# =============================================================================

class M1IndicatorBarsCalculator:
    """
    Calculates M1 indicator bars for a full trading day.

    Reads raw M1 bars from the m1_bars_2 database table (no Polygon API
    calls for M1 data), computes all indicators, and calculates
    multi-timeframe structure at each bar.

    Produces one row per 1-minute bar in the extended session
    (prior day 16:00 ET to trade day 16:00 ET).
    """

    def __init__(
        self,
        indicator_calculator: M1IndicatorCalculator = None,
        structure_analyzer: StructureAnalyzer = None,
        verbose: bool = True
    ):
        """
        Initialize the calculator.

        Args:
            indicator_calculator: M1IndicatorCalculator instance
            structure_analyzer: StructureAnalyzer instance
            verbose: Enable verbose logging
        """
        self.indicator_calculator = indicator_calculator or M1IndicatorCalculator()
        self.structure_analyzer = structure_analyzer or StructureAnalyzer()
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)

    def _log(self, message: str, level: str = 'info'):
        """Log message if verbose mode enabled."""
        if self.verbose:
            prefix = {'error': '!', 'warning': '?', 'info': ' ', 'debug': '  '}
            print(f"  {prefix.get(level, ' ')} {message}")

    def _read_m1_bars_from_db(self, ticker: str, trade_date: date) -> pd.DataFrame:
        """
        Read M1 bars from m1_bars_2 table for a given ticker-date.

        All bars stored under this bar_date are returned (prior day 16:00
        through trade day 16:00), already sorted by bar_timestamp.

        Args:
            ticker: Stock symbol
            trade_date: Trading date (bar_date in m1_bars_2)

        Returns:
            DataFrame with columns: bar_date, bar_time, open, high, low, close, volume, vwap
        """
        query = f"""
            SELECT bar_date, bar_time, open, high, low, close, volume, vwap
            FROM {M1_BARS_TABLE}
            WHERE ticker = %s AND bar_date = %s
            ORDER BY bar_timestamp ASC
        """

        conn = psycopg2.connect(**DB_CONFIG)
        try:
            df = pd.read_sql_query(query, conn, params=(ticker, trade_date))
            return df
        finally:
            conn.close()

    def calculate_for_ticker_date(
        self,
        ticker: str,
        trade_date: date
    ) -> List[M1IndicatorBarResult]:
        """
        Calculate all M1 indicator bars for a single ticker-date.

        Args:
            ticker: Stock symbol
            trade_date: Trading date

        Returns:
            List of M1IndicatorBarResult objects (one per bar)
        """
        self._log(f"Calculating M1 indicator bars for {ticker} on {trade_date}")

        # Read M1 bars from database (not Polygon API)
        df = self._read_m1_bars_from_db(ticker, trade_date)

        if df.empty:
            self._log(f"No M1 bars found in {M1_BARS_TABLE} for {ticker} on {trade_date}", 'warning')
            return []

        self._log(f"Read {len(df)} M1 bars from {M1_BARS_TABLE}")

        # Add all indicators to the DataFrame
        df = self.indicator_calculator.add_all_indicators(df)

        self._log(f"Processing {len(df)} bars with indicators")

        # Calculate structure and build results for each bar
        results = []

        for idx, (df_idx, row) in enumerate(df.iterrows()):
            bar_time = row['bar_time']

            # Get structure at this bar time
            structures = self.structure_analyzer.get_all_structures(
                ticker=ticker,
                trade_date=trade_date,
                bar_time=bar_time
            )

            # Calculate HTF ATR (reuses cached bars from structure detection)
            atr_m5 = self._calculate_htf_atr(ticker, trade_date, bar_time, 'M5')
            atr_m15 = self._calculate_htf_atr(ticker, trade_date, bar_time, 'M15')

            # Build result
            result = M1IndicatorBarResult(
                ticker=ticker,
                bar_date=trade_date,
                bar_time=bar_time,

                # OHLCV
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=int(row['volume']),

                # Entry Qualifier Standard Indicators
                candle_range_pct=self._safe_float(row.get('candle_range_pct')),
                vol_delta_raw=self._safe_float(row.get('vol_delta_raw')),
                vol_delta_roll=self._safe_float(row.get('vol_delta_roll')),
                vol_delta_norm=self._safe_float(row.get('vol_delta_norm')),
                vol_roc=self._safe_float(row.get('vol_roc')),
                sma9=self._safe_float(row.get('sma9')),
                sma21=self._safe_float(row.get('sma21')),
                sma_config=row.get('sma_config'),
                sma_spread_pct=self._safe_float(row.get('sma_spread_pct')),
                price_position=row.get('price_position'),

                # Extended Indicators
                vwap=self._safe_float(row.get('vwap_calc')),
                sma_spread=self._safe_float(row.get('sma_spread')),
                sma_momentum_ratio=self._safe_float(row.get('sma_momentum_ratio')),
                sma_momentum_label=row.get('sma_momentum_label'),
                cvd_slope=self._safe_float(row.get('cvd_slope')),

                # Structure
                h4_structure=structures['H4'].direction_label if structures.get('H4') else None,
                h1_structure=structures['H1'].direction_label if structures.get('H1') else None,
                m15_structure=structures['M15'].direction_label if structures.get('M15') else None,
                m5_structure=structures['M5'].direction_label if structures.get('M5') else None,
                m1_structure=structures['M1'].direction_label if structures.get('M1') else None,

                # Composite Scores
                health_score=self._safe_int(row.get('health_score')),
                long_score=self._safe_int(row.get('long_score')),
                short_score=self._safe_int(row.get('short_score')),

                # ATR (Average True Range, 14-period)
                atr_m1=self._safe_float(row.get('atr_m1')),
                atr_m5=self._safe_float(atr_m5),
                atr_m15=self._safe_float(atr_m15),

                # Metadata
                bars_in_calculation=idx + 1
            )

            results.append(result)

        self._log(f"Calculated {len(results)} M1 indicator bars")

        return results

    def _calculate_htf_atr(
        self,
        ticker: str,
        trade_date: date,
        bar_time: time,
        timeframe: str,
        period: int = 14
    ) -> Optional[float]:
        """
        Calculate ATR for a higher timeframe at a specific bar time.

        Reuses bars already cached by HTFBarFetcher (from structure detection),
        so no additional Polygon API calls are needed.

        Args:
            ticker: Stock symbol
            trade_date: Trading date
            bar_time: Current bar time (filter HTF bars up to this point)
            timeframe: 'M5' or 'M15'
            period: ATR period (default 14)

        Returns:
            ATR value or None if insufficient data
        """
        try:
            bars = self.structure_analyzer.fetcher.fetch_bars(
                ticker, timeframe, trade_date, bar_time
            )

            if len(bars) < period + 1:
                return None

            # Calculate True Range for each bar (need prev close)
            true_ranges = []
            for i in range(1, len(bars)):
                high = float(bars[i]['high'])
                low = float(bars[i]['low'])
                prev_close = float(bars[i - 1]['close'])
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                true_ranges.append(tr)

            # ATR = SMA of last `period` true ranges
            if len(true_ranges) < period:
                return None

            return sum(true_ranges[-period:]) / period

        except Exception:
            return None

    def _safe_float(self, value) -> Optional[float]:
        """Convert value to float, returning None for NaN."""
        if value is None:
            return None
        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
            return None
        try:
            return round(float(value), 6)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value) -> Optional[int]:
        """Convert value to int, returning None for NaN."""
        if value is None:
            return None
        if isinstance(value, float) and np.isnan(value):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def clear_caches(self):
        """Clear all internal caches."""
        self.structure_analyzer.clear_cache()
