"""
Trade Adapter - Convert journal_trades DB row -> HighlightTrade-compatible object
Epoch Trading System - XIII Trading LLC

This is the key bridging file. Converts a journal_trades DB row dict into a
JournalHighlight dataclass that duck-types HighlightTrade, so the chart
builders from 11_trade_reel/charts/ work without modification.

M5 ATR Stop Calculation (on-the-fly):
    1. Fetch M5 bars from Polygon for the trade ticker/date (3-day lookback)
    2. Calculate ATR(14) on M5 bars at the entry candle time
    3. stop_distance = m5_atr (1x multiplier, matching backtest)
    4. stop_price = entry_price -/+ stop_distance (LONG: -, SHORT: +)
    5. R-level prices: entry_price +/- (N * stop_distance) for N=1..5

R-Level Hit Detection (on-the-fly):
    1. Walk M1 bars from entry_time to exit_time (or EOD 15:30)
    2. R-target detection: LONG -> bar.high >= r_price, SHORT -> bar.low <= r_price
    3. Stop detection: LONG -> bar.close <= stop_price, SHORT -> bar.close >= stop_price
    4. Same-candle conflict: stop wins (matching backtest logic exactly)
"""

import logging
from dataclasses import dataclass, field
from datetime import date, time, datetime
from typing import Optional, Dict, List

import pandas as pd
import numpy as np

from .config import DISPLAY_TIMEZONE

logger = logging.getLogger(__name__)


# =============================================================================
# JournalHighlight - Duck-types HighlightTrade for chart builders
# =============================================================================

@dataclass
class JournalHighlight:
    """
    Adapter that converts a journal_trades row into a HighlightTrade-compatible
    object. All chart builders from 11_trade_reel/charts/ access attributes
    on the highlight object -- this dataclass provides all of them.
    """
    # Core trade info
    trade_id: str = ""
    date: date = None
    ticker: str = ""
    direction: str = "LONG"         # "LONG" / "SHORT"
    model: Optional[str] = None     # Not in journal (backtest-specific)
    zone_type: Optional[str] = None

    # Zone boundaries (for chart overlays)
    zone_high: Optional[float] = None
    zone_low: Optional[float] = None

    # Entry
    entry_price: float = 0.0
    entry_time: Optional[time] = None

    # Exit (actual exit from journal trade)
    exit_price: Optional[float] = None
    exit_time: Optional[time] = None

    # ATR-based stop
    m5_atr_value: Optional[float] = None
    stop_price: Optional[float] = None
    stop_distance: Optional[float] = None

    # R-level prices
    r1_price: Optional[float] = None
    r2_price: Optional[float] = None
    r3_price: Optional[float] = None
    r4_price: Optional[float] = None
    r5_price: Optional[float] = None

    # R-level hits
    r1_hit: bool = False
    r1_time: Optional[time] = None
    r1_bars: Optional[int] = None

    r2_hit: bool = False
    r2_time: Optional[time] = None
    r2_bars: Optional[int] = None

    r3_hit: bool = False
    r3_time: Optional[time] = None
    r3_bars: Optional[int] = None

    r4_hit: bool = False
    r4_time: Optional[time] = None
    r4_bars: Optional[int] = None

    r5_hit: bool = False
    r5_time: Optional[time] = None
    r5_bars: Optional[int] = None

    # Stop hit
    stop_hit: bool = False
    stop_hit_time: Optional[time] = None

    # Outcome
    max_r_achieved: int = 0
    outcome: str = "LOSS"
    exit_reason: str = "JOURNAL"
    is_winner: bool = False
    pnl_r: Optional[float] = None
    pnl_dollars: Optional[float] = None
    outcome_method: Optional[str] = "JOURNAL"
    eod_price: Optional[float] = None

    # Convenience (used by chart_preview summary)
    reached_2r: bool = False
    reached_3r: bool = False
    minutes_to_r1: Optional[int] = None

    # Journal-specific
    entry_qty: int = 0

    @property
    def rating(self) -> int:
        """Star rating based on max R achieved (0-5)."""
        return self.max_r_achieved

    @property
    def is_highlight(self) -> bool:
        """Trade qualifies as a highlight (WIN with R3+)."""
        return self.outcome == 'WIN' and self.max_r_achieved >= 3

    @property
    def highest_r_hit_time(self) -> Optional[time]:
        """Time when the highest R-level was hit. Used for M1 chart window."""
        r_times = {
            5: self.r5_time,
            4: self.r4_time,
            3: self.r3_time,
            2: self.r2_time,
            1: self.r1_time,
        }
        return r_times.get(self.max_r_achieved)

    @property
    def highest_r_price(self) -> Optional[float]:
        """Price of the highest R-level hit."""
        r_prices = {
            5: self.r5_price,
            4: self.r4_price,
            3: self.r3_price,
            2: self.r2_price,
            1: self.r1_price,
        }
        return r_prices.get(self.max_r_achieved)

    @property
    def entry_datetime(self) -> Optional[datetime]:
        """Combine date and entry_time into datetime."""
        if self.entry_time and self.date:
            return datetime.combine(self.date, self.entry_time)
        return None

    @property
    def star_display(self) -> str:
        """Display string for rating (e.g., 'R3' or 'R5')."""
        if self.max_r_achieved > 0:
            return f"R{self.max_r_achieved}"
        return "R0"


