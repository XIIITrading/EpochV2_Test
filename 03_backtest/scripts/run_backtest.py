#!/usr/bin/env python
"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 03: BACKTEST RUNNER v4.0
CLI Backtest Runner Script - Entry Detection + Secondary Processors
XIII Trading LLC
================================================================================

Runs entry detection for a specific date using S15 bars and EPCH1-4 models.
Exports detected entries to trades_2 table.
Optionally runs secondary processors (M1 bars storage, etc.)
Designed to be called from the PyQt6 GUI via QProcess.

USAGE:
    python run_backtest.py 2026-01-20              # Run entry detection for date
    python run_backtest.py 2026-01-20 --dry-run    # Preview without DB writes
    python run_backtest.py 2026-01-20 --no-export  # Skip Supabase export
    python run_backtest.py 2026-01-20 --m1-bars    # Also fetch/store M1 bars
    python run_backtest.py 2026-01-20 --m1-atr-stop  # Run M1 ATR stop analysis
    python run_backtest.py 2026-01-20 --m5-atr-stop  # Run M5 ATR stop analysis

MODEL:
    - S15 (15-second) bar close triggers EPCH1-4 entry detection
    - No exit management (handled by secondary processors)

================================================================================
"""
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List
import argparse

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import POLYGON_API_KEY
from data.supabase_zone_loader import SupabaseZoneLoader
from data.s15_fetcher import S15Fetcher
from data.trades_exporter import export_trades
from engine.trade_simulator import TradeSimulator, EntryRecord

# Secondary processor paths
M1_BARS_PROCESSOR = Path(__file__).parent.parent / "processor" / "secondary_analysis" / "m1_bars"
M1_INDICATORS_PROCESSOR = Path(__file__).parent.parent / "processor" / "secondary_analysis" / "m1_indicator_bars_2"
M1_ATR_STOP_PROCESSOR = Path(__file__).parent.parent / "processor" / "secondary_analysis" / "m1_atr_stop_2"
M5_ATR_STOP_PROCESSOR = Path(__file__).parent.parent / "processor" / "secondary_analysis" / "m5_atr_stop_2"
TRADES_M5_R_WIN_2_PROCESSOR = Path(__file__).parent.parent / "processor" / "secondary_analysis" / "trades_m5_r_win_2"

# Indicator phase processors (run after m5_atr_stop_2 for outcomes)
M1_TRADE_INDICATOR_PROCESSOR = Path(__file__).parent.parent / "processor" / "secondary_analysis" / "m1_trade_indicator_2"
M1_RAMP_UP_INDICATOR_PROCESSOR = Path(__file__).parent.parent / "processor" / "secondary_analysis" / "m1_ramp_up_indicator_2"
M1_POST_TRADE_INDICATOR_PROCESSOR = Path(__file__).parent.parent / "processor" / "secondary_analysis" / "m1_post_trade_indicator_2"


def run_backtest_for_date(trade_date: str, dry_run: bool = False) -> List[EntryRecord]:
    """
    Run entry detection for a single date.

    Returns: List of all detected entries
    """
    all_entries = []

    # Load zones from Supabase
    print(f"\n[1/3] Loading zones for {trade_date}...")

    try:
        zone_loader = SupabaseZoneLoader(trade_date, verbose=False)
        primary_zones, secondary_zones = zone_loader.load_all_zones()
    except Exception as e:
        print(f"  ERROR: Failed to load zones: {e}")
        return all_entries

    if not primary_zones and not secondary_zones:
        print("  No zones found - skipping date")
        zone_loader.close()
        return all_entries

    # Get unique tickers
    tickers = set()
    for z in primary_zones:
        tickers.add(z.ticker)
    for z in secondary_zones:
        tickers.add(z.ticker)

    tickers = sorted(tickers)

    print(f"  Found {len(primary_zones)} primary zones, {len(secondary_zones)} secondary zones")
    print(f"  Tickers: {', '.join(tickers)}")

    # Initialize S15 fetcher
    s15_fetcher = S15Fetcher(POLYGON_API_KEY)

    # Process each ticker
    total_tickers = len(tickers)
    for idx, ticker in enumerate(tickers, 1):
        print(f"\n[2/{total_tickers + 2}] Processing {ticker} ({idx}/{total_tickers})...")

        # Get zones for this ticker
        primary = next((z for z in primary_zones if z.ticker == ticker), None)
        secondary = next((z for z in secondary_zones if z.ticker == ticker), None)

        # Convert to dict format
        primary_dict = zone_loader.get_zone_dict(primary) if primary else None
        secondary_dict = zone_loader.get_zone_dict(secondary) if secondary else None

        if primary_dict:
            print(f"  Primary Zone: ${primary_dict['zone_low']:.2f} - ${primary_dict['zone_high']:.2f}")
        if secondary_dict:
            print(f"  Secondary Zone: ${secondary_dict['zone_low']:.2f} - ${secondary_dict['zone_high']:.2f}")

        # Fetch S15 data for entry detection
        s15_bars = s15_fetcher.fetch_bars_extended(ticker, trade_date)

        if not s15_bars:
            print(f"  No S15 data available - skipping")
            continue

        # Initialize simulator (entry detection only)
        simulator = TradeSimulator(ticker=ticker, trade_date=trade_date)
        simulator.set_zones(primary_zone=primary_dict, secondary_zone=secondary_dict)

        # Process S15 bars for entry detection
        for s15_idx, s15_bar in enumerate(s15_bars):
            simulator.process_bar_entries_only(
                bar_idx=s15_idx,
                bar_time=s15_bar.timestamp,
                bar_open=s15_bar.open,
                bar_high=s15_bar.high,
                bar_low=s15_bar.low,
                bar_close=s15_bar.close
            )

        # Collect entries
        ticker_entries = simulator.get_entries()
        all_entries.extend(ticker_entries)

        print(f"  Detected {len(ticker_entries)} entries for {ticker}")

        # Show entry summary
        for entry in ticker_entries:
            print(f"    {entry.model} {entry.direction}: "
                  f"${entry.entry_price:.2f} @ {entry.entry_time.strftime('%H:%M:%S')}")

    zone_loader.close()
    return all_entries


def print_summary(entries: List[EntryRecord]):
    """Print entry detection summary."""
    if not entries:
        return

    total = len(entries)

    # By model
    by_model = {}
    for entry in entries:
        model = entry.model
        if model not in by_model:
            by_model[model] = 0
        by_model[model] += 1

    # By direction
    longs = sum(1 for e in entries if e.direction == 'LONG')
    shorts = total - longs

    # By zone type
    primary = sum(1 for e in entries if e.zone_type == 'PRIMARY')
    secondary = total - primary

    print(f"\nTotal Entries: {total}")
    print(f"Long: {longs} | Short: {shorts}")
    print(f"Primary: {primary} | Secondary: {secondary}")

    print(f"\nBy Model:")
    for model in sorted(by_model.keys()):
        print(f"  {model}: {by_model[model]} entries")


def run_m1_bars_processor():
    """Run the M1 bars secondary processor."""
    print(f"\n{'='*70}")
    print("[M1 BARS] Fetching M1 bar data (Prior Day 16:00 -> Trade Day 16:00)")
    print(f"{'='*70}")

    runner_script = M1_BARS_PROCESSOR / "m1_bars_runner.py"

    if not runner_script.exists():
        print(f"  ERROR: M1 bars runner not found: {runner_script}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(runner_script), "--verbose"],
            cwd=str(M1_BARS_PROCESSOR),
            capture_output=False,
            text=True
        )

        if result.returncode == 0:
            print(f"\n[M1 BARS] Completed successfully")
            return True
        else:
            print(f"\n[M1 BARS] Failed with exit code {result.returncode}")
            return False

    except Exception as e:
        print(f"\n[M1 BARS] Error: {e}")
        return False


def run_m1_indicators_processor():
    """Run the M1 indicator bars secondary processor."""
    print(f"\n{'='*70}")
    print("[M1 INDICATORS] Calculating M1 indicator bars from m1_bars_2")
    print(f"{'='*70}")

    runner_script = M1_INDICATORS_PROCESSOR / "runner.py"

    if not runner_script.exists():
        print(f"  ERROR: M1 indicators runner not found: {runner_script}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(runner_script), "--verbose"],
            cwd=str(M1_INDICATORS_PROCESSOR),
            capture_output=False,
            text=True
        )

        if result.returncode == 0:
            print(f"\n[M1 INDICATORS] Completed successfully")
            return True
        else:
            print(f"\n[M1 INDICATORS] Failed with exit code {result.returncode}")
            return False

    except Exception as e:
        print(f"\n[M1 INDICATORS] Error: {e}")
        return False


def run_m1_atr_stop_processor():
    """Run the M1 ATR Stop secondary processor."""
    print(f"\n{'='*70}")
    print("[M1 ATR STOP] Calculating M1 ATR stop outcomes (R-multiple targets)")
    print(f"{'='*70}")

    runner_script = M1_ATR_STOP_PROCESSOR / "runner.py"

    if not runner_script.exists():
        print(f"  ERROR: M1 ATR Stop runner not found: {runner_script}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(runner_script), "--verbose"],
            cwd=str(M1_ATR_STOP_PROCESSOR),
            capture_output=False,
            text=True
        )

        if result.returncode == 0:
            print(f"\n[M1 ATR STOP] Completed successfully")
            return True
        else:
            print(f"\n[M1 ATR STOP] Failed with exit code {result.returncode}")
            return False

    except Exception as e:
        print(f"\n[M1 ATR STOP] Error: {e}")
        return False


def run_m5_atr_stop_processor():
    """Run the M5 ATR Stop secondary processor."""
    print(f"\n{'='*70}")
    print("[M5 ATR STOP] Calculating M5 ATR stop outcomes (R-multiple targets)")
    print(f"{'='*70}")

    runner_script = M5_ATR_STOP_PROCESSOR / "runner.py"

    if not runner_script.exists():
        print(f"  ERROR: M5 ATR Stop runner not found: {runner_script}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(runner_script), "--verbose"],
            cwd=str(M5_ATR_STOP_PROCESSOR),
            capture_output=False,
            text=True
        )

        if result.returncode == 0:
            print(f"\n[M5 ATR STOP] Completed successfully")
            return True
        else:
            print(f"\n[M5 ATR STOP] Failed with exit code {result.returncode}")
            return False

    except Exception as e:
        print(f"\n[M5 ATR STOP] Error: {e}")
        return False


def run_trades_consolidated_processor():
    """Run the trades consolidation secondary processor."""
    print(f"\n{'='*70}")
    print("[TRADES CONSOLIDATED] Consolidating trades into trades_m5_r_win_2")
    print(f"{'='*70}")

    runner_script = TRADES_M5_R_WIN_2_PROCESSOR / "runner.py"

    if not runner_script.exists():
        print(f"  ERROR: Trades consolidated runner not found: {runner_script}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(runner_script), "--verbose"],
            cwd=str(TRADES_M5_R_WIN_2_PROCESSOR),
            capture_output=False,
            text=True
        )

        if result.returncode == 0:
            print(f"\n[TRADES CONSOLIDATED] Completed successfully")
            return True
        else:
            print(f"\n[TRADES CONSOLIDATED] Failed with exit code {result.returncode}")
            return False

    except Exception as e:
        print(f"\n[TRADES CONSOLIDATED] Error: {e}")
        return False


def run_m1_trade_indicator_processor():
    """Run the M1 trade indicator secondary processor."""
    print(f"\n{'='*70}")
    print("[M1 TRADE IND] Populating m1_trade_indicator_2 (entry bar snapshots)")
    print(f"{'='*70}")

    runner_script = M1_TRADE_INDICATOR_PROCESSOR / "runner.py"

    if not runner_script.exists():
        print(f"  ERROR: M1 trade indicator runner not found: {runner_script}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(runner_script), "--verbose"],
            cwd=str(M1_TRADE_INDICATOR_PROCESSOR),
            capture_output=False,
            text=True
        )

        if result.returncode == 0:
            print(f"\n[M1 TRADE IND] Completed successfully")
            return True
        else:
            print(f"\n[M1 TRADE IND] Failed with exit code {result.returncode}")
            return False

    except Exception as e:
        print(f"\n[M1 TRADE IND] Error: {e}")
        return False


def run_m1_ramp_up_indicator_processor():
    """Run the M1 ramp-up indicator secondary processor."""
    print(f"\n{'='*70}")
    print("[M1 RAMP-UP] Populating m1_ramp_up_indicator_2 (25-bar pre-entry)")
    print(f"{'='*70}")

    runner_script = M1_RAMP_UP_INDICATOR_PROCESSOR / "runner.py"

    if not runner_script.exists():
        print(f"  ERROR: M1 ramp-up indicator runner not found: {runner_script}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(runner_script), "--verbose"],
            cwd=str(M1_RAMP_UP_INDICATOR_PROCESSOR),
            capture_output=False,
            text=True
        )

        if result.returncode == 0:
            print(f"\n[M1 RAMP-UP] Completed successfully")
            return True
        else:
            print(f"\n[M1 RAMP-UP] Failed with exit code {result.returncode}")
            return False

    except Exception as e:
        print(f"\n[M1 RAMP-UP] Error: {e}")
        return False


def run_m1_post_trade_indicator_processor():
    """Run the M1 post-trade indicator secondary processor."""
    print(f"\n{'='*70}")
    print("[M1 POST-TRADE] Populating m1_post_trade_indicator_2 (25-bar post-entry)")
    print(f"{'='*70}")

    runner_script = M1_POST_TRADE_INDICATOR_PROCESSOR / "runner.py"

    if not runner_script.exists():
        print(f"  ERROR: M1 post-trade indicator runner not found: {runner_script}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(runner_script), "--verbose"],
            cwd=str(M1_POST_TRADE_INDICATOR_PROCESSOR),
            capture_output=False,
            text=True
        )

        if result.returncode == 0:
            print(f"\n[M1 POST-TRADE] Completed successfully")
            return True
        else:
            print(f"\n[M1 POST-TRADE] Failed with exit code {result.returncode}")
            return False

    except Exception as e:
        print(f"\n[M1 POST-TRADE] Error: {e}")
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Epoch Backtest Runner v4.0 - Entry Detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_backtest.py 2026-01-20              # Run entry detection for date
  python run_backtest.py 2026-01-20 --dry-run    # Preview without DB writes
  python run_backtest.py 2026-01-20 --no-export  # Skip Supabase export
  python run_backtest.py 2026-01-20 --m1-bars    # Also fetch/store M1 bars
        """
    )

    parser.add_argument('date', help='Trading date (YYYY-MM-DD)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview without database writes')
    parser.add_argument('--no-export', action='store_true',
                        help='Skip Supabase export')
    parser.add_argument('--m1-bars', action='store_true',
                        help='Fetch and store M1 bars after entry detection')
    parser.add_argument('--m1-indicators', action='store_true',
                        help='Calculate M1 indicator bars after M1 bars storage')
    parser.add_argument('--m1-atr-stop', action='store_true',
                        help='Calculate M1 ATR stop outcomes (R-multiple targets)')
    parser.add_argument('--m5-atr-stop', action='store_true',
                        help='Calculate M5 ATR stop outcomes (R-multiple targets)')
    parser.add_argument('--trades-consolidated', action='store_true',
                        help='Consolidate trades into trades_m5_r_win_2 for trade_reel')
    parser.add_argument('--m1-trade-ind', action='store_true',
                        help='Populate m1_trade_indicator_2 (entry bar indicator snapshot)')
    parser.add_argument('--m1-ramp-up', action='store_true',
                        help='Populate m1_ramp_up_indicator_2 (25-bar pre-entry indicators)')
    parser.add_argument('--m1-post-trade', action='store_true',
                        help='Populate m1_post_trade_indicator_2 (25-bar post-entry indicators)')

    args = parser.parse_args()

    print("=" * 70)
    print("EPOCH BACKTEST RUNNER v4.0")
    print("Entry Detection: S15 Bars / EPCH1-4 Models")
    print("XIII Trading LLC")
    print("=" * 70)

    print(f"\nDate: {args.date}")
    print(f"Mode: {'DRY RUN (no writes)' if args.dry_run else 'LIVE'}")
    print(f"Export: {'Disabled' if args.no_export else 'Enabled'}")
    print(f"M1 Bars: {'Enabled' if args.m1_bars else 'Disabled'}")
    print(f"M1 Indicators: {'Enabled' if args.m1_indicators else 'Disabled'}")
    print(f"M1 ATR Stop: {'Enabled' if args.m1_atr_stop else 'Disabled'}")
    print(f"M5 ATR Stop: {'Enabled' if args.m5_atr_stop else 'Disabled'}")
    print(f"Consolidate Trades: {'Enabled' if args.trades_consolidated else 'Disabled'}")
    print(f"M1 Trade Indicator: {'Enabled' if args.m1_trade_ind else 'Disabled'}")
    print(f"M1 Ramp-Up Indicator: {'Enabled' if args.m1_ramp_up else 'Disabled'}")
    print(f"M1 Post-Trade Indicator: {'Enabled' if args.m1_post_trade else 'Disabled'}")

    # Run entry detection
    entries = run_backtest_for_date(args.date, dry_run=args.dry_run)

    # Print results
    print(f"\n{'='*70}")
    print("ENTRY DETECTION COMPLETE")
    print(f"{'='*70}")

    if entries:
        print_summary(entries)

        # Export to Supabase trades_2
        if not args.dry_run and not args.no_export:
            print(f"\n{'='*70}")
            print("EXPORTING TO SUPABASE (trades_2)")
            print(f"{'='*70}")

            try:
                from datetime import datetime as dt
                trade_date = dt.strptime(args.date, '%Y-%m-%d').date()
                export_stats = export_trades(entries, trade_date, verbose=True)

                if export_stats.success:
                    print(f"\n  Exported {export_stats.trades_exported} entries successfully")
                else:
                    print(f"\n  Export failed: {export_stats.errors}")

            except Exception as e:
                print(f"\n  Export error: {e}")

        # Run M1 bars processor if requested
        if args.m1_bars and not args.dry_run:
            run_m1_bars_processor()

        # Run M1 indicators processor if requested
        if args.m1_indicators and not args.dry_run:
            run_m1_indicators_processor()

        # Run M1 ATR Stop processor if requested
        if args.m1_atr_stop and not args.dry_run:
            run_m1_atr_stop_processor()

        # Run M5 ATR Stop processor if requested
        if args.m5_atr_stop and not args.dry_run:
            run_m5_atr_stop_processor()

        # Run trades consolidation processor if requested
        if args.trades_consolidated and not args.dry_run:
            run_trades_consolidated_processor()

        # Run indicator phase processors if requested
        # (These require m5_atr_stop_2 outcomes to exist)
        if args.m1_trade_ind and not args.dry_run:
            run_m1_trade_indicator_processor()

        if args.m1_ramp_up and not args.dry_run:
            run_m1_ramp_up_indicator_processor()

        if args.m1_post_trade and not args.dry_run:
            run_m1_post_trade_indicator_processor()

    else:
        print("\nNo entries detected.")

    print(f"\n{'='*70}")
    print("ALL COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
