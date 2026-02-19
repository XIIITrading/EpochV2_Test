"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
M1 Trade Indicator Processor v2 - Populator
XIII Trading LLC
================================================================================

Populates m1_trade_indicator_2 with the M1 indicator bar that closed just
before the entry candle, denormalized with trade context and outcome.

Pipeline:
    1. Query trades in trades_2 INNER JOIN m5_atr_stop_2 (outcome required)
       that are NOT yet in m1_trade_indicator_2
    2. For each trade: find the M1 bar from m1_indicator_bars_2 that closed
       just before the entry candle (entry_time floored to minute - 1 minute)
    3. Merge trade context + outcome + indicator values into single row
    4. INSERT with ON CONFLICT DO UPDATE

No indicator calculations - pure data reshaping from existing tables.

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
from config import DB_CONFIG, SOURCE_TABLES, TARGET_TABLE, INDICATOR_COLUMNS, BATCH_SIZE

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


def _floor_to_minute(entry_time: time) -> time:
    """Floor a time value to the minute boundary.

    Example: 09:35:15 -> 09:35:00 (this is the entry candle start)
    """
    return time(entry_time.hour, entry_time.minute, 0)


def _prior_bar_time(entry_candle_start: time) -> time:
    """Get the time of the M1 bar that closed just before the entry candle.

    Example: entry_candle_start = 09:35:00 -> prior bar = 09:34:00
    """
    dt = datetime(2000, 1, 1, entry_candle_start.hour,
                  entry_candle_start.minute, 0)
    prior = dt - timedelta(minutes=1)
    return time(prior.hour, prior.minute, 0)


# =============================================================================
# POPULATOR CLASS
# =============================================================================