# =============================================================================
# Adapter: journal_trades row -> JournalHighlight
# =============================================================================

def build_journal_highlight(
    row: Dict,
    bars_m5: Optional[pd.DataFrame] = None,
    bars_m1: Optional[pd.DataFrame] = None,
    zones: Optional[List[Dict]] = None,
) -> JournalHighlight:
    """
    Convert a journal_trades DB row into a JournalHighlight.

    This is the main adapter function. It:
    1. Maps DB columns to JournalHighlight fields
    2. Reads pre-computed M5 ATR data from DB if available
    3. Falls back to on-the-fly computation from bars if ATR not in DB
    4. Attaches zone info from the first matching zone

    Args:
        row: Dict from JournalDB.get_trades_by_range() (RealDictCursor row)
        bars_m5: M5 bars for ATR calculation (fallback, optional)
        bars_m1: M1 bars for R-level hit detection (fallback, optional)
        zones: Zone dicts from JournalDB.get_zones_for_ticker()

    Returns:
        JournalHighlight duck-typing HighlightTrade
    """
    from decimal import Decimal

    def to_float(val) -> Optional[float]:
        if val is None:
            return None
        if isinstance(val, Decimal):
            return float(val)
        return float(val)

    trade_date = row.get('trade_date') or row.get('date')
    entry_time = row.get('entry_time')
    exit_time = row.get('exit_time')
    entry_price = to_float(row.get('entry_price')) or 0.0
    exit_price = to_float(row.get('exit_price'))
    direction = (row.get('direction') or 'LONG').upper()
    pnl_dollars = to_float(row.get('pnl_dollars'))

    # Determine outcome from PnL
    outcome = (row.get('outcome') or '').upper()
    if not outcome:
        if pnl_dollars is not None:
            outcome = 'WIN' if pnl_dollars > 0 else 'LOSS'
        else:
            outcome = 'FLAT'

    is_winner = outcome == 'WIN'

    # Build highlight
    hl = JournalHighlight(
        trade_id=row.get('trade_id', ''),
        date=trade_date,
        ticker=(row.get('symbol') or row.get('ticker', '')).upper(),
        direction=direction,
        entry_price=entry_price,
        entry_time=entry_time,
        exit_price=exit_price,
        exit_time=exit_time,
        outcome=outcome,
        is_winner=is_winner,
        pnl_dollars=pnl_dollars,
        pnl_r=to_float(row.get('pnl_r')),
        entry_qty=int(row.get('entry_qty', 0) or 0),
        exit_reason="JOURNAL",
    )

    # Attach zone info (use first/highest-scored zone)
    if zones:
        best_zone = zones[0]
        hl.zone_high = to_float(best_zone.get('zone_high'))
        hl.zone_low = to_float(best_zone.get('zone_low'))
        hl.zone_type = best_zone.get('setup_type') or best_zone.get('zone_type')

    # ---- ATR data: prefer pre-computed from DB (M5 model for chart display) ----
    has_precomputed = row.get('m5_atr_value') is not None

    if has_precomputed:
        # Read pre-computed M5 ATR stop data from DB
        hl.m5_atr_value = to_float(row.get('m5_atr_value'))
        hl.stop_price = to_float(row.get('m5_stop_price'))
        hl.stop_distance = to_float(row.get('m5_stop_distance'))
        hl.r1_price = to_float(row.get('m5_r1_price'))
        hl.r2_price = to_float(row.get('m5_r2_price'))
        hl.r3_price = to_float(row.get('m5_r3_price'))
        hl.r4_price = to_float(row.get('m5_r4_price'))
        hl.r5_price = to_float(row.get('m5_r5_price'))
        hl.r1_hit = bool(row.get('m5_r1_hit'))
        hl.r2_hit = bool(row.get('m5_r2_hit'))
        hl.r3_hit = bool(row.get('m5_r3_hit'))
        hl.r4_hit = bool(row.get('m5_r4_hit'))
        hl.r5_hit = bool(row.get('m5_r5_hit'))
        hl.r1_time = row.get('m5_r1_time')
        hl.r2_time = row.get('m5_r2_time')
        hl.r3_time = row.get('m5_r3_time')
        hl.r4_time = row.get('m5_r4_time')
        hl.r5_time = row.get('m5_r5_time')
        hl.stop_hit = bool(row.get('m5_stop_hit'))
        hl.stop_hit_time = row.get('m5_stop_hit_time')
        hl.max_r_achieved = int(row.get('m5_max_r', 0) or 0)
        hl.pnl_r = to_float(row.get('m5_pnl_r'))
        hl.reached_2r = hl.max_r_achieved >= 2
        hl.reached_3r = hl.max_r_achieved >= 3

        # Update outcome based on R analysis
        if hl.max_r_achieved > 0:
            hl.is_winner = True
        elif hl.stop_hit:
            hl.is_winner = False

        logger.info(f"Using pre-computed M5 ATR for {hl.trade_id}: R{hl.max_r_achieved}")

    else:
        # Fall back to on-the-fly computation from bars
        if bars_m5 is not None and not bars_m5.empty and entry_time is not None:
            _compute_atr_levels(hl, bars_m5, trade_date)

        if bars_m1 is not None and not bars_m1.empty and hl.stop_price is not None:
            _detect_r_hits(hl, bars_m1, trade_date)

        # Compute pnl_r from actual exit if we have stop_distance
        if hl.stop_distance and hl.stop_distance > 0 and exit_price is not None:
            if direction == 'LONG':
                hl.pnl_r = (exit_price - entry_price) / hl.stop_distance
            else:
                hl.pnl_r = (entry_price - exit_price) / hl.stop_distance

    return hl


