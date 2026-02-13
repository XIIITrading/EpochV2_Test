"""
FIFO Trade Processor Window
Epoch Trading System v2.0 - XIII Trading LLC

PyQt6 GUI for processing DAS Trader CSV files with FIFO trade matching.
Follows the 03_backtest/backtest_gui/main_window.py pattern.
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QTextEdit,
    QProgressBar, QMessageBox, QComboBox, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont, QTextCursor

from styles import DARK_STYLESHEET, COLORS

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.fifo_processor import process_session_fifo, parse_csv_auto, group_fills
from core.fifo_models import FIFOTrade, FIFODailyLog
from core.atr_calculator import calculate_atr_stops, compute_pnl_r
from data.journal_db import JournalDB


# =============================================================================
# Trade log directory
# =============================================================================

TRADE_LOG_DIR = Path(__file__).parent.parent / "trade_log"


def scan_csv_files(base_dir: Path) -> List[str]:
    """
    Scan trade_log/ directory for CSV files.
    Returns relative paths sorted by name (most recent first).
    """
    if not base_dir.exists():
        return []

    csv_files = []
    for csv_path in sorted(base_dir.rglob("*.csv"), reverse=True):
        rel_path = csv_path.relative_to(base_dir)
        csv_files.append(str(rel_path))

    return csv_files


# =============================================================================
# Main Window
# =============================================================================

class FIFOProcessorWindow(QMainWindow):
    """
    FIFO Trade Processor GUI.

    Features:
    - CSV file selector (dropdown + browse)
    - PROCESS button (runs FIFO logic, logs to terminal)
    - SAVE TO DB button (writes to journal_trades)
    - CLEAR ENTRIES button (deletes by date)
    - Terminal output with color-coded logging
    - Progress tracking
    """

    def __init__(self):
        super().__init__()

        self._daily_log: Optional[FIFODailyLog] = None
        self._is_processing = False

        self._setup_ui()

    def _setup_ui(self):
        """Set up the main window UI."""
        self.setWindowTitle("EPOCH FIFO TRADE PROCESSOR v1.0")
        self.setMinimumSize(1200, 800)
        self.resize(1300, 950)

        self.setStyleSheet(DARK_STYLESHEET)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 15)
        main_layout.setSpacing(15)

        # Header
        header = self._create_header()
        main_layout.addLayout(header)

        # Control panel
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel)

        # Terminal output
        terminal_frame = self._create_terminal()
        main_layout.addWidget(terminal_frame, stretch=8)

        # Status bar
        status_bar = self._create_status_bar()
        main_layout.addWidget(status_bar)

    def _create_header(self) -> QHBoxLayout:
        """Create the header layout."""
        layout = QHBoxLayout()

        title = QLabel("EPOCH FIFO TRADE PROCESSOR")
        title.setObjectName("headerLabel")
        font = QFont("Segoe UI", 18)
        font.setBold(True)
        title.setFont(font)

        version = QLabel("v1.0 FIFO Matching")
        version.setStyleSheet(f"color: {COLORS['text_muted']};")
        font = QFont("Consolas", 12)
        version.setFont(font)

        layout.addWidget(title)
        layout.addWidget(version)
        layout.addStretch()

        return layout

    def _create_control_panel(self) -> QFrame:
        """Create the control panel with file selector and buttons."""
        frame = QFrame()
        frame.setObjectName("controlPanel")
        frame.setFixedHeight(120)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(30)

        # CSV File Selection
        file_layout = QVBoxLayout()
        file_label = QLabel("CSV FILE")
        file_label.setObjectName("sectionLabel")

        file_row = QHBoxLayout()
        file_row.setSpacing(10)

        self.file_combo = QComboBox()
        self.file_combo.setMinimumWidth(350)
        self._populate_file_combo()

        self.browse_button = QPushButton("Browse...")
        self.browse_button.setFixedSize(90, 40)
        self.browse_button.clicked.connect(self._on_browse_clicked)

        file_row.addWidget(self.file_combo)
        file_row.addWidget(self.browse_button)

        file_layout.addWidget(file_label)
        file_layout.addLayout(file_row)
        file_layout.addStretch()
        layout.addLayout(file_layout)

        layout.addStretch()

        # Progress
        progress_layout = QVBoxLayout()
        progress_label = QLabel("PROGRESS")
        progress_label.setObjectName("sectionLabel")

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimumWidth(200)
        self.progress_bar.setFixedHeight(25)

        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addStretch()
        layout.addLayout(progress_layout)

        layout.addSpacing(20)

        # Control Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        self.clear_db_button = QPushButton("CLEAR ENTRIES")
        self.clear_db_button.setObjectName("clearDbButton")
        self.clear_db_button.clicked.connect(self._on_clear_db_clicked)

        self.process_button = QPushButton("PROCESS")
        self.process_button.setObjectName("processButton")
        self.process_button.clicked.connect(self._on_process_clicked)

        self.save_button = QPushButton("SAVE TO DB")
        self.save_button.setObjectName("saveButton")
        self.save_button.clicked.connect(self._on_save_clicked)
        self.save_button.setEnabled(False)

        button_layout.addWidget(self.clear_db_button)
        button_layout.addWidget(self.process_button)
        button_layout.addWidget(self.save_button)
        layout.addLayout(button_layout)

        return frame

    def _create_terminal(self) -> QFrame:
        """Create the terminal output panel."""
        frame = QFrame()
        frame.setObjectName("terminalFrame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Terminal header
        header = QHBoxLayout()
        header.setContentsMargins(15, 10, 15, 5)

        terminal_title = QLabel("TERMINAL OUTPUT")
        terminal_title.setObjectName("sectionLabel")
        terminal_title.setFont(QFont("Consolas", 11))

        self.terminal_status = QLabel("Ready")
        self.terminal_status.setStyleSheet(f"color: {COLORS['status_ready']};")
        self.terminal_status.setFont(QFont("Consolas", 10))

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedSize(60, 25)
        clear_btn.clicked.connect(self._clear_terminal)

        header.addWidget(terminal_title)
        header.addStretch()
        header.addWidget(self.terminal_status)
        header.addSpacing(15)
        header.addWidget(clear_btn)

        layout.addLayout(header)

        # Terminal text area
        self.terminal = QTextEdit()
        self.terminal.setObjectName("terminalOutput")
        self.terminal.setReadOnly(True)
        self.terminal.setFont(QFont("Consolas", 10))

        self._print_welcome()

        layout.addWidget(self.terminal)

        return frame

    def _create_status_bar(self) -> QFrame:
        """Create the status bar."""
        frame = QFrame()
        frame.setObjectName("statusBar")
        frame.setFixedHeight(35)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(15, 5, 15, 5)

        self.status_label = QLabel("Status: Ready")
        self.status_label.setObjectName("statusLabel")

        self.time_label = QLabel("")
        self.time_label.setObjectName("statusLabel")

        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(self.time_label)

        return frame

    # =========================================================================
    # Helpers
    # =========================================================================

    def _populate_file_combo(self):
        """Populate file dropdown from trade_log/ directory."""
        self.file_combo.clear()
        csv_files = scan_csv_files(TRADE_LOG_DIR)
        if csv_files:
            for f in csv_files:
                self.file_combo.addItem(f)
        else:
            self.file_combo.addItem("(no CSV files found)")

    def _print_welcome(self):
        """Print welcome message to terminal."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.terminal.setPlainText(
            f"{'='*70}\n"
            f"  EPOCH FIFO TRADE PROCESSOR v1.0\n"
            f"  FIFO Matching: Each add = new trade, exits close oldest first\n"
            f"  Epoch Trading System - XIII Trading LLC\n"
            f"{'='*70}\n"
            f"  Session started: {now}\n"
            f"{'='*70}\n\n"
            f"  Select a CSV file and click PROCESS.\n\n"
            f"  Pipeline:\n"
            f"    1. Parse DAS Trader CSV (auto-detect delimiter)\n"
            f"    2. Group fills by symbol, sort chronologically\n"
            f"    3. First fill determines direction (SHORT/LONG)\n"
            f"    4. Each same-direction fill creates a NEW trade\n"
            f"    5. Opposite fills exit oldest trades first (FIFO)\n"
            f"    6. Exit price = VWAP of all exit portions per trade\n\n"
        )

    def _append_terminal(self, text: str, color: str = None):
        """Append text to terminal with optional color."""
        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        if color:
            # Escape HTML special characters
            escaped = (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace(" ", "&nbsp;")
            )
            html = f'<span style="color: {color}; white-space: pre;">{escaped}</span>'
            cursor.insertHtml(html + "<br>")
        else:
            cursor.insertText(text + "\n")

        self.terminal.setTextCursor(cursor)
        self.terminal.ensureCursorVisible()

    def _clear_terminal(self):
        """Clear terminal and show welcome message."""
        self._print_welcome()

    def _update_status(self, message: str):
        """Update status bar."""
        self.status_label.setText(f"Status: {message}")
        self.time_label.setText(datetime.now().strftime("%H:%M:%S"))

    def _get_selected_filepath(self) -> Optional[Path]:
        """Get the full path of the selected CSV file."""
        selected = self.file_combo.currentText()
        if not selected or selected.startswith("("):
            return None

        # Check if it's a relative path from trade_log/ or an absolute path
        abs_path = Path(selected)
        if abs_path.is_absolute() and abs_path.exists():
            return abs_path

        rel_path = TRADE_LOG_DIR / selected
        if rel_path.exists():
            return rel_path

        return None

    # =========================================================================
    # Button Handlers
    # =========================================================================

    @pyqtSlot()
    def _on_browse_clicked(self):
        """Handle Browse button click -- open file dialog."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select DAS Trader CSV",
            str(TRADE_LOG_DIR) if TRADE_LOG_DIR.exists() else "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if filepath:
            # Add to combo if not already there, and select it
            abs_path = str(filepath)
            idx = self.file_combo.findText(abs_path)
            if idx == -1:
                self.file_combo.insertItem(0, abs_path)
                self.file_combo.setCurrentIndex(0)
            else:
                self.file_combo.setCurrentIndex(idx)

    @pyqtSlot()
    def _on_process_clicked(self):
        """Handle PROCESS button click -- run FIFO logic."""
        if self._is_processing:
            return

        filepath = self._get_selected_filepath()
        if not filepath:
            QMessageBox.warning(
                self, "No File",
                "Please select a valid CSV file to process."
            )
            return

        self._is_processing = True
        self._daily_log = None
        self.save_button.setEnabled(False)
        self.process_button.setEnabled(False)
        self.file_combo.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.terminal_status.setText("Processing...")
        self.terminal_status.setStyleSheet(f"color: {COLORS['status_running']};")
        self._update_status("Processing...")

        try:
            self._run_fifo_processing(filepath)
        finally:
            self._is_processing = False
            self.process_button.setEnabled(True)
            self.file_combo.setEnabled(True)
            self.browse_button.setEnabled(True)

    def _run_fifo_processing(self, filepath: Path):
        """Execute FIFO processing and log results to terminal."""
        from core.fifo_processor import (
            parse_csv_auto, extract_date_from_filename,
            group_fills, process_symbol_fifo, determine_direction,
        )
        from core.fifo_models import FIFODailyLog

        self._append_terminal(f"\n{'='*70}")
        self._append_terminal(f"  FIFO PROCESSING")
        self._append_terminal(f"{'='*70}\n")

        # Step 1: Parse
        self._append_terminal(f"[PARSE] Loading: {filepath.name}")

        try:
            trade_date = extract_date_from_filename(filepath)
        except ValueError as e:
            self._append_terminal(f"[ERROR] {e}", COLORS['status_error'])
            self.terminal_status.setText("Error")
            self.terminal_status.setStyleSheet(f"color: {COLORS['status_error']};")
            self._update_status("Parse error")
            return

        fills, parse_errors, delimiter = parse_csv_auto(filepath)
        delim_name = "tab" if delimiter == "\t" else "comma"
        self._append_terminal(f"[PARSE] Date: {trade_date}")
        self._append_terminal(f"[PARSE] Delimiter: {delim_name}")
        self._append_terminal(f"[PARSE] Parsed {len(fills)} fills ({len(parse_errors)} errors)")

        for err in parse_errors:
            self._append_terminal(f"  WARNING: {err}", COLORS['status_running'])

        if not fills:
            self._append_terminal("\n[ERROR] No fills found in CSV", COLORS['status_error'])
            self.terminal_status.setText("Error")
            self.terminal_status.setStyleSheet(f"color: {COLORS['status_error']};")
            self._update_status("No fills")
            return

        # Step 2: Group
        groups = group_fills(fills)
        symbol_summary = ", ".join(
            f"{sym} ({len(grp)} fills)" for sym, grp in sorted(groups.items())
        )
        self._append_terminal(f"\n[GROUP] Grouped into {len(groups)} symbols: {symbol_summary}")

        # Step 3: Process each symbol
        all_trades = []
        all_warnings = []
        symbols = sorted(groups.keys())

        for idx, symbol in enumerate(symbols):
            symbol_fills = groups[symbol]
            direction = determine_direction(symbol_fills)

            self._append_terminal(
                f"\n[{idx+1}/{len(symbols)}] Processing {symbol} "
                f"({len(symbol_fills)} fills, direction={direction.value})..."
            )

            # Callback for per-fill logging
            def fill_callback(fill_num, fill, action):
                side_str = fill.side.value.ljust(2)
                qty_str = str(fill.qty).rjust(3)
                price_str = f"{fill.price:.2f}".rjust(8)
                time_str = str(fill.time)

                line = f"  Fill #{fill_num}: {side_str} {qty_str} @ {price_str} ({time_str})"

                if "NEW Trade" in action:
                    self._append_terminal(
                        f"{line} -> {action}",
                        COLORS['status_complete']
                    )
                elif "EXIT:" in action:
                    self._append_terminal(f"{line} -> {action}", COLORS['status_running'])
                else:
                    self._append_terminal(f"{line} -> {action}")

            trades, warnings = process_symbol_fifo(
                symbol, symbol_fills, trade_date, callback=fill_callback
            )
            all_trades.extend(trades)
            all_warnings.extend(warnings)

            # Per-symbol summary
            closed = sum(1 for t in trades if t.is_closed)
            open_count = len(trades) - closed
            self._append_terminal(
                f"\n  {symbol} Results: {len(trades)} trades "
                f"({closed} closed, {open_count} open)"
            )

            # Results table
            if trades:
                self._print_trade_table(trades)

            # Update progress
            progress = int(((idx + 1) / len(symbols)) * 100)
            self.progress_bar.setValue(progress)

        # Build daily log
        self._daily_log = FIFODailyLog(
            trade_date=trade_date,
            source_file=filepath.name,
            trades=all_trades,
            parse_errors=all_warnings,
        )

        # Print summary
        self._append_terminal(f"\n{'='*70}")
        self._append_terminal("FIFO PROCESSING COMPLETE", COLORS['status_complete'])
        self._append_terminal(f"{'='*70}")
        self._append_terminal(f"  Date:          {trade_date}")
        self._append_terminal(
            f"  Total Trades:  {self._daily_log.trade_count} "
            f"({self._daily_log.closed_count} closed, {self._daily_log.open_count} open)"
        )

        # Symbol breakdown
        from collections import Counter
        symbol_counts = Counter(t.symbol for t in all_trades)
        sym_str = ", ".join(f"{s} ({c})" for s, c in sorted(symbol_counts.items()))
        self._append_terminal(f"  Symbols:       {sym_str}")

        self._append_terminal(f"  Total P&L:     ${self._daily_log.total_pnl:,.2f}")

        if self._daily_log.win_rate is not None:
            wr_pct = self._daily_log.win_rate * 100
            self._append_terminal(
                f"  Win Rate:      {wr_pct:.0f}% "
                f"({self._daily_log.win_count}W / {self._daily_log.loss_count}L)"
            )

        self._append_terminal(f"{'='*70}\n")
        self._append_terminal(
            "Ready to save. Click SAVE TO DB.",
            COLORS['status_complete']
        )

        # Enable save
        self.save_button.setEnabled(True)
        self.terminal_status.setText("Complete")
        self.terminal_status.setStyleSheet(f"color: {COLORS['status_complete']};")
        self._update_status(f"Processed {self._daily_log.trade_count} trades")

    def _print_trade_table(self, trades: List[FIFOTrade]):
        """Print an ASCII table of trades to the terminal."""
        # Header
        self._append_terminal(
            "  +-----+----------+------+----------+----------+----------+---------+"
        )
        self._append_terminal(
            "  | Seq | Entry    | Qty  | Exit     | PnL/shr  | PnL Tot  | Outcome |"
        )
        self._append_terminal(
            "  +-----+----------+------+----------+----------+----------+---------+"
        )

        for t in trades:
            seq = str(t.trade_seq).center(3)
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

            # Color based on outcome
            line = f"  | {seq} | {entry} | {qty} | {exit_p} | {pnl_s} | {pnl_t} | {outcome} |"

            if t.outcome.value == "WIN":
                self._append_terminal(line, COLORS['status_complete'])
            elif t.outcome.value == "LOSS":
                self._append_terminal(line, COLORS['status_error'])
            else:
                self._append_terminal(line)

        self._append_terminal(
            "  +-----+----------+------+----------+----------+----------+---------+"
        )

    @pyqtSlot()
    def _on_save_clicked(self):
        """Handle SAVE TO DB button click. Computes ATR stops then saves."""
        if not self._daily_log or not self._daily_log.trades:
            QMessageBox.warning(
                self, "No Data",
                "No processed trades to save. Run PROCESS first."
            )
            return

        reply = QMessageBox.question(
            self,
            "Save to Database",
            f"Save {self._daily_log.trade_count} FIFO trades for "
            f"{self._daily_log.trade_date} to journal_trades?\n\n"
            f"This will fetch bars from Polygon and compute M1/M5 ATR stops.\n"
            f"Existing trades with matching IDs will be updated (upsert).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.save_button.setEnabled(False)
        self.process_button.setEnabled(False)
        self.progress_bar.setValue(0)

        try:
            # ---- Step 1: Fetch bars per symbol (cached) ----
            self._append_terminal(f"\n{'='*70}")
            self._append_terminal("  ATR STOP COMPUTATION", COLORS['status_running'])
            self._append_terminal(f"{'='*70}\n")
            self._update_status("Fetching bars from Polygon...")

            from viewer.bar_fetcher import fetch_bars

            trade_date = self._daily_log.trade_date
            symbols = sorted(set(t.symbol for t in self._daily_log.trades))
            bars_cache = {}  # {symbol: (bars_m1, bars_m5)}

            for i, symbol in enumerate(symbols):
                self._append_terminal(
                    f"[BARS] Fetching M1 + M5 bars for {symbol} ({i+1}/{len(symbols)})...",
                    COLORS['status_running']
                )
                QMessageBox  # Force Qt event processing
                from PyQt6.QtWidgets import QApplication
                QApplication.processEvents()

                bars_m1 = fetch_bars(symbol, trade_date, tf_minutes=1, lookback_days=2)
                bars_m5 = fetch_bars(symbol, trade_date, tf_minutes=5, lookback_days=3)
                bars_cache[symbol] = (bars_m1, bars_m5)

                m1_count = len(bars_m1) if bars_m1 is not None else 0
                m5_count = len(bars_m5) if bars_m5 is not None else 0
                self._append_terminal(f"  {symbol}: M1={m1_count} bars, M5={m5_count} bars")

            self._append_terminal("")

            # ---- Step 2: Compute ATR stops per trade ----
            self._append_terminal("[ATR] Computing M1 + M5 ATR stops for each trade...")
            self._update_status("Computing ATR stops...")

            atr_results = {}  # {trade_id: atr_dict}

            for trade in self._daily_log.trades:
                bars_m1, bars_m5 = bars_cache.get(trade.symbol, (None, None))

                def atr_callback(msg):
                    self._append_terminal(msg)

                self._append_terminal(
                    f"\n[ATR] Trade #{trade.trade_seq} {trade.symbol} "
                    f"{trade.direction.value} {trade.entry_qty} @ ${trade.entry_price:.2f}:",
                    COLORS['status_running']
                )

                atr_data = calculate_atr_stops(
                    ticker=trade.symbol,
                    trade_date=trade_date,
                    direction=trade.direction.value,
                    entry_price=trade.entry_price,
                    entry_time=trade.entry_time,
                    exit_time=trade.exit_time,
                    bars_m1=bars_m1,
                    bars_m5=bars_m5,
                    callback=atr_callback,
                )

                # Compute PnL in R terms from actual exit
                if trade.exit_price is not None:
                    for prefix in ('m1', 'm5'):
                        sd = atr_data.get(f'{prefix}_stop_distance')
                        if sd and sd > 0:
                            atr_data[f'{prefix}_pnl_r'] = compute_pnl_r(
                                trade.direction.value,
                                trade.entry_price,
                                trade.exit_price,
                                sd,
                            )

                atr_results[trade.trade_id] = atr_data

            self._append_terminal("")

            # ---- Step 3: Save to DB ----
            self._append_terminal(f"[DB] Connecting to Supabase...")
            self._update_status("Saving to database...")

            with JournalDB() as db:
                saved = 0
                total = len(self._daily_log.trades)

                for idx, trade in enumerate(self._daily_log.trades):
                    row = trade.to_db_row(source_file=self._daily_log.source_file)

                    # Merge ATR data into the row dict
                    atr_data = atr_results.get(trade.trade_id, {})
                    row.update(atr_data)

                    success, err_msg = self._save_fifo_trade(db, row)
                    if success:
                        saved += 1
                        m5_max_r = atr_data.get('m5_max_r', 0)
                        m1_max_r = atr_data.get('m1_max_r', 0)
                        self._append_terminal(
                            f"[DB] Saved {trade.trade_id} "
                            f"({trade.symbol} {trade.direction.value} "
                            f"{trade.entry_qty} @ ${trade.entry_price:.2f}) "
                            f"M1:R{m1_max_r} M5:R{m5_max_r}",
                            COLORS['status_complete']
                        )
                    else:
                        self._append_terminal(
                            f"[DB] FAILED to save {trade.trade_id}",
                            COLORS['status_error']
                        )
                        self._append_terminal(
                            f"  Error: {err_msg}",
                            COLORS['status_error']
                        )

                    self.progress_bar.setValue(int(((idx + 1) / total) * 100))
                    QApplication.processEvents()

                self._append_terminal(
                    f"\n[DB] All {saved}/{total} trades saved successfully.",
                    COLORS['status_complete']
                )

            self._update_status(f"Saved {saved} trades with ATR stops")

        except Exception as e:
            self._append_terminal(f"\n[DB] Error: {e}", COLORS['status_error'])
            self._update_status("Error during save")
        finally:
            self.save_button.setEnabled(True)
            self.process_button.setEnabled(True)

    def _save_fifo_trade(self, db: JournalDB, row: dict) -> tuple:
        """
        Save a single FIFO trade dict to journal_trades.
        Extended version with FIFO columns + M1/M5 ATR stop columns.

        Returns:
            (True, None) on success, (False, error_message) on failure.
        """
        db._ensure_connected()

        query = f"""
            INSERT INTO {db.TABLE} (
                trade_id, trade_date, symbol, direction, account,
                entry_price, entry_time, entry_qty, entry_fills,
                exit_price, exit_time, exit_qty, exit_fills,
                pnl_dollars, pnl_total, pnl_r, outcome, duration_seconds,
                zone_id, model, stop_price, notes,
                source_file, is_closed, trade_seq, processing_mode,
                m1_atr_value, m1_stop_price, m1_stop_distance,
                m1_r1_price, m1_r2_price, m1_r3_price, m1_r4_price, m1_r5_price,
                m1_r1_hit, m1_r2_hit, m1_r3_hit, m1_r4_hit, m1_r5_hit,
                m1_r1_time, m1_r2_time, m1_r3_time, m1_r4_time, m1_r5_time,
                m1_stop_hit, m1_stop_hit_time, m1_max_r, m1_pnl_r,
                m5_atr_value, m5_stop_price, m5_stop_distance,
                m5_r1_price, m5_r2_price, m5_r3_price, m5_r4_price, m5_r5_price,
                m5_r1_hit, m5_r2_hit, m5_r3_hit, m5_r4_hit, m5_r5_hit,
                m5_r1_time, m5_r2_time, m5_r3_time, m5_r4_time, m5_r5_time,
                m5_stop_hit, m5_stop_hit_time, m5_max_r, m5_pnl_r,
                updated_at
            ) VALUES (
                %(trade_id)s, %(trade_date)s, %(symbol)s, %(direction)s, %(account)s,
                %(entry_price)s, %(entry_time)s, %(entry_qty)s, %(entry_fills)s,
                %(exit_price)s, %(exit_time)s, %(exit_qty)s, %(exit_fills)s,
                %(pnl_dollars)s, %(pnl_total)s, %(pnl_r)s, %(outcome)s, %(duration_seconds)s,
                %(zone_id)s, %(model)s, %(stop_price)s, %(notes)s,
                %(source_file)s, %(is_closed)s, %(trade_seq)s, %(processing_mode)s,
                %(m1_atr_value)s, %(m1_stop_price)s, %(m1_stop_distance)s,
                %(m1_r1_price)s, %(m1_r2_price)s, %(m1_r3_price)s, %(m1_r4_price)s, %(m1_r5_price)s,
                %(m1_r1_hit)s, %(m1_r2_hit)s, %(m1_r3_hit)s, %(m1_r4_hit)s, %(m1_r5_hit)s,
                %(m1_r1_time)s, %(m1_r2_time)s, %(m1_r3_time)s, %(m1_r4_time)s, %(m1_r5_time)s,
                %(m1_stop_hit)s, %(m1_stop_hit_time)s, %(m1_max_r)s, %(m1_pnl_r)s,
                %(m5_atr_value)s, %(m5_stop_price)s, %(m5_stop_distance)s,
                %(m5_r1_price)s, %(m5_r2_price)s, %(m5_r3_price)s, %(m5_r4_price)s, %(m5_r5_price)s,
                %(m5_r1_hit)s, %(m5_r2_hit)s, %(m5_r3_hit)s, %(m5_r4_hit)s, %(m5_r5_hit)s,
                %(m5_r1_time)s, %(m5_r2_time)s, %(m5_r3_time)s, %(m5_r4_time)s, %(m5_r5_time)s,
                %(m5_stop_hit)s, %(m5_stop_hit_time)s, %(m5_max_r)s, %(m5_pnl_r)s,
                NOW()
            )
            ON CONFLICT (trade_id) DO UPDATE SET
                trade_date = EXCLUDED.trade_date,
                symbol = EXCLUDED.symbol,
                direction = EXCLUDED.direction,
                account = EXCLUDED.account,
                entry_price = EXCLUDED.entry_price,
                entry_time = EXCLUDED.entry_time,
                entry_qty = EXCLUDED.entry_qty,
                entry_fills = EXCLUDED.entry_fills,
                exit_price = EXCLUDED.exit_price,
                exit_time = EXCLUDED.exit_time,
                exit_qty = EXCLUDED.exit_qty,
                exit_fills = EXCLUDED.exit_fills,
                pnl_dollars = EXCLUDED.pnl_dollars,
                pnl_total = EXCLUDED.pnl_total,
                pnl_r = EXCLUDED.pnl_r,
                outcome = EXCLUDED.outcome,
                duration_seconds = EXCLUDED.duration_seconds,
                source_file = EXCLUDED.source_file,
                is_closed = EXCLUDED.is_closed,
                trade_seq = EXCLUDED.trade_seq,
                processing_mode = EXCLUDED.processing_mode,
                m1_atr_value = EXCLUDED.m1_atr_value,
                m1_stop_price = EXCLUDED.m1_stop_price,
                m1_stop_distance = EXCLUDED.m1_stop_distance,
                m1_r1_price = EXCLUDED.m1_r1_price,
                m1_r2_price = EXCLUDED.m1_r2_price,
                m1_r3_price = EXCLUDED.m1_r3_price,
                m1_r4_price = EXCLUDED.m1_r4_price,
                m1_r5_price = EXCLUDED.m1_r5_price,
                m1_r1_hit = EXCLUDED.m1_r1_hit,
                m1_r2_hit = EXCLUDED.m1_r2_hit,
                m1_r3_hit = EXCLUDED.m1_r3_hit,
                m1_r4_hit = EXCLUDED.m1_r4_hit,
                m1_r5_hit = EXCLUDED.m1_r5_hit,
                m1_r1_time = EXCLUDED.m1_r1_time,
                m1_r2_time = EXCLUDED.m1_r2_time,
                m1_r3_time = EXCLUDED.m1_r3_time,
                m1_r4_time = EXCLUDED.m1_r4_time,
                m1_r5_time = EXCLUDED.m1_r5_time,
                m1_stop_hit = EXCLUDED.m1_stop_hit,
                m1_stop_hit_time = EXCLUDED.m1_stop_hit_time,
                m1_max_r = EXCLUDED.m1_max_r,
                m1_pnl_r = EXCLUDED.m1_pnl_r,
                m5_atr_value = EXCLUDED.m5_atr_value,
                m5_stop_price = EXCLUDED.m5_stop_price,
                m5_stop_distance = EXCLUDED.m5_stop_distance,
                m5_r1_price = EXCLUDED.m5_r1_price,
                m5_r2_price = EXCLUDED.m5_r2_price,
                m5_r3_price = EXCLUDED.m5_r3_price,
                m5_r4_price = EXCLUDED.m5_r4_price,
                m5_r5_price = EXCLUDED.m5_r5_price,
                m5_r1_hit = EXCLUDED.m5_r1_hit,
                m5_r2_hit = EXCLUDED.m5_r2_hit,
                m5_r3_hit = EXCLUDED.m5_r3_hit,
                m5_r4_hit = EXCLUDED.m5_r4_hit,
                m5_r5_hit = EXCLUDED.m5_r5_hit,
                m5_r1_time = EXCLUDED.m5_r1_time,
                m5_r2_time = EXCLUDED.m5_r2_time,
                m5_r3_time = EXCLUDED.m5_r3_time,
                m5_r4_time = EXCLUDED.m5_r4_time,
                m5_r5_time = EXCLUDED.m5_r5_time,
                m5_stop_hit = EXCLUDED.m5_stop_hit,
                m5_stop_hit_time = EXCLUDED.m5_stop_hit_time,
                m5_max_r = EXCLUDED.m5_max_r,
                m5_pnl_r = EXCLUDED.m5_pnl_r,
                updated_at = NOW()
        """

        try:
            with db.conn.cursor() as cur:
                cur.execute(query, row)
            db.conn.commit()
            return True, None
        except Exception as e:
            error_msg = str(e)
            import logging
            logging.getLogger(__name__).error(f"Error saving FIFO trade {row.get('trade_id')}: {e}")
            try:
                db.conn.rollback()
            except Exception:
                pass
            return False, error_msg

    @pyqtSlot()
    def _on_clear_db_clicked(self):
        """Handle Clear Entries button click."""
        if not self._daily_log:
            QMessageBox.warning(
                self, "No Data",
                "Process a CSV file first to determine the date to clear."
            )
            return

        trade_date = self._daily_log.trade_date

        reply = QMessageBox.question(
            self,
            "Clear Entries",
            f"This will delete ALL journal_trades entries for {trade_date}.\n\n"
            f"Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._append_terminal(f"\n[DB] Connecting to Supabase...")

            with JournalDB() as db:
                count = db.delete_session(trade_date)

            self._append_terminal(
                f"[DB] Cleared {count} entries for {trade_date}",
                COLORS['status_complete']
            )
            self._update_status(f"Entries cleared ({count} records)")

        except Exception as e:
            self._append_terminal(f"[DB] Error: {str(e)}", COLORS['status_error'])
            self._update_status("Database error")

    def closeEvent(self, event):
        """Handle window close."""
        event.accept()
