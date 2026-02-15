#!/usr/bin/env python3
"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
M1 Post-Trade Indicator Processor v2 - Runner
XIII Trading LLC
================================================================================

CLI entry point for the m1_post_trade_indicator_2 processor.
Populates 25 M1 indicator bars after each trade entry.

Usage:
    python runner.py                  # Full population run
    python runner.py --dry-run        # Preview without saving
    python runner.py --limit 50       # Process 50 trades
    python runner.py --schema         # Create database table
    python runner.py --status         # Show pipeline status
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
    DB_CONFIG, SOURCE_TABLES, TARGET_TABLE, POST_TRADE_BARS,
    SCHEMA_DIR, MODULE_DIR
)
from populator import M1PostTradeIndicatorPopulator


# =============================================================================
# SCHEMA CREATION
# =============================================================================

def run_schema():
    """Create the m1_post_trade_indicator_2 table from SQL schema file."""
    schema_file = SCHEMA_DIR / "m1_post_trade_indicator_2.sql"

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
# STATUS DISPLAY
# =============================================================================

def show_status():
    """Display pipeline status - what needs processing."""
    print(f"\n{'='*70}")
    print(f"M1 POST-TRADE INDICATOR PROCESSOR - STATUS")
    print(f"{'='*70}")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        populator = M1PostTradeIndicatorPopulator(verbose=False)
        populator.show_status(conn)
        conn.close()

    except Exception as e:
        print(f"\n  Status unavailable: {e}")


# =============================================================================
# INFO DISPLAY
# =============================================================================

def show_info():
    """Display processor information and current stats."""
    print(f"\n{'='*70}")
    print(f"M1 POST-TRADE INDICATOR PROCESSOR v2")
    print(f"{'='*70}")
    print(f"\n  Purpose: Store {POST_TRADE_BARS} M1 indicator bars after each trade entry")
    print(f"           for post-trade analysis (how indicators behave after entry)")
    print(f"\n  Source Tables:")
    for key, table in SOURCE_TABLES.items():
        print(f"    {key:<15} -> {table}")
    print(f"  Target Table:  {TARGET_TABLE}")
    print(f"\n  Logic:")
    print(f"    1. For each trade in trades_2 with an m5_atr_stop_2 outcome")
    print(f"    2. Fetch {POST_TRADE_BARS} M1 bars starting at entry candle")
    print(f"    3. Assign bar_sequence 0 (entry candle) to {POST_TRADE_BARS - 1}")
    print(f"    4. Stamp trade outcome on every row")
    print(f"    5. Insert {POST_TRADE_BARS} rows per trade")
    print(f"\n  Note:")
    print(f"    Entry candle IS included (bar_sequence 0) because this analyzes")
    print(f"    what happens AFTER the trade, including how the entry candle closed.")

    show_status()


# =============================================================================
# MAIN CALCULATION
# =============================================================================

def run_calculation(limit=None, dry_run=False, verbose=True):
    """Run the population calculation."""
    print(f"\n{'='*70}")
    print(f"M1 POST-TRADE INDICATOR POPULATION")
    print(f"{'='*70}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    if limit:
        print(f"  Limit: {limit} trades")
    print(f"  Bars per trade: {POST_TRADE_BARS}")
    print(f"  Target: {TARGET_TABLE}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    populator = M1PostTradeIndicatorPopulator(verbose=verbose)
    stats = populator.run(limit=limit, dry_run=dry_run)

    print(f"\n{'='*70}")
    print(f"POPULATION COMPLETE")
    print(f"{'='*70}")
    print(f"  Eligible trades:  {stats['total_eligible']}")
    print(f"  Trades processed: {stats['trades_processed']}")
    print(f"  No bars:          {stats['trades_skipped_no_bars']}")
    print(f"  Partial bars:     {stats['trades_partial_bars']}")
    print(f"  Rows built:       {stats['rows_built']}")
    print(f"  Rows inserted:    {stats['rows_inserted']}")
    print(f"  Errors:           {stats['errors']}")

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
        description=f'Populate m1_post_trade_indicator_2 with {POST_TRADE_BARS}-bar post-entry indicator windows',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  python runner.py              # Full population run
  python runner.py --dry-run    # Preview without saving
  python runner.py --limit 50   # Process 50 trades
  python runner.py --schema     # Create database table
  python runner.py --status     # Show pipeline status
  python runner.py --info       # Show processor information

Output:
  Results are written to the m1_post_trade_indicator_2 table in Supabase.
  Each trade gets {POST_TRADE_BARS} rows (bar_sequence 0-{POST_TRADE_BARS - 1}).
  bar_sequence 0 = entry candle, {POST_TRADE_BARS - 1} = 25th bar after entry.
  Trades without m5_atr_stop_2 outcomes are SKIPPED.
        """
    )

    parser.add_argument('--dry-run', action='store_true',
                        help='Process without saving to database')
    parser.add_argument('--limit', type=int, metavar='N',
                        help='Maximum number of trades to process')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('--schema', action='store_true',
                        help='Run schema creation only (create table)')
    parser.add_argument('--status', action='store_true',
                        help='Show pipeline status (trades pending/processed)')
    parser.add_argument('--info', action='store_true',
                        help='Display information about the processor')

    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.info:
        show_info()
        sys.exit(0)

    if args.status:
        show_status()
        sys.exit(0)

    if args.schema:
        success = run_schema()
        sys.exit(0 if success else 1)

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
