"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
M1 Post-Trade Indicator Processor v2 - Populator
XIII Trading LLC
================================================================================

Populates m1_post_trade_indicator_2 with 25 M1 indicator bars after each
trade entry. Bar_sequence 0 = entry candle, bar_sequence 24 = 25th bar after.
Trade outcome is stamped on every row for easy aggregation.

Pipeline:
    1. Query trades in trades_2 INNER JOIN m5_atr_stop_2 (outcome required)
       that are NOT yet in m1_post_trade_indicator_2
    2. For each trade: query 25 bars from m1_indicator_bars_2 starting at
       the entry candle (entry_time floored to minute)
    3. Assign bar_sequence 0-24
    4. Stamp outcome (is_winner, pnl_r, max_r) on every row
    5. INSERT with ON CONFLICT DO UPDATE

Note: The entry candle IS included here (bar_sequence 0) because we are
analyzing what happens AFTER the trade is entered.

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

import psycopg2
from psycopg2.extras import execute_values, RealDictCursor

# Self-contained imports
from config import (
    DB_CONFIG, SOURCE_TABLES, TARGET_TABLE,
    INDICATOR_COLUMNS, POST_TRADE_BARS, BATCH_SIZE
)

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


# =============================================================================
# POPULATOR CLASS
# =============================================================================

