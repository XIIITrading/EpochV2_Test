"""
================================================================================
EPOCH TRADING SYSTEM - JOURNAL PROCESSOR 5
j_trades_m5_r_win - Consolidation Calculator
XIII Trading LLC
================================================================================

Consolidates journal_trades + j_m5_atr_stop + j_m1_bars into a single
denormalized table (j_trades_m5_r_win) for downstream trade analysis.

Pipeline:
    1. Query trades in j_m5_atr_stop that are NOT yet in j_trades_m5_r_win
    2. JOIN with journal_trades for actual exit data, PnL, FIFO data
    3. Fetch eod_price from j_m1_bars (last bar close before EOD_CUTOFF)
    4. Attempt zone match from zones table for zone_type, zone_high, zone_low
    5. Compute derived fields (is_winner, pnl_r, reached_2r, reached_3r,
       minutes_to_r1, exit_reason, outcome_method)
    6. INSERT into j_trades_m5_r_win with ON CONFLICT DO UPDATE

No simulation logic -- this is a pure consolidation/denormalization step.

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
from psycopg2.extras import execute_values, RealDictCursor, Json

# Self-contained imports from shared db_config
_PROC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROC_DIR))
from db_config import (
    DB_CONFIG, SOURCE_TABLE, J_M1_BARS_TABLE, J_M5_ATR_STOP_TABLE,
    J_TRADES_M5_R_WIN_TABLE, BATCH_INSERT_SIZE, VERBOSE,
    JOURNAL_SYMBOL_COL, JOURNAL_DATE_COL, EOD_CUTOFF
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
        td1 = timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
        td2 = timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
        diff = td2 - td1
        return max(0, int(diff.total_seconds() / 60))
    except Exception:
        return None


# =============================================================================
# CALCULATOR CLASS
# =============================================================================

class JTradesM5RWinCalculator:
    """
    Consolidates journal_trades + j_m5_atr_stop into j_trades_m5_r_win.

    This is a denormalization processor -- no simulation logic.
    It JOINs source tables, fetches EOD prices from j_m1_bars,
    attempts zone matching from the zones table, computes derived
    fields, and writes a single flat table for trade analysis.
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._eod_cache: Dict[str, Optional[float]] = {}

    def _log(self, message: str, level: str = 'info'):
        """Log a message if verbose is enabled."""
        if self.verbose or level in ('error', 'warning'):
            prefix = {'error': '!', 'warning': '?', 'info': ' ', 'debug': '  '}
            print(f"  {prefix.get(level, ' ')} {message}")

    # -----------------------------------------------------------------
    # STEP 1: Get trades needing consolidation
    # -----------------------------------------------------------------

    def get_trades_needing_consolidation(
        self, conn, limit: Optional[int] = None
    ) -> List[dict]:
        """
        Query trades from journal_trades that have j_m5_atr_stop results
        but are NOT yet in j_trades_m5_r_win.

        JOINs journal_trades (t) with j_m5_atr_stop (a) for all needed
        columns. Returns list of dicts with all source data.
        """
        query = f"""
            SELECT t.trade_id, t.{JOURNAL_DATE_COL} AS trade_date,
                   t.{JOURNAL_SYMBOL_COL} AS ticker, t.direction, t.model, t.account,
                   t.entry_price, t.entry_time, t.entry_qty,
                   t.exit_price, t.exit_time, t.exit_qty, t.exit_portions_json, t.fills_json,
                   t.pnl_dollars, t.pnl_total,
                   a.m5_atr_value, a.stop_price, a.stop_distance, a.stop_distance_pct,
                   a.r1_price, a.r2_price, a.r3_price, a.r4_price, a.r5_price,
                   a.r1_hit, a.r1_time, a.r1_bars_from_entry,
                   a.r2_hit, a.r2_time, a.r2_bars_from_entry,
                   a.r3_hit, a.r3_time, a.r3_bars_from_entry,
                   a.r4_hit, a.r4_time, a.r4_bars_from_entry,
                   a.r5_hit, a.r5_time, a.r5_bars_from_entry,
                   a.stop_hit, a.stop_time AS stop_hit_time,
                   a.stop_bars_from_entry AS stop_hit_bars_from_entry,
                   a.max_r, a.result AS atr_result
            FROM {SOURCE_TABLE} t
            INNER JOIN {J_M5_ATR_STOP_TABLE} a ON t.trade_id = a.trade_id
            WHERE NOT EXISTS (
                SELECT 1 FROM {J_TRADES_M5_R_WIN_TABLE} w
                WHERE w.trade_id = t.trade_id
            )
            ORDER BY t.{JOURNAL_DATE_COL}, t.entry_time
        """

        if limit:
            query += f" LIMIT {limit}"

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()

        self._log(f"Found {len(rows)} trades needing consolidation")
        return [dict(r) for r in rows]

    # -----------------------------------------------------------------
    # STEP 2: Fetch EOD price from j_m1_bars
    # -----------------------------------------------------------------

    def get_eod_price(
        self, conn, ticker: str, trade_date: date
    ) -> Optional[float]:
        """
        Get the last M1 bar close price from j_m1_bars before EOD_CUTOFF.

        Uses a per-session cache to avoid duplicate queries for the same
        ticker/date combination.
        """
        cache_key = f"{ticker}_{trade_date}"

        if cache_key in self._eod_cache:
            return self._eod_cache[cache_key]

        eod_cutoff_str = EOD_CUTOFF.strftime('%H:%M:%S')

        query = f"""
            SELECT close
            FROM {J_M1_BARS_TABLE}
            WHERE ticker = %s AND bar_date = %s AND bar_time <= %s
            ORDER BY bar_time DESC
            LIMIT 1
        """

        with conn.cursor() as cur:
            cur.execute(query, (ticker, trade_date, eod_cutoff_str))
            row = cur.fetchone()

        eod_price = _safe_float(row[0]) if row else None
        self._eod_cache[cache_key] = eod_price

        return eod_price

    # -----------------------------------------------------------------
    # STEP 3: Fetch zone info from zones table
    # -----------------------------------------------------------------

    def get_zone_for_trade(
        self, conn, ticker: str, trade_date: date, entry_price: float
    ) -> Optional[dict]:
        """
        Try to find a matching zone from the zones table for this trade.

        Matches on ticker, date, and entry_price falling within zone_low..zone_high.
        Returns the highest-scored zone with optional setup_type from the setups table.
        Returns None if no zone matches.
        """
        if entry_price is None:
            return None

        query = """
            SELECT z.zone_id, z.zone_high, z.zone_low, s.setup_type
            FROM zones z
            LEFT JOIN setups s ON z.date = s.date AND z.zone_id = s.zone_id
            WHERE z.ticker = %s AND z.date = %s
              AND z.zone_low <= %s AND z.zone_high >= %s
            ORDER BY z.score DESC NULLS LAST
            LIMIT 1
        """

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (ticker, trade_date, entry_price, entry_price))
                row = cur.fetchone()

            if row:
                return dict(row)
        except Exception as e:
            # Zone table may not exist or have different schema; non-fatal
            logger.debug(f"Zone lookup failed for {ticker} {trade_date}: {e}")

        return None

    # -----------------------------------------------------------------
    # STEP 4: Build consolidated row with derived fields
    # -----------------------------------------------------------------

    def build_consolidated_row(
        self, trade_row: dict, eod_price: Optional[float],
        zone_info: Optional[dict]
    ) -> dict:
        """
        Build a dict with all j_trades_m5_r_win columns from source data
        plus derived fields.

        Derived fields:
        - is_winner: atr_result == 'WIN'
        - outcome: atr_result (WIN/LOSS)
        - exit_reason: STOP_HIT / R5_HIT / EOD_WIN / EOD_LOSS
        - pnl_r: computed from actual exit if available
        - reached_2r / reached_3r: convenience booleans
        - minutes_to_r1: time difference from entry to R1 hit
        - zone_type, zone_high, zone_low: from zone lookup
        - outcome_method: 'M5_ATR'
        """
        # --- Source fields ---
        trade_id = trade_row['trade_id']
        trade_date = trade_row['trade_date']
        ticker = trade_row['ticker']
        direction = trade_row['direction']
        model = trade_row.get('model')
        account = trade_row.get('account')

        entry_price = _safe_float(trade_row['entry_price'])
        entry_time = trade_row['entry_time']
        entry_qty = _safe_int(trade_row.get('entry_qty'))

        # Actual exit data from journal_trades
        exit_price = _safe_float(trade_row.get('exit_price'))
        exit_time = trade_row.get('exit_time')
        exit_qty = _safe_int(trade_row.get('exit_qty'))
        exit_portions_json = trade_row.get('exit_portions_json')
        fills_json = trade_row.get('fills_json')

        # Actual P&L from journal_trades
        pnl_dollars = _safe_float(trade_row.get('pnl_dollars'))
        pnl_total = _safe_float(trade_row.get('pnl_total'))

        # FIFO trade sequence (may be NULL)
        trade_seq = _safe_int(trade_row.get('trade_seq'))

        # M5 ATR stop data
        m5_atr_value = _safe_float(trade_row['m5_atr_value'])
        stop_price = _safe_float(trade_row['stop_price'])
        stop_distance = _safe_float(trade_row['stop_distance'])
        stop_distance_pct = _safe_float(trade_row['stop_distance_pct'])

        # R-level prices
        r1_price = _safe_float(trade_row['r1_price'])
        r2_price = _safe_float(trade_row['r2_price'])
        r3_price = _safe_float(trade_row['r3_price'])
        r4_price = _safe_float(trade_row['r4_price'])
        r5_price = _safe_float(trade_row['r5_price'])

        # R-level hits
        r1_hit = _safe_bool(trade_row['r1_hit'])
        r1_time = trade_row['r1_time']
        r1_bars = _safe_int(trade_row['r1_bars_from_entry'])

        r2_hit = _safe_bool(trade_row['r2_hit'])
        r2_time = trade_row['r2_time']
        r2_bars = _safe_int(trade_row['r2_bars_from_entry'])

        r3_hit = _safe_bool(trade_row['r3_hit'])
        r3_time = trade_row['r3_time']
        r3_bars = _safe_int(trade_row['r3_bars_from_entry'])

        r4_hit = _safe_bool(trade_row['r4_hit'])
        r4_time = trade_row['r4_time']
        r4_bars = _safe_int(trade_row['r4_bars_from_entry'])

        r5_hit = _safe_bool(trade_row['r5_hit'])
        r5_time = trade_row['r5_time']
        r5_bars = _safe_int(trade_row['r5_bars_from_entry'])

        # Stop hit
        stop_hit = _safe_bool(trade_row['stop_hit'])
        stop_hit_time = trade_row.get('stop_hit_time')
        stop_hit_bars = _safe_int(trade_row.get('stop_hit_bars_from_entry'))

        # Source outcome from j_m5_atr_stop
        max_r = _safe_int(trade_row['max_r']) or -1
        atr_result = trade_row['atr_result']

        # --- DERIVED FIELDS ---

        # Outcome and winner flag
        outcome = atr_result  # WIN or LOSS
        is_winner = (atr_result == 'WIN')
        max_r_achieved = max_r

        # Exit reason with EOD_WIN/EOD_LOSS distinction
        if stop_hit:
            exit_reason = 'STOP_HIT'
        elif r5_hit:
            exit_reason = 'R5_HIT'
        elif is_winner and not stop_hit and not r5_hit:
            exit_reason = 'EOD_WIN'
        else:
            exit_reason = 'EOD_LOSS'

        # pnl_r: computed from actual exit if available
        pnl_r = None
        if exit_price is not None and entry_price is not None and stop_distance and stop_distance > 0:
            if direction == 'LONG':
                pnl_r = round((exit_price - entry_price) / stop_distance, 2)
            elif direction == 'SHORT':
                pnl_r = round((entry_price - exit_price) / stop_distance, 2)
        else:
            # Fallback to max_r from ATR stop analysis
            pnl_r = float(max_r) if max_r is not None else None

        # Convenience flags
        reached_2r = r2_hit
        reached_3r = r3_hit

        # Minutes to R1
        minutes_to_r1 = _minutes_between(entry_time, r1_time) if r1_hit else None

        # Zone info (may be None if no match found)
        zone_type = None
        zone_high = None
        zone_low = None
        if zone_info:
            zone_type = zone_info.get('setup_type')
            zone_high = _safe_float(zone_info.get('zone_high'))
            zone_low = _safe_float(zone_info.get('zone_low'))

        # Outcome method
        outcome_method = 'M5_ATR'

        return {
            'trade_id': trade_id,
            'trade_date': trade_date,
            'ticker': ticker,
            'direction': direction,
            'model': model,
            'zone_type': zone_type,
            'account': account,
            'zone_high': zone_high,
            'zone_low': zone_low,
            'entry_price': entry_price,
            'entry_time': entry_time,
            'entry_qty': entry_qty,
            'trade_seq': trade_seq,
            'exit_price': exit_price,
            'exit_time': exit_time,
            'exit_qty': exit_qty,
            'exit_portions_json': exit_portions_json,
            'fills_json': fills_json,
            'pnl_dollars': pnl_dollars,
            'pnl_total': pnl_total,
            'm5_atr_value': m5_atr_value,
            'stop_price': stop_price,
            'stop_distance': stop_distance,
            'stop_distance_pct': stop_distance_pct,
            'r1_price': r1_price,
            'r2_price': r2_price,
            'r3_price': r3_price,
            'r4_price': r4_price,
            'r5_price': r5_price,
            'r1_hit': r1_hit,
            'r1_time': r1_time,
            'r1_bars_from_entry': r1_bars,
            'r2_hit': r2_hit,
            'r2_time': r2_time,
            'r2_bars_from_entry': r2_bars,
            'r3_hit': r3_hit,
            'r3_time': r3_time,
            'r3_bars_from_entry': r3_bars,
            'r4_hit': r4_hit,
            'r4_time': r4_time,
            'r4_bars_from_entry': r4_bars,
            'r5_hit': r5_hit,
            'r5_time': r5_time,
            'r5_bars_from_entry': r5_bars,
            'stop_hit': stop_hit,
            'stop_hit_time': stop_hit_time,
            'stop_hit_bars_from_entry': stop_hit_bars,
            'max_r_achieved': max_r_achieved,
            'outcome': outcome,
            'exit_reason': exit_reason,
            'is_winner': is_winner,
            'pnl_r': pnl_r,
            'outcome_method': outcome_method,
            'eod_price': eod_price,
            'reached_2r': reached_2r,
            'reached_3r': reached_3r,
            'minutes_to_r1': minutes_to_r1,
        }

    # -----------------------------------------------------------------
    # STEP 5: INSERT consolidated rows
    # -----------------------------------------------------------------

    def insert_results(self, conn, rows: List[dict]) -> int:
        """
        Insert consolidated rows into j_trades_m5_r_win table.

        Uses execute_values with ON CONFLICT (trade_id) DO UPDATE SET
        to handle re-runs gracefully.
        """
        if not rows:
            return 0

        # Column order for INSERT
        columns = [
            'trade_id', 'trade_date', 'ticker', 'direction', 'model',
            'zone_type', 'account', 'zone_high', 'zone_low',
            'entry_price', 'entry_time', 'entry_qty', 'trade_seq',
            'exit_price', 'exit_time', 'exit_qty', 'exit_portions_json', 'fills_json',
            'pnl_dollars', 'pnl_total',
            'm5_atr_value', 'stop_price', 'stop_distance', 'stop_distance_pct',
            'r1_price', 'r2_price', 'r3_price', 'r4_price', 'r5_price',
            'r1_hit', 'r1_time', 'r1_bars_from_entry',
            'r2_hit', 'r2_time', 'r2_bars_from_entry',
            'r3_hit', 'r3_time', 'r3_bars_from_entry',
            'r4_hit', 'r4_time', 'r4_bars_from_entry',
            'r5_hit', 'r5_time', 'r5_bars_from_entry',
            'stop_hit', 'stop_hit_time', 'stop_hit_bars_from_entry',
            'max_r_achieved', 'outcome', 'exit_reason',
            'is_winner', 'pnl_r', 'outcome_method',
            'eod_price', 'reached_2r', 'reached_3r', 'minutes_to_r1',
        ]

        # Columns to update on conflict (everything except trade_id and calculated_at)
        update_columns = [c for c in columns if c != 'trade_id']

        columns_str = ', '.join(columns)
        update_str = ',\n                '.join(
            f"{c} = EXCLUDED.{c}" for c in update_columns
        )

        query = f"""
            INSERT INTO {J_TRADES_M5_R_WIN_TABLE} (
                {columns_str}
            ) VALUES %s
            ON CONFLICT (trade_id) DO UPDATE SET
                {update_str},
                updated_at = NOW()
        """

        # Convert dicts to tuples in column order
        # Wrap dict/list values with Json() for JSONB columns (e.g. exit_portions_json)
        values = []
        for row in rows:
            vals = []
            for c in columns:
                v = row[c]
                if isinstance(v, (dict, list)):
                    v = Json(v)
                vals.append(v)
            values.append(tuple(vals))

        with conn.cursor() as cur:
            execute_values(cur, query, values, page_size=BATCH_INSERT_SIZE)

        return len(values)

    # -----------------------------------------------------------------
    # STATUS
    # -----------------------------------------------------------------

    def get_status(self, conn) -> Dict:
        """Get current table status for the --status CLI flag."""
        status = {}

        with conn.cursor() as cur:
            # Total trades in consolidated table
            try:
                cur.execute(f"SELECT COUNT(*) FROM {J_TRADES_M5_R_WIN_TABLE}")
                status['total_trades'] = cur.fetchone()[0]
            except psycopg2.errors.UndefinedTable:
                conn.rollback()
                status['total_trades'] = 'TABLE NOT FOUND'
                return status

            # Win/Loss breakdown
            cur.execute(f"""
                SELECT outcome, COUNT(*)
                FROM {J_TRADES_M5_R_WIN_TABLE}
                GROUP BY outcome
                ORDER BY outcome
            """)
            breakdown = {}
            for row in cur.fetchall():
                breakdown[row[0]] = row[1]
            status['win_count'] = breakdown.get('WIN', 0)
            status['loss_count'] = breakdown.get('LOSS', 0)

            # Date range
            cur.execute(f"""
                SELECT MIN(trade_date), MAX(trade_date)
                FROM {J_TRADES_M5_R_WIN_TABLE}
            """)
            row = cur.fetchone()
            status['min_date'] = row[0]
            status['max_date'] = row[1]

            # Unique tickers
            cur.execute(f"SELECT COUNT(DISTINCT ticker) FROM {J_TRADES_M5_R_WIN_TABLE}")
            status['unique_tickers'] = cur.fetchone()[0]

            # Source table counts
            cur.execute(f"SELECT COUNT(*) FROM {SOURCE_TABLE}")
            status['journal_trades_count'] = cur.fetchone()[0]

            cur.execute(f"SELECT COUNT(*) FROM {J_M5_ATR_STOP_TABLE}")
            status['m5_atr_stop_count'] = cur.fetchone()[0]

            # Pending count (trades with ATR stop results but not yet consolidated)
            cur.execute(f"""
                SELECT COUNT(*) FROM {J_M5_ATR_STOP_TABLE} a
                WHERE NOT EXISTS (
                    SELECT 1 FROM {J_TRADES_M5_R_WIN_TABLE} w
                    WHERE w.trade_id = a.trade_id
                )
            """)
            status['pending_count'] = cur.fetchone()[0]

            # Exit reason breakdown
            cur.execute(f"""
                SELECT exit_reason, COUNT(*)
                FROM {J_TRADES_M5_R_WIN_TABLE}
                GROUP BY exit_reason
                ORDER BY COUNT(*) DESC
            """)
            status['exit_reasons'] = {row[0]: row[1] for row in cur.fetchall()}

            # Account breakdown
            cur.execute(f"""
                SELECT account, COUNT(*)
                FROM {J_TRADES_M5_R_WIN_TABLE}
                WHERE account IS NOT NULL
                GROUP BY account
                ORDER BY COUNT(*) DESC
            """)
            status['accounts'] = {row[0]: row[1] for row in cur.fetchall()}

        return status

    # -----------------------------------------------------------------
    # MAIN ENTRY POINT
    # -----------------------------------------------------------------

    def run_batch_calculation(
        self,
        limit: Optional[int] = None,
        dry_run: bool = False,
        callback=None
    ) -> Dict:
        """
        Main entry point: consolidate trades from source tables.

        For each trade:
        1. Fetch EOD price from j_m1_bars
        2. Fetch zone info from zones table
        3. Build consolidated row with derived fields
        4. Batch insert at end

        Args:
            limit: Maximum number of trades to process (None = all)
            dry_run: If True, compute but don't write to DB
            callback: Optional callback for progress messages

        Returns:
            Dict with processing statistics
        """
        start_time = datetime.now()

        stats = {
            'total_source': 0,
            'processed': 0,
            'inserted': 0,
            'errors': 0,
            'skipped': 0,
            'win_count': 0,
            'loss_count': 0,
            'error_details': [],
        }

        def _emit(msg):
            print(msg)
            if callback:
                callback(msg)

        _emit("=" * 60)
        _emit("Journal Trades M5 R-Win Consolidator v1.0")
        _emit("=" * 60)
        _emit(f"Source: {SOURCE_TABLE} + {J_M5_ATR_STOP_TABLE}")
        _emit(f"Target: {J_TRADES_M5_R_WIN_TABLE}")
        _emit(f"Dry Run: {dry_run}")
        if limit:
            _emit(f"Limit: {limit} trades")
        _emit("")

        conn = None

        try:
            # Step 1: Connect
            _emit("[1/4] Connecting to Supabase...")
            conn = psycopg2.connect(**DB_CONFIG)
            conn.autocommit = False
            _emit("  Connected successfully")

            # Step 2: Query trades needing consolidation
            _emit("\n[2/4] Querying trades needing consolidation...")
            trades = self.get_trades_needing_consolidation(conn, limit)
            stats['total_source'] = len(trades)

            if not trades:
                _emit("\n  No new trades to consolidate. Exiting.")
                stats['execution_time_seconds'] = round(
                    (datetime.now() - start_time).total_seconds(), 2
                )
                return stats

            # Step 3: Build consolidated rows
            _emit(f"\n[3/4] Building consolidated rows ({len(trades)} trades)...")
            rows = []

            for i, trade in enumerate(trades, 1):
                trade_id = trade['trade_id']
                ticker = trade['ticker']
                trade_date = trade['trade_date']
                entry_price = _safe_float(trade['entry_price'])

                try:
                    # Fetch EOD price
                    eod_price = self.get_eod_price(conn, ticker, trade_date)

                    # Fetch zone info
                    zone_info = self.get_zone_for_trade(
                        conn, ticker, trade_date, entry_price
                    )

                    # Build consolidated row
                    row = self.build_consolidated_row(trade, eod_price, zone_info)
                    rows.append(row)
                    stats['processed'] += 1

                    # Track outcome counts
                    if row['is_winner']:
                        stats['win_count'] += 1
                    else:
                        stats['loss_count'] += 1

                    if self.verbose:
                        outcome_str = row['outcome']
                        exit_str = row['exit_reason']
                        pnl_r_str = f"{row['pnl_r']:.2f}R" if row['pnl_r'] is not None else "N/A"
                        _emit(
                            f"  [{i}/{len(trades)}] {ticker} {trade_date} "
                            f"{row['direction']} -> {outcome_str} ({exit_str}) "
                            f"pnl_r={pnl_r_str}"
                        )

                except Exception as e:
                    stats['errors'] += 1
                    stats['error_details'].append(f"{trade_id}: {str(e)}")
                    logger.error(f"Error consolidating {trade_id}: {e}")
                    _emit(f"  [{i}/{len(trades)}] {trade_id}: ERROR - {e}")

            # Summary before insert
            _emit(f"\n  Consolidated: {stats['processed']} trades")
            _emit(f"  WIN: {stats['win_count']}, LOSS: {stats['loss_count']}")
            if stats['errors']:
                _emit(f"  Errors: {stats['errors']}")

            # Step 4: Insert
            if dry_run:
                _emit(f"\n[4/4] DRY RUN - skipping database write")
                if rows:
                    sample = rows[0]
                    _emit(f"\n  Sample row:")
                    _emit(f"    trade_id:    {sample['trade_id']}")
                    _emit(f"    ticker:      {sample['ticker']}")
                    _emit(f"    trade_date:  {sample['trade_date']}")
                    _emit(f"    direction:   {sample['direction']}")
                    _emit(f"    outcome:     {sample['outcome']}")
                    _emit(f"    exit_reason: {sample['exit_reason']}")
                    _emit(f"    is_winner:   {sample['is_winner']}")
                    _emit(f"    pnl_r:       {sample['pnl_r']}")
                    _emit(f"    eod_price:   {sample['eod_price']}")
                    _emit(f"    zone_type:   {sample['zone_type']}")
                    _emit(f"    minutes_to_r1: {sample['minutes_to_r1']}")
            else:
                _emit(f"\n[4/4] Inserting {len(rows)} rows into {J_TRADES_M5_R_WIN_TABLE}...")
                inserted = self.insert_results(conn, rows)
                conn.commit()
                stats['inserted'] = inserted
                _emit(f"  Inserted: {inserted} rows")

        except KeyboardInterrupt:
            _emit("\n  Interrupted by user")
            if conn:
                conn.rollback()
            raise

        except Exception as e:
            stats['error_details'].append(f"Fatal: {str(e)}")
            logger.error(f"Batch consolidation failed: {e}")
            _emit(f"\n  FATAL ERROR: {e}")
            if conn:
                conn.rollback()
            raise

        finally:
            if conn:
                conn.close()
            self._eod_cache.clear()

        elapsed = (datetime.now() - start_time).total_seconds()
        stats['execution_time_seconds'] = round(elapsed, 2)
        return stats
