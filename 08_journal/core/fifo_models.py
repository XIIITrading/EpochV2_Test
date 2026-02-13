"""
FIFO Trade Data Models for the Epoch Trading Journal.

Data flow: CSV row -> Fill -> FIFO Queue -> FIFOTrade -> FIFODailyLog

Key design decisions:
- Each entry-side fill creates a NEW FIFOTrade (adds are independent trades)
- Exits are matched FIFO: oldest open trade closes first
- A single exit fill can span multiple trades (partial + full closes)
- Exit price per trade = VWAP of all exit portions allocated to that trade
- S and SS are equivalent (both represent selling)
- CSV rows may NOT be in chronological order -- always sort by time

Separate from models.py to avoid breaking the existing Streamlit app.
Reuses Fill, FillSide, TradeDirection, TradeOutcome from models.py.
"""

from dataclasses import dataclass, field
from pydantic import BaseModel, Field, computed_field
from typing import Optional, List, Dict
from datetime import date, time, datetime
from enum import Enum

from .models import Fill, FillSide, TradeDirection, TradeOutcome


# =============================================================================
# Exit Portion -- one piece of an exit fill allocated to a FIFO trade
# =============================================================================

@dataclass
class ExitPortion:
    """
    One piece of an exit fill allocated to a specific FIFO trade.

    When a single exit fill spans multiple trades (e.g., B 12 closes
    2 shares of Trade #1 and 10 shares of Trade #2), each trade gets
    its own ExitPortion with the allocated qty.

    The exit fill's price is shared across all portions from that fill.
    """
    price: float        # Exit fill price
    qty: int            # Shares allocated to this trade from this fill
    time: time          # Exit fill time


# =============================================================================
# FIFO Trade -- a single trade from one entry fill with FIFO-matched exits
# =============================================================================

