"""
Main Window
Epoch Trading System v3.0 - XIII Trading LLC

Main application window for the Entry Qualifier.
v3.0: Dual-pass AI analysis with user notes input.
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
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont
from datetime import datetime
from typing import Dict, List, Optional

from eq_config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, MAX_TICKERS,
    ROLLING_BARS, PREFETCH_BARS, FETCH_DELAY_MS
)
from data.market_hours import MarketHours
from data.api_client import PolygonClient
from data.data_worker import DataWorker
from calculations.volume_delta import calculate_all_deltas
from ui.ticker_panel import TickerPanel
from ui.ticker_dialog import TickerDialog
from ui.global_control_panel import GlobalControlPanel
from ui.terminal_panel import TerminalPanel
from ui.styles import DARK_STYLESHEET, COLORS
from ai.query_worker import AIQueryWorker
from ai.dual_pass_worker import DualPassQueryWorker


class MainWindow(QMainWindow):
    """
    Main application window for Epoch Entry Qualifier.

    Displays up to 4 ticker panels with rolling indicator data.
    Refreshes on minute boundaries (e.g., :01, :02, etc.).
    """

    def __init__(self):
        super().__init__()

        # Data management
        self._ticker_data: Dict[str, List[dict]] = {}  # ticker -> bars
        self._panels: List[TickerPanel] = []
        self._active_tickers: List[str] = []

        # Services
        self._market_hours = MarketHours()
        self._api_client = PolygonClient()

        # Timers
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._update_countdown)

        # Workers
        self._active_workers: List[DataWorker] = []
        self._ai_worker: Optional[AIQueryWorker] = None

        # State
        self._next_refresh_seconds = 60
        self._is_market_open = False
        self._current_user_notes = ""  # v3.0: User notes for dual-pass display

        self._setup_ui()
        self._setup_timers()

    def _setup_ui(self):
        """Set up the main window UI."""
        self.setWindowTitle("EPOCH ENTRY QUALIFIER v3.0")
        self.setMinimumSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        # Apply dark theme
        self.setStyleSheet(DARK_STYLESHEET)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 10, 15, 5)
        main_layout.setSpacing(6)

        # Header
        header_layout = self._create_header()
        main_layout.addLayout(header_layout)

        # Add ticker button
        add_layout = QHBoxLayout()
        self.add_ticker_btn = QPushButton("+ Add Ticker")
        self.add_ticker_btn.setObjectName("addButton")
        self.add_ticker_btn.clicked.connect(self._on_add_ticker)
        add_layout.addWidget(self.add_ticker_btn)
        add_layout.addStretch()
        main_layout.addLayout(add_layout)

        # Scrollable ticker panels — each table is fixed-height with no internal scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_content = QWidget()
        self.panels_layout = QVBoxLayout(scroll_content)
        self.panels_layout.setContentsMargins(0, 0, 0, 0)
        self.panels_layout.setSpacing(6)

        # Create empty panels
        for i in range(MAX_TICKERS):
            panel = TickerPanel(parent=self)
            panel.remove_requested.connect(self._on_remove_ticker)
            self._panels.append(panel)
            self.panels_layout.addWidget(panel)

        self.panels_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area, 3)  # 60% of flexible space

        # Global AI Control Panel (above terminal)
        self.control_panel = GlobalControlPanel(self)
        self.control_panel.ai_query_requested.connect(self._on_ai_query)
        main_layout.addWidget(self.control_panel)

        # DOW AI Terminal Panel — fills remaining space below tickers
        self.terminal_panel = TerminalPanel(self)
        main_layout.addWidget(self.terminal_panel, 2)  # 40% of flexible space

        # Status bar
        status_frame = self._create_status_bar()
        main_layout.addWidget(status_frame)

    def _create_header(self) -> QHBoxLayout:
        """Create the header layout."""
        layout = QHBoxLayout()

        # Title
        title = QLabel("EPOCH ENTRY QUALIFIER v3.0")
        title.setObjectName("headerLabel")
        font = QFont()
        font.setBold(True)
        font.setPointSize(16)
        title.setFont(font)

        # Clock
        self.clock_label = QLabel("00:00:00")
        font = QFont("Consolas", 14)
        self.clock_label.setFont(font)

        # Status indicator
        self.status_indicator = QLabel("\u25CF STARTING")  # Filled circle
        self.status_indicator.setStyleSheet(f"color: {COLORS['status_paused']};")
        font = QFont()
        font.setBold(True)
        self.status_indicator.setFont(font)

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.clock_label)
        layout.addSpacing(20)
        layout.addWidget(self.status_indicator)

        return layout

    def _create_status_bar(self) -> QFrame:
        """Create the status bar frame."""
        frame = QFrame()
        frame.setObjectName("statusBar")
        frame.setFixedHeight(30)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 5, 10, 5)

        # Status text
        self.status_text = QLabel("Status: Initializing")
        self.status_text.setObjectName("statusLabel")

        # Next update countdown
        self.countdown_label = QLabel("Next Update: --s")
        self.countdown_label.setObjectName("statusLabel")

        # Ticker count
        self.ticker_count_label = QLabel(f"Tickers: 0/{MAX_TICKERS}")
        self.ticker_count_label.setObjectName("statusLabel")

        # Market status
        self.market_status_label = QLabel("Market: --")
        self.market_status_label.setObjectName("statusLabel")

        layout.addWidget(self.status_text)
        layout.addSpacing(30)
        layout.addWidget(self.countdown_label)
        layout.addSpacing(30)
        layout.addWidget(self.ticker_count_label)
        layout.addStretch()
        layout.addWidget(self.market_status_label)

        return frame

    def _setup_timers(self):
        """Initialize and start timers."""
        # Clock timer - update every second
        self._clock_timer.start(1000)
        self._update_clock()

        # Countdown timer - update every second
        self._countdown_timer.start(1000)

        # Calculate time until next minute boundary
        self._sync_to_minute_boundary()

        # Initial market status check
        self._update_market_status()

    def _sync_to_minute_boundary(self):
        """Sync the refresh timer to the next minute boundary + fetch delay."""
        seconds_until = self._market_hours.seconds_until_next_minute()
        delay_ms = (seconds_until * 1000) + FETCH_DELAY_MS
        self._next_refresh_seconds = seconds_until + (FETCH_DELAY_MS // 1000)

        # Single-shot to :00 + offset, then re-sync each cycle
        QTimer.singleShot(delay_ms, self._on_minute_boundary)

        self._update_status(f"Syncing to minute boundary ({self._next_refresh_seconds}s)")

    def _on_minute_boundary(self):
        """Fire refresh after minute boundary + offset, then schedule next."""
        # Refresh all tickers now
        self._on_refresh_timer()

        # Re-sync to the next minute boundary + offset (avoids drift)
        seconds_until = self._market_hours.seconds_until_next_minute()
        delay_ms = (seconds_until * 1000) + FETCH_DELAY_MS
        self._next_refresh_seconds = seconds_until + (FETCH_DELAY_MS // 1000)
        QTimer.singleShot(delay_ms, self._on_minute_boundary)

    def _update_clock(self):
        """Update the clock display."""
        now = self._market_hours.get_current_time()
        self.clock_label.setText(now.strftime("%H:%M:%S"))

    def _update_countdown(self):
        """Update the countdown display."""
        if self._next_refresh_seconds > 0:
            self._next_refresh_seconds -= 1

        self.countdown_label.setText(f"Next Update: {self._next_refresh_seconds}s")

    def _update_market_status(self):
        """Update market status display."""
        is_open, status_text = self._market_hours.get_market_status()
        self._is_market_open = is_open

        self.market_status_label.setText(f"Market: {status_text}")

        if is_open:
            self.status_indicator.setText("\u25CF LIVE")
            self.status_indicator.setStyleSheet(f"color: {COLORS['status_live']};")
        else:
            self.status_indicator.setText("\u25CF PAUSED")
            self.status_indicator.setStyleSheet(f"color: {COLORS['status_paused']};")

    def _update_status(self, message: str):
        """Update status bar text."""
        self.status_text.setText(f"Status: {message}")

    def _update_ticker_count(self):
        """Update ticker count display."""
        count = len(self._active_tickers)
        self.ticker_count_label.setText(f"Tickers: {count}/{MAX_TICKERS}")

        # Enable/disable add button
        self.add_ticker_btn.setEnabled(count < MAX_TICKERS)

    @pyqtSlot()
    def _on_refresh_timer(self):
        """Handle refresh timer tick."""
        self._update_market_status()

        if not self._is_market_open:
            self._update_status("Market Closed - Updates Paused")
            return

        if not self._active_tickers:
            self._update_status("No tickers configured")
            return

        self._update_status("Refreshing...")
        self._fetch_all_tickers()

    def _fetch_all_tickers(self):
        """Fetch data for all active tickers."""
        for ticker in self._active_tickers:
            self._fetch_ticker_data(ticker)

    def _fetch_ticker_data(self, ticker: str, is_initial: bool = False):
        """
        Fetch data for a single ticker.

        Args:
            ticker: Ticker symbol
            is_initial: True if this is the initial load (pre-population)
        """
        worker = DataWorker(self)
        worker.data_ready.connect(self._on_data_ready)
        worker.error_occurred.connect(self._on_data_error)
        worker.add_ticker_to_fetch(ticker)
        worker.start()

        self._active_workers.append(worker)

    @pyqtSlot(str, list)
    def _on_data_ready(self, ticker: str, bars: List[dict]):
        """Handle data ready from worker."""
        # Store the data
        self._ticker_data[ticker] = bars

        # Find and update the panel
        for panel in self._panels:
            if panel.get_ticker() == ticker:
                panel.update_data(bars)
                break

        self._update_status(f"Updated {ticker}")
        self._cleanup_workers()

    @pyqtSlot(str, str)
    def _on_data_error(self, ticker: str, error_msg: str):
        """Handle data fetch error."""
        # Find and clear the panel
        for panel in self._panels:
            if panel.get_ticker() == ticker:
                panel.clear_data()
                break

        self._update_status(f"Error: {error_msg}")
        self._cleanup_workers()

    def _cleanup_workers(self):
        """Clean up finished workers."""
        self._active_workers = [w for w in self._active_workers if w.isRunning()]

    @pyqtSlot()
    def _on_add_ticker(self):
        """Handle add ticker button click."""
        if len(self._active_tickers) >= MAX_TICKERS:
            QMessageBox.warning(
                self,
                "Maximum Tickers",
                f"Maximum of {MAX_TICKERS} tickers allowed."
            )
            return

        dialog = TickerDialog(self._active_tickers, self)
        dialog.ticker_added.connect(self._add_ticker)
        dialog.exec()

    @pyqtSlot(str)
    def _add_ticker(self, ticker: str):
        """Add a new ticker."""
        ticker = ticker.upper().strip()

        if ticker in self._active_tickers:
            return

        # Find an empty panel
        panel = self._find_empty_panel()
        if not panel:
            return

        # Add to active list
        self._active_tickers.append(ticker)

        # Configure the panel
        panel.set_ticker(ticker)

        # Update UI
        self._update_ticker_count()
        self._update_control_panel_tickers()
        self._update_status(f"Loading {ticker}...")

        # Fetch initial data (pre-population)
        self._fetch_ticker_data(ticker, is_initial=True)

    def _find_empty_panel(self) -> Optional[TickerPanel]:
        """Find the first empty panel."""
        for panel in self._panels:
            if not panel.has_ticker():
                return panel
        return None

    @pyqtSlot(str)
    def _on_remove_ticker(self, ticker: str):
        """Handle remove ticker request."""
        ticker = ticker.upper().strip()

        if ticker not in self._active_tickers:
            return

        # Remove from active list
        self._active_tickers.remove(ticker)

        # Clear data
        if ticker in self._ticker_data:
            del self._ticker_data[ticker]

        # Find and reset the panel
        for panel in self._panels:
            if panel.get_ticker() == ticker:
                panel.set_ticker(None)
                panel.clear_data()
                break

        # Reorder panels - move empty ones to the end
        self._reorder_panels()

        # Update UI
        self._update_ticker_count()
        self._update_control_panel_tickers()
        self._update_status(f"Removed {ticker}")

    def _reorder_panels(self):
        """Reorder panels so active ones are at the top."""
        # Get current tickers in order
        active_panels = []
        empty_panels = []

        for panel in self._panels:
            if panel.has_ticker():
                active_panels.append(panel)
            else:
                empty_panels.append(panel)

        # Remove all panels from layout
        for panel in active_panels + empty_panels:
            self.panels_layout.removeWidget(panel)

        # Re-add in order: active first, then empty (before the stretch)
        for panel in active_panels + empty_panels:
            self.panels_layout.insertWidget(self.panels_layout.count() - 1, panel)

    def _update_control_panel_tickers(self):
        """Update the control panel dropdown with current active tickers."""
        self.control_panel.update_tickers(self._active_tickers)

    @pyqtSlot(str, str, str)
    def _on_ai_query(self, ticker: str, direction: str, user_notes: str = ""):
        """
        Handle dual-pass AI query request from control panel.

        v3.0: Uses DualPassQueryWorker which combines user notes (Pass 1)
        with system analysis using backtested context (Pass 2).

        Args:
            ticker: Stock symbol to analyze
            direction: Trade direction (LONG/SHORT)
            user_notes: User's perspective/notes (Pass 1 input)
        """
        if ticker not in self._active_tickers:
            self.terminal_panel.set_error(f"Ticker {ticker} not loaded")
            return

        # Get bar data for this ticker
        bars = self._ticker_data.get(ticker, [])
        if not bars:
            self.terminal_panel.set_error(f"No data loaded for {ticker}")
            return

        # Store user notes for response display
        self._current_user_notes = user_notes

        # Show loading state
        self.terminal_panel.set_loading(ticker, direction)
        self.control_panel.set_enabled(False)

        # Stop any existing AI query
        if self._ai_worker and self._ai_worker.isRunning():
            self._ai_worker.terminate()
            self._ai_worker.wait(500)

        # Start new dual-pass AI query
        self._ai_worker = DualPassQueryWorker(ticker, direction, user_notes, bars, self)
        self._ai_worker.response_ready.connect(self._on_ai_response_v3)
        self._ai_worker.error_occurred.connect(self._on_ai_error)
        self._ai_worker.status_update.connect(self._on_ai_status)
        self._ai_worker.finished.connect(self._on_ai_finished)
        self._ai_worker.start()

    @pyqtSlot(str, str, str)
    def _on_ai_response(self, ticker: str, direction: str, response: str):
        """Handle AI response ready (legacy single-pass)."""
        self.terminal_panel.set_response(response, ticker, direction)

    @pyqtSlot(str, str, str, str)
    def _on_ai_response_v3(self, ticker: str, direction: str, user_notes: str, response: str):
        """Handle dual-pass AI response ready (v3.0)."""
        self.terminal_panel.set_response(response, ticker, direction, user_notes)

    @pyqtSlot(str)
    def _on_ai_error(self, error_msg: str):
        """Handle AI query error."""
        self.terminal_panel.set_error(error_msg)

    @pyqtSlot(str)
    def _on_ai_status(self, status_msg: str):
        """Handle AI query status updates."""
        self.terminal_panel.append_message(status_msg)

    @pyqtSlot()
    def _on_ai_finished(self):
        """Handle AI query finished (success or error)."""
        self.control_panel.set_enabled(True)

    def closeEvent(self, event):
        """Handle window close."""
        # Stop timers
        self._clock_timer.stop()
        self._countdown_timer.stop()

        # Stop workers
        for worker in self._active_workers:
            if worker.isRunning():
                worker.stop()
                worker.wait(1000)

        # Stop AI worker
        if self._ai_worker and self._ai_worker.isRunning():
            self._ai_worker.terminate()
            self._ai_worker.wait(500)

        super().closeEvent(event)
