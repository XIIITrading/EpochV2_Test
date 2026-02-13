#!/usr/bin/env python3
"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
M1 ATR Stop Processor v2 - CLI Runner
XIII Trading LLC
================================================================================

Command-line interface for running the M1 ATR Stop calculation.

Usage:
    python runner.py              # Full batch run
    python runner.py --dry-run    # Calculate but don't save
    python runner.py --limit 50   # Process max 50 trades
    python runner.py --verbose    # Detailed logging
    python runner.py --schema     # Run schema creation only
    python runner.py --info       # Show processor information

Version: 1.0.0
================================================================================
"""

import argparse
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add module to path
sys.path.insert(0, str(Path(__file__).parent))

from config import DB_CONFIG, SCHEMA_DIR, R_LEVELS, EOD_CUTOFF
from calculator import M1AtrStopCalculator


def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def run_schema():
    """Execute the schema SQL to create the m1_atr_stop_2 table."""
    import psycopg2

    schema_file = SCHEMA_DIR / "m1_atr_stop_2.sql"

    if not schema_file.exists():
        print(f"ERROR: Schema file not found: {schema_file}")
        return False

    print("=" * 60)
    print("M1 ATR Stop v2 - Schema Creation")
    print("=" * 60)

    try:
        print("\n[1/3] Reading schema file...")
        with open(schema_file, 'r') as f:
            schema_sql = f.read()
        print(f"  Read {len(schema_sql)} bytes")

        print("\n[2/3] Connecting to Supabase...")
        conn = psycopg2.connect(**DB_CONFIG)
        print("  Connected successfully")

        print("\n[3/3] Executing schema...")
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
        print("  Schema created successfully")

        conn.close()
        return True

    except Exception as e:
        print(f"\nERROR: {e}")
        return False


def show_info():
    """Display information about the M1 ATR Stop processor."""
    print()
    print("=" * 60)
    print("M1 ATR STOP PROCESSOR v2")
    print("=" * 60)
    print()
    print("PURPOSE:")
    print("  Evaluate trades using M1 ATR(14) as the stop distance (1R)")
    print("  and track R-multiple targets (1R-5R) to determine win/loss outcomes.")
    print()
    print("STOP CONFIGURATION:")
    print("  ATR Source:     m1_indicator_bars_2.atr_m1 (pre-computed)")
    print("  ATR Period:     14")
    print("  Multiplier:     1.0x (raw ATR, no multiplier)")
    print("  Stop Trigger:   Close-based (M1 bar close beyond stop)")
    print()
    print("R-LEVEL TARGETS:")
    for r in R_LEVELS:
        print(f"  R{r}: entry +/- ({r} x stop_distance)")
    print()
    print("WIN/LOSS RULES:")
    print("  WIN:  R1 target hit before stop (price high/low touches R1+)")
    print("  LOSS: Stop triggered before R1 (M1 close beyond stop level)")
    print("  LOSS: Neither R1 nor stop by 15:30 (no R1 = LOSS always)")
    print()
    print("SAME-CANDLE CONFLICT:")
    print("  If M1 bar shows R-level hit AND close beyond stop => LOSS")
    print("  (stop takes priority, R-level hits on that bar invalidated)")
    print()
    print("MAX_R TRACKING:")
    print("  Highest R-level (5->4->3->2->1) hit before stop_time.")
    print("  0 if no R-levels reached.")
    print()
    print(f"EOD CUTOFF: {EOD_CUTOFF}")
    print()
    print("DATA SOURCES (v2 tables):")
    print("  - trades_2 (trade metadata: entry-only detection)")
    print("  - m1_bars_2 (M1 candle data for bar-by-bar simulation)")
    print("  - m1_indicator_bars_2 (pre-computed atr_m1 at entry candle)")
    print()
    print("TARGET TABLE:")
    print("  - m1_atr_stop_2 (1 row per trade)")
    print()
    print("=" * 60)


def run_calculation(args):
    """Run the M1 ATR Stop calculation."""
    print()
    print("=" * 60)
    print("EPOCH TRADING SYSTEM")
    print("M1 ATR Stop Calculator v1.0.0")
    print("=" * 60)
    print()
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'FULL RUN'}")
    if args.limit:
        print(f"Limit: {args.limit} trades")
    print()

    # Create calculator
    calculator = M1AtrStopCalculator(verbose=args.verbose)

    # Run calculation
    results = calculator.run_batch_calculation(
        limit=args.limit,
        dry_run=args.dry_run
    )

    # Print results summary
    print()
    print("=" * 60)
    print("EXECUTION SUMMARY")
    print("=" * 60)
    print(f"  Trades Processed:  {results['trades_processed']}")
    print(f"  Trades Skipped:    {results['trades_skipped']}")
    print(f"  Records Created:   {results['records_created']}")
    print(f"  Execution Time:    {results['execution_time_seconds']:.1f}s")

    if results['errors']:
        print()
        print("ERRORS:")
        print("-" * 40)
        for err in results['errors'][:10]:
            print(f"  ! {err}")
        if len(results['errors']) > 10:
            print(f"  ... and {len(results['errors']) - 10} more errors")

    print()
    print("=" * 60)
    if results['errors']:
        print("COMPLETED WITH ERRORS")
    elif results['trades_processed'] == 0:
        print("NO TRADES TO PROCESS")
    else:
        print("COMPLETED SUCCESSFULLY")
    print("=" * 60)

    return len(results['errors']) == 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Calculate M1 ATR Stop outcomes using M1 ATR(14) stop and R-multiple targets (1R-5R)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python runner.py              # Full batch run
  python runner.py --dry-run    # Test without saving
  python runner.py --limit 50   # Process 50 trades
  python runner.py --schema     # Create database table
  python runner.py --info       # Show processor information

Output:
  Results are written to the m1_atr_stop_2 table in Supabase.
  Each trade gets 1 row with R-level hit tracking and outcome.
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Calculate without saving to database'
    )

    parser.add_argument(
        '--limit',
        type=int,
        metavar='N',
        help='Maximum number of trades to process'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--schema',
        action='store_true',
        help='Run schema creation only (create m1_atr_stop_2 table)'
    )

    parser.add_argument(
        '--info',
        action='store_true',
        help='Display information about the M1 ATR Stop processor'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Show info if requested
    if args.info:
        show_info()
        sys.exit(0)

    # Run schema creation if requested
    if args.schema:
        success = run_schema()
        sys.exit(0 if success else 1)

    # Run calculation
    try:
        success = run_calculation(args)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