class FIFOTrade(BaseModel):
    """
    A single FIFO trade: one entry fill with FIFO-matched exits.

    Each entry-side fill (initial or add) creates a new FIFOTrade.
    Exits are matched FIFO -- oldest open trade closes first.
    A trade may receive exit portions from multiple exit fills.

    trade_id format: {SYMBOL}_{MMDDYY}_JRNL_{HHMM}_{SEQ:02d}
    Example: MU_021326_JRNL_0928_01
    """

    # === Identification ===
    trade_seq: int                      # Sequence number within symbol (1, 2, 3...)
    symbol: str
    trade_date: date
    direction: TradeDirection
    account: str = ""

    # === Entry (single fill -- each add creates a new trade) ===
    entry_price: float
    entry_qty: int
    entry_time: time

    # === Exit (FIFO-matched portions, possibly from multiple exit fills) ===
    exit_portions: List[ExitPortion] = Field(default_factory=list, exclude=True)
    remaining_qty: int                  # Decrements as exits close this trade

    # === Computed: Trade ID ===

    @computed_field
    @property
    def trade_id(self) -> str:
        """
        Format: {SYMBOL}_{MMDDYY}_JRNL_{HHMM}_{SEQ:02d}
        Example: MU_021326_JRNL_0928_01

        Uses JRNL to distinguish from backtest trades (EPCH1-4).
        Sequence number ensures uniqueness for multiple trades per symbol.
        """
        date_str = self.trade_date.strftime("%m%d%y")
        time_str = f"{self.entry_time.hour:02d}{self.entry_time.minute:02d}"
        return f"{self.symbol}_{date_str}_JRNL_{time_str}_{self.trade_seq:02d}"

    # === Computed: Exit Accessors ===

    @computed_field
    @property
    def is_closed(self) -> bool:
        """True if all entry shares have been exited."""
        return self.remaining_qty == 0 and len(self.exit_portions) > 0

    @computed_field
    @property
    def exit_price(self) -> Optional[float]:
        """VWAP exit price across all exit portions."""
        if not self.exit_portions:
            return None
        total_notional = sum(p.price * p.qty for p in self.exit_portions)
        total_qty = sum(p.qty for p in self.exit_portions)
        return total_notional / total_qty if total_qty else None

    @computed_field
    @property
    def exit_qty(self) -> int:
        """Total shares exited so far."""
        return sum(p.qty for p in self.exit_portions)

    @computed_field
    @property
    def exit_fills(self) -> int:
        """Number of exit portions (distinct exit fill allocations)."""
        return len(self.exit_portions)

    @computed_field
    @property
    def exit_time(self) -> Optional[time]:
        """Time of last exit portion (when trade was fully closed)."""
        if not self.exit_portions:
            return None
        return max(p.time for p in self.exit_portions)

    # === Computed: P&L ===

    @computed_field
    @property
    def pnl_dollars(self) -> Optional[float]:
        """Per-share P&L. Matches existing journal_trades convention."""
        if self.exit_price is None:
            return None
        if self.direction == TradeDirection.LONG:
            return self.exit_price - self.entry_price
        else:
            return self.entry_price - self.exit_price

    @computed_field
    @property
    def pnl_total(self) -> Optional[float]:
        """Total dollar P&L (per-share P&L * entry qty)."""
        if self.pnl_dollars is None:
            return None
        return self.pnl_dollars * self.entry_qty

    @computed_field
    @property
    def outcome(self) -> TradeOutcome:
        """Win/Loss/Breakeven classification."""
        if not self.is_closed or self.pnl_dollars is None:
            return TradeOutcome.OPEN
        if self.pnl_dollars > 0:
            return TradeOutcome.WIN
        elif self.pnl_dollars < 0:
            return TradeOutcome.LOSS
        return TradeOutcome.BREAKEVEN

    # === Computed: Duration ===

    @computed_field
    @property
    def duration_seconds(self) -> Optional[int]:
        """Trade duration from entry fill to last exit portion."""
        if self.entry_time is None or self.exit_time is None:
            return None
        entry_dt = datetime.combine(self.trade_date, self.entry_time)
        exit_dt = datetime.combine(self.trade_date, self.exit_time)
        return int((exit_dt - entry_dt).total_seconds())

    @computed_field
    @property
    def duration_display(self) -> Optional[str]:
        """Human-readable duration string (e.g., '1m 50s')."""
        if self.duration_seconds is None:
            return None
        minutes = self.duration_seconds // 60
        seconds = self.duration_seconds % 60
        return f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

    # === Serialization ===

    def to_db_row(self, source_file: str = "") -> Dict:
        """
        Serialize FIFOTrade to flat dict for DB insert into journal_trades.
        Produces the same shape as Trade.to_db_row() so JournalDB.save_trade() works.

        Additional FIFO-specific fields: trade_seq, processing_mode.
        """
        return {
            "trade_id": self.trade_id,
            "trade_date": self.trade_date,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "account": self.account,
            "entry_price": round(self.entry_price, 4),
            "entry_time": self.entry_time,
            "entry_qty": self.entry_qty,
            "entry_fills": 1,               # Always 1 -- each add is its own trade
            "exit_price": round(self.exit_price, 4) if self.exit_price is not None else None,
            "exit_time": self.exit_time,
            "exit_qty": self.exit_qty if self.exit_qty > 0 else None,
            "exit_fills": self.exit_fills if self.exit_fills > 0 else None,
            "pnl_dollars": round(self.pnl_dollars, 4) if self.pnl_dollars is not None else None,
            "pnl_total": round(self.pnl_total, 2) if self.pnl_total is not None else None,
            "pnl_r": None,                  # Requires stop_price (set in review)
            "outcome": self.outcome.value,
            "duration_seconds": self.duration_seconds,
            "zone_id": None,                # Set in review
            "model": None,                  # Set in review
            "stop_price": None,             # Set in review
            "notes": None,                  # Set in review
            "source_file": source_file,
            "is_closed": self.is_closed,
            "trade_seq": self.trade_seq,
            "processing_mode": "FIFO",
        }


# =============================================================================
# FIFO Daily Log -- all FIFO trades from one CSV session
# =============================================================================

class FIFODailyLog(BaseModel):
    """
    All FIFO trades from a single trading session (one CSV file).
    Contains parsed trades plus any errors encountered during processing.
    """
    trade_date: date
    source_file: str
    trades: List[FIFOTrade] = Field(default_factory=list)
    parse_errors: List[str] = Field(default_factory=list)

    @computed_field
    @property
    def trade_count(self) -> int:
        """Total number of FIFO trades in this session."""
        return len(self.trades)

    @computed_field
    @property
    def closed_count(self) -> int:
        """Number of fully closed trades."""
        return sum(1 for t in self.trades if t.is_closed)

    @computed_field
    @property
    def open_count(self) -> int:
        """Number of trades still open (should be 0 in practice)."""
        return sum(1 for t in self.trades if not t.is_closed)

    @computed_field
    @property
    def symbols_traded(self) -> List[str]:
        """Sorted list of unique symbols traded."""
        return sorted(set(t.symbol for t in self.trades))

    @computed_field
    @property
    def total_pnl(self) -> float:
        """Total P&L across all closed trades."""
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
        """Win rate as a decimal (0.0-1.0). None if no closed trades."""
        closed = self.closed_count
        return self.win_count / closed if closed > 0 else None
