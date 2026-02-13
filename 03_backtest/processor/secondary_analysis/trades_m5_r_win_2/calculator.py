"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
Trades M5 R Win Consolidation Processor v2 - Calculator
XIII Trading LLC
================================================================================

Consolidates trades_2 + m5_atr_stop_2 + m1_bars_2 into a single denormalized
table (trades_m5_r_win_2) for downstream consumption by 11_trade_reel.

Pipeline:
    1. Query trades in m5_atr_stop_2 that are NOT yet in trades_m5_r_win_2
    2. JOIN with trades_2 for zone_high, zone_low
    3. Fetch eod_price from m1_bars_2 (last bar close per ticker/date)
    4. Compute derived fields (is_winner, pnl_r, reached_2r, reached_3r,
       minutes_to_r1, exit_reason, outcome_method)
    5. INSERT into trades_m5_r_win_2 with ON CONFLICT DO UPDATE

No simulation logic — this is a pure consolidation/denormalization step.

Version: 1.0.0
================================================================================
"""

import sys
import logging
from pathlib import Path
from datetime import date, time, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

import psycopg2
from psycopg2.extras import execute_values, RealDictCursor

# Self-contained imports
from config import DB_CONFIG, SOURCE_TABLES, TARGET_TABLE, OUTCOME_METHOD

logger = logging.getLogger(__name__)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def _safe_float(val) -> Optional[float]:
    """Convert Decimal/numpy to Python float, None-safe."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> Optional[int]:
    """Convert to Python int, None-safe."""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _safe_bool(val) -> bool:
    """Convert to Python bool, default False."""
    if val is None:
        return False
    return bool(val)


def _minutes_between(t1: Optional[time], t2: Optional[time]) -> Optional[int]:
    """Calculate minutes between two time values. Returns None if either is None."""
    if t1 is None or t2 is None:
        return None
    try:
        # Convert to timedeltas for math
        td1 = timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
        td2 = timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
        diff = td2 - td1
        return max(0, int(diff.total_seconds() / 60))
    except Exception:
        return None


def _determine_exit_reason(stop_hit: bool, max_r: int) -> str:
    """Determine exit reason from stop/R-level data.

    Priority:
        1. STOP_HIT - if stop was triggered
        2. R5_HIT - if trade reached R5 (maximum target)
        3. EOD - end of day / end of data (default)
    """
    if stop_hit:
        return 'STOP_HIT'
    if max_r >= 5:
        return 'R5_HIT'
    return 'EOD'


# =============================================================================
# CALCULATOR CLASS
# =============================================================================

