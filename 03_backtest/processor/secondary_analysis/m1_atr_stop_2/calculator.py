"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
M1 ATR Stop Calculator
XIII Trading LLC
================================================================================

Evaluates trades using M1 ATR(14) as the stop distance (1R) and tracks
R-multiple targets (1R through 5R) to determine win/loss outcomes.

LOGIC:
    1. Read entry from trades_2, adjust entry_time to M1 candle (truncate seconds)
    2. Fetch pre-computed atr_m1 from m1_indicator_bars_2 at adjusted entry candle
    3. Set stop = entry -/+ atr_m1 (no multiplier) => this distance = 1R
    4. Set R-level targets at entry +/- (N * 1R) for N = 1..5
    5. Walk M1 bars from entry to 15:30 ET:
       - R targets: hit when price high/low touches target (price-based)
       - Stop: hit when M1 bar CLOSES beyond stop level (close-based)
       - Same-candle conflict: if R-level hit AND close beyond stop => LOSS
    6. Result:
       - WIN  = R1 hit before stop
       - LOSS = everything else (stop before R1, no R1 by 15:30, no data)
    7. max_r = highest R-level hit before stop_time (0 if none)

DATA SOURCES (v2 tables):
    - trades_2 (trade metadata)
    - m1_bars_2 (M1 candle data for bar-by-bar simulation)
    - m1_indicator_bars_2 (pre-computed atr_m1 at entry candle)

