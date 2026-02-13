"""
FIFO CSV processing pipeline for the Epoch Trading Journal.

Pipeline:
    process_session_fifo(filepath)              <- Main entry point
        ├── extract_date_from_filename(filepath) <- Reused from trade_processor
        ├── parse_csv_auto(filepath)             <- Auto-detect delimiter
        ├── group_fills(fills)                   <- Reused from trade_processor
        └── process_symbol_fifo(symbol, fills, date)  <- Per symbol
                ├── determine_direction(fills)    <- Reused from trade_processor
                └── FIFO queue matching           <- NEW

FIFO Algorithm:
    1. First fill determines direction (SHORT if sell-side, LONG if buy-side)
    2. Every same-direction fill creates a NEW FIFOTrade (added to queue)
    3. Opposite-direction fills are EXITS -- applied FIFO to oldest open trade first
    4. A single exit fill can span multiple trades (partial close + full close)
    5. Exit price per trade = VWAP of all exit portions allocated to that trade

Key differences from trade_processor.py:
    - trade_processor: One Trade per symbol per session (all fills blended at VWAP)
    - fifo_processor: Multiple trades per symbol (each add = new trade, FIFO exits)

Existing code reused (imported, not duplicated):
    - extract_date_from_filename()
    - group_fills()
    - determine_direction()
"""

import logging
from pathlib import Path
from datetime import date, time
from typing import List, Tuple, Optional

from .models import Fill, FillSide, TradeDirection
from .fifo_models import ExitPortion, FIFOTrade, FIFODailyLog
from .trade_processor import extract_date_from_filename, group_fills, determine_direction

logger = logging.getLogger(__name__)


# =============================================================================
# CSV parsing with auto-delimiter detection
# =============================================================================

SIDE_MAP = {
    "B": FillSide.BUY,
    "SS": FillSide.SHORT_SELL,
    "S": FillSide.SELL,
}


def detect_delimiter(first_line: str) -> str:
    """
    Auto-detect CSV delimiter from the header line.

    DAS Trader Format 2 exports use tab-delimited or comma-delimited.
    Tab takes priority if present (more reliable indicator).
    """
    if "\t" in first_line:
        return "\t"
    return ","


def parse_csv_auto(filepath: Path) -> Tuple[List[Fill], List[str], str]:
    """
    Parse DAS Trader CSV with auto-detected delimiter.

    Handles both tab-delimited (Format 2) and comma-delimited CSVs.
    Also handles trailing delimiters (common in DAS exports).

    Columns: Time, Symbol, Side, Price, Qty, Route, Account, Type, Cloid

    Returns:
        (fills, errors, delimiter) -- parsed fills, errors, and detected delimiter.
    """
    fills: List[Fill] = []
    errors: List[str] = []

    text = filepath.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if not lines:
        errors.append(f"Empty CSV file: {filepath.name}")
        return fills, errors, ","

    # Detect delimiter from header
    delimiter = detect_delimiter(lines[0])

    # Skip header row
    data_lines = lines[1:]

    for line_num, line in enumerate(data_lines, start=2):
        try:
            cols = line.split(delimiter)

            # Strip trailing empty columns (trailing delimiter)
            while cols and cols[-1].strip() == "":
                cols.pop()

            if len(cols) < 5:
                errors.append(f"Row {line_num}: insufficient columns ({len(cols)})")
                continue

            # Parse time (HH:MM:SS)
            time_parts = cols[0].strip().split(":")
            fill_time = time(int(time_parts[0]), int(time_parts[1]), int(time_parts[2]))

            # Parse side
            raw_side = cols[2].strip().upper()
            if raw_side not in SIDE_MAP:
                errors.append(f"Row {line_num}: unknown side '{raw_side}'")
                continue

            side = SIDE_MAP[raw_side]

            fill = Fill(
                time=fill_time,
                symbol=cols[1].strip().upper(),
                side=side,
                price=float(cols[3].strip()),
                qty=int(cols[4].strip()),
                route=cols[5].strip() if len(cols) > 5 else "",
                account=cols[6].strip() if len(cols) > 6 else "",
                fill_type=cols[7].strip() if len(cols) > 7 else "",
                cloid=cols[8].strip() if len(cols) > 8 else "",
            )
            fills.append(fill)

        except (ValueError, IndexError) as e:
            errors.append(f"Row {line_num}: {e}")

    return fills, errors, delimiter


# =============================================================================
# FIFO processing for one symbol
# =============================================================================