# =============================================================================
# M5 ATR Stop + R-Level Calculation
# =============================================================================

def _compute_atr_levels(
    hl: JournalHighlight,
    bars_m5: pd.DataFrame,
    trade_date: date,
):
    """
    Compute M5 ATR(14) stop price and R-level prices.

    Replicates 03_backtest/processor/secondary_analysis/m5_atr_stop_2/calculator.py:
    - ATR(14) = SMA of True Range over 14 M5 bars
    - stop_distance = m5_atr (1x, no multiplier)
    - LONG: stop = entry - distance, R(n) = entry + n * distance
    - SHORT: stop = entry + distance, R(n) = entry - n * distance
    """
    from .bar_fetcher import calculate_m5_atr

    atr = calculate_m5_atr(bars_m5, hl.entry_time, trade_date)
    if atr is None or atr <= 0:
        return

    hl.m5_atr_value = atr
    hl.stop_distance = atr

    if hl.direction == 'LONG':
        hl.stop_price = hl.entry_price - atr
        hl.r1_price = hl.entry_price + 1 * atr
        hl.r2_price = hl.entry_price + 2 * atr
        hl.r3_price = hl.entry_price + 3 * atr
        hl.r4_price = hl.entry_price + 4 * atr
        hl.r5_price = hl.entry_price + 5 * atr
    else:  # SHORT
        hl.stop_price = hl.entry_price + atr
        hl.r1_price = hl.entry_price - 1 * atr
        hl.r2_price = hl.entry_price - 2 * atr
        hl.r3_price = hl.entry_price - 3 * atr
        hl.r4_price = hl.entry_price - 4 * atr
        hl.r5_price = hl.entry_price - 5 * atr


