"""
Trade Table Widget for Journal Viewer
Epoch Trading System - XIII Trading LLC

Displays journal trades in a sortable table.
Single-row selection triggers chart rendering (no checkboxes).
Adapted from 11_trade_reel/ui/highlight_table.py.
"""

from typing import List, Dict, Optional
from decimal import Decimal

from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QFont

from .config import TV_COLORS


# Column configuration
COLUMNS = [
    ('Date', 90),
    ('Ticker', 60),
    ('Dir', 55),
    ('Entry', 70),
    ('Exit', 70),
    ('PnL', 65),
    ('Qty', 45),
    ('R', 45),
    ('Outcome', 60),
]


class TradeTable(QTableWidget):
    """
    Table widget displaying journal trades.
    Single-row selection emits trade row dict.
    """

    # Emitted when a row is selected, with the trade row dict
    selection_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._trades: List[Dict] = []
        self._setup_table()

    def _setup_table(self):
        """Configure table appearance and behavior."""
        self.setColumnCount(len(COLUMNS))
        self.setHorizontalHeaderLabels([col[0] for col in COLUMNS])

        # Set column widths
        for i, (_, width) in enumerate(COLUMNS):
            self.setColumnWidth(i, width)

        # Appearance
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSortingEnabled(True)

        # Header
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        # Row height
        self.verticalHeader().setDefaultSectionSize(28)

        # Connect selection signal
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def set_trades(self, trades: List[Dict]):
        """
        Populate the table with journal trade rows.

        Args:
            trades: List of trade dicts from JournalDB.get_trades_by_range()
        """
        self._trades = trades
        self.setSortingEnabled(False)
        self.setRowCount(len(trades))

        for row_idx, trade in enumerate(trades):
            self._populate_row(row_idx, trade)

        self.setSortingEnabled(True)
        self.clearSelection()

    def _populate_row(self, row_idx: int, trade: Dict):
        """Fill one table row from a trade dict."""

        def to_float(val) -> Optional[float]:
            if val is None:
                return None
            if isinstance(val, Decimal):
                return float(val)
            return float(val)

        direction = (trade.get('direction') or '').upper()
        entry_price = to_float(trade.get('entry_price'))
        exit_price = to_float(trade.get('exit_price'))
        pnl = to_float(trade.get('pnl_dollars'))
        entry_qty = trade.get('entry_qty', 0) or 0
        outcome = (trade.get('outcome') or '').upper()
        trade_date = trade.get('trade_date') or trade.get('date')
        # Read pre-computed M5 max R from DB (falls back to 0 if not computed)
        max_r = trade.get('m5_max_r', 0) or trade.get('max_r_achieved', 0) or 0

        # Determine outcome from PnL if not set
        if not outcome and pnl is not None:
            outcome = 'WIN' if pnl > 0 else 'LOSS'

        # Colors
        dir_color = QColor(TV_COLORS['bull']) if direction == 'LONG' else QColor(TV_COLORS['bear'])
        pnl_color = QColor(TV_COLORS['bull']) if (pnl and pnl > 0) else QColor(TV_COLORS['bear'])
        outcome_color = QColor(TV_COLORS['bull']) if outcome == 'WIN' else QColor(TV_COLORS['bear'])

        items = []

        # Date
        date_str = str(trade_date) if trade_date else ""
        items.append(self._make_item(date_str))

        # Ticker
        ticker_item = self._make_item((trade.get('symbol') or '').upper())
        ticker_item.setFont(QFont("Trebuchet MS", 10, QFont.Weight.Bold))
        items.append(ticker_item)

        # Direction
        dir_item = self._make_item(direction)
        dir_item.setForeground(dir_color)
        items.append(dir_item)

        # Entry price
        entry_str = f"${entry_price:.2f}" if entry_price else ""
        items.append(self._make_item(entry_str))

        # Exit price
        exit_str = f"${exit_price:.2f}" if exit_price else ""
        items.append(self._make_item(exit_str))

        # PnL ($/share)
        if pnl is not None and entry_qty:
            pnl_per_share = pnl / entry_qty if entry_qty > 0 else 0
            pnl_str = f"${pnl_per_share:+.2f}"
        elif pnl is not None:
            pnl_str = f"${pnl:+.2f}"
        else:
            pnl_str = ""
        pnl_item = self._make_item(pnl_str)
        pnl_item.setForeground(pnl_color)
        items.append(pnl_item)

        # Qty
        items.append(self._make_item(str(entry_qty)))

        # R (max R achieved, will be computed later)
        r_str = f"R{max_r}" if max_r > 0 else ""
        items.append(self._make_item(r_str))

        # Outcome
        outcome_item = self._make_item(outcome)
        outcome_item.setForeground(outcome_color)
        outcome_item.setFont(QFont("Trebuchet MS", 9, QFont.Weight.Bold))
        items.append(outcome_item)

        # Set all items in row
        for col_idx, item in enumerate(items):
            item.setData(Qt.ItemDataRole.UserRole, row_idx)  # Store row index
            self.setItem(row_idx, col_idx, item)

    def _make_item(self, text: str) -> QTableWidgetItem:
        """Create a centered, non-editable table item."""
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def _on_selection_changed(self):
        """Handle row selection change."""
        selected = self.selectedItems()
        if not selected:
            self.selection_changed.emit(None)
            return

        # Get the original trade index from UserRole
        row_idx = selected[0].data(Qt.ItemDataRole.UserRole)
        if row_idx is not None and 0 <= row_idx < len(self._trades):
            self.selection_changed.emit(self._trades[row_idx])
        else:
            self.selection_changed.emit(None)

    def update_trade_r(self, trade_id: str, max_r: int, pnl_r: Optional[float] = None):
        """
        Update the R column for a specific trade after ATR calculation.

        Args:
            trade_id: The trade_id to update
            max_r: Max R achieved value
            pnl_r: PnL in R terms
        """
        for row_idx in range(self.rowCount()):
            item = self.item(row_idx, 0)
            if item is None:
                continue
            orig_idx = item.data(Qt.ItemDataRole.UserRole)
            if orig_idx is not None and orig_idx < len(self._trades):
                if self._trades[orig_idx].get('trade_id') == trade_id:
                    # Update R column (index 7)
                    r_str = f"R{max_r}" if max_r > 0 else ""
                    r_item = self._make_item(r_str)
                    r_item.setData(Qt.ItemDataRole.UserRole, orig_idx)
                    self.setItem(row_idx, 7, r_item)
                    break

    def get_selected_trade(self) -> Optional[Dict]:
        """Get the currently selected trade dict, or None."""
        selected = self.selectedItems()
        if not selected:
            return None
        row_idx = selected[0].data(Qt.ItemDataRole.UserRole)
        if row_idx is not None and 0 <= row_idx < len(self._trades):
            return self._trades[row_idx]
        return None

    def clear_trades(self):
        """Clear all trades from the table."""
        self._trades = []
        self.setRowCount(0)
