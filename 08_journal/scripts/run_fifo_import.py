"""
================================================================================
EPOCH TRADING SYSTEM - FIFO Trade Importer (CLI)
XIII Trading LLC
================================================================================

Command-line FIFO trade processor for DAS Trader CSV files.

Usage:
    python scripts/run_fifo_import.py path/to/csv              # Process + print
    python scripts/run_fifo_import.py path/to/csv --save        # Process + save to DB
    python scripts/run_fifo_import.py path/to/csv --clear       # Clear date first, then save

Examples:
    python scripts/run_fifo_import.py trade_log/02_Feb_2026/tl_021326.csv
    python scripts/run_fifo_import.py trade_log/02_Feb_2026/tl_021326.csv --save

================================================================================
"""

import sys
import argparse
from pathlib import Path
from collections import Counter

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.fifo_processor import process_session_fifo
from core.fifo_models import FIFOTrade, FIFODailyLog
from data.journal_db import JournalDB


def print_trade_table(trades: list):
    """Print ASCII table of trades."""
    print("  +-----+--------+----------+------+----------+----------+----------+---------+")
    print("  | Seq | Symbol | Entry    | Qty  | Exit     | PnL/shr  | PnL Tot  | Outcome |")
    print("  +-----+--------+----------+------+----------+----------+----------+---------+")

    for t in trades:
        seq = str(t.trade_seq).center(3)
        sym = t.symbol.ljust(6)
        entry = f"${t.entry_price:.2f}".rjust(8)
        qty = str(t.entry_qty).rjust(4)

        if t.exit_price is not None:
            exit_p = f"${t.exit_price:.2f}".rjust(8)
        else:
            exit_p = "   OPEN ".rjust(8)

        if t.pnl_dollars is not None:
            sign = "+" if t.pnl_dollars >= 0 else ""
            pnl_s = f"{sign}${t.pnl_dollars:.2f}".rjust(8)
        else:
            pnl_s = "     -- ".rjust(8)

        if t.pnl_total is not None:
            sign = "+" if t.pnl_total >= 0 else ""
            pnl_t = f"{sign}${t.pnl_total:.2f}".rjust(8)
        else:
            pnl_t = "     -- ".rjust(8)

        outcome = t.outcome.value.center(7)
        print(f"  | {seq} | {sym} | {entry} | {qty} | {exit_p} | {pnl_s} | {pnl_t} | {outcome} |")

    print("  +-----+--------+----------+------+----------+----------+----------+---------+")


def main():
    parser = argparse.ArgumentParser(
        description="FIFO Trade Importer - Process DAS Trader CSV files"
    )
    parser.add_argument(
        "csv_file",
        type=str,
        help="Path to DAS Trader CSV file"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save processed trades to journal_trades table"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing entries for the date before saving (implies --save)"
    )

    args = parser.parse_args()

    filepath = Path(args.csv_file)
    if not filepath.exists():
        # Try relative to script's parent (08_journal/)
        alt_path = Path(__file__).parent.parent / args.csv_file
        if alt_path.exists():
            filepath = alt_path
        else:
            print(f"ERROR: File not found: {args.csv_file}")
            sys.exit(1)

    if args.clear:
        args.save = True  # --clear implies --save

    # Process
    print(f"\n{'='*70}")
    print(f"  EPOCH FIFO TRADE PROCESSOR - CLI")
    print(f"{'='*70}\n")

    def fill_callback(fill_num, fill, action):
        side_str = fill.side.value.ljust(2)
        qty_str = str(fill.qty).rjust(3)
        price_str = f"{fill.price:.2f}".rjust(8)
        print(f"  Fill #{fill_num}: {side_str} {qty_str} @ {price_str} ({fill.time}) -> {action}")

    log = process_session_fifo(filepath, callback=fill_callback)

    # Print results
    if log.parse_errors:
        print(f"\nWarnings:")
        for err in log.parse_errors:
            print(f"  - {err}")

    print(f"\n{'='*70}")
    print(f"  RESULTS")
    print(f"{'='*70}")
    print(f"  Date:          {log.trade_date}")
    print(f"  Source:        {log.source_file}")
    print(f"  Total Trades:  {log.trade_count} ({log.closed_count} closed, {log.open_count} open)")

    symbol_counts = Counter(t.symbol for t in log.trades)
    sym_str = ", ".join(f"{s} ({c})" for s, c in sorted(symbol_counts.items()))
    print(f"  Symbols:       {sym_str}")
    print(f"  Total P&L:     ${log.total_pnl:,.2f}")

    if log.win_rate is not None:
        wr_pct = log.win_rate * 100
        print(f"  Win Rate:      {wr_pct:.0f}% ({log.win_count}W / {log.loss_count}L)")

    print(f"{'='*70}\n")

    if log.trades:
        print_trade_table(log.trades)

    # Save to database
    if args.save and log.trades:
        print(f"\n[DB] Connecting to Supabase...")

        with JournalDB() as db:
            if args.clear:
                count = db.delete_session(log.trade_date)
                print(f"[DB] Cleared {count} existing entries for {log.trade_date}")

            saved = 0
            for trade in log.trades:
                if db.save_trade(trade, source_file=log.source_file):
                    saved += 1
                    print(f"[DB] Saved {trade.trade_id}")
                else:
                    print(f"[DB] FAILED: {trade.trade_id}")

            print(f"\n[DB] Saved {saved}/{log.trade_count} trades successfully.")

    elif not args.save and log.trades:
        print(f"\nDry run -- use --save to write to database.")

    print()


if __name__ == "__main__":
    main()
