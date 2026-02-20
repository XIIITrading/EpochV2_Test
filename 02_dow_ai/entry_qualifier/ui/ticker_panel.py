"""
Ticker Panel Widget
Epoch Trading System v1 - XIII Trading LLC

Individual ticker panel displaying rolling indicator data.
"""
import sys
from pathlib import Path

# Ensure entry_qualifier is at the front of sys.path
_entry_qualifier_dir = str(Path(__file__).parent.parent.resolve())
if _entry_qualifier_dir not in sys.path:
    sys.path.insert(0, _entry_qualifier_dir)
elif sys.path[0] != _entry_qualifier_dir:
    sys.path.remove(_entry_qualifier_dir)
    sys.path.insert(0, _entry_qualifier_dir)

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QLabel, QPushButton, QFrame, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from typing import List, Optional
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from eq_config import ROLLING_BARS, MILLION_THRESHOLD, THOUSAND_THRESHOLD
from ui.styles import COLORS, get_delta_style

# Eastern Time zone for display
_ET = ZoneInfo("America/New_York")


class TickerPanel(QFrame):
    """
    Panel widget for displaying a single ticker's rolling data.

    Displays a table with 8 rows and 26 columns (25 rolling bars + label column).
    Rows: Time, Candle Range, Vol Delta, Vol ROC, SMA Config, M5 Struct, M15 Struct, H1 Structure
    """

    # Signal emitted when remove button is clicked
    remove_requested = pyqtSignal(str)  # ticker

    # Row indices (top to bottom)
    ROW_TIME = 0
    ROW_CANDLE_RANGE = 1
    ROW_VOL_DELTA = 2
    ROW_VOL_ROC = 3
    ROW_SMA_CONFIG = 4
    ROW_M5_STRUCTURE = 5
    ROW_M15_STRUCTURE = 6
    ROW_H1_STRUCTURE = 7

    NUM_ROWS = 8

    # Row labels
    ROW_LABELS = {
        ROW_TIME: 'Time',
        ROW_CANDLE_RANGE: 'Candle %',
        ROW_VOL_DELTA: 'Vol Δ',
        ROW_VOL_ROC: 'Vol ROC',
        ROW_SMA_CONFIG: 'SMA',
        ROW_M5_STRUCTURE: 'M5 Struct',
        ROW_M15_STRUCTURE: 'M15 Struct',
        ROW_H1_STRUCTURE: 'H1 Struct'
    }

    def __init__(self, ticker: str = None, parent=None):
        super().__init__(parent)
        self.ticker = ticker
        self._bars_data: List[dict] = []

        self.setObjectName("tickerPanel")
        self._setup_ui()

    def _setup_ui(self):
        """Set up the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        # Header row with ticker name and remove button
        header_layout = QHBoxLayout()

        self.ticker_label = QLabel(self.ticker or "No Ticker Configured")
        self.ticker_label.setObjectName("tickerLabel")
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        self.ticker_label.setFont(font)

        self.remove_btn = QPushButton("\u2715")  # X symbol
        self.remove_btn.setObjectName("removeButton")
        self.remove_btn.setFixedSize(24, 24)
        self.remove_btn.clicked.connect(self._on_remove_clicked)
        self.remove_btn.setToolTip("Remove ticker")

        header_layout.addWidget(self.ticker_label)
        header_layout.addStretch()
        header_layout.addWidget(self.remove_btn)

        layout.addLayout(header_layout)

        # Create the data table
        self._create_table()
        layout.addWidget(self.table)

        # Show placeholder if no ticker
        if not self.ticker:
            self._show_placeholder()

    def _create_table(self):
        """Create the data table widget."""
        # 7 rows, 26 columns (1 label + 25 data)
        self.table = QTableWidget(self.NUM_ROWS, ROLLING_BARS + 1)

        # Set up headers: label column first (empty), then 0 to -24 (left to right, newest to oldest)
        headers = [''] + [str(-i) for i in range(ROLLING_BARS)]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setVerticalHeaderLabels([''] * self.NUM_ROWS)

        # Hide vertical header
        self.table.verticalHeader().setVisible(False)

        # Disable vertical scrollbar — all 7 rows must be visible without scrolling
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Row heights sized for 11pt font readability
        ROW_HEIGHT = 26
        HEADER_HEIGHT = 24
        for row in range(self.NUM_ROWS):
            self.table.setRowHeight(row, ROW_HEIGHT)
        self.table.horizontalHeader().setFixedHeight(HEADER_HEIGHT)

        # Fixed table height: header + 7 rows + 2px border
        table_height = HEADER_HEIGHT + (self.NUM_ROWS * ROW_HEIGHT) + 2
        self.table.setFixedHeight(table_height)

        # Configure horizontal header
        h_header = self.table.horizontalHeader()
        h_header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        h_header.setMinimumSectionSize(40)

        # Set first column (label column) to fixed width
        h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 90)

        # Disable editing and selection
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Initialize cells
        self._initialize_cells()

    def _initialize_cells(self):
        """Initialize all cells with default values."""
        cell_font = QFont("Segoe UI", 11)  # 11pt font for readability

        for row in range(self.NUM_ROWS):
            for col in range(ROLLING_BARS + 1):
                item = QTableWidgetItem()
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFont(cell_font)

                if col == 0:
                    # Label column (first column)
                    item.setText(self.ROW_LABELS.get(row, ''))
                    item.setForeground(QColor(COLORS['text_secondary']))
                else:
                    # Data column - show dash for empty
                    item.setText('-')
                    item.setForeground(QColor(COLORS['text_muted']))

                self.table.setItem(row, col, item)

    def _show_placeholder(self):
        """Show placeholder state when no ticker is configured."""
        self.ticker_label.setText("No Ticker Configured")
        self.ticker_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        self.remove_btn.hide()
        self.table.setEnabled(False)

    def set_ticker(self, ticker: str):
        """Set the ticker for this panel."""
        self.ticker = ticker.upper().strip() if ticker else None

        if self.ticker:
            self.ticker_label.setText(self.ticker)
            self.ticker_label.setStyleSheet(f"color: {COLORS['text_primary']};")
            self.remove_btn.show()
            self.table.setEnabled(True)
        else:
            self._show_placeholder()

    def update_data(self, bars: List[dict]):
        """
        Update the panel with new bar data.

        Args:
            bars: List of processed bar dictionaries with keys:
                  timestamp, open, high, low, close, volume,
                  raw_delta, roll_delta, candle_range_pct
        """
        self._bars_data = bars

        # Take the most recent ROLLING_BARS
        display_bars = bars[-ROLLING_BARS:] if len(bars) >= ROLLING_BARS else bars

        # Calculate offset if we have fewer bars than columns
        # Data columns start at index 1 (column 0 is the label column)
        offset = ROLLING_BARS - len(display_bars)

        # Clear cells after the available data (data columns start at 1)
        # With reversed order, empty cells are at the end (higher column indices)
        for row in range(self.NUM_ROWS):
            for col in range(len(display_bars) + 1, ROLLING_BARS + 1):
                item = self.table.item(row, col)
                if item:
                    item.setText('-')
                    item.setForeground(QColor(COLORS['text_muted']))
                    item.setBackground(QColor(COLORS['bg_cell']))

        # Update data cells (data columns start at 1, newest first)
        # Reverse the display_bars so most recent (index -1) maps to column 1
        for i, bar in enumerate(reversed(display_bars)):
            col = i + 1  # +1 because column 0 is the label column

            # Update Time (Row 0)
            timestamp_ms = bar.get('timestamp', 0)
            self._update_time_cell(col, timestamp_ms)

            # Get indicator values
            candle_range_pct = bar.get('candle_range_pct', 0)
            roll_delta = bar.get('roll_delta')
            volume_roc = bar.get('volume_roc')

            # Update Candle Range %
            self._update_candle_range_cell(col, candle_range_pct)

            # Update Vol Delta (Row 1) - using roll_delta as primary
            self._update_delta_cell(self.ROW_VOL_DELTA, col, roll_delta)

            # Update Vol ROC (Row 2)
            self._update_volume_roc_cell(col, volume_roc)

            # Update SMA Config (Row 3)
            sma_display = bar.get('sma_display')
            sma_config = bar.get('sma_config')
            self._update_sma_cell(col, sma_display, sma_config)

            # Update M5 Structure (Row 4)
            m5_display = bar.get('m5_display')
            m5_structure = bar.get('m5_structure')
            self._update_structure_cell(self.ROW_M5_STRUCTURE, col, m5_display, m5_structure)

            # Update M15 Structure (Row 5)
            m15_display = bar.get('m15_display')
            m15_structure = bar.get('m15_structure')
            self._update_structure_cell(self.ROW_M15_STRUCTURE, col, m15_display, m15_structure)

            # Update H1 Structure (Row 6)
            h1_display = bar.get('h1_display')
            h1_structure = bar.get('h1_structure')
            self._update_structure_cell(self.ROW_H1_STRUCTURE, col, h1_display, h1_structure)

    def _update_time_cell(self, col: int, timestamp_ms: int):
        """Update the time cell with HH:MM format from millisecond epoch."""
        item = self.table.item(self.ROW_TIME, col)
        if not item:
            item = QTableWidgetItem()
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(self.ROW_TIME, col, item)

        item.setBackground(QColor(COLORS['bg_cell']))

        if timestamp_ms == 0:
            item.setText('-')
            item.setForeground(QColor(COLORS['text_muted']))
            return

        # Convert ms epoch to ET time string
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        # Polygon timestamps are UTC — convert to ET
        et = dt.astimezone(_ET)
        item.setText(et.strftime("%H:%M"))
        item.setForeground(QColor(COLORS['text_secondary']))

    def _update_delta_cell(self, row: int, col: int, value: Optional[float]):
        """Update a delta cell."""
        item = self.table.item(row, col)
        if not item:
            item = QTableWidgetItem()
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, col, item)

        item.setBackground(QColor(COLORS['bg_cell']))

        if value is None:
            item.setText('-')
            item.setForeground(QColor(COLORS['text_muted']))
            return

        item.setText(self._format_number(value))

        if value > 0:
            item.setForeground(QColor(COLORS['positive']))
        elif value < 0:
            item.setForeground(QColor(COLORS['negative']))
        else:
            item.setForeground(QColor(COLORS['text_primary']))

    def _update_candle_range_cell(self, col: int, value: float):
        """Update the candle range cell with percentage formatting."""
        item = self.table.item(self.ROW_CANDLE_RANGE, col)
        if not item:
            item = QTableWidgetItem()
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(self.ROW_CANDLE_RANGE, col, item)

        item.setBackground(QColor(COLORS['bg_cell']))
        item.setText(f"{value:.2f}%")
        item.setForeground(QColor(COLORS['text_primary']))

    def _update_volume_roc_cell(self, col: int, value: Optional[float]):
        """Update the volume ROC cell with percentage formatting."""
        item = self.table.item(self.ROW_VOL_ROC, col)
        if not item:
            item = QTableWidgetItem()
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(self.ROW_VOL_ROC, col, item)

        item.setBackground(QColor(COLORS['bg_cell']))

        if value is None:
            item.setText('-')
            item.setForeground(QColor(COLORS['text_muted']))
            return

        item.setText(f"{value:+.0f}%")

        if value > 0:
            item.setForeground(QColor(COLORS['positive']))
        elif value < 0:
            item.setForeground(QColor(COLORS['negative']))
        else:
            item.setForeground(QColor(COLORS['text_primary']))

    def _update_sma_cell(self, col: int, display: Optional[str], config):
        """Update the SMA config cell."""
        item = self.table.item(self.ROW_SMA_CONFIG, col)
        if not item:
            item = QTableWidgetItem()
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(self.ROW_SMA_CONFIG, col, item)

        item.setBackground(QColor(COLORS['bg_cell']))

        if display is None:
            item.setText('-')
            item.setForeground(QColor(COLORS['text_muted']))
            return

        item.setText(display)

        # Simple color: B+=green, B-=red, else=white
        if config is not None:
            config_value = config.value if hasattr(config, 'value') else str(config)
            if config_value == 'B+':
                item.setForeground(QColor(COLORS['positive']))
            elif config_value == 'B-':
                item.setForeground(QColor(COLORS['negative']))
            else:
                item.setForeground(QColor(COLORS['text_primary']))
        else:
            item.setForeground(QColor(COLORS['text_primary']))

    def _update_structure_cell(self, row: int, col: int, display: Optional[str], structure):
        """Update a structure cell (M5, M15, or H1)."""
        item = self.table.item(row, col)
        if not item:
            item = QTableWidgetItem()
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, col, item)

        item.setBackground(QColor(COLORS['bg_cell']))

        if display is None:
            item.setText('-')
            item.setForeground(QColor(COLORS['text_muted']))
            return

        item.setText(display)

        # Simple color: B+=green, B-=red, N=white
        if structure is not None:
            struct_value = structure.value if hasattr(structure, 'value') else str(structure)
            if struct_value == 'B+':
                item.setForeground(QColor(COLORS['positive']))
            elif struct_value == 'B-':
                item.setForeground(QColor(COLORS['negative']))
            else:
                item.setForeground(QColor(COLORS['text_primary']))
        else:
            item.setForeground(QColor(COLORS['text_primary']))

    def _format_number(self, value: float) -> str:
        """
        Format a number for display.

        Formats:
        - >= 1,000,000: X.XM (rounded to whole number for abbreviation)
        - >= 1,000: Xk (rounded to whole number)
        - < 1,000: Whole number
        - Negative: Prefix with -
        - Positive: Prefix with +
        """
        if value == 0:
            return '0'

        sign = '+' if value > 0 else ''
        abs_value = abs(value)

        if abs_value >= MILLION_THRESHOLD:
            # Format as millions (whole number)
            formatted = f"{sign}{int(value / MILLION_THRESHOLD)}M"
        elif abs_value >= THOUSAND_THRESHOLD:
            # Format as thousands (whole number)
            formatted = f"{sign}{int(value / THOUSAND_THRESHOLD)}k"
        else:
            # Whole number
            formatted = f"{sign}{int(value)}"

        return formatted

    def clear_data(self):
        """Clear all data cells (on error or ticker removal)."""
        for row in range(self.NUM_ROWS):
            # Data columns start at 1 (column 0 is the label column)
            for col in range(1, ROLLING_BARS + 1):
                item = self.table.item(row, col)
                if item:
                    item.setText('-')
                    item.setForeground(QColor(COLORS['text_muted']))
                    item.setBackground(QColor(COLORS['bg_cell']))

    def show_error(self, message: str):
        """Display error state (blank cells, show message in label)."""
        self.clear_data()
        # Could add error indicator to UI here if needed

    def _on_remove_clicked(self):
        """Handle remove button click."""
        if self.ticker:
            self.remove_requested.emit(self.ticker)

    def get_ticker(self) -> Optional[str]:
        """Get the current ticker."""
        return self.ticker

    def has_ticker(self) -> bool:
        """Check if a ticker is configured."""
        return self.ticker is not None and len(self.ticker) > 0