class TradesM5RWin2Calculator:
    """
    Consolidates trades_2 + m5_atr_stop_2 into trades_m5_r_win_2.

    This is a denormalization processor — no simulation logic.
    It JOINs source tables, computes derived fields, and writes
    a single flat table that 11_trade_reel can query directly.
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._eod_cache: Dict[str, Optional[float]] = {}  # {ticker_date: eod_price}

    # -----------------------------------------------------------------
    # STEP 1: Get trades needing consolidation
    # -----------------------------------------------------------------

    def get_trades_needing_consolidation(self, conn, limit: Optional[int] = None) -> List[dict]:
        """
        Query trades from m5_atr_stop_2 that are NOT yet in trades_m5_r_win_2.
        JOINs with trades_2 for zone_high/zone_low.

        Returns list of dicts with all columns needed for the target table.
        """
        trades_table = SOURCE_TABLES['trades']
        m5_table = SOURCE_TABLES['m5_atr_stop']

        query = f"""
            SELECT
                m5.trade_id,
                m5.date,
                m5.ticker,
                m5.direction,
                m5.model,
                m5.zone_type,
                t.zone_high,
                t.zone_low,
                m5.entry_price,
                m5.entry_time,
                m5.m5_atr_value,
                m5.stop_price,
                m5.stop_distance,
                m5.stop_distance_pct,
                m5.r1_price, m5.r2_price, m5.r3_price, m5.r4_price, m5.r5_price,
                m5.r1_hit, m5.r1_time, m5.r1_bars_from_entry,
                m5.r2_hit, m5.r2_time, m5.r2_bars_from_entry,
                m5.r3_hit, m5.r3_time, m5.r3_bars_from_entry,
                m5.r4_hit, m5.r4_time, m5.r4_bars_from_entry,
                m5.r5_hit, m5.r5_time, m5.r5_bars_from_entry,
                m5.stop_hit, m5.stop_time, m5.stop_bars_from_entry,
                m5.max_r,
                m5.result
            FROM {m5_table} m5
            JOIN {trades_table} t ON m5.trade_id = t.trade_id
            WHERE NOT EXISTS (
                SELECT 1 FROM {TARGET_TABLE} tw
                WHERE tw.trade_id = m5.trade_id
            )
            ORDER BY m5.date, m5.ticker, m5.entry_time
        """

        if limit:
            query += f" LIMIT {limit}"

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()

        if self.verbose:
            print(f"  Found {len(rows)} trades needing consolidation")

        return [dict(r) for r in rows]

    # -----------------------------------------------------------------
    # STEP 2: Fetch EOD price from m1_bars_2
    # -----------------------------------------------------------------

    def get_eod_price(self, conn, ticker: str, trade_date: date) -> Optional[float]:
        """
        Get end-of-day price from m1_bars_2 (last bar close for ticker/date).
        Cached per ticker/date to avoid duplicate queries.
        """
        cache_key = f"{ticker}_{trade_date}"

        if cache_key in self._eod_cache:
            return self._eod_cache[cache_key]

        m1_table = SOURCE_TABLES['m1_bars']

        query = f"""
            SELECT close
            FROM {m1_table}
            WHERE ticker = %s AND bar_date = %s
            ORDER BY bar_time DESC
            LIMIT 1
        """

        with conn.cursor() as cur:
            cur.execute(query, (ticker, trade_date))
            row = cur.fetchone()

        eod_price = _safe_float(row[0]) if row else None
        self._eod_cache[cache_key] = eod_price

        return eod_price

    # -----------------------------------------------------------------
    # STEP 3: Build consolidated row with derived fields
    # -----------------------------------------------------------------

    def build_consolidated_row(self, conn, trade: dict) -> tuple:
        """
        Build a single consolidated row from source data + derived fields.

        Returns a tuple ready for execute_values INSERT.
        """
        # Source fields (direct from JOIN)
        trade_id = trade['trade_id']
        trade_date = trade['date']
        ticker = trade['ticker']
        direction = trade['direction']
        model = trade['model']
        zone_type = trade['zone_type']
        zone_high = _safe_float(trade['zone_high'])
        zone_low = _safe_float(trade['zone_low'])
        entry_price = _safe_float(trade['entry_price'])
        entry_time = trade['entry_time']

        # M5 ATR stop data
        m5_atr_value = _safe_float(trade['m5_atr_value'])
        stop_price = _safe_float(trade['stop_price'])
        stop_distance = _safe_float(trade['stop_distance'])
        stop_distance_pct = _safe_float(trade['stop_distance_pct'])

        # R-level prices
        r1_price = _safe_float(trade['r1_price'])
        r2_price = _safe_float(trade['r2_price'])
        r3_price = _safe_float(trade['r3_price'])
        r4_price = _safe_float(trade['r4_price'])
        r5_price = _safe_float(trade['r5_price'])

        # R-level hits
        r1_hit = _safe_bool(trade['r1_hit'])
        r1_time = trade['r1_time']
        r1_bars = _safe_int(trade['r1_bars_from_entry'])

        r2_hit = _safe_bool(trade['r2_hit'])
        r2_time = trade['r2_time']
        r2_bars = _safe_int(trade['r2_bars_from_entry'])

        r3_hit = _safe_bool(trade['r3_hit'])
        r3_time = trade['r3_time']
        r3_bars = _safe_int(trade['r3_bars_from_entry'])

        r4_hit = _safe_bool(trade['r4_hit'])
        r4_time = trade['r4_time']
        r4_bars = _safe_int(trade['r4_bars_from_entry'])

        r5_hit = _safe_bool(trade['r5_hit'])
        r5_time = trade['r5_time']
        r5_bars = _safe_int(trade['r5_bars_from_entry'])

        # Stop hit
        stop_hit = _safe_bool(trade['stop_hit'])
        stop_hit_time = trade['stop_time']  # rename: stop_time -> stop_hit_time
        stop_hit_bars = _safe_int(trade['stop_bars_from_entry'])

        # Source outcome
        max_r = _safe_int(trade['max_r']) or -1
        result = trade['result']

        # --- DERIVED FIELDS ---

        # Rename: max_r -> max_r_achieved, result -> outcome
        max_r_achieved = max_r
        outcome = result  # WIN or LOSS

        # is_winner
        is_winner = (result == 'WIN')

        # pnl_r (same as max_r: -1 for loss, 1-5 for win)
        pnl_r = float(max_r)

        # reached_2r / reached_3r
        reached_2r = r2_hit
        reached_3r = r3_hit

        # minutes_to_r1
        minutes_to_r1 = _minutes_between(entry_time, r1_time)

        # exit_reason
        exit_reason = _determine_exit_reason(stop_hit, max_r)

        # outcome_method
        outcome_method = OUTCOME_METHOD

        # eod_price from m1_bars_2
        eod_price = self.get_eod_price(conn, ticker, trade_date)

        return (
            trade_id, trade_date, ticker, direction, model, zone_type,
            zone_high, zone_low, entry_price, entry_time,
            m5_atr_value, stop_price, stop_distance, stop_distance_pct,
            r1_price, r2_price, r3_price, r4_price, r5_price,
            r1_hit, r1_time, r1_bars,
            r2_hit, r2_time, r2_bars,
            r3_hit, r3_time, r3_bars,
            r4_hit, r4_time, r4_bars,
            r5_hit, r5_time, r5_bars,
            stop_hit, stop_hit_time, stop_hit_bars,
            max_r_achieved, outcome, exit_reason,
            is_winner, pnl_r, outcome_method,
            eod_price, reached_2r, reached_3r, minutes_to_r1,
        )

    # -----------------------------------------------------------------
    # STEP 4: INSERT consolidated rows
    # -----------------------------------------------------------------

    def insert_results(self, conn, rows: List[tuple]) -> int:
        """Insert consolidated rows into trades_m5_r_win_2 table."""
        if not rows:
            return 0

        query = f"""
            INSERT INTO {TARGET_TABLE} (
                trade_id, date, ticker, direction, model, zone_type,
                zone_high, zone_low, entry_price, entry_time,
                m5_atr_value, stop_price, stop_distance, stop_distance_pct,
                r1_price, r2_price, r3_price, r4_price, r5_price,
                r1_hit, r1_time, r1_bars_from_entry,
                r2_hit, r2_time, r2_bars_from_entry,
                r3_hit, r3_time, r3_bars_from_entry,
                r4_hit, r4_time, r4_bars_from_entry,
                r5_hit, r5_time, r5_bars_from_entry,
                stop_hit, stop_hit_time, stop_hit_bars_from_entry,
                max_r_achieved, outcome, exit_reason,
                is_winner, pnl_r, outcome_method,
                eod_price, reached_2r, reached_3r, minutes_to_r1
            ) VALUES %s
            ON CONFLICT (trade_id) DO UPDATE SET
                zone_high = EXCLUDED.zone_high,
                zone_low = EXCLUDED.zone_low,
                m5_atr_value = EXCLUDED.m5_atr_value,
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
                stop_hit_time = EXCLUDED.stop_hit_time,
                stop_hit_bars_from_entry = EXCLUDED.stop_hit_bars_from_entry,
                max_r_achieved = EXCLUDED.max_r_achieved,
                outcome = EXCLUDED.outcome,
                exit_reason = EXCLUDED.exit_reason,
                is_winner = EXCLUDED.is_winner,
                pnl_r = EXCLUDED.pnl_r,
                outcome_method = EXCLUDED.outcome_method,
                eod_price = EXCLUDED.eod_price,
                reached_2r = EXCLUDED.reached_2r,
                reached_3r = EXCLUDED.reached_3r,
                minutes_to_r1 = EXCLUDED.minutes_to_r1,
                updated_at = NOW()
        """

        with conn.cursor() as cur:
            execute_values(cur, query, rows)

        return len(rows)

    # -----------------------------------------------------------------
    # MAIN ENTRY POINT
    # -----------------------------------------------------------------

    def run_batch_consolidation(self, limit: Optional[int] = None,
                                 dry_run: bool = False) -> Dict:
        """
        Main entry point: consolidate trades from source tables.

        Args:
            limit: Maximum number of trades to process (None = all)
            dry_run: If True, compute but don't write to DB

        Returns:
            Dict with processing stats
        """
        stats = {
            'total_source': 0,
            'processed': 0,
            'inserted': 0,
            'errors': 0,
            'skipped': 0,
        }

        conn = None
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.autocommit = False

            # Step 1: Get trades needing consolidation
            print(f"\n[1/4] Querying trades needing consolidation...")
            trades = self.get_trades_needing_consolidation(conn, limit)
            stats['total_source'] = len(trades)

            if not trades:
                print("  No new trades to consolidate")
                return stats

            # Step 2: Build consolidated rows
            print(f"[2/4] Building consolidated rows ({len(trades)} trades)...")
            rows = []
            for trade in trades:
                try:
                    row = self.build_consolidated_row(conn, trade)
                    rows.append(row)
                    stats['processed'] += 1
                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error consolidating {trade['trade_id']}: {e}")
                    if self.verbose:
                        print(f"  ERROR: {trade['trade_id']}: {e}")

            # Step 3: Show summary
            print(f"[3/4] Summary:")
            print(f"  Consolidated: {stats['processed']} trades")
            print(f"  Errors: {stats['errors']}")

            # Count outcomes
            win_count = sum(1 for r in rows if r[38] == 'WIN')  # outcome is index 38
            loss_count = len(rows) - win_count
            print(f"  WIN: {win_count}, LOSS: {loss_count}")

            # Step 4: Insert
            if dry_run:
                print(f"[4/4] DRY RUN - skipping database write")
                if self.verbose and rows:
                    # Show sample
                    sample = rows[0]
                    print(f"\n  Sample row:")
                    print(f"    trade_id: {sample[0]}")
                    print(f"    date: {sample[1]}, ticker: {sample[2]}")
                    print(f"    direction: {sample[3]}, model: {sample[4]}")
                    print(f"    outcome: {sample[38]}, max_r: {sample[37]}")
                    print(f"    is_winner: {sample[40]}, pnl_r: {sample[41]}")
                    print(f"    exit_reason: {sample[39]}")
                    print(f"    eod_price: {sample[43]}")
                    print(f"    minutes_to_r1: {sample[46]}")
            else:
                print(f"[4/4] Inserting {len(rows)} rows into {TARGET_TABLE}...")
                inserted = self.insert_results(conn, rows)
                conn.commit()
                stats['inserted'] = inserted
                print(f"  Inserted: {inserted} rows")

        except KeyboardInterrupt:
            print("\n  Interrupted by user")
            if conn:
                conn.rollback()
            raise

        except Exception as e:
            logger.error(f"Batch consolidation failed: {e}")
            print(f"\n  FATAL ERROR: {e}")
            if conn:
                conn.rollback()
            raise

        finally:
            if conn:
                conn.close()
            self._eod_cache.clear()

        return stats