Version: 1.0.0
================================================================================
"""

import psycopg2
from psycopg2.extras import execute_values
import numpy as np
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from decimal import Decimal
import logging

from config import (
    DB_CONFIG, EOD_CUTOFF, R_LEVELS, SOURCE_TABLES, TARGET_TABLE
)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def _convert_numpy(value):
    """Convert numpy types to Python native types for database insertion."""
    if value is None:
        return None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value) if not np.isnan(value) else None
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def _safe_float(value, default: float = 0.0) -> float:
    """Safely convert value to float, handling Decimal types."""
    if value is None:
        return default
    try:
        if isinstance(value, Decimal):
            return float(value)
        return float(value)
    except (ValueError, TypeError):
        return default


def _time_to_minutes(time_val) -> Optional[float]:
    """Convert a time value to minutes from midnight."""
    if time_val is None:
        return None
    try:
        if isinstance(time_val, timedelta):
            return time_val.total_seconds() / 60
        if isinstance(time_val, time):
            return time_val.hour * 60 + time_val.minute + time_val.second / 60
        if isinstance(time_val, datetime):
            return time_val.hour * 60 + time_val.minute + time_val.second / 60
        if isinstance(time_val, str):
            parts = time_val.split(':')
            if len(parts) >= 2:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = int(parts[2]) if len(parts) > 2 else 0
                return hours * 60 + minutes + seconds / 60
        return None
    except Exception:
        return None


def _timedelta_to_time(td) -> Optional[time]:
    """Convert timedelta (from psycopg2) to time object."""
    if td is None:
        return None
    if isinstance(td, time):
        return td
    if isinstance(td, timedelta):
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return time(hours, minutes, seconds)
    return None


def _truncate_to_m1_candle(time_val) -> Optional[time]:
    """
    Truncate a time value to the containing M1 candle.
    e.g., 09:31:15 → 09:31:00 (zero out seconds and microseconds)
    """
    t = _timedelta_to_time(time_val)
    if t is None:
        return None
    return t.replace(second=0, microsecond=0)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class M1AtrStopResult:
    """Result of M1 ATR Stop calculation for a single trade."""
    # Trade identification
    trade_id: str
    date: date
    ticker: str
    direction: str
    model: str
    zone_type: str

    # Entry reference
    entry_time: time
    entry_price: float
    m1_entry_candle_adj: Optional[time]

    # ATR stop calculation
    m1_atr_value: Optional[float]
    stop_price: Optional[float]
    stop_distance: Optional[float]
    stop_distance_pct: Optional[float]

    # R-level target prices
    r1_price: Optional[float]
    r2_price: Optional[float]
    r3_price: Optional[float]
    r4_price: Optional[float]
    r5_price: Optional[float]

    # R-level hit tracking
    r1_hit: bool = False
    r1_time: Optional[time] = None
    r1_bars_from_entry: Optional[int] = None

    r2_hit: bool = False
    r2_time: Optional[time] = None
    r2_bars_from_entry: Optional[int] = None

    r3_hit: bool = False
    r3_time: Optional[time] = None
    r3_bars_from_entry: Optional[int] = None

    r4_hit: bool = False
    r4_time: Optional[time] = None
    r4_bars_from_entry: Optional[int] = None

    r5_hit: bool = False
    r5_time: Optional[time] = None
    r5_bars_from_entry: Optional[int] = None

    # Stop hit tracking
    stop_hit: bool = False
    stop_time: Optional[time] = None
    stop_bars_from_entry: Optional[int] = None

    # Outcome
    max_r: int = -1          # -1 = LOSS, 1-5 = highest R-level hit before stop
    result: str = 'LOSS'


# =============================================================================
# CALCULATOR CLASS
# =============================================================================

class M1AtrStopCalculator:
    """
    Calculates M1 ATR Stop outcomes using pre-computed M1 ATR and R-multiple targets.

    This class:
    1. Queries trades_2 for trades not yet in m1_atr_stop_2
    2. Adjusts entry time to containing M1 candle
    3. Fetches pre-computed atr_m1 from m1_indicator_bars_2
    4. Calculates stop price and R-level targets
    5. Walks M1 bars to detect R-level hits and stop triggers
    6. Writes results to m1_atr_stop_2 table
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        self.stats = {
            'trades_processed': 0,
            'trades_skipped': 0,
            'records_created': 0,
            'errors': []
        }

    def _log(self, message: str, level: str = 'info'):
        """Log message if verbose mode is enabled."""
        if self.verbose:
            prefix = {'error': '  ERROR:', 'warning': '  WARNING:', 'info': ' '}
            print(f"{prefix.get(level, ' ')} {message}")

    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================

    def get_trades_needing_calculation(self, conn, limit: int = None) -> List[Dict[str, Any]]:
        """
        Query trades_2 for trades not yet processed in m1_atr_stop_2.
        Requires entry_time and entry_price to be populated.
        """
        query = f"""
            SELECT
                t.trade_id,
                t.date,
                t.ticker,
                t.direction,
                t.model,
                t.zone_type,
                t.entry_time,
                t.entry_price
            FROM {SOURCE_TABLES['trades']} t
            WHERE t.entry_time IS NOT NULL
              AND t.entry_price IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM {TARGET_TABLE} r
                  WHERE r.trade_id = t.trade_id
              )
            ORDER BY t.date, t.ticker, t.entry_time
        """

        if limit:
            query += f" LIMIT {limit}"

        with conn.cursor() as cur:
            cur.execute(query)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

        return [dict(zip(columns, row)) for row in rows]

    def get_m1_atr_at_entry(
        self,
        conn,
        ticker: str,
        trade_date: date,
        m1_candle_time: time
    ) -> Optional[float]:
        """
        Fetch pre-computed atr_m1 from m1_indicator_bars_2 at the adjusted entry candle.

        Args:
            conn: Database connection
            ticker: Stock symbol
            trade_date: Trading date
            m1_candle_time: M1 candle time (seconds truncated)

        Returns:
            atr_m1 value or None if not available
        """
        query = f"""
            SELECT atr_m1
            FROM {SOURCE_TABLES['m1_indicator_bars']}
            WHERE ticker = %s AND bar_date = %s AND bar_time = %s
        """

        with conn.cursor() as cur:
            cur.execute(query, (ticker, trade_date, m1_candle_time))
            row = cur.fetchone()

        if row is None or row[0] is None:
            return None

        return float(row[0])

    def get_m1_bars(
        self,
        conn,
        ticker: str,
        trade_date: date
    ) -> List[Dict[str, Any]]:
        """Fetch M1 bars for a ticker/date from m1_bars_2."""
        query = f"""
            SELECT bar_date, bar_time, open, high, low, close, volume
            FROM {SOURCE_TABLES['m1_bars']}
            WHERE ticker = %s AND bar_date = %s
            ORDER BY bar_time
        """

        with conn.cursor() as cur:
            cur.execute(query, (ticker, trade_date))
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

        return [dict(zip(columns, row)) for row in rows]

    def insert_results(self, conn, results: List[M1AtrStopResult]) -> int:
        """Insert calculation results into m1_atr_stop_2 table."""
        if not results:
            return 0

        query = f"""
            INSERT INTO {TARGET_TABLE} (
                trade_id, date, ticker, direction, model, zone_type,
                entry_time, entry_price, m1_entry_candle_adj,
                m1_atr_value, stop_price, stop_distance, stop_distance_pct,
                r1_price, r2_price, r3_price, r4_price, r5_price,
                r1_hit, r1_time, r1_bars_from_entry,
                r2_hit, r2_time, r2_bars_from_entry,
                r3_hit, r3_time, r3_bars_from_entry,
                r4_hit, r4_time, r4_bars_from_entry,
                r5_hit, r5_time, r5_bars_from_entry,
                stop_hit, stop_time, stop_bars_from_entry,
                max_r, result
            ) VALUES %s
            ON CONFLICT (trade_id) DO UPDATE SET
                m1_atr_value = EXCLUDED.m1_atr_value,
                stop_price = EXCLUDED.stop_price,
                stop_distance = EXCLUDED.stop_distance,
                stop_distance_pct = EXCLUDED.stop_distance_pct,
                r1_price = EXCLUDED.r1_price,
                r2_price = EXCLUDED.r2_price,
                r3_price = EXCLUDED.r3_price,
                r4_price = EXCLUDED.r4_price,
                r5_price = EXCLUDED.r5_price,
                r1_hit = EXCLUDED.r1_hit,
                r1_time = EXCLUDED.r1_time,
                r1_bars_from_entry = EXCLUDED.r1_bars_from_entry,
                r2_hit = EXCLUDED.r2_hit,
                r2_time = EXCLUDED.r2_time,
                r2_bars_from_entry = EXCLUDED.r2_bars_from_entry,
                r3_hit = EXCLUDED.r3_hit,
                r3_time = EXCLUDED.r3_time,
                r3_bars_from_entry = EXCLUDED.r3_bars_from_entry,
                r4_hit = EXCLUDED.r4_hit,
                r4_time = EXCLUDED.r4_time,
                r4_bars_from_entry = EXCLUDED.r4_bars_from_entry,
                r5_hit = EXCLUDED.r5_hit,
                r5_time = EXCLUDED.r5_time,
                r5_bars_from_entry = EXCLUDED.r5_bars_from_entry,
                stop_hit = EXCLUDED.stop_hit,
                stop_time = EXCLUDED.stop_time,
                stop_bars_from_entry = EXCLUDED.stop_bars_from_entry,
                max_r = EXCLUDED.max_r,
                result = EXCLUDED.result,
                updated_at = NOW()
        """

        values = [
            (
                r.trade_id, r.date, r.ticker, r.direction, r.model, r.zone_type,
                r.entry_time, _convert_numpy(r.entry_price), r.m1_entry_candle_adj,
                _convert_numpy(r.m1_atr_value),
                _convert_numpy(r.stop_price),
                _convert_numpy(r.stop_distance),
                _convert_numpy(r.stop_distance_pct),
                _convert_numpy(r.r1_price),
                _convert_numpy(r.r2_price),
                _convert_numpy(r.r3_price),
                _convert_numpy(r.r4_price),
                _convert_numpy(r.r5_price),
                r.r1_hit, r.r1_time, r.r1_bars_from_entry,
                r.r2_hit, r.r2_time, r.r2_bars_from_entry,
                r.r3_hit, r.r3_time, r.r3_bars_from_entry,
                r.r4_hit, r.r4_time, r.r4_bars_from_entry,
                r.r5_hit, r.r5_time, r.r5_bars_from_entry,
                r.stop_hit, r.stop_time, r.stop_bars_from_entry,
                r.max_r, r.result,
            )
            for r in results
        ]

        with conn.cursor() as cur:
            execute_values(cur, query, values)

        return len(results)

    # =========================================================================
    # CORE CALCULATION LOGIC
    # =========================================================================

    def calculate_single_trade(
        self,
        trade: Dict[str, Any],
        m1_bars: List[Dict[str, Any]],
        m1_atr_value: float
    ) -> Optional[M1AtrStopResult]:
        """
        Calculate M1 ATR Stop outcome for a single trade.

        Walk M1 bars sequentially from entry to 15:30:
        - Check R-level targets (price-based: high/low touch)
        - Check stop (close-based: M1 close beyond stop)
        - Same-candle conflict: R-level hit + close beyond stop => stop takes priority
        - max_r = highest R-level hit before stop_time
        - result = WIN if R1 hit before stop, LOSS otherwise
        """
        trade_id = trade['trade_id']

        # Parse entry time
        entry_time = _timedelta_to_time(trade['entry_time'])
        if entry_time is None:
            entry_time = trade['entry_time']

        entry_price = _safe_float(trade['entry_price'])
        direction = trade['direction']
        is_long = direction.upper() == 'LONG'

        # Adjust entry time to M1 candle
        m1_entry_candle_adj = _truncate_to_m1_candle(entry_time)

        # Stop distance = M1 ATR (1x, no multiplier)
        stop_distance = m1_atr_value

        # Calculate stop price
        if is_long:
            stop_price = entry_price - stop_distance
        else:
            stop_price = entry_price + stop_distance

        stop_distance_pct = (stop_distance / entry_price) * 100 if entry_price > 0 else 0

        # Calculate R-level target prices
        r_prices = {}
        for r in R_LEVELS:
            if is_long:
                r_prices[r] = entry_price + (r * stop_distance)
            else:
                r_prices[r] = entry_price - (r * stop_distance)

        # Build result with initial values
        result = M1AtrStopResult(
            trade_id=trade_id,
            date=trade['date'],
            ticker=trade['ticker'],
            direction=direction,
            model=trade['model'],
            zone_type=trade.get('zone_type', ''),
            entry_time=entry_time,
            entry_price=round(entry_price, 4),
            m1_entry_candle_adj=m1_entry_candle_adj,
            m1_atr_value=round(m1_atr_value, 6),
            stop_price=round(stop_price, 4),
            stop_distance=round(stop_distance, 6),
            stop_distance_pct=round(stop_distance_pct, 4),
            r1_price=round(r_prices[1], 4),
            r2_price=round(r_prices[2], 4),
            r3_price=round(r_prices[3], 4),
            r4_price=round(r_prices[4], 4),
            r5_price=round(r_prices[5], 4),
        )

        # Walk M1 bars from entry to EOD
        entry_minutes = _time_to_minutes(entry_time)
        eod_minutes = _time_to_minutes(EOD_CUTOFF)

        if entry_minutes is None:
            self._log(f"Skipping {trade_id}: could not parse entry time", 'warning')
            return None

        # Track state during walk
        r_levels_hit = {}  # {r_level: bar_time}
        stop_triggered = False
        bar_count = 0

        # Sort M1 bars by time
        sorted_m1 = sorted(m1_bars, key=lambda b: _time_to_minutes(b.get('bar_time')) or 0)

        for bar in sorted_m1:
            bar_minutes = _time_to_minutes(bar.get('bar_time'))
            if bar_minutes is None:
                continue

            # Only process bars after entry and up to EOD cutoff
            if bar_minutes <= entry_minutes:
                continue
            if bar_minutes > eod_minutes:
                break

            bar_count += 1
            bar_high = _safe_float(bar.get('high'))
            bar_low = _safe_float(bar.get('low'))
            bar_close = _safe_float(bar.get('close'))
            bar_time = _timedelta_to_time(bar.get('bar_time'))

            # --- Check stop (close-based) ---
            stop_on_this_bar = False
            if is_long:
                if bar_close <= stop_price:
                    stop_on_this_bar = True
            else:
                if bar_close >= stop_price:
                    stop_on_this_bar = True

            # --- Check R-level targets (price-based: high/low touch) ---
            new_r_hits_this_bar = []
            for r in R_LEVELS:
                if r in r_levels_hit:
                    continue  # Already hit this level

                target = r_prices[r]
                target_hit = False
                if is_long:
                    if bar_high >= target:
                        target_hit = True
                else:
                    if bar_low <= target:
                        target_hit = True

                if target_hit:
                    new_r_hits_this_bar.append(r)

            # --- Same-candle conflict resolution ---
            # If stop triggers on this bar, R-level hits on this SAME bar
            # are invalidated. The stop takes priority.
            if stop_on_this_bar:
                stop_triggered = True
                result.stop_hit = True
                result.stop_time = bar_time
                result.stop_bars_from_entry = bar_count
                # Do NOT credit R-levels hit on this same bar
                break

            # If no stop on this bar, credit R-level hits
            for r in new_r_hits_this_bar:
                r_levels_hit[r] = bar_time
                if r == 1:
                    result.r1_hit = True
                    result.r1_time = bar_time
                    result.r1_bars_from_entry = bar_count
                elif r == 2:
                    result.r2_hit = True
                    result.r2_time = bar_time
                    result.r2_bars_from_entry = bar_count
                elif r == 3:
                    result.r3_hit = True
                    result.r3_time = bar_time
                    result.r3_bars_from_entry = bar_count
                elif r == 4:
                    result.r4_hit = True
                    result.r4_time = bar_time
                    result.r4_bars_from_entry = bar_count
                elif r == 5:
                    result.r5_hit = True
                    result.r5_time = bar_time
                    result.r5_bars_from_entry = bar_count

            # All R-levels hit, no need to continue
            if len(r_levels_hit) == len(R_LEVELS):
                break

        # --- Determine result and max_r ---
        # WIN = R1 hit before stop, LOSS = everything else
        # max_r: -1 for LOSS (allows direct use in R-multiple calculations)
        #        1-5 for WIN (highest R-level hit before stop_time)
        if result.r1_hit:
            # R1 was hit (and it was before stop, since same-candle conflict
            # prevents R-hits on the stop bar)
            result.result = 'WIN'
            result.max_r = max(r_levels_hit.keys())
        else:
            result.result = 'LOSS'
            result.max_r = -1

        return result

    # =========================================================================
    # BATCH PROCESSING
    # =========================================================================

    def run_batch_calculation(
        self,
        limit: int = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Main entry point. Process all trades needing M1 ATR Stop calculation.

        Args:
            limit: Max trades to process (for testing)
            dry_run: If True, calculate but don't write to DB

        Returns:
            Dictionary with execution statistics
        """
        start_time = datetime.now()

        print("=" * 60)
        print("M1 ATR Stop Calculator")
        print("=" * 60)
        print(f"Stop Type: M1 ATR(14) × 1.0")
        print(f"R-Levels: {R_LEVELS}")
        print(f"EOD Cutoff: {EOD_CUTOFF}")
        print(f"Dry Run: {dry_run}")
        if limit:
            print(f"Limit: {limit} trades")
        print()

        # Reset statistics
        self.stats = {
            'trades_processed': 0,
            'trades_skipped': 0,
            'records_created': 0,
            'errors': []
        }

        conn = None
        try:
            # Connect to database
            print("[1/4] Connecting to Supabase...")
            conn = psycopg2.connect(**DB_CONFIG)
            print("  Connected successfully")

            # Get trades needing calculation
            print("\n[2/4] Querying trades needing calculation...")
            trades = self.get_trades_needing_calculation(conn, limit)
            print(f"  Found {len(trades)} trades to process")

            if not trades:
                print("\n  No trades need calculation. Exiting.")
                return self._build_result(start_time)

            # Process trades
            print("\n[3/4] Processing trades...")
            all_results = []

            # Cache M1 bars by ticker+date to minimize DB queries
            m1_cache = {}

            for idx, trade in enumerate(trades):
                trade_id = trade['trade_id']
                ticker = trade['ticker']
                trade_date = trade['date']

                # Step 1: Adjust entry time to M1 candle
                m1_candle = _truncate_to_m1_candle(trade['entry_time'])
                if m1_candle is None:
                    self._log(f"Skipping {trade_id}: could not parse entry time", 'warning')
                    self.stats['trades_skipped'] += 1
                    continue

                # Step 2: Fetch M1 ATR at adjusted entry candle
                m1_atr = self.get_m1_atr_at_entry(conn, ticker, trade_date, m1_candle)
                if m1_atr is None or m1_atr <= 0:
                    self._log(
                        f"Skipping {trade_id}: no M1 ATR at {ticker} {trade_date} {m1_candle}",
                        'warning'
                    )
                    self.stats['trades_skipped'] += 1
                    continue

                # Step 3: Get M1 bars (cached by ticker+date)
                m1_key = f"{ticker}_{trade_date}"
                if m1_key not in m1_cache:
                    m1_cache[m1_key] = self.get_m1_bars(conn, ticker, trade_date)
                m1_bars = m1_cache[m1_key]

                if not m1_bars:
                    self._log(f"Skipping {trade_id}: no M1 bars", 'warning')
                    self.stats['trades_skipped'] += 1
                    continue

                # Step 4: Calculate
                try:
                    result = self.calculate_single_trade(trade, m1_bars, m1_atr)

                    if result is not None:
                        all_results.append(result)
                        self.stats['trades_processed'] += 1

                        # Trade-by-trade output
                        r_hits = ''.join([
                            f"R{r}" for r in R_LEVELS
                            if getattr(result, f'r{r}_hit', False)
                        ]) or '-'
                        stop_info = f"stop@{result.stop_time}" if result.stop_hit else "no_stop"
                        print(
                            f"  [{idx + 1}/{len(trades)}] "
                            f"{result.trade_id:<35s} "
                            f"{result.direction:<6s} "
                            f"{result.result:<5s} "
                            f"maxR={result.max_r} "
                            f"hits={r_hits} "
                            f"{stop_info}"
                        )
                    else:
                        self.stats['trades_skipped'] += 1
                        print(
                            f"  [{idx + 1}/{len(trades)}] "
                            f"{trade_id:<35s} "
                            f"SKIPPED"
                        )

                except Exception as e:
                    self.stats['errors'].append(f"{trade_id}: {str(e)}")
                    self._log(f"Error processing {trade_id}: {e}", 'error')

            # Write results to database
            print(f"\n[4/4] Writing results to database...")
            if dry_run:
                print(f"  [DRY-RUN] Would insert {len(all_results)} records")
            else:
                inserted = self.insert_results(conn, all_results)
                conn.commit()
                self.stats['records_created'] = inserted
                print(f"  Inserted {inserted} records")

            return self._build_result(start_time)

        except Exception as e:
            self.stats['errors'].append(str(e))
            if conn:
                conn.rollback()
            raise

        finally:
            if conn:
                conn.close()

    def _build_result(self, start_time: datetime) -> Dict[str, Any]:
        """Build the result dictionary."""
        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            'trades_processed': self.stats['trades_processed'],
            'trades_skipped': self.stats['trades_skipped'],
            'records_created': self.stats['records_created'],
            'errors': self.stats['errors'],
            'execution_time_seconds': round(elapsed, 2)
        }


# =============================================================================
# STANDALONE TEST
# =============================================================================
if __name__ == "__main__":
    print("M1 ATR Stop Calculator - Test Mode")
    print("=" * 60)

    calculator = M1AtrStopCalculator(verbose=True)
    results = calculator.run_batch_calculation(limit=5, dry_run=True)

    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    for key, value in results.items():
        print(f"  {key}: {value}")
