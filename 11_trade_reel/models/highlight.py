"""
Epoch Trading System - Highlight Trade Data Model
Maps to trades_m5_r_win_2 table for highlight trade detection.
"""

from dataclasses import dataclass
from datetime import date, time, datetime
from typing import Optional
from decimal import Decimal


@dataclass
class HighlightTrade:
    """
    Trade highlight from trades_m5_r_win_2 table.
    Contains R-level hit data for determining highlight quality.
    """
    trade_id: str
    date: date
    ticker: str
    direction: str          # LONG / SHORT
    model: Optional[str]    # EPCH1-4
    zone_type: Optional[str]  # PRIMARY / SECONDARY

    # Zone boundaries (for chart overlays)
    zone_high: Optional[float]
    zone_low: Optional[float]

    # Entry
    entry_price: float
    entry_time: time

    # ATR-based stop
    m5_atr_value: Optional[float]
    stop_price: Optional[float]
    stop_distance: Optional[float]

    # R-level prices
    r1_price: Optional[float]
    r2_price: Optional[float]
    r3_price: Optional[float]
    r4_price: Optional[float]
    r5_price: Optional[float]

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
    outcome: str = 'LOSS'
    exit_reason: str = 'EOD_LOSS'
    is_winner: bool = False
    pnl_r: Optional[float] = None
    outcome_method: Optional[str] = None
    eod_price: Optional[float] = None

    # Convenience
    reached_2r: bool = False
    reached_3r: bool = False
    minutes_to_r1: Optional[int] = None

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
        if self.entry_time:
            return datetime.combine(self.date, self.entry_time)
        return None

    @property
    def star_display(self) -> str:
        """Display string for rating (e.g., 'R3' or 'R5')."""
        return f"R{self.max_r_achieved}"

    @classmethod
    def from_db_row(cls, row: dict) -> 'HighlightTrade':
        """Create from psycopg2 RealDictCursor row."""

        def to_float(val) -> Optional[float]:
            if val is None:
                return None
            if isinstance(val, Decimal):
                return float(val)
            return float(val)

        return cls(
            trade_id=row['trade_id'],
            date=row['date'],
            ticker=row['ticker'],
            direction=row['direction'],
            model=row.get('model'),
            zone_type=row.get('zone_type'),
            zone_high=to_float(row.get('zone_high')),
            zone_low=to_float(row.get('zone_low')),
            entry_price=to_float(row['entry_price']),
            entry_time=row['entry_time'],
            m5_atr_value=to_float(row.get('m5_atr_value')),
            stop_price=to_float(row.get('stop_price')),
            stop_distance=to_float(row.get('stop_distance')),
            r1_price=to_float(row.get('r1_price')),
            r2_price=to_float(row.get('r2_price')),
            r3_price=to_float(row.get('r3_price')),
            r4_price=to_float(row.get('r4_price')),
            r5_price=to_float(row.get('r5_price')),
            r1_hit=row.get('r1_hit', False) or False,
            r1_time=row.get('r1_time'),
            r1_bars=row.get('r1_bars_from_entry'),
            r2_hit=row.get('r2_hit', False) or False,
            r2_time=row.get('r2_time'),
            r2_bars=row.get('r2_bars_from_entry'),
            r3_hit=row.get('r3_hit', False) or False,
            r3_time=row.get('r3_time'),
            r3_bars=row.get('r3_bars_from_entry'),
            r4_hit=row.get('r4_hit', False) or False,
            r4_time=row.get('r4_time'),
            r4_bars=row.get('r4_bars_from_entry'),
            r5_hit=row.get('r5_hit', False) or False,
            r5_time=row.get('r5_time'),
            r5_bars=row.get('r5_bars_from_entry'),
            stop_hit=row.get('stop_hit', False) or False,
            stop_hit_time=row.get('stop_hit_time'),
            max_r_achieved=row.get('max_r_achieved', 0) or 0,
            outcome=row['outcome'],
            exit_reason=row['exit_reason'],
            is_winner=row.get('is_winner', False) or False,
            pnl_r=to_float(row.get('pnl_r')),
            outcome_method=row.get('outcome_method'),
            eod_price=to_float(row.get('eod_price')),
            reached_2r=row.get('reached_2r', False) or False,
            reached_3r=row.get('reached_3r', False) or False,
            minutes_to_r1=row.get('minutes_to_r1'),
        )