def process_symbol_fifo(
    symbol: str,
    fills: List[Fill],
    trade_date: date,
    callback=None,
) -> Tuple[List[FIFOTrade], List[str]]:
    """
    FIFO trade processor for one symbol.

    Algorithm:
    1. First fill determines direction (SHORT if sell-side, LONG if buy-side)
    2. Same-direction fills each create a NEW FIFOTrade (added to queue)
    3. Opposite-direction fills are EXITS -- applied FIFO to oldest open trade first
    4. A single exit fill can span multiple trades (partial close + full close)
    5. Exit price per trade = VWAP of all exit portions allocated to that trade

    Args:
        symbol: Ticker symbol
        fills: Sorted fills for this symbol (must be chronological)
        trade_date: Trading date
        callback: Optional callable(fill_num, fill, action_str) for logging

    Returns:
        (trades, warnings) -- list of FIFOTrade objects and any warnings
    """
    warnings: List[str] = []

    if not fills:
        return [], warnings

    direction = determine_direction(fills)

    fifo_queue: List[FIFOTrade] = []      # Open trades (FIFO order)
    completed_trades: List[FIFOTrade] = []
    trade_seq = 0

    for fill_num, fill in enumerate(fills, start=1):
        is_entry_side = (
            (direction == TradeDirection.SHORT and fill.side.is_sell_side) or
            (direction == TradeDirection.LONG and fill.side.is_buy_side)
        )

        if is_entry_side:
            # Each entry-side fill creates a NEW trade
            trade_seq += 1
            trade = FIFOTrade(
                trade_seq=trade_seq,
                symbol=symbol,
                trade_date=trade_date,
                direction=direction,
                account=fill.account,
                entry_price=fill.price,
                entry_qty=fill.qty,
                entry_time=fill.time,
                exit_portions=[],
                remaining_qty=fill.qty,
            )
            fifo_queue.append(trade)

            action = f"NEW Trade #{trade_seq} (qty={fill.qty})"
            if callback:
                callback(fill_num, fill, action)

        else:
            # Exit-side fill: apply FIFO to oldest open trades
            exit_remaining = fill.qty
            actions = []

            while exit_remaining > 0 and fifo_queue:
                oldest = fifo_queue[0]
                close_qty = min(exit_remaining, oldest.remaining_qty)

                oldest.exit_portions.append(ExitPortion(
                    price=fill.price,
                    qty=close_qty,
                    time=fill.time,
                ))
                oldest.remaining_qty -= close_qty
                exit_remaining -= close_qty

                if oldest.remaining_qty == 0:
                    completed_trades.append(fifo_queue.pop(0))
                    actions.append(
                        f"Trade #{oldest.trade_seq} closed ({close_qty})"
                    )
                else:
                    actions.append(
                        f"Trade #{oldest.trade_seq} partial "
                        f"({close_qty}/{oldest.entry_qty} closed)"
                    )

            if exit_remaining > 0:
                warnings.append(
                    f"{symbol}: Orphan exit of {exit_remaining} shares at "
                    f"{fill.time} -- no open trades to match"
                )

            action = "EXIT: " + ", ".join(actions) if actions else "EXIT: no match"
            if callback:
                callback(fill_num, fill, action)

    # Any remaining open trades go to completed (with is_closed=False)
    for remaining_trade in fifo_queue:
        warnings.append(
            f"{symbol}: Trade #{remaining_trade.trade_seq} still open "
            f"({remaining_trade.remaining_qty} shares remaining)"
        )
        completed_trades.append(remaining_trade)

    return completed_trades, warnings


# =============================================================================
# Main entry point
# =============================================================================

def process_session_fifo(
    filepath: Path,
    callback=None,
) -> FIFODailyLog:
    """
    Main entry point: DAS Trader CSV -> FIFO-processed trades.

    Pipeline:
    1. Extract date from filename (reused from trade_processor)
    2. Parse CSV with auto-detected delimiter
    3. Group fills by symbol (reused from trade_processor)
    4. Process each symbol with FIFO logic

    Args:
        filepath: Path to DAS Trader CSV file
        callback: Optional callable for logging progress

    Returns:
        FIFODailyLog with all trades and any errors
    """
    filepath = Path(filepath)
    errors: List[str] = []

    # Step 1: Extract date
    try:
        trade_date = extract_date_from_filename(filepath)
    except ValueError as e:
        return FIFODailyLog(
            trade_date=date.today(),
            source_file=filepath.name,
            parse_errors=[str(e)],
        )

    # Step 2: Parse CSV
    fills, parse_errors, delimiter = parse_csv_auto(filepath)
    errors.extend(parse_errors)

    if not fills:
        return FIFODailyLog(
            trade_date=trade_date,
            source_file=filepath.name,
            parse_errors=errors or ["No fills found in CSV"],
        )

    # Step 3: Group by symbol
    groups = group_fills(fills)

    # Step 4: Process each symbol with FIFO logic
    all_trades: List[FIFOTrade] = []
    for symbol, symbol_fills in sorted(groups.items()):
        try:
            trades, warnings = process_symbol_fifo(
                symbol, symbol_fills, trade_date, callback=callback
            )
            all_trades.extend(trades)
            errors.extend(warnings)
        except Exception as e:
            errors.append(f"{symbol}: {e}")

    return FIFODailyLog(
        trade_date=trade_date,
        source_file=filepath.name,
        trades=all_trades,
        parse_errors=errors,
    )
