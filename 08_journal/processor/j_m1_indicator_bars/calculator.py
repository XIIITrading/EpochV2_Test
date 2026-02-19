"""
================================================================================
EPOCH TRADING SYSTEM - JOURNAL PROCESSOR 2
j_m1_indicator_bars - Calculator & Populator
XIII Trading LLC
================================================================================

Calculates all M1 indicator bars and populates j_m1_indicator_bars.

Key imports:
  - Indicators: shared.indicators (canonical per SWH-6)
  - M1IndicatorCalculator: 03_backtest (uses shared.indicators internally)
  - StructureAnalyzer: 03_backtest (HTF API/DB fetcher + fractal BOS/ChoCH)
  - HTF structure from M1: shared.indicators.structure (canonical fractal)

Key difference from backtest: Reads from j_m1_bars (not m1_bars_2) and
journal_trades (not trades_2). Writes to j_m1_indicator_bars.

Version: 2.0.0 (SWH-6 migration)
================================================================================
"""

import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from datetime import datetime, date, time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging
import pandas as pd
import numpy as np

import sys
from pathlib import Path

# Import shared config
_PROC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROC_DIR))
from db_config import (
    DB_CONFIG, SOURCE_TABLE, J_M1_BARS_TABLE, J_M1_INDICATOR_BARS_TABLE,
    BATCH_INSERT_SIZE, VERBOSE, JOURNAL_SYMBOL_COL, JOURNAL_DATE_COL,
    POLYGON_API_KEY, ATR_PERIOD,
)

# =============================================================================
# IMPORT FROM SHARED INDICATORS (canonical per SWH-6)
# =============================================================================

from shared.indicators.config import CONFIG
from shared.indicators.core.atr import calculate_true_range
from shared.indicators.structure import calculate_structure_from_bars

# =============================================================================
# IMPORT FROM BACKTEST (M1IndicatorCalculator + StructureAnalyzer)
# M1IndicatorCalculator now imports from shared.indicators internally.
# StructureAnalyzer handles HTF API/DB fetching + BOS/ChoCH detection.
# =============================================================================

_BACKTEST_DIR = Path(__file__).resolve().parent.parent.parent.parent / "03_backtest" / "processor" / "secondary_analysis" / "m1_indicator_bars_2"

import importlib.util

# Load indicators module from backtest (now uses shared.indicators)
_indicators_spec = importlib.util.spec_from_file_location("bt_indicators", _BACKTEST_DIR / "indicators.py")
_indicators_mod = importlib.util.module_from_spec(_indicators_spec)
_indicators_spec.loader.exec_module(_indicators_mod)
M1IndicatorCalculator = _indicators_mod.M1IndicatorCalculator

# Load structure module from backtest (HTF fetcher + BOS/ChoCH analyzer)
_structure_spec = importlib.util.spec_from_file_location("bt_structure", _BACKTEST_DIR / "structure.py")
_structure_mod = importlib.util.module_from_spec(_structure_spec)
_structure_spec.loader.exec_module(_structure_mod)
StructureAnalyzer = _structure_mod.StructureAnalyzer
StructureResult = _structure_mod.StructureResult
STRUCTURE_LABELS = _structure_mod.STRUCTURE_LABELS


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class M1IndicatorBarResult:
    """Complete M1 indicator bar result for database insertion."""
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

    # Composite Scores (DEPRECATED per SWH-6 - always NULL)
    health_score: Optional[int]
    long_score: Optional[int]
    short_score: Optional[int]

    # ATR
    atr_m1: Optional[float] = None
    atr_m5: Optional[float] = None
    atr_m15: Optional[float] = None

    # Metadata
    bars_in_calculation: int = 0


# =============================================================================
# CALCULATOR
# =============================================================================