class M1TradeIndicatorPopulator:
    """
    Populates m1_trade_indicator_2 with entry-bar indicator snapshots.

    For each trade in trades_2 that has an outcome in m5_atr_stop_2:
    - Find the M1 bar from m1_indicator_bars_2 that closed just before entry
    - Merge trade context + outcome + indicator values
    - Insert into m1_trade_indicator_2
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    # -----------------------------------------------------------------
    # STEP 1: Get eligible trades (have outcomes, not yet populated)
    # -----------------------------------------------------------------

    def get_eligible_trades(self, conn, limit: Optional[int] = None) -> List[dict]:
        """
        Query trades that have outcomes but are not yet in m1_trade_indicator_2.

        INNER JOIN m5_atr_stop_2 ensures only trades with completed outcomes
        are returned. Trades without outcomes are SKIPPED entirely.
        """
        trades_table = SOURCE_TABLES['trades']
        m5_table = SOURCE_TABLES['m5_atr_stop']

        query = f"""
            SELECT
                t.trade_id,
                t.ticker,
                t.date,
                t.direction,
                t.model,
                t.zone_type,
                t.entry_time,
                t.entry_price,
                -- Outcome from m5_atr_stop_2
                m5.result,
                m5.max_r
            FROM {trades_table} t
            INNER JOIN {m5_table} m5 ON t.trade_id = m5.trade_id
            WHERE NOT EXISTS (
                SELECT 1 FROM {TARGET_TABLE} ti
                WHERE ti.trade_id = t.trade_id
            )
            ORDER BY t.date, t.ticker, t.entry_time
        """

        if limit:
            query += f" LIMIT {limit}"

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()

        if self.verbose:
            print(f"  Found {len(rows)} trades needing indicator snapshots")

        return [dict(r) for r in rows]

    # -----------------------------------------------------------------
    # STEP 2: Get indicator bar for a single trade
    # -----------------------------------------------------------------

    def get_indicator_bar(self, conn, ticker: str, bar_date: date,
                          bar_time: time) -> Optional[dict]:
        """
        Fetch the M1 indicator bar for a specific ticker/date/time.

        Returns None if no matching bar exists in m1_indicator_bars_2.
        """
        indicators_table = SOURCE_TABLES['m1_indicators']
        cols = ', '.join(INDICATOR_COLUMNS)

        query = f"""
            SELECT bar_date, bar_time, {cols}
            FROM {indicators_table}
            WHERE ticker = %s AND bar_date = %s AND bar_time = %s
        """

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (ticker, bar_date, bar_time))
            row = cur.fetchone()

        return dict(row) if row else None

    # -----------------------------------------------------------------
    # STEP 3: Build a single target row
    # -----------------------------------------------------------------

    def build_row(self, trade: dict, indicator_bar: dict) -> tuple:
        """
        Build a single row for m1_trade_indicator_2.

        Merges trade context + outcome + indicator values.
        Returns a tuple ready for execute_values INSERT.
        """
        # Outcome
        is_winner = (trade['result'] == 'WIN')
        max_r = _safe_int(trade['max_r']) or -1
        pnl_r = float(max_r)

        return (
            # Trade Reference
            trade['trade_id'],
            # Trade Context
            trade['ticker'],
            trade['date'],
            trade['direction'],
            trade['model'],
            trade['zone_type'],
            trade['entry_time'],
            _safe_float(trade['entry_price']),
            # Outcome
            is_winner,
            pnl_r,
            max_r,
            # Bar Identification
            indicator_bar['bar_date'],
            indicator_bar['bar_time'],
            # OHLCV
            _safe_float(indicator_bar.get('open')),
            _safe_float(indicator_bar.get('high')),
            _safe_float(indicator_bar.get('low')),
            _safe_float(indicator_bar.get('close')),
            _safe_int(indicator_bar.get('volume')),
            # Core Indicators
            _safe_float(indicator_bar.get('candle_range_pct')),
            _safe_float(indicator_bar.get('vol_delta_raw')),
            _safe_float(indicator_bar.get('vol_delta_roll')),
            _safe_float(indicator_bar.get('vol_delta_norm')),
            _safe_float(indicator_bar.get('vol_roc')),
            _safe_float(indicator_bar.get('sma9')),
            _safe_float(indicator_bar.get('sma21')),
            indicator_bar.get('sma_config'),
            _safe_float(indicator_bar.get('sma_spread_pct')),
            indicator_bar.get('sma_momentum_label'),
            indicator_bar.get('price_position'),
            _safe_float(indicator_bar.get('cvd_slope')),
            # Structure
            indicator_bar.get('m5_structure'),
            indicator_bar.get('m15_structure'),
            indicator_bar.get('h1_structure'),
            # Composite Scores
            _safe_int(indicator_bar.get('health_score')),
            _safe_int(indicator_bar.get('long_score')),
            _safe_int(indicator_bar.get('short_score')),
        )

    # -----------------------------------------------------------------
    # STEP 4: Insert rows
    # -----------------------------------------------------------------

    def insert_rows(self, conn, rows: List[tuple]) -> int:
        """Insert rows into m1_trade_indicator_2 with ON CONFLICT upsert."""
        if not rows:
            return 0

        query = f"""
            INSERT INTO {TARGET_TABLE} (
                trade_id,
                ticker, date, direction, model, zone_type,
                entry_time, entry_price,
                is_winner, pnl_r, max_r_achieved,
                bar_date, bar_time,
                open, high, low, close, volume,
                candle_range_pct,
                vol_delta_raw, vol_delta_roll, vol_delta_norm,
                vol_roc,
                sma9, sma21, sma_config, sma_spread_pct,
                sma_momentum_label, price_position,
                cvd_slope,
                m5_structure, m15_structure, h1_structure,
                health_score, long_score, short_score
            ) VALUES %s
            ON CONFLICT (trade_id) DO UPDATE SET
                is_winner = EXCLUDED.is_winner,
                pnl_r = EXCLUDED.pnl_r,
                max_r_achieved = EXCLUDED.max_r_achieved,
                bar_date = EXCLUDED.bar_date,
                bar_time = EXCLUDED.bar_time,
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                candle_range_pct = EXCLUDED.candle_range_pct,
                vol_delta_raw = EXCLUDED.vol_delta_raw,
                vol_delta_roll = EXCLUDED.vol_delta_roll,
                vol_delta_norm = EXCLUDED.vol_delta_norm,
                vol_roc = EXCLUDED.vol_roc,
                sma9 = EXCLUDED.sma9,
                sma21 = EXCLUDED.sma21,
                sma_config = EXCLUDED.sma_config,
                sma_spread_pct = EXCLUDED.sma_spread_pct,
                sma_momentum_label = EXCLUDED.sma_momentum_label,
                price_position = EXCLUDED.price_position,
                cvd_slope = EXCLUDED.cvd_slope,
                m5_structure = EXCLUDED.m5_structure,
                m15_structure = EXCLUDED.m15_structure,
                h1_structure = EXCLUDED.h1_structure,
                health_score = EXCLUDED.health_score,
                long_score = EXCLUDED.long_score,
                short_score = EXCLUDED.short_score,
                calculated_at = NOW()
        """

        total_inserted = 0
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            with conn.cursor() as cur:
                execute_values(cur, query, batch)
            total_inserted += len(batch)

        return total_inserted

    # -----------------------------------------------------------------
    # STATUS: Show pipeline state
    # -----------------------------------------------------------------

    def show_status(self, conn):
        """Show the current state of the processing pipeline."""
        trades_table = SOURCE_TABLES['trades']
        m5_table = SOURCE_TABLES['m5_atr_stop']

        with conn.cursor() as cur:
            # Total trades
            cur.execute(f"SELECT COUNT(*) FROM {trades_table}")
            total_trades = cur.fetchone()[0]

            # Trades with outcomes
            cur.execute(f"""
                SELECT COUNT(*) FROM {trades_table} t
                INNER JOIN {m5_table} m5 ON t.trade_id = m5.trade_id
            """)
            with_outcomes = cur.fetchone()[0]

            # Already populated
            try:
                cur.execute(f"SELECT COUNT(*) FROM {TARGET_TABLE}")
                already_done = cur.fetchone()[0]
            except psycopg2.errors.UndefinedTable:
                conn.rollback()
                already_done = "TABLE NOT FOUND"

            # Ready to process
            if isinstance(already_done, int):
                ready = with_outcomes - already_done
                pending_outcomes = total_trades - with_outcomes
            else:
                ready = "N/A"
                pending_outcomes = total_trades - with_outcomes

        print(f"\n  Status: {TARGET_TABLE}")
        print(f"  {'Total trades in trades_2:':<45} {total_trades:>8,}")
        print(f"  {'Trades with outcomes (m5_atr_stop_2):':<45} {with_outcomes:>8,}")
        print(f"  {'Already in m1_trade_indicator_2:':<45} {str(already_done):>8}")
        if isinstance(already_done, int):
            print(f"  {'Ready to process:':<45} {ready:>8,}")
        print(f"  {'Pending outcome analysis:':<45} {pending_outcomes:>8,}")
        if pending_outcomes > 0:
            print(f"  {'':>4}^ Run m5_atr_stop processor first")

    # -----------------------------------------------------------------
    # MAIN ENTRY POINT
    # -----------------------------------------------------------------

    def run(self, limit: Optional[int] = None,
            dry_run: bool = False) -> Dict:
        """
        Main entry point: populate m1_trade_indicator_2.

        For each eligible trade:
        1. Find the M1 bar that closed just before entry
        2. Merge trade context + outcome + indicator values
        3. Insert into target table

        Args:
            limit: Maximum trades to process (None = all)
            dry_run: If True, compute but don't write to DB

        Returns:
            Dict with processing stats
        """
        stats = {
            'total_eligible': 0,
            'processed': 0,
            'inserted': 0,
            'skipped_no_indicator': 0,
            'errors': 0,
        }

        conn = None
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.autocommit = False

            # Step 1: Get eligible trades
            print(f"\n[1/4] Querying eligible trades (with outcomes, not yet populated)...")
            trades = self.get_eligible_trades(conn, limit)
            stats['total_eligible'] = len(trades)

            if not trades:
                print("  No new trades to process")
                return stats

            # Step 2: Build rows
            print(f"[2/4] Fetching indicator bars for {len(trades)} trades...")
            rows = []
            for trade in trades:
                try:
                    # Calculate the prior M1 bar time
                    entry_time = trade['entry_time']
                    entry_candle_start = _floor_to_minute(entry_time)
                    prior_bar = _prior_bar_time(entry_candle_start)

                    # Fetch indicator bar
                    indicator_bar = self.get_indicator_bar(
                        conn, trade['ticker'], trade['date'], prior_bar
                    )

                    if indicator_bar is None:
                        stats['skipped_no_indicator'] += 1
                        if self.verbose:
                            print(f"  SKIP: {trade['trade_id']} - no indicator bar "
                                  f"at {trade['ticker']} {trade['date']} {prior_bar}")
                        continue

                    # Build target row
                    row = self.build_row(trade, indicator_bar)
                    rows.append(row)
                    stats['processed'] += 1

                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error processing {trade['trade_id']}: {e}")
                    if self.verbose:
                        print(f"  ERROR: {trade['trade_id']}: {e}")

            # Step 3: Summary
            print(f"[3/4] Summary:")
            print(f"  Processed:              {stats['processed']}")
            print(f"  Skipped (no indicator): {stats['skipped_no_indicator']}")
            print(f"  Errors:                 {stats['errors']}")

            if rows:
                win_count = sum(1 for r in rows if r[8] is True)  # is_winner index
                loss_count = len(rows) - win_count
                print(f"  WIN: {win_count}, LOSS: {loss_count}")

            # Step 4: Insert
            if dry_run:
                print(f"[4/4] DRY RUN - skipping database write")
                if self.verbose and rows:
                    sample = rows[0]
                    print(f"\n  Sample row:")
                    print(f"    trade_id:  {sample[0]}")
                    print(f"    ticker:    {sample[1]}, date: {sample[2]}")
                    print(f"    direction: {sample[3]}, model: {sample[4]}")
                    print(f"    is_winner: {sample[8]}, pnl_r: {sample[9]}")
                    print(f"    bar_time:  {sample[12]}")
                    print(f"    candle_%:  {sample[18]}")
                    print(f"    vol_roc:   {sample[21]}")
                    print(f"    sma_cfg:   {sample[24]}")
                    print(f"    h1_struct: {sample[31]}")
            else:
                print(f"[4/4] Inserting {len(rows)} rows into {TARGET_TABLE}...")
                inserted = self.insert_rows(conn, rows)
                conn.commit()
                stats['inserted'] = inserted
                print(f"  Inserted: {inserted} rows")

        except KeyboardInterrupt:
            print("\n  Interrupted by user")
            if conn:
                conn.rollback()
            raise

        except Exception as e:
            logger.error(f"Population failed: {e}")
            print(f"\n  FATAL ERROR: {e}")
            if conn:
                conn.rollback()
            raise

        finally:
            if conn:
                conn.close()

        return stats
