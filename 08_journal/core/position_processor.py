"""
Position-Based CSV processing pipeline for the Epoch Trading Journal.

Pipeline:
    process_session_position(filepath)              <- Main entry point
        +-- extract_date_from_filename(filepath)     <- Reused from trade_processor
        +-- parse_csv_auto(filepath)                 <- Reused from fifo_processor
        +-- group_fills(fills)                       <- Reused from trade_processor
        +-- process_symbol_position(symbol, fills, date)  <- Per symbol
                +-- determine_direction(fills)        <- Reused from trade_processor
                +-- Position state machine            <- NEW

Position Algorithm:
    1. First fill determines direction (SHORT if sell-side, LONG if buy-side)
    2. First same-direction fill = ENTRY (opens position)
    3. Subsequent same-direction fills = ADD (scale in)
    4. Opposite-direction fills = EXIT (partial or full close)
    5. All fills tracked with running position size
    6. One PositionTrade per symbol per session

Key differences from fifo_processor.py:
    - fifo_processor: Each add = new FIFOTrade, FIFO exit matching
    - position_processor: All fills in one PositionTrade, no matching needed
"""

import logging
from pathlib import Path
from datetime import date, time
from typing import List, Tuple, Optional

from .models import Fill, FillSide, TradeDirection
from .position_models import PositionFill, PositionTrade, PositionDailyLog, FillType
from .trade_processor import extract_date_from_filename, group_fills, determine_direction
from .fifo_processor import parse_csv_auto

logger = logging.getLogger(__name__)


# =============================================================================
# Position processing for one symbol
# =============================================================================

def process_symbol_position(
    symbol: str,
    fills: List[Fill],
    trade_date: date,
    callback=None,
) -> Tuple[Optional[PositionTrade], List[str]]:
    """
    Position-based trade processor for one symbol.

    Algorithm:
    1. First fill determines direction (SHORT if sell-side, LONG if buy-side)
    2. Same-direction fills: first = ENTRY, subsequent = ADD
    3. Opposite-direction fills = EXIT
    4. Running position size tracked after each fill
    5. Returns one PositionTrade containing all fills

    Args:
        symbol: Ticker symbol
        fills: Sorted fills for this symbol (must be chronological)
        trade_date: Trading date
        callback: Optional callable(fill_num, fill, action_str) for logging

    Returns:
        (position_trade, warnings) -- single PositionTrade and any warnings
    """
    warnings: List[str] = []

    if not fills:
        return None, warnings

    direction = determine_direction(fills)

    position = PositionTrade(
        symbol=symbol,
        trade_date=trade_date,
        direction=direction,
        account=fills[0].account,
        fills=[],
    )

    current_size = 0        # Running share count
    has_entry = False       # Track if we've seen the first entry

    for fill_num, fill in enumerate(fills, start=1):
        is_entry_side = (
            (direction == TradeDirection.SHORT and fill.side.is_sell_side) or
            (direction == TradeDirection.LONG and fill.side.is_buy_side)
        )

        if is_entry_side:
            # First entry or add
            if not has_entry:
                fill_type = FillType.ENTRY
                has_entry = True
            else:
                fill_type = FillType.ADD

            current_size += fill.qty

            pos_fill = PositionFill(
                side=fill.side,
                fill_type=fill_type,
                price=fill.price,
                qty=fill.qty,
                time=fill.time,
                position_after=current_size,
            )
            position.fills.append(pos_fill)

            action = f"{fill_type.value} (position: {current_size} shares)"
            if callback:
                callback(fill_num, fill, action)

        else:
            # Exit (partial or full)
            exit_qty = min(fill.qty, current_size)
            current_size -= exit_qty

            if exit_qty <= 0:
                warnings.append(
                    f"{symbol}: Orphan exit of {fill.qty} shares at "
                    f"{fill.time} -- no open position to match"
                )
                if callback:
                    callback(fill_num, fill, "EXIT: no position to match")
                continue

            pos_fill = PositionFill(
                side=fill.side,
                fill_type=FillType.EXIT,
                price=fill.price,
                qty=exit_qty,
                time=fill.time,
                position_after=current_size,
            )
            position.fills.append(pos_fill)

            if current_size == 0:
                action = f"EXIT FULL (position: FLAT)"
            else:
                action = f"EXIT PARTIAL -{exit_qty} (position: {current_size} shares)"

            if callback:
                callback(fill_num, fill, action)

            # Warn if exit fill had excess shares
            if fill.qty > exit_qty:
                excess = fill.qty - exit_qty
                warnings.append(
                    f"{symbol}: Exit fill at {fill.time} had {excess} excess shares "
                    f"beyond position size"
                )

    # Warn if position still open
    if current_size > 0:
        warnings.append(
            f"{symbol}: Position still open with {current_size} shares remaining"
        )

    return position, warnings


# =============================================================================
# Main entry point
# =============================================================================

def process_session_position(
    filepath: Path,
    callback=None,
) -> PositionDailyLog:
    """
    Main entry point: DAS Trader CSV -> Position-based trades.

    Pipeline:
    1. Extract date from filename (reused from trade_processor)
    2. Parse CSV with auto-detected delimiter (reused from fifo_processor)
    3. Group fills by symbol (reused from trade_processor)
    4. Process each symbol with position logic

    Args:
        filepath: Path to DAS Trader CSV file
        callback: Optional callable for logging progress

    Returns:
        PositionDailyLog with all trades and any errors
    """
    filepath = Path(filepath)
    errors: List[str] = []

    # Step 1: Extract date
    try:
        trade_date = extract_date_from_filename(filepath)
    except ValueError as e:
        return PositionDailyLog(
            trade_date=date.today(),
            source_file=filepath.name,
            parse_errors=[str(e)],
        )

    # Step 2: Parse CSV
    fills, parse_errors, delimiter = parse_csv_auto(filepath)
    errors.extend(parse_errors)

    if not fills:
        return PositionDailyLog(
            trade_date=trade_date,
            source_file=filepath.name,
            parse_errors=errors or ["No fills found in CSV"],
        )

    # Step 3: Group by symbol
    groups = group_fills(fills)

    # Step 4: Process each symbol with position logic
    all_trades: List[PositionTrade] = []
    for symbol, symbol_fills in sorted(groups.items()):
        try:
            trade, warnings = process_symbol_position(
                symbol, symbol_fills, trade_date, callback=callback
            )
            if trade is not None:
                all_trades.append(trade)
            errors.extend(warnings)
        except Exception as e:
            errors.append(f"{symbol}: {e}")

    return PositionDailyLog(
        trade_date=trade_date,
        source_file=filepath.name,
        trades=all_trades,
        parse_errors=errors,
    )
