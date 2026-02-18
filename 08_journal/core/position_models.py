"""
Position-Based Trade Data Models for the Epoch Trading Journal.

Data flow: CSV row -> Fill -> PositionTrade -> PositionDailyLog

Key design decisions:
- One PositionTrade per symbol per session (all fills tracked as events)
- Every fill is classified as ENTRY, ADD, or EXIT
- Running position size tracked after each fill
- Stop/R-levels based on initial entry price (first fill)
- P&L computed from net cash flow across all fills
- fills_json stores ALL fills for DAS-style chart rendering
- exit_portions_json maintained for backward compatibility

Reuses Fill, FillSide, TradeDirection, TradeOutcome from models.py.
"""

import json
from dataclasses import dataclass
from pydantic import BaseModel, Field, computed_field
from typing import Optional, List, Dict
from datetime import date, time, datetime
from enum import Enum

from .models import Fill, FillSide, TradeDirection, TradeOutcome


# =============================================================================
# Fill Type -- classification within a position
# =============================================================================

class FillType(str, Enum):
    ENTRY = "ENTRY"     # First same-direction fill (opens position)
    ADD = "ADD"         # Subsequent same-direction fill (scales in)
    EXIT = "EXIT"       # Opposite-direction fill (reduces position)


# =============================================================================
# Position Fill -- one fill within a position lifecycle
# =============================================================================

@dataclass
class PositionFill:
    """
    A single fill within a position, classified by its role.

    Tracks the running position size after this fill executes,
    enabling DAS Trader-style chart rendering with triangles at every fill.
    """
    side: FillSide          # B, SS, S
    fill_type: FillType     # ENTRY, ADD, EXIT
    price: float
    qty: int
    time: time
    position_after: int     # Shares held after this fill

    def to_dict(self) -> Dict:
        """Serialize for JSON storage in fills_json."""
        return {
            "side": self.side.value,
            "type": self.fill_type.value,
            "price": round(self.price, 4),
            "qty": self.qty,
            "time": self.time.strftime("%H:%M:%S"),
            "position_after": self.position_after,
        }


# =============================================================================
# Position Trade -- full lifecycle from first fill to flat
# =============================================================================

