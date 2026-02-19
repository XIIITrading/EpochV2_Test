"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
M1 Indicator Bars v2 - Database Populator
XIII Trading LLC
================================================================================

Batch populator that calculates M1 indicator bars for all unique ticker+dates
from the trades_2 table and writes results to the m1_indicator_bars_2 table.

Key Features:
- Queries trades_2 for unique (ticker, date) pairs
- INNER JOIN on m1_bars_2 to ensure raw data exists
- LEFT JOIN to m1_indicator_bars_2 to find pairs not yet calculated
- Batch insert with ON CONFLICT handling
- Incremental updates (only processes missing pairs)

Version: 2.0.0
================================================================================
"""

import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from datetime import datetime, date, time
from typing import Dict, List, Any, Optional
import logging
import numpy as np

# Use explicit path imports to avoid collisions with 03_indicators modules
import importlib.util
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent

# Load local config
_config_spec = importlib.util.spec_from_file_location("local_config", _MODULE_DIR / "config.py")
_config = importlib.util.module_from_spec(_config_spec)
_config_spec.loader.exec_module(_config)
DB_CONFIG = _config.DB_CONFIG
SOURCE_TABLE = _config.SOURCE_TABLE
M1_BARS_TABLE = _config.M1_BARS_TABLE
TARGET_TABLE = _config.TARGET_TABLE
BATCH_INSERT_SIZE = _config.BATCH_INSERT_SIZE
VERBOSE = _config.VERBOSE

# Load local calculator
_calc_spec = importlib.util.spec_from_file_location("calculator", _MODULE_DIR / "calculator.py")
_calc_mod = importlib.util.module_from_spec(_calc_spec)
_calc_spec.loader.exec_module(_calc_mod)
M1IndicatorBarsCalculator = _calc_mod.M1IndicatorBarsCalculator
M1IndicatorBarResult = _calc_mod.M1IndicatorBarResult


class M1IndicatorBarsPopulator:
    """
    Populates the m1_indicator_bars_2 table from unique ticker+dates in trades_2.

    Workflow:
    1. Query trades_2 for unique (ticker, date) pairs
    2. INNER JOIN on m1_bars_2 to ensure raw data is available
    3. LEFT JOIN to m1_indicator_bars_2 to find missing pairs
    4. For each missing pair, calculate all M1 indicator bars
    5. Batch insert results
    """

    def __init__(self, verbose: bool = None):
        """
        Initialize the populator.

        Args:
            verbose: Enable verbose logging (defaults to config)
        """
        self.verbose = verbose if verbose is not None else VERBOSE
        self.logger = logging.getLogger(__name__)

        # Statistics
        self.stats = {
            'ticker_dates_processed': 0,
            'ticker_dates_skipped': 0,
            'bars_inserted': 0,
            'api_calls_made': 0,
            'errors': []
        }

    def _log(self, message: str, level: str = 'info'):
        """Log message if verbose."""
        if self.verbose or level in ('error', 'warning'):
            prefix = {'error': '!', 'warning': '?', 'info': ' ', 'debug': '  '}
            print(f"  {prefix.get(level, ' ')} {message}")

    def _convert_numpy(self, value):
        """Convert numpy types to Python native types for database insertion."""
        if isinstance(value, np.bool_):
            return bool(value)
        elif isinstance(value, np.integer):
            return int(value)
        elif isinstance(value, np.floating):
            return float(value) if not np.isnan(value) else None
        elif isinstance(value, np.ndarray):
            return value.tolist()
        return value

    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================

    def get_ticker_dates_needing_calculation(
        self,
        conn,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """
        Get unique (ticker, date) pairs that need M1 indicator bar calculation.

        Uses INNER JOIN on m1_bars_2 to ensure raw data is available,
        and LEFT JOIN on m1_indicator_bars_2 to find missing pairs.

        Args:
            conn: Database connection
            limit: Maximum number of ticker-dates to return

        Returns:
            List of dicts with 'ticker' and 'date' keys
        """
        query = f"""
            WITH unique_ticker_dates AS (
                SELECT DISTINCT ticker, date
                FROM {SOURCE_TABLE}
                WHERE date IS NOT NULL
                  AND ticker IS NOT NULL
            ),
            has_m1_bars AS (
                SELECT DISTINCT ticker, bar_date as date
                FROM {M1_BARS_TABLE}
            ),
            existing_indicator_bars AS (
                SELECT DISTINCT ticker, bar_date as date
                FROM {TARGET_TABLE}
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

    def insert_results(
        self,
        conn,
        results: List[M1IndicatorBarResult]
    ) -> int:
        """
        Insert calculation results into m1_indicator_bars_2 table.

        Args:
            conn: Database connection
            results: List of M1IndicatorBarResult objects

        Returns:
            Number of records inserted
        """
        if not results:
            return 0

        query = f"""
            INSERT INTO {TARGET_TABLE} (
                ticker, bar_date, bar_time,
                open, high, low, close, volume,
                candle_range_pct, vol_delta_raw, vol_delta_roll, vol_delta_norm, vol_roc,
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
                r.ticker,
                r.bar_date,
                r.bar_time,
                self._convert_numpy(r.open),
                self._convert_numpy(r.high),
                self._convert_numpy(r.low),
                self._convert_numpy(r.close),
                self._convert_numpy(r.volume),
                self._convert_numpy(r.candle_range_pct),
                self._convert_numpy(r.vol_delta_raw),
                self._convert_numpy(r.vol_delta_roll),
                self._convert_numpy(r.vol_delta_norm),
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
                r.h4_structure,
                r.h1_structure,
                r.m15_structure,
                r.m5_structure,
                r.m1_structure,
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
        """
        Get current status of m1_indicator_bars_2 table.

        Args:
            conn: Database connection

        Returns:
            Status dictionary
        """
        status = {}

        # Count total bars
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {TARGET_TABLE}")
            status['total_bars'] = cur.fetchone()[0]

        # Count unique ticker-dates
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(DISTINCT (ticker, bar_date)) FROM {TARGET_TABLE}")
            status['unique_ticker_dates'] = cur.fetchone()[0]

        # Count unique tickers
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(DISTINCT ticker) FROM {TARGET_TABLE}")
            status['unique_tickers'] = cur.fetchone()[0]

        # Get date range
        with conn.cursor() as cur:
            cur.execute(f"SELECT MIN(bar_date), MAX(bar_date) FROM {TARGET_TABLE}")
            row = cur.fetchone()
            status['min_date'] = row[0]
            status['max_date'] = row[1]

        # Count pending
        pending = self.get_ticker_dates_needing_calculation(conn)
        status['pending_ticker_dates'] = len(pending)

        return status

    # =========================================================================
    # BATCH PROCESSING
    # =========================================================================

    def run_batch_population(
        self,
        limit: int = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Main entry point. Process all ticker-dates needing M1 indicator bar calculation.

        Args:
            limit: Max ticker-dates to process
            dry_run: If True, calculate but don't write to DB

        Returns:
            Dictionary with execution statistics
        """
        start_time = datetime.now()

        print("=" * 60)
        print("M1 Indicator Bars v2 Populator")
        print("=" * 60)
        print(f"Source Table: {SOURCE_TABLE}")
        print(f"M1 Bars Table: {M1_BARS_TABLE}")
        print(f"Target Table: {TARGET_TABLE}")
        print(f"Dry Run: {dry_run}")
        if limit:
            print(f"Limit: {limit} ticker-dates")
        print()

        # Reset statistics
        self.stats = {
            'ticker_dates_processed': 0,
            'ticker_dates_skipped': 0,
            'bars_inserted': 0,
            'api_calls_made': 0,
            'errors': []
        }

        conn = None
        calculator = None

        try:
            # Connect to database
            print("[1/4] Connecting to Supabase...")
            conn = psycopg2.connect(**DB_CONFIG)
            print("  Connected successfully")

            # Get ticker-dates needing calculation
            print("\n[2/4] Querying ticker-dates needing M1 indicator calculation...")
            ticker_dates = self.get_ticker_dates_needing_calculation(conn, limit)
            print(f"  Found {len(ticker_dates)} ticker-dates to process")

            if not ticker_dates:
                print("\n  No ticker-dates need calculation. Exiting.")
                return self._build_result(start_time)

            # Initialize calculator
            print("\n[3/4] Initializing calculator...")
            calculator = M1IndicatorBarsCalculator(verbose=False)
            print("  Calculator ready")

            # Process each ticker-date
            print("\n[4/4] Processing ticker-dates...")
            total = len(ticker_dates)

            for i, td in enumerate(ticker_dates, 1):
                ticker = td['ticker']
                trade_date = td['date']

                self._log(f"\n[{i}/{total}] Processing {ticker} on {trade_date}...")

                try:
                    # Calculate all M1 bars for this ticker-date
                    results = calculator.calculate_for_ticker_date(ticker, trade_date)

                    if results:
                        self.stats['ticker_dates_processed'] += 1

                        if dry_run:
                            self._log(f"[DRY-RUN] Would insert {len(results)} bars")
                        else:
                            inserted = self.insert_results(conn, results)
                            conn.commit()
                            self.stats['bars_inserted'] += inserted
                            self._log(f"Inserted {inserted} bars")

                        print(f"  [{i}/{total}] {ticker} {trade_date}: {len(results)} bars")
                    else:
                        self.stats['ticker_dates_skipped'] += 1
                        self._log(f"Skipped {ticker} {trade_date} (no bars)", 'debug')

                except Exception as e:
                    # Rollback to clear the aborted transaction state
                    conn.rollback()
                    self.stats['ticker_dates_skipped'] += 1
                    self.stats['errors'].append(f"{ticker} {trade_date}: {str(e)}")
                    self._log(f"Error processing {ticker} {trade_date}: {e}", 'error')

                # Clear caches between ticker-dates to manage memory
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
        """Build the result dictionary."""
        elapsed = (datetime.now() - start_time).total_seconds()

        self.stats['execution_time_seconds'] = round(elapsed, 2)

        return self.stats