class M1PostTradeIndicatorPopulator:
    """
    Populates m1_post_trade_indicator_2 with 25-bar post-trade indicator windows.

    For each trade in trades_2 that has an outcome in m5_atr_stop_2:
    - Query 25 M1 bars starting at entry candle
    - Stamp outcome on every row
    - Insert into m1_post_trade_indicator_2
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    # -----------------------------------------------------------------
    # STEP 1: Get eligible trades
    # -----------------------------------------------------------------

    def get_eligible_trades(self, conn, limit: Optional[int] = None) -> List[dict]:
        """
        Query trades that have outcomes but are not yet in m1_post_trade_indicator_2.

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
                m5.result,
                m5.max_r
            FROM {trades_table} t
            INNER JOIN {m5_table} m5 ON t.trade_id = m5.trade_id
            WHERE NOT EXISTS (
                SELECT 1 FROM {TARGET_TABLE} pt
                WHERE pt.trade_id = t.trade_id
            )
            ORDER BY t.date, t.ticker, t.entry_time
        """

        if limit:
            query += f" LIMIT {limit}"

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()

        if self.verbose:
            print(f"  Found {len(rows)} trades needing post-trade data")

        return [dict(r) for r in rows]

    # -----------------------------------------------------------------
    # STEP 2: Get post-trade indicator bars for a single trade
    # -----------------------------------------------------------------

    def get_post_trade_bars(self, conn, ticker: str, bar_date: date,
                            start_bar_time: time, num_bars: int = 25) -> List[dict]:
        """
        Fetch the N M1 indicator bars starting at start_bar_time (inclusive).

        Returns bars in chronological order.
        """
        indicators_table = SOURCE_TABLES['m1_indicators']
        cols = ', '.join(INDICATOR_COLUMNS)

        query = f"""
            SELECT bar_date, bar_time, {cols}
            FROM {indicators_table}
            WHERE ticker = %s AND bar_date = %s AND bar_time >= %s
            ORDER BY bar_time ASC
            LIMIT %s
        """

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (ticker, bar_date, start_bar_time, num_bars))
            rows = cur.fetchall()

        return [dict(r) for r in rows]

    # -----------------------------------------------------------------
    # STEP 3: Build rows for a single trade
    # -----------------------------------------------------------------

    def build_trade_rows(self, trade: dict, bars: List[dict]) -> List[tuple]:
        """
        Build rows for m1_post_trade_indicator_2 from a trade's post-trade bars.

        Each bar gets a bar_sequence from 0 (entry candle) to len(bars)-1.
        Trade outcome is stamped on every row.
        Returns list of tuples ready for execute_values INSERT.
        """
        rows = []
        trade_id = trade['trade_id']
        ticker = trade['ticker']

        # Outcome (stamped on every row)
        is_winner = (trade['result'] == 'WIN')
        max_r = _safe_int(trade['max_r']) or -1
        pnl_r = float(max_r)

        for seq, bar in enumerate(bars):
            row = (
                trade_id,
                seq,
                ticker,
                bar['bar_date'],
                bar['bar_time'],
                # OHLCV
                _safe_float(bar.get('open')),
                _safe_float(bar.get('high')),
                _safe_float(bar.get('low')),
                _safe_float(bar.get('close')),
                _safe_int(bar.get('volume')),
                # Core Indicators
                _safe_float(bar.get('candle_range_pct')),
                _safe_float(bar.get('vol_delta_raw')),
                _safe_float(bar.get('vol_delta_roll')),
                _safe_float(bar.get('vol_roc')),
                _safe_float(bar.get('sma9')),
                _safe_float(bar.get('sma21')),
                bar.get('sma_config'),
                _safe_float(bar.get('sma_spread_pct')),
                bar.get('sma_momentum_label'),
                bar.get('price_position'),
                _safe_float(bar.get('cvd_slope')),
                # Structure
                bar.get('m5_structure'),
                bar.get('m15_structure'),
                bar.get('h1_structure'),
                # Composite Scores
                _safe_int(bar.get('health_score')),
                _safe_int(bar.get('long_score')),
                _safe_int(bar.get('short_score')),
                # Outcome (stamped on every row)
                is_winner,
                pnl_r,
                max_r,
            )
            rows.append(row)

        return rows

    # -----------------------------------------------------------------
    # STEP 4: Insert rows
    # -----------------------------------------------------------------

    def insert_rows(self, conn, rows: List[tuple]) -> int:
        """Insert rows into m1_post_trade_indicator_2 with ON CONFLICT upsert."""
        if not rows:
            return 0

        query = f"""
            INSERT INTO {TARGET_TABLE} (
                trade_id, bar_sequence,
                ticker, bar_date, bar_time,
                open, high, low, close, volume,
                candle_range_pct,
                vol_delta_raw, vol_delta_roll,
                vol_roc,
                sma9, sma21, sma_config, sma_spread_pct,
                sma_momentum_label, price_position,
                cvd_slope,
                m5_structure, m15_structure, h1_structure,
                health_score, long_score, short_score,
                is_winner, pnl_r, max_r_achieved
            ) VALUES %s
            ON CONFLICT (trade_id, bar_sequence) DO UPDATE SET
                ticker = EXCLUDED.ticker,
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
                is_winner = EXCLUDED.is_winner,
                pnl_r = EXCLUDED.pnl_r,
                max_r_achieved = EXCLUDED.max_r_achieved,
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

            # Already populated (count distinct trade_ids)
            try:
                cur.execute(f"SELECT COUNT(DISTINCT trade_id) FROM {TARGET_TABLE}")
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
        print(f"  {'Already in m1_post_trade_indicator_2:':<45} {str(already_done):>8}")
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
        Main entry point: populate m1_post_trade_indicator_2.

        For each eligible trade:
        1. Find 25 M1 bars starting at entry candle
        2. Stamp outcome on each row
        3. Insert into target table

        Args:
            limit: Maximum trades to process (None = all)
            dry_run: If True, compute but don't write to DB

        Returns:
            Dict with processing stats
        """
        stats = {
            'total_eligible': 0,
            'trades_processed': 0,
            'trades_skipped_no_bars': 0,
            'trades_partial_bars': 0,
            'rows_built': 0,
            'rows_inserted': 0,
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
            print(f"[2/4] Fetching post-trade bars for {len(trades)} trades ({POST_TRADE_BARS} bars each)...")
            all_rows = []
            for idx, trade in enumerate(trades):
                try:
                    # Calculate the entry candle time (bar_sequence 0)
                    entry_time = trade['entry_time']
                    entry_candle_start = _floor_to_minute(entry_time)

                    # Fetch post-trade bars
                    bars = self.get_post_trade_bars(
                        conn, trade['ticker'], trade['date'],
                        entry_candle_start, POST_TRADE_BARS
                    )

                    if not bars:
                        stats['trades_skipped_no_bars'] += 1
                        if self.verbose:
                            print(f"  SKIP: {trade['trade_id']} - no indicator bars "
                                  f"for {trade['ticker']} {trade['date']}")
                        continue

                    if len(bars) < POST_TRADE_BARS:
                        stats['trades_partial_bars'] += 1
                        if self.verbose:
                            print(f"  PARTIAL: {trade['trade_id']} - only {len(bars)}/{POST_TRADE_BARS} bars")

                    # Build rows for this trade
                    trade_rows = self.build_trade_rows(trade, bars)
                    all_rows.extend(trade_rows)
                    stats['trades_processed'] += 1

                    # Progress indicator every 100 trades
                    if self.verbose and (idx + 1) % 100 == 0:
                        print(f"  ... processed {idx + 1}/{len(trades)} trades")

                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error processing {trade['trade_id']}: {e}")
                    if self.verbose:
                        print(f"  ERROR: {trade['trade_id']}: {e}")

            stats['rows_built'] = len(all_rows)

            # Step 3: Summary
            print(f"[3/4] Summary:")
            print(f"  Trades processed:   {stats['trades_processed']}")
            print(f"  Trades skipped:     {stats['trades_skipped_no_bars']} (no bars)")
            print(f"  Trades partial:     {stats['trades_partial_bars']} (<{POST_TRADE_BARS} bars)")
            print(f"  Rows built:         {stats['rows_built']}")
            print(f"  Errors:             {stats['errors']}")

            if all_rows:
                win_rows = sum(1 for r in all_rows if r[27] is True)  # is_winner index
                loss_rows = len(all_rows) - win_rows
                print(f"  Winner rows: {win_rows}, Loser rows: {loss_rows}")

            # Step 4: Insert
            if dry_run:
                print(f"[4/4] DRY RUN - skipping database write")
                if self.verbose and all_rows:
                    sample = all_rows[0]
                    print(f"\n  Sample row:")
                    print(f"    trade_id:     {sample[0]}")
                    print(f"    bar_sequence: {sample[1]}")
                    print(f"    ticker:       {sample[2]}")
                    print(f"    bar_time:     {sample[4]}")
                    print(f"    candle_%:     {sample[10]}")
                    print(f"    is_winner:    {sample[27]}")
                    print(f"    pnl_r:        {sample[28]}")
            else:
                print(f"[4/4] Inserting {len(all_rows)} rows into {TARGET_TABLE}...")
                inserted = self.insert_rows(conn, all_rows)
                conn.commit()
                stats['rows_inserted'] = inserted
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