class PositionTrade(BaseModel):
    """
    A single position trade: all fills from open to flat.

    One PositionTrade per symbol per session. Tracks entries, adds,
    partial exits, and final exit as events within the position.

    trade_id format: {SYMBOL}_{MMDDYY}_JRNL_{HHMM}
    Example: MU_021726_JRNL_0940
    """

    # === Identification ===
    symbol: str
    trade_date: date
    direction: TradeDirection
    account: str = ""

    # === All fills (chronological) ===
    fills: List[PositionFill] = Field(default_factory=list, exclude=True)

    # === Computed: Trade ID ===

    @computed_field
    @property
    def trade_id(self) -> str:
        """
        Format: {SYMBOL}_{MMDDYY}_JRNL_{HHMM}
        One per symbol per session (no sequence suffix).
        """
        date_str = self.trade_date.strftime("%m%d%y")
        if self.fills:
            t = self.fills[0].time
            time_str = f"{t.hour:02d}{t.minute:02d}"
        else:
            time_str = "0000"
        return f"{self.symbol}_{date_str}_JRNL_{time_str}"

    # === Computed: Entry accessors (initial entry = first fill) ===

    @computed_field
    @property
    def initial_entry_price(self) -> float:
        """First fill price -- used for stop/R-level calculation."""
        return self.fills[0].price if self.fills else 0.0

    @computed_field
    @property
    def initial_entry_time(self) -> Optional[time]:
        """First fill time."""
        return self.fills[0].time if self.fills else None

    @computed_field
    @property
    def entry_fills_list(self) -> List[PositionFill]:
        """All entry-side fills (ENTRY + ADD)."""
        return [f for f in self.fills if f.fill_type in (FillType.ENTRY, FillType.ADD)]

    @computed_field
    @property
    def exit_fills_list(self) -> List[PositionFill]:
        """All exit-side fills."""
        return [f for f in self.fills if f.fill_type == FillType.EXIT]

    @computed_field
    @property
    def avg_entry_price(self) -> float:
        """VWAP of all entry-side fills."""
        entries = self.entry_fills_list
        if not entries:
            return 0.0
        total_notional = sum(f.price * f.qty for f in entries)
        total_qty = sum(f.qty for f in entries)
        return total_notional / total_qty if total_qty else 0.0

    @computed_field
    @property
    def avg_exit_price(self) -> Optional[float]:
        """VWAP of all exit-side fills."""
        exits = self.exit_fills_list
        if not exits:
            return None
        total_notional = sum(f.price * f.qty for f in exits)
        total_qty = sum(f.qty for f in exits)
        return total_notional / total_qty if total_qty else None

    @computed_field
    @property
    def total_entry_qty(self) -> int:
        """Total shares entered (entries + adds)."""
        return sum(f.qty for f in self.entry_fills_list)

    @computed_field
    @property
    def total_exit_qty(self) -> int:
        """Total shares exited."""
        return sum(f.qty for f in self.exit_fills_list)

    @computed_field
    @property
    def entry_fill_count(self) -> int:
        """Number of entry-side fills."""
        return len(self.entry_fills_list)

    @computed_field
    @property
    def exit_fill_count(self) -> int:
        """Number of exit-side fills."""
        return len(self.exit_fills_list)

    @computed_field
    @property
    def max_position_size(self) -> int:
        """Peak shares held during the position lifecycle."""
        if not self.fills:
            return 0
        return max(f.position_after for f in self.fills)

    @computed_field
    @property
    def last_exit_time(self) -> Optional[time]:
        """Time of the last exit fill."""
        exits = self.exit_fills_list
        if not exits:
            return None
        return max(f.time for f in exits)

    @computed_field
    @property
    def is_closed(self) -> bool:
        """True if position is flat (all shares exited)."""
        return self.total_exit_qty >= self.total_entry_qty and self.total_exit_qty > 0

    # === Computed: P&L ===

    @computed_field
    @property
    def pnl_total(self) -> Optional[float]:
        """
        Total dollar P&L from net cash flow.
        SHORT: cash_in (sells) - cash_out (buys)
        LONG: cash_in (buys resold) - cash_out (buys)
        """
        if not self.exit_fills_list:
            return None

        sell_cash = sum(
            f.price * f.qty for f in self.fills
            if f.side.is_sell_side
        )
        buy_cash = sum(
            f.price * f.qty for f in self.fills
            if f.side.is_buy_side
        )
        # Sell cash - buy cash = net P&L (positive = profit for shorts, negative = profit for longs)
        # For SHORT: sell high, buy low -> sell_cash > buy_cash -> positive
        # For LONG: buy low, sell high -> buy_cash < sell_cash -> positive
        return sell_cash - buy_cash

    @computed_field
    @property
    def pnl_per_share(self) -> Optional[float]:
        """Per-share P&L based on total P&L / total entry qty."""
        if self.pnl_total is None or self.total_entry_qty == 0:
            return None
        return self.pnl_total / self.total_entry_qty

    @computed_field
    @property
    def outcome(self) -> TradeOutcome:
        """Win/Loss/Breakeven classification."""
        if not self.is_closed or self.pnl_total is None:
            return TradeOutcome.OPEN
        if self.pnl_total > 0:
            return TradeOutcome.WIN
        elif self.pnl_total < 0:
            return TradeOutcome.LOSS
        return TradeOutcome.BREAKEVEN

    # === Computed: Duration ===

    @computed_field
    @property
    def duration_seconds(self) -> Optional[int]:
        """Duration from first fill to last exit."""
        if not self.fills or self.last_exit_time is None:
            return None
        entry_dt = datetime.combine(self.trade_date, self.fills[0].time)
        exit_dt = datetime.combine(self.trade_date, self.last_exit_time)
        return int((exit_dt - entry_dt).total_seconds())

    @computed_field
    @property
    def duration_display(self) -> Optional[str]:
        """Human-readable duration string."""
        if self.duration_seconds is None:
            return None
        minutes = self.duration_seconds // 60
        seconds = self.duration_seconds % 60
        return f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

    # === Serialization ===

    def to_db_row(self, source_file: str = "") -> Dict:
        """
        Serialize PositionTrade to flat dict for DB insert into journal_trades.
        Compatible with the existing column schema.
        """
        # Build exit_portions_json for backward compatibility with chart rendering
        exit_portions = [
            {"price": round(f.price, 4), "qty": f.qty, "time": f.time.strftime("%H:%M:%S")}
            for f in self.exit_fills_list
        ]

        return {
            "trade_id": self.trade_id,
            "trade_date": self.trade_date,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "account": self.account,
            "entry_price": round(self.initial_entry_price, 4),
            "entry_time": self.initial_entry_time,
            "entry_qty": self.total_entry_qty,
            "entry_fills": self.entry_fill_count,
            "exit_price": round(self.avg_exit_price, 4) if self.avg_exit_price is not None else None,
            "exit_time": self.last_exit_time,
            "exit_qty": self.total_exit_qty if self.total_exit_qty > 0 else None,
            "exit_fills": self.exit_fill_count if self.exit_fill_count > 0 else None,
            "pnl_dollars": round(self.pnl_per_share, 4) if self.pnl_per_share is not None else None,
            "pnl_total": round(self.pnl_total, 2) if self.pnl_total is not None else None,
            "pnl_r": None,
            "outcome": self.outcome.value,
            "duration_seconds": self.duration_seconds,
            "zone_id": None,
            "model": None,
            "stop_price": None,
            "notes": None,
            "source_file": source_file,
            "is_closed": self.is_closed,
            "trade_seq": 1,         # Always 1 -- one position per symbol
            "processing_mode": "POSITION",
            "exit_portions_json": json.dumps(exit_portions) if exit_portions else None,
            "fills_json": json.dumps([f.to_dict() for f in self.fills]) if self.fills else None,
        }


# =============================================================================
# Position Daily Log -- all positions from one CSV session
# =============================================================================

class PositionDailyLog(BaseModel):
    """
    All position trades from a single trading session (one CSV file).
    """
    trade_date: date
    source_file: str
    trades: List[PositionTrade] = Field(default_factory=list)
    parse_errors: List[str] = Field(default_factory=list)

    @computed_field
    @property
    def trade_count(self) -> int:
        return len(self.trades)

    @computed_field
    @property
    def closed_count(self) -> int:
        return sum(1 for t in self.trades if t.is_closed)

    @computed_field
    @property
    def open_count(self) -> int:
        return sum(1 for t in self.trades if not t.is_closed)

    @computed_field
    @property
    def symbols_traded(self) -> List[str]:
        return sorted(set(t.symbol for t in self.trades))

    @computed_field
    @property
    def total_pnl(self) -> float:
        return sum(t.pnl_total or 0.0 for t in self.trades if t.is_closed)

    @computed_field
    @property
    def win_count(self) -> int:
        return sum(1 for t in self.trades if t.outcome == TradeOutcome.WIN)

    @computed_field
    @property
    def loss_count(self) -> int:
        return sum(1 for t in self.trades if t.outcome == TradeOutcome.LOSS)

    @computed_field
    @property
    def win_rate(self) -> Optional[float]:
        closed = self.closed_count
        return self.win_count / closed if closed > 0 else None