class JM1IndicatorBarsCalculator:
    """
    Calculates M1 indicator bars for a full trading day.
    Reads raw bars from j_m1_bars, computes indicators, and detects structure.
    """

    def __init__(
        self,
        indicator_calculator: M1IndicatorCalculator = None,
        structure_analyzer: StructureAnalyzer = None,
        verbose: bool = True
    ):
        self.indicator_calculator = indicator_calculator or M1IndicatorCalculator()
        self.structure_analyzer = structure_analyzer or StructureAnalyzer()
        self.verbose = verbose

    def _log(self, message: str, level: str = 'info'):
        if self.verbose:
            prefix = {'error': '!', 'warning': '?', 'info': ' ', 'debug': '  '}
            print(f"  {prefix.get(level, ' ')} {message}")

    def _read_m1_bars_from_db(self, ticker: str, trade_date: date) -> pd.DataFrame:
        """Read M1 bars from j_m1_bars for a given ticker-date."""
        query = f"""
            SELECT bar_date, bar_time, open, high, low, close, volume, vwap
            FROM {J_M1_BARS_TABLE}
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
        self, ticker: str, trade_date: date
    ) -> List[M1IndicatorBarResult]:
        """Calculate all M1 indicator bars for a single ticker-date."""
        self._log(f"Calculating M1 indicator bars for {ticker} on {trade_date}")

        df = self._read_m1_bars_from_db(ticker, trade_date)

        if df.empty:
            self._log(f"No M1 bars found for {ticker} on {trade_date}", 'warning')
            return []

        self._log(f"Read {len(df)} M1 bars from {J_M1_BARS_TABLE}")

        # Pre-compute M5 and M15 ATR from M1 bars (avoids Polygon API + timezone issues)
        atr_period = CONFIG.atr.period
        m5_atr_map = self._compute_htf_atr_from_m1(df, 5, atr_period)
        m15_atr_map = self._compute_htf_atr_from_m1(df, 15, atr_period)
        m5_count = sum(1 for v in m5_atr_map.values() if v is not None)
        m15_count = sum(1 for v in m15_atr_map.values() if v is not None)
        self._log(f"Pre-computed HTF ATR from M1 bars: M5={m5_count} non-null, M15={m15_count} non-null")

        # Pre-compute M5 and M15 structure from M1 bars using shared canonical fractal
        m5_structure_map = self._compute_htf_structure_from_m1(df, 5)
        m15_structure_map = self._compute_htf_structure_from_m1(df, 15)
        self._log(f"Pre-computed HTF structure from M1 bars: "
                  f"M5={sum(1 for v in m5_structure_map.values() if v != 'NEUTRAL')} non-neutral, "
                  f"M15={sum(1 for v in m15_structure_map.values() if v != 'NEUTRAL')} non-neutral")

        # Add all indicators using shared canonical calculations
        df = self.indicator_calculator.add_all_indicators(df)

        self._log(f"Processing {len(df)} bars with indicators")

        results = []
        for idx, (df_idx, row) in enumerate(df.iterrows()):
            bar_time = row['bar_time']

            # Get structure at this bar time (H4, H1, M1 via backtest StructureAnalyzer)
            structures = self.structure_analyzer.get_all_structures(
                ticker=ticker,
                trade_date=trade_date,
                bar_time=bar_time
            )

            # Override M5 and M15 structure with locally-computed values
            m5_struct_label = m5_structure_map.get(idx, 'NEUTRAL')
            m15_struct_label = m15_structure_map.get(idx, 'NEUTRAL')

            # Look up pre-computed HTF ATR
            atr_m5 = m5_atr_map.get(idx)
            atr_m15 = m15_atr_map.get(idx)

            result = M1IndicatorBarResult(
                ticker=ticker,
                bar_date=trade_date,
                bar_time=bar_time,

                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=int(row['volume']),

                candle_range_pct=self._safe_float(row.get('candle_range_pct')),
                vol_delta_raw=self._safe_float(row.get('vol_delta_raw')),
                vol_delta_roll=self._safe_float(row.get('vol_delta_roll')),
                vol_roc=self._safe_float(row.get('vol_roc')),
                sma9=self._safe_float(row.get('sma9')),
                sma21=self._safe_float(row.get('sma21')),
                sma_config=row.get('sma_config'),
                sma_spread_pct=self._safe_float(row.get('sma_spread_pct')),
                price_position=row.get('price_position'),

                vwap=self._safe_float(row.get('vwap_calc')),
                sma_spread=self._safe_float(row.get('sma_spread')),
                sma_momentum_ratio=self._safe_float(row.get('sma_momentum_ratio')),
                sma_momentum_label=row.get('sma_momentum_label'),
                cvd_slope=self._safe_float(row.get('cvd_slope')),

                h4_structure=structures['H4'].direction_label if structures.get('H4') else None,
                h1_structure=structures['H1'].direction_label if structures.get('H1') else None,
                m15_structure=m15_struct_label,
                m5_structure=m5_struct_label,
                m1_structure=structures['M1'].direction_label if structures.get('M1') else None,

                health_score=None,   # DEPRECATED per SWH-6
                long_score=None,     # DEPRECATED per SWH-6
                short_score=None,    # DEPRECATED per SWH-6

                atr_m1=self._safe_float(row.get('atr_m1')),
                atr_m5=self._safe_float(atr_m5),
                atr_m15=self._safe_float(atr_m15),

                bars_in_calculation=idx + 1
            )

            results.append(result)

        self._log(f"Calculated {len(results)} M1 indicator bars")
        return results

    def _compute_htf_atr_from_m1(
        self, df: pd.DataFrame, htf_minutes: int, period: int = 14
    ) -> Dict[int, Optional[float]]:
        """
        Compute higher-timeframe ATR by aggregating M1 bars into HTF candles.

        Uses shared.indicators.core.atr.calculate_true_range for TR calculation.

        Args:
            df: M1 bars DataFrame with open, high, low, close columns
            htf_minutes: HTF candle size in minutes (5 for M5, 15 for M15)
            period: ATR period (default from CONFIG)

        Returns:
            Dict mapping M1 bar index -> ATR value (or None if insufficient data)
        """
        atr_map = {}

        if df.empty:
            return atr_map

        # Build HTF candles by grouping M1 bars into htf_minutes buckets
        m1_highs = df['high'].astype(float).values
        m1_lows = df['low'].astype(float).values
        m1_closes = df['close'].astype(float).values
        m1_opens = df['open'].astype(float).values

        # Convert bar_time to total minutes for grouping
        bar_times = df['bar_time'].values
        minutes_list = []
        for bt in bar_times:
            if hasattr(bt, 'hour'):
                total_min = bt.hour * 60 + bt.minute
            else:
                total_seconds = int(bt.total_seconds()) if hasattr(bt, 'total_seconds') else 0
                total_min = total_seconds // 60
            minutes_list.append(total_min)

        # Group M1 bars into HTF candles
        htf_candles = []
        htf_bar_end_indices = []

        current_bucket = None
        bucket_high = bucket_low = bucket_open = bucket_close = None

        for i in range(len(df)):
            bucket = minutes_list[i] // htf_minutes

            if bucket != current_bucket:
                if current_bucket is not None:
                    htf_candles.append((bucket_open, bucket_high, bucket_low, bucket_close))
                    htf_bar_end_indices.append(i - 1)

                current_bucket = bucket
                bucket_open = m1_opens[i]
                bucket_high = m1_highs[i]
                bucket_low = m1_lows[i]
                bucket_close = m1_closes[i]
            else:
                bucket_high = max(bucket_high, m1_highs[i])
                bucket_low = min(bucket_low, m1_lows[i])
                bucket_close = m1_closes[i]

        # Last candle
        if current_bucket is not None:
            htf_candles.append((bucket_open, bucket_high, bucket_low, bucket_close))
            htf_bar_end_indices.append(len(df) - 1)

        # Compute true range for each HTF candle using shared canonical function
        true_ranges = []
        for j in range(len(htf_candles)):
            o, h, l, c = htf_candles[j]
            if j == 0:
                tr = h - l  # No previous close for the first candle
            else:
                prev_c = htf_candles[j - 1][3]
                tr = calculate_true_range(h, l, prev_c)
            true_ranges.append(tr)

        # Build ATR values: for each HTF candle, ATR = SMA of last `period` TRs
        htf_atrs = []
        for j in range(len(true_ranges)):
            if j + 1 < period:
                htf_atrs.append(None)
            else:
                atr_val = sum(true_ranges[j - period + 1: j + 1]) / period
                htf_atrs.append(atr_val)

        # Map each M1 bar index to the ATR of the most recently COMPLETED HTF candle
        for i in range(len(df)):
            completed_htf = -1
            for j in range(len(htf_bar_end_indices)):
                if htf_bar_end_indices[j] < i:
                    completed_htf = j
                else:
                    break

            if completed_htf >= 0 and htf_atrs[completed_htf] is not None:
                atr_map[i] = round(htf_atrs[completed_htf], 6)
            else:
                atr_map[i] = None

        return atr_map

    def _compute_htf_structure_from_m1(
        self, df: pd.DataFrame, htf_minutes: int
    ) -> Dict[int, str]:
        """
        Compute higher-timeframe market structure by aggregating M1 bars into
        HTF candles and running the canonical fractal-based structure detector.

        Uses shared.indicators.structure.calculate_structure_from_bars (SWH-6).

        Args:
            df: M1 bars DataFrame with open, high, low, close columns
            htf_minutes: HTF candle size in minutes (5 for M5, 15 for M15)

        Returns:
            Dict mapping M1 bar index -> structure label ('BULL', 'BEAR', 'NEUTRAL')
        """
        structure_map = {}

        if df.empty:
            return structure_map

        m1_highs = df['high'].astype(float).values
        m1_lows = df['low'].astype(float).values
        m1_closes = df['close'].astype(float).values
        m1_opens = df['open'].astype(float).values

        # Convert bar_time to total minutes for grouping
        bar_times = df['bar_time'].values
        minutes_list = []
        for bt in bar_times:
            if hasattr(bt, 'hour'):
                total_min = bt.hour * 60 + bt.minute
            else:
                total_seconds = int(bt.total_seconds()) if hasattr(bt, 'total_seconds') else 0
                total_min = total_seconds // 60
            minutes_list.append(total_min)

        # Build HTF candles by time bucket
        htf_candles = []
        htf_bar_end_indices = []

        current_bucket = None
        bucket_high = bucket_low = bucket_open = bucket_close = None

        for i in range(len(df)):
            bucket = minutes_list[i] // htf_minutes

            if bucket != current_bucket:
                if current_bucket is not None:
                    htf_candles.append({
                        'open': bucket_open, 'high': bucket_high,
                        'low': bucket_low, 'close': bucket_close,
                    })
                    htf_bar_end_indices.append(i - 1)

                current_bucket = bucket
                bucket_open = m1_opens[i]
                bucket_high = m1_highs[i]
                bucket_low = m1_lows[i]
                bucket_close = m1_closes[i]
            else:
                bucket_high = max(bucket_high, m1_highs[i])
                bucket_low = min(bucket_low, m1_lows[i])
                bucket_close = m1_closes[i]

        # Last candle
        if current_bucket is not None:
            htf_candles.append({
                'open': bucket_open, 'high': bucket_high,
                'low': bucket_low, 'close': bucket_close,
            })
            htf_bar_end_indices.append(len(df) - 1)

        # Use canonical shared fractal structure detector
        fractal_length = CONFIG.structure.fractal_length

        # For each M1 bar, compute structure from completed HTF candles
        # Cache structure results to avoid redundant recalculation
        last_completed = -1
        last_structure_label = 'NEUTRAL'

        for i in range(len(df)):
            completed_htf = -1
            for j in range(len(htf_bar_end_indices)):
                if htf_bar_end_indices[j] < i:
                    completed_htf = j
                else:
                    break

            if completed_htf < 0:
                structure_map[i] = 'NEUTRAL'
                continue

            # Only recalculate if we have a new completed candle
            if completed_htf != last_completed:
                last_completed = completed_htf
                bars_for_structure = htf_candles[:completed_htf + 1]
                result = calculate_structure_from_bars(
                    bars_for_structure, length=fractal_length
                )
                last_structure_label = result.label

            structure_map[i] = last_structure_label

        return structure_map

    def _safe_float(self, value) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
            return None
        try:
            return round(float(value), 6)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, float) and np.isnan(value):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def clear_caches(self):
        self.structure_analyzer.clear_cache()


# =============================================================================
# POPULATOR
# =============================================================================

class JM1IndicatorBarsPopulator:
    """Populates j_m1_indicator_bars from journal_trades + j_m1_bars."""

    def __init__(self, verbose: bool = None):
        self.verbose = verbose if verbose is not None else VERBOSE
        self.stats = {
            'ticker_dates_processed': 0,
            'ticker_dates_skipped': 0,
            'bars_inserted': 0,
            'api_calls_made': 0,
            'errors': []
        }

    def _log(self, message: str, level: str = 'info'):
        if self.verbose or level in ('error', 'warning'):
            prefix = {'error': '!', 'warning': '?', 'info': ' ', 'debug': '  '}
            print(f"  {prefix.get(level, ' ')} {message}")

    def _convert_numpy(self, value):
        if isinstance(value, np.bool_):
            return bool(value)
        elif isinstance(value, np.integer):
            return int(value)
        elif isinstance(value, np.floating):
            return float(value) if not np.isnan(value) else None
        elif isinstance(value, np.ndarray):
            return value.tolist()
        return value

    def get_ticker_dates_needing_calculation(self, conn, limit: int = None) -> List[Dict[str, Any]]:
        """Get journal (symbol, trade_date) pairs needing indicator calculation."""
        query = f"""
            WITH unique_ticker_dates AS (
                SELECT DISTINCT {JOURNAL_SYMBOL_COL} AS ticker, {JOURNAL_DATE_COL} AS date
                FROM {SOURCE_TABLE}
                WHERE {JOURNAL_DATE_COL} IS NOT NULL
                  AND {JOURNAL_SYMBOL_COL} IS NOT NULL
            ),
            has_m1_bars AS (
                SELECT DISTINCT ticker, bar_date AS date
                FROM {J_M1_BARS_TABLE}
            ),
            existing_indicator_bars AS (
                SELECT DISTINCT ticker, bar_date AS date
                FROM {J_M1_INDICATOR_BARS_TABLE}
            )
            SELECT u.ticker, u.date
            FROM unique_ticker_dates u
            INNER JOIN has_m1_bars m
                ON u.ticker = m.ticker AND u.date = m.date
            LEFT JOIN existing_indicator_bars e
                ON u.ticker = e.ticker AND u.date = e.date
            WHERE e.ticker IS NULL
            ORDER BY u.date DESC, u.ticker
        """

        if limit:
            query += f" LIMIT {limit}"

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()

        return [dict(row) for row in rows]

    def insert_results(self, conn, results: List[M1IndicatorBarResult]) -> int:
        """Insert calculation results into j_m1_indicator_bars."""
        if not results:
            return 0

        query = f"""
            INSERT INTO {J_M1_INDICATOR_BARS_TABLE} (
                ticker, bar_date, bar_time,
                open, high, low, close, volume,
                candle_range_pct, vol_delta_raw, vol_delta_roll, vol_roc,
                sma9, sma21, sma_config, sma_spread_pct, price_position,
                vwap, sma_spread, sma_momentum_ratio, sma_momentum_label, cvd_slope,
                h4_structure, h1_structure, m15_structure, m5_structure, m1_structure,
                health_score, long_score, short_score,
                atr_m1, atr_m5, atr_m15,
                bars_in_calculation
            ) VALUES %s
            ON CONFLICT (ticker, bar_date, bar_time) DO NOTHING
        """

        values = []
        for r in results:
            row = (
                r.ticker, r.bar_date, r.bar_time,
                self._convert_numpy(r.open),
                self._convert_numpy(r.high),
                self._convert_numpy(r.low),
                self._convert_numpy(r.close),
                self._convert_numpy(r.volume),
                self._convert_numpy(r.candle_range_pct),
                self._convert_numpy(r.vol_delta_raw),
                self._convert_numpy(r.vol_delta_roll),
                self._convert_numpy(r.vol_roc),
                self._convert_numpy(r.sma9),
                self._convert_numpy(r.sma21),
                r.sma_config,
                self._convert_numpy(r.sma_spread_pct),
                r.price_position,
                self._convert_numpy(r.vwap),
                self._convert_numpy(r.sma_spread),
                self._convert_numpy(r.sma_momentum_ratio),
                r.sma_momentum_label,
                self._convert_numpy(r.cvd_slope),
                r.h4_structure, r.h1_structure, r.m15_structure,
                r.m5_structure, r.m1_structure,
                self._convert_numpy(r.health_score),
                self._convert_numpy(r.long_score),
                self._convert_numpy(r.short_score),
                self._convert_numpy(r.atr_m1),
                self._convert_numpy(r.atr_m5),
                self._convert_numpy(r.atr_m15),
                self._convert_numpy(r.bars_in_calculation)
            )
            values.append(row)

        with conn.cursor() as cur:
            execute_values(cur, query, values, page_size=BATCH_INSERT_SIZE)

        return len(values)

    def get_status(self, conn) -> Dict[str, Any]:
        """Get current table status."""
        status = {}
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {J_M1_INDICATOR_BARS_TABLE}")
            status['total_bars'] = cur.fetchone()[0]

            cur.execute(f"SELECT COUNT(DISTINCT (ticker, bar_date)) FROM {J_M1_INDICATOR_BARS_TABLE}")
            status['unique_ticker_dates'] = cur.fetchone()[0]

            cur.execute(f"SELECT MIN(bar_date), MAX(bar_date) FROM {J_M1_INDICATOR_BARS_TABLE}")
            row = cur.fetchone()
            status['min_date'] = row[0]
            status['max_date'] = row[1]

        pending = self.get_ticker_dates_needing_calculation(conn)
        status['pending_ticker_dates'] = len(pending)
        return status

    def run_batch_population(
        self, limit: int = None, dry_run: bool = False, callback=None
    ) -> Dict[str, Any]:
        """Main entry point for batch processing."""
        start_time = datetime.now()

        self.stats = {
            'ticker_dates_processed': 0,
            'ticker_dates_skipped': 0,
            'bars_inserted': 0,
            'api_calls_made': 0,
            'errors': []
        }

        def _emit(msg):
            print(msg)
            if callback:
                callback(msg)

        _emit("=" * 60)
        _emit("Journal M1 Indicator Bars Populator v2.0 (SWH-6)")
        _emit("=" * 60)
        _emit(f"Source: {SOURCE_TABLE} + {J_M1_BARS_TABLE}")
        _emit(f"Target: {J_M1_INDICATOR_BARS_TABLE}")
        _emit(f"Dry Run: {dry_run}")
        if limit:
            _emit(f"Limit: {limit} ticker-dates")
        _emit("")

        conn = None
        calculator = None

        try:
            _emit("[1/4] Connecting to Supabase...")
            conn = psycopg2.connect(**DB_CONFIG)
            _emit("  Connected successfully")

            _emit("\n[2/4] Querying ticker-dates needing calculation...")
            ticker_dates = self.get_ticker_dates_needing_calculation(conn, limit)
            _emit(f"  Found {len(ticker_dates)} ticker-dates to process")

            if not ticker_dates:
                _emit("\n  No ticker-dates need calculation. Exiting.")
                return self._build_result(start_time)

            _emit("\n[3/4] Initializing calculator...")
            calculator = JM1IndicatorBarsCalculator(verbose=False)
            _emit("  Calculator ready")

            _emit("\n[4/4] Processing ticker-dates...")
            total = len(ticker_dates)

            for i, td in enumerate(ticker_dates, 1):
                ticker = td['ticker']
                trade_date = td['date']

                try:
                    results = calculator.calculate_for_ticker_date(ticker, trade_date)

                    if results:
                        self.stats['ticker_dates_processed'] += 1
                        if dry_run:
                            _emit(f"  [{i}/{total}] {ticker} {trade_date}: [DRY-RUN] {len(results)} bars")
                        else:
                            inserted = self.insert_results(conn, results)
                            conn.commit()
                            self.stats['bars_inserted'] += inserted
                            _emit(f"  [{i}/{total}] {ticker} {trade_date}: {inserted} bars")
                    else:
                        self.stats['ticker_dates_skipped'] += 1

                except Exception as e:
                    conn.rollback()
                    self.stats['ticker_dates_skipped'] += 1
                    self.stats['errors'].append(f"{ticker} {trade_date}: {str(e)}")
                    _emit(f"  [{i}/{total}] {ticker} {trade_date}: ERROR - {e}")

                calculator.clear_caches()

            return self._build_result(start_time)

        except Exception as e:
            self.stats['errors'].append(f"Fatal: {str(e)}")
            if conn:
                conn.rollback()
            raise

        finally:
            if calculator:
                calculator.clear_caches()
            if conn:
                conn.close()

    def _build_result(self, start_time: datetime) -> Dict[str, Any]:
        elapsed = (datetime.now() - start_time).total_seconds()
        self.stats['execution_time_seconds'] = round(elapsed, 2)
        return self.stats