# =============================================================================
# R-Level Hit Detection from M1 Bars
# =============================================================================

def _detect_r_hits(
    hl: JournalHighlight,
    bars_m1: pd.DataFrame,
    trade_date: date,
):
    """
    Walk M1 bars from entry to exit (or 15:30 EOD) to detect R-level hits.

    Algorithm (matches backtest logic exactly):
    - R-target: LONG -> bar.high >= r_price, SHORT -> bar.low <= r_price
    - Stop: LONG -> bar.close <= stop_price, SHORT -> bar.close >= stop_price
    - Same-candle conflict: stop wins
    - max_r = highest R hit before stop (or 0 for no R hit)
    """
    import pytz
    tz = pytz.timezone(DISPLAY_TIMEZONE)

    if hl.entry_time is None or hl.stop_price is None:
        return

    # Build time window
    entry_dt = tz.localize(datetime.combine(trade_date, hl.entry_time))

    # End time: use actual exit_time if available, else 15:30 EOD
    if hl.exit_time:
        end_dt = tz.localize(datetime.combine(trade_date, hl.exit_time))
    else:
        end_dt = tz.localize(datetime.combine(trade_date, time(15, 30)))

    # Filter M1 bars within window (entry to end, inclusive)
    window = bars_m1[(bars_m1.index >= entry_dt) & (bars_m1.index <= end_dt)]

    if window.empty:
        return

    is_long = hl.direction == 'LONG'
    r_prices = [
        (1, hl.r1_price),
        (2, hl.r2_price),
        (3, hl.r3_price),
        (4, hl.r4_price),
        (5, hl.r5_price),
    ]

    stop_triggered = False

    for idx, bar in window.iterrows():
        bar_time = idx.time() if hasattr(idx, 'time') else None

        if stop_triggered:
            break

        # Check stop first (same-candle conflict: stop wins)
        if is_long:
            if bar['close'] <= hl.stop_price:
                hl.stop_hit = True
                hl.stop_hit_time = bar_time
                stop_triggered = True
        else:
            if bar['close'] >= hl.stop_price:
                hl.stop_hit = True
                hl.stop_hit_time = bar_time
                stop_triggered = True

        # Check R-levels (wick-based: high/low touch)
        for r_num, r_price in r_prices:
            if r_price is None:
                continue

            already_hit = getattr(hl, f'r{r_num}_hit')
            if already_hit:
                continue

            hit = False
            if is_long:
                hit = bar['high'] >= r_price
            else:
                hit = bar['low'] <= r_price

            if hit and not stop_triggered:
                setattr(hl, f'r{r_num}_hit', True)
                setattr(hl, f'r{r_num}_time', bar_time)

    # Compute max_r_achieved
    max_r = 0
    for r_num in range(5, 0, -1):
        if getattr(hl, f'r{r_num}_hit'):
            max_r = r_num
            break

    hl.max_r_achieved = max_r
    hl.reached_2r = max_r >= 2
    hl.reached_3r = max_r >= 3

    # Update outcome based on R analysis
    if max_r > 0:
        hl.outcome = 'WIN'
        hl.is_winner = True
    elif hl.stop_hit:
        hl.outcome = 'LOSS'
        hl.is_winner = False
