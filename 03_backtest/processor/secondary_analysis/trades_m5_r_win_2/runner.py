#!/usr/bin/env python3
"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
Trades M5 R Win Consolidation Processor v2 - Runner
XIII Trading LLC
================================================================================

CLI entry point for the trades consolidation processor.
Joins trades_2 + m5_atr_stop_2 + m1_bars_2 into trades_m5_r_win_2.

Usage:
    python runner.py                  # Full consolidation run
    python runner.py --dry-run        # Preview without saving
    python runner.py --limit 50       # Process 50 trades
    python runner.py --schema         # Create database table
    python runner.py --info           # Show processor information

Version: 1.0.0
================================================================================
"""

import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime

import psycopg2

# Self-contained imports
from config import (
    DB_CONFIG, SOURCE_TABLES, TARGET_TABLE, OUTCOME_METHOD,
    SCHEMA_DIR, MODULE_DIR
)
from calculator import TradesM5RWin2Calculator


# =============================================================================
# SCHEMA CREATION
# =============================================================================

def run_schema():
    """Create the trades_m5_r_win_2 table from SQL schema file."""
    schema_file = SCHEMA_DIR / "trades_m5_r_win_2.sql"

    if not schema_file.exists():
        print(f"  ERROR: Schema file not found: {schema_file}")
        return False

    print(f"\n{'='*70}")
    print(f"SCHEMA CREATION: {TARGET_TABLE}")
    print(f"{'='*70}")
    print(f"  Schema file: {schema_file}")

    try:
        sql = schema_file.read_text()
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True

        with conn.cursor() as cur:
            cur.execute(sql)

        conn.close()

        print(f"  Schema created successfully")
        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        return False


# =============================================================================
# INFO DISPLAY
# =============================================================================

def show_info():
    """Display processor information and current stats."""
    print(f"\n{'='*70}")
    print(f"TRADES M5 R WIN CONSOLIDATION PROCESSOR v2")
    print(f"{'='*70}")
    print(f"\n  Purpose: Consolidate trades_2 + m5_atr_stop_2 into")
    print(f"           a single denormalized table for 11_trade_reel")
    print(f"\n  Source Tables:")
    for key, table in SOURCE_TABLES.items():
        print(f"    {key:<15} -> {table}")
    print(f"  Target Table:  {TARGET_TABLE}")
    print(f"  Outcome Method: {OUTCOME_METHOD}")

    # Get current stats
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            # Target table count
            try:
                cur.execute(f"SELECT COUNT(*) FROM {TARGET_TABLE}")
                target_count = cur.fetchone()[0]
            except psycopg2.errors.UndefinedTable:
                conn.rollback()
                target_count = "TABLE NOT FOUND"

            # Source counts
            cur.execute(f"SELECT COUNT(*) FROM {SOURCE_TABLES['trades']}")
            trades_count = cur.fetchone()[0]

            cur.execute(f"SELECT COUNT(*) FROM {SOURCE_TABLES['m5_atr_stop']}")
            m5_count = cur.fetchone()[0]

            # Pending count
            if isinstance(target_count, int):
                cur.execute(f"""
                    SELECT COUNT(*) FROM {SOURCE_TABLES['m5_atr_stop']} m5
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {TARGET_TABLE} tw
                        WHERE tw.trade_id = m5.trade_id
                    )
                """)
                pending = cur.fetchone()[0]
            else:
                pending = "N/A"

        conn.close()

        print(f"\n  Current Stats:")
        print(f"    trades_2:            {trades_count} entries")
        print(f"    m5_atr_stop_2:       {m5_count} rows")
        print(f"    trades_m5_r_win_2:   {target_count} rows")
        print(f"    Pending:             {pending}")

    except Exception as e:
        print(f"\n  Stats unavailable: {e}")


# =============================================================================
# MAIN CALCULATION
# =============================================================================

def run_calculation(limit=None, dry_run=False, verbose=True):
    """Run the consolidation calculation."""
    print(f"\n{'='*70}")
    print(f"TRADES M5 R WIN CONSOLIDATION")
    print(f"{'='*70}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    if limit:
        print(f"  Limit: {limit} trades")
    print(f"  Target: {TARGET_TABLE}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    calculator = TradesM5RWin2Calculator(verbose=verbose)
    stats = calculator.run_batch_consolidation(limit=limit, dry_run=dry_run)

    print(f"\n{'='*70}")
    print(f"CONSOLIDATION COMPLETE")
    print(f"{'='*70}")
    print(f"  Source trades:  {stats['total_source']}")
    print(f"  Processed:      {stats['processed']}")
    print(f"  Inserted:       {stats['inserted']}")
    print(f"  Errors:         {stats['errors']}")

    return stats['errors'] == 0


# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Consolidate trades_2 + m5_atr_stop_2 into trades_m5_r_win_2 for trade_reel',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python runner.py              # Full consolidation run
  python runner.py --dry-run    # Preview without saving
  python runner.py --limit 50   # Process 50 trades
  python runner.py --schema     # Create database table
  python runner.py --info       # Show processor information

Output:
  Results are written to the trades_m5_r_win_2 table in Supabase.
  Each trade gets 1 row with all fields needed by 11_trade_reel.
        """
    )

    parser.add_argument('--dry-run', action='store_true',
                        help='Consolidate without saving to database')
    parser.add_argument('--limit', type=int, metavar='N',
                        help='Maximum number of trades to process')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('--schema', action='store_true',
                        help='Run schema creation only (create trades_m5_r_win_2 table)')
    parser.add_argument('--info', action='store_true',
                        help='Display information about the consolidation processor')

    args = parser.parse_args()

    setup_logging(args.verbose)

    # Handle --info flag
    if args.info:
        show_info()
        sys.exit(0)

    # Handle --schema flag
    if args.schema:
        success = run_schema()
        sys.exit(0 if success else 1)

    # Run consolidation
    try:
        success = run_calculation(
            limit=args.limit,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)

    except Exception as e:
        print(f"\nFATAL: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
