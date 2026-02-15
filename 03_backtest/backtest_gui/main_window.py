"""
Backtest Runner Window
Epoch Trading System v2.0 - XIII Trading LLC

Main window with date selector and terminal-style output.
Entry detection (v4.0) - exports to trades_2 table.
Optional M1 bars storage for secondary processor data.
"""
import sys
from pathlib import Path
from datetime import datetime, date
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QTextEdit,
    QProgressBar, QMessageBox, QDateEdit, QCheckBox
)
from PyQt6.QtCore import Qt, QProcess, pyqtSlot, QDate
from PyQt6.QtGui import QFont, QTextCursor
import psycopg2

from styles import DARK_STYLESHEET, COLORS

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_CONFIG


class BacktestRunnerWindow(QMainWindow):
    """
    Main window for Backtest Runner tool.

    Features:
    - Date selector
    - M1 Bars checkbox (fetch/store M1 bar data)
    - Run/Stop controls
    - Terminal output (80% of screen)
    - Progress tracking
    """

    def __init__(self):
        super().__init__()

        self._process: Optional[QProcess] = None
        self._is_running = False
        self._trades_processed = 0
        self._trades_total = 0

        self._setup_ui()

    def _setup_ui(self):
        """Set up the main window UI."""
        self.setWindowTitle("EPOCH BACKTEST RUNNER v4.0 - Entry Detection")
        self.setMinimumSize(1200, 900)
        self.resize(1400, 1000)

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

        title = QLabel("EPOCH BACKTEST RUNNER")
        title.setObjectName("headerLabel")
        font = QFont("Segoe UI", 18)
        font.setBold(True)
        title.setFont(font)

        version = QLabel("v4.0 Entry Detection")
        version.setStyleSheet(f"color: {COLORS['text_muted']};")
        font = QFont("Consolas", 12)
        version.setFont(font)

        layout.addWidget(title)
        layout.addWidget(version)
        layout.addStretch()

        return layout

    def _create_control_panel(self) -> QFrame:
        """Create the control panel with date selector and run button."""
        frame = QFrame()
        frame.setObjectName("controlPanel")
        frame.setFixedHeight(215)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(30)

        # Date Selection
        date_layout = QVBoxLayout()
        date_label = QLabel("DATE")
        date_label.setObjectName("sectionLabel")

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setMinimumWidth(150)

        date_layout.addWidget(date_label)
        date_layout.addWidget(self.date_edit)
        date_layout.addStretch()
        layout.addLayout(date_layout)

        # Secondary Processors - compact grid layout
        processors_outer = QVBoxLayout()
        processors_outer.setSpacing(4)

        # Header row with label + Run All toggle
        proc_header = QHBoxLayout()
        processors_label = QLabel("PROCESSORS")
        processors_label.setObjectName("sectionLabel")
        proc_header.addWidget(processors_label)
        proc_header.addSpacing(15)

        self.run_all_checkbox = QCheckBox("Run All Secondary")
        self.run_all_checkbox.setChecked(False)
        self.run_all_checkbox.setToolTip(
            "Toggle ALL secondary processors on/off\n"
            "Runs the full pipeline after entry detection"
        )
        self.run_all_checkbox.setStyleSheet(
            f"QCheckBox {{ color: {COLORS['status_running']}; font-weight: bold; }}"
        )
        self.run_all_checkbox.stateChanged.connect(self._on_run_all_toggled)
        proc_header.addWidget(self.run_all_checkbox)
        proc_header.addStretch()
        processors_outer.addLayout(proc_header)

        # Row 1: Data processors
        proc_row1 = QHBoxLayout()
        proc_row1.setSpacing(20)

        self.m1_bars_checkbox = QCheckBox("Fetch M1 Bars")
        self.m1_bars_checkbox.setChecked(False)
        self.m1_bars_checkbox.setToolTip(
            "Fetch and store M1 bar data from Polygon\n"
            "Prior day 16:00 ET → Trade day 16:00 ET\n"
            "Required for downstream secondary analysis"
        )

        self.m1_indicators_checkbox = QCheckBox("Calculate M1 Indicators")
        self.m1_indicators_checkbox.setChecked(False)
        self.m1_indicators_checkbox.setToolTip(
            "Calculate indicator bars from m1_bars_2 data\n"
            "Requires M1 Bars to be populated first\n"
            "Writes to m1_indicator_bars_2 table"
        )

        proc_row1.addWidget(self.m1_bars_checkbox)
        proc_row1.addWidget(self.m1_indicators_checkbox)
        processors_outer.addLayout(proc_row1)

        # Row 2: ATR Stop processors
        proc_row2 = QHBoxLayout()
        proc_row2.setSpacing(20)

        self.m1_atr_stop_checkbox = QCheckBox("M1 ATR Stop Analysis")
        self.m1_atr_stop_checkbox.setChecked(False)
        self.m1_atr_stop_checkbox.setToolTip(
            "Calculate M1 ATR(14) stop outcomes\n"
            "R-multiple targets (1R-5R) with M1 bar simulation\n"
            "Requires M1 Indicators populated first\n"
            "Writes to m1_atr_stop_2 table"
        )

        self.m5_atr_stop_checkbox = QCheckBox("M5 ATR Stop Analysis")
        self.m5_atr_stop_checkbox.setChecked(False)
        self.m5_atr_stop_checkbox.setToolTip(
            "Calculate M5 ATR(14) stop outcomes\n"
            "R-multiple targets (1R-5R) with M1 bar simulation\n"
            "Wider stop than M1 ATR for cross-timeframe comparison\n"
            "Requires M1 Indicators populated first\n"
            "Writes to m5_atr_stop_2 table"
        )

        proc_row2.addWidget(self.m1_atr_stop_checkbox)
        proc_row2.addWidget(self.m5_atr_stop_checkbox)
        processors_outer.addLayout(proc_row2)

        # Row 3: Consolidation + Indicator processors
        proc_row3 = QHBoxLayout()
        proc_row3.setSpacing(20)

        self.trades_consolidated_checkbox = QCheckBox("Consolidate Trades")
        self.trades_consolidated_checkbox.setChecked(False)
        self.trades_consolidated_checkbox.setToolTip(
            "Consolidate trades_2 + m5_atr_stop_2 into trades_m5_r_win_2\n"
            "Denormalized table for 11_trade_reel highlight viewer\n"
            "Requires M5 ATR Stop populated first\n"
            "Writes to trades_m5_r_win_2 table"
        )

        self.m1_trade_ind_checkbox = QCheckBox("Entry Indicators")
        self.m1_trade_ind_checkbox.setChecked(False)
        self.m1_trade_ind_checkbox.setToolTip(
            "Snapshot M1 indicator bar at entry (prior completed bar)\n"
            "Denormalized with trade context + outcome\n"
            "Requires M5 ATR Stop outcomes\n"
            "Writes to m1_trade_indicator_2 table"
        )

        proc_row3.addWidget(self.trades_consolidated_checkbox)
        proc_row3.addWidget(self.m1_trade_ind_checkbox)
        processors_outer.addLayout(proc_row3)

        # Row 4: Ramp-Up + Post-Trade indicator processors
        proc_row4 = QHBoxLayout()
        proc_row4.setSpacing(20)

        self.m1_ramp_up_checkbox = QCheckBox("Ramp-Up Indicators")
        self.m1_ramp_up_checkbox.setChecked(False)
        self.m1_ramp_up_checkbox.setToolTip(
            "25 M1 indicator bars before entry (pre-entry evolution)\n"
            "bar_sequence 0 (oldest) to 24 (just before entry candle)\n"
            "Requires M5 ATR Stop outcomes\n"
            "Writes to m1_ramp_up_indicator_2 table"
        )

        self.m1_post_trade_checkbox = QCheckBox("Post-Trade Indicators")
        self.m1_post_trade_checkbox.setChecked(False)
        self.m1_post_trade_checkbox.setToolTip(
            "25 M1 indicator bars after entry (post-entry evolution)\n"
            "bar_sequence 0 (entry candle) to 24\n"
            "Outcome stamped on every row for aggregation\n"
            "Requires M5 ATR Stop outcomes\n"
            "Writes to m1_post_trade_indicator_2 table"
        )

        proc_row4.addWidget(self.m1_ramp_up_checkbox)
        proc_row4.addWidget(self.m1_post_trade_checkbox)
        processors_outer.addLayout(proc_row4)

        # Connect individual checkboxes to sync Run All state
        for cb in self._get_all_processor_checkboxes():
            cb.stateChanged.connect(self._on_individual_checkbox_changed)

        layout.addLayout(processors_outer)

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

        self.run_button = QPushButton("RUN BACKTEST")
        self.run_button.setObjectName("runButton")
        self.run_button.clicked.connect(self._on_run_clicked)

        self.stop_button = QPushButton("STOP")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.stop_button.setEnabled(False)

        button_layout.addWidget(self.clear_db_button)
        button_layout.addWidget(self.run_button)
        button_layout.addWidget(self.stop_button)
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

    def _print_welcome(self):
        """Print welcome message to terminal."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.terminal.setPlainText(
            f"{'='*70}\n"
            f"  EPOCH BACKTEST RUNNER v4.0\n"
            f"  Entry Detection: S15 Bars / EPCH1-4 Models\n"
            f"  Epoch Trading System - XIII Trading LLC\n"
            f"{'='*70}\n"
            f"  Session started: {now}\n"
            f"{'='*70}\n\n"
            f"  Select a date and click RUN BACKTEST.\n\n"
            f"  Pipeline:\n"
            f"    1. Load zones from Supabase setups table\n"
            f"    2. Run EPCH1-4 entry detection on S15 bars\n"
            f"    3. Export entries to Supabase trades_2 table\n"
            f"    4. [Optional] Fetch M1 bars for secondary analysis\n"
            f"    5. [Optional] Calculate M1 indicator bars\n"
            f"    6. [Optional] M1 ATR stop analysis (R-multiple targets)\n"
            f"    7. [Optional] M5 ATR stop analysis (R-multiple targets)\n"
            f"    8. [Optional] Consolidate trades (trades_m5_r_win_2)\n"
            f"    9. [Optional] Entry indicators (m1_trade_indicator_2)\n"
            f"   10. [Optional] Ramp-up indicators (m1_ramp_up_indicator_2)\n"
            f"   11. [Optional] Post-trade indicators (m1_post_trade_indicator_2)\n\n"
            f"  Tip: Use 'Run All Secondary' to enable the full pipeline.\n\n"
        )

    def _append_terminal(self, text: str, color: str = None):
        """Append text to terminal with optional color."""
        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        if color:
            html = f'<span style="color: {color};">{text}</span>'
            cursor.insertHtml(html + "<br>")
        else:
            cursor.insertText(text + "\n")

        self.terminal.setTextCursor(cursor)
        self.terminal.ensureCursorVisible()

    def _clear_terminal(self):
        """Clear terminal and show welcome message."""
        self._print_welcome()

    @pyqtSlot()
    def _on_clear_db_clicked(self):
        """Handle Clear Entries button click."""
        selected_date = self.date_edit.date().toPyDate()

        reply = QMessageBox.question(
            self,
            "Clear Entries",
            f"This will delete all entries from trades_2 for {selected_date}.\n\nAre you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._append_terminal(f"\n[DB] Connecting to database...")
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM trades_2 WHERE date = %s", (selected_date,))
            count = cursor.fetchone()[0]

            cursor.execute("DELETE FROM trades_2 WHERE date = %s", (selected_date,))
            conn.commit()

            cursor.close()
            conn.close()

            self._append_terminal(f"[DB] Cleared {count} entries for {selected_date}", COLORS['status_complete'])
            self._update_status(f"Entries cleared ({count} records)")

        except Exception as e:
            self._append_terminal(f"[DB] Error: {str(e)}", COLORS['status_error'])
            self._update_status("Database error")

    def _update_status(self, message: str):
        """Update status bar."""
        self.status_label.setText(f"Status: {message}")
        self.time_label.setText(datetime.now().strftime("%H:%M:%S"))

    @pyqtSlot()
    def _on_run_clicked(self):
        """Handle Run button click."""
        if self._is_running:
            return

        selected_date = self.date_edit.date().toString("yyyy-MM-dd")
        run_m1_bars = self.m1_bars_checkbox.isChecked()
        run_m1_indicators = self.m1_indicators_checkbox.isChecked()
        run_m1_atr_stop = self.m1_atr_stop_checkbox.isChecked()
        run_m5_atr_stop = self.m5_atr_stop_checkbox.isChecked()
        run_trades_consolidated = self.trades_consolidated_checkbox.isChecked()
        run_m1_trade_ind = self.m1_trade_ind_checkbox.isChecked()
        run_m1_ramp_up = self.m1_ramp_up_checkbox.isChecked()
        run_m1_post_trade = self.m1_post_trade_checkbox.isChecked()

        # Build command
        scripts_dir = Path(__file__).parent.parent / "scripts"
        script_path = scripts_dir / "run_backtest.py"

        if not script_path.exists():
            QMessageBox.critical(
                self,
                "Error",
                f"Backtest script not found:\n{script_path}"
            )
            return

        args = ["-u", str(script_path), selected_date]

        if run_m1_bars:
            args.append("--m1-bars")

        if run_m1_indicators:
            args.append("--m1-indicators")

        if run_m1_atr_stop:
            args.append("--m1-atr-stop")

        if run_m5_atr_stop:
            args.append("--m5-atr-stop")

        if run_trades_consolidated:
            args.append("--trades-consolidated")

        if run_m1_trade_ind:
            args.append("--m1-trade-ind")

        if run_m1_ramp_up:
            args.append("--m1-ramp-up")

        if run_m1_post_trade:
            args.append("--m1-post-trade")

        # Start process
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_process_output)
        self._process.finished.connect(self._on_process_finished)
        self._process.errorOccurred.connect(self._on_process_error)

        from PyQt6.QtCore import QProcessEnvironment
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        self._process.setProcessEnvironment(env)

        self._append_terminal(f"\n{'='*70}")
        self._append_terminal(f"Starting entry detection for {selected_date}")
        if run_m1_bars:
            self._append_terminal("M1 Bars: ENABLED (will fetch after entry detection)")
        if run_m1_indicators:
            self._append_terminal("M1 Indicators: ENABLED (will calculate after M1 bars)")
        if run_m1_atr_stop:
            self._append_terminal("M1 ATR Stop: ENABLED (R-multiple target analysis)")
        if run_m5_atr_stop:
            self._append_terminal("M5 ATR Stop: ENABLED (R-multiple target analysis)")
        if run_trades_consolidated:
            self._append_terminal("Consolidate Trades: ENABLED (trades_m5_r_win_2)")
        if run_m1_trade_ind:
            self._append_terminal("Entry Indicators: ENABLED (m1_trade_indicator_2)")
        if run_m1_ramp_up:
            self._append_terminal("Ramp-Up Indicators: ENABLED (m1_ramp_up_indicator_2)")
        if run_m1_post_trade:
            self._append_terminal("Post-Trade Indicators: ENABLED (m1_post_trade_indicator_2)")
        self._append_terminal(f"Script: {script_path}")
        self._append_terminal(f"{'='*70}\n")

        self._process.start(sys.executable, args)

        self._is_running = True
        self._trades_processed = 0
        self._trades_total = 0
        self.progress_bar.setValue(0)
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.date_edit.setEnabled(False)
        self.run_all_checkbox.setEnabled(False)
        for cb in self._get_all_processor_checkboxes():
            cb.setEnabled(False)
        self.terminal_status.setText("Running...")
        self.terminal_status.setStyleSheet(f"color: {COLORS['status_running']};")
        self._update_status("Running entry detection...")

    @pyqtSlot()
    def _on_stop_clicked(self):
        """Handle Stop button click."""
        if self._process and self._is_running:
            self._append_terminal("\n[!] Stopping backtest...", COLORS['status_error'])
            self._process.kill()

    @pyqtSlot()
    def _on_process_output(self):
        """Handle process output."""
        if not self._process:
            return

        data = self._process.readAllStandardOutput()
        if not data:
            return

        text = bytes(data).decode('utf-8', errors='replace')

        for line in text.splitlines():
            line = line.rstrip()
            if not line:
                continue

            # Parse progress from output like "[1/5]" or "[2/8]"
            if line.startswith("[") and "/" in line and "]" in line:
                try:
                    bracket_content = line.split("]")[0].replace("[", "")
                    if "/" in bracket_content:
                        parts = bracket_content.split("/")
                        current = int(parts[0])
                        total = int(parts[1])
                        self._trades_processed = current
                        self._trades_total = total
                        progress = int((current / total) * 100)
                        self.progress_bar.setValue(progress)
                        self._update_status(f"Processing {current}/{total}")
                except (ValueError, IndexError):
                    pass

            # Color output based on content
            if "ERROR" in line or "Error" in line or "Traceback" in line:
                self._append_terminal(line, COLORS['status_error'])
            elif "[OK]" in line or "Complete" in line or "COMPLETE" in line:
                self._append_terminal(line, COLORS['status_complete'])
            elif "ENTRY" in line:
                self._append_terminal(line, COLORS['status_complete'])
            elif "[M1 BARS]" in line:
                self._append_terminal(line, COLORS['status_running'])
            elif "[M1 INDICATORS]" in line:
                self._append_terminal(line, COLORS['status_running'])
            elif "[M1 ATR STOP]" in line:
                self._append_terminal(line, COLORS['status_running'])
            elif "[M5 ATR STOP]" in line:
                self._append_terminal(line, COLORS['status_running'])
            elif "[TRADES CONSOLIDATED]" in line:
                self._append_terminal(line, COLORS['status_running'])
            elif "[M1 TRADE IND]" in line or "[TRADE INDICATOR]" in line:
                self._append_terminal(line, COLORS['status_running'])
            elif "[M1 RAMP-UP]" in line or "[RAMP-UP]" in line:
                self._append_terminal(line, COLORS['status_running'])
            elif "[M1 POST-TRADE]" in line or "[POST-TRADE]" in line:
                self._append_terminal(line, COLORS['status_running'])
            else:
                self._append_terminal(line)

    @pyqtSlot(int, QProcess.ExitStatus)
    def _on_process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handle process completion."""
        self._is_running = False
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.date_edit.setEnabled(True)
        self.run_all_checkbox.setEnabled(True)
        for cb in self._get_all_processor_checkboxes():
            cb.setEnabled(True)

        if exit_code == 0:
            self.progress_bar.setValue(100)
            self.terminal_status.setText("Complete")
            self.terminal_status.setStyleSheet(f"color: {COLORS['status_complete']};")
            self._append_terminal(f"\n{'='*70}")
            self._append_terminal("Backtest complete!", COLORS['status_complete'])
            self._update_status("Backtest complete")
        else:
            self.terminal_status.setText("Stopped")
            self.terminal_status.setStyleSheet(f"color: {COLORS['status_error']};")
            self._append_terminal(f"\n[!] Process exited with code {exit_code}", COLORS['status_error'])
            self._update_status(f"Stopped (exit code: {exit_code})")

    @pyqtSlot(QProcess.ProcessError)
    def _on_process_error(self, error: QProcess.ProcessError):
        """Handle process error."""
        self._is_running = False
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.date_edit.setEnabled(True)
        self.run_all_checkbox.setEnabled(True)
        for cb in self._get_all_processor_checkboxes():
            cb.setEnabled(True)

        self.terminal_status.setText("Error")
        self.terminal_status.setStyleSheet(f"color: {COLORS['status_error']};")

        error_messages = {
            QProcess.ProcessError.FailedToStart: "Failed to start process",
            QProcess.ProcessError.Crashed: "Process crashed",
            QProcess.ProcessError.Timedout: "Process timed out",
            QProcess.ProcessError.WriteError: "Write error",
            QProcess.ProcessError.ReadError: "Read error",
            QProcess.ProcessError.UnknownError: "Unknown error"
        }

        msg = error_messages.get(error, "Unknown error")
        self._append_terminal(f"\n[!] Error: {msg}", COLORS['status_error'])
        self._update_status(f"Error: {msg}")

    def _get_all_processor_checkboxes(self) -> list:
        """Return all individual processor checkboxes (not Run All)."""
        return [
            self.m1_bars_checkbox,
            self.m1_indicators_checkbox,
            self.m1_atr_stop_checkbox,
            self.m5_atr_stop_checkbox,
            self.trades_consolidated_checkbox,
            self.m1_trade_ind_checkbox,
            self.m1_ramp_up_checkbox,
            self.m1_post_trade_checkbox,
        ]

    @pyqtSlot(int)
    def _on_run_all_toggled(self, state: int):
        """Toggle all processor checkboxes when Run All is changed."""
        checked = state == Qt.CheckState.Checked.value
        # Block signals to avoid recursive updates
        for cb in self._get_all_processor_checkboxes():
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)

    @pyqtSlot(int)
    def _on_individual_checkbox_changed(self, _state: int):
        """Sync Run All checkbox when individual checkboxes change."""
        all_checkboxes = self._get_all_processor_checkboxes()
        all_checked = all(cb.isChecked() for cb in all_checkboxes)
        # Block signals to avoid triggering _on_run_all_toggled
        self.run_all_checkbox.blockSignals(True)
        self.run_all_checkbox.setChecked(all_checked)
        self.run_all_checkbox.blockSignals(False)

    def closeEvent(self, event):
        """Handle window close."""
        if self._process and self._is_running:
            reply = QMessageBox.question(
                self,
                "Backtest Running",
                "Backtest is still running. Stop and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self._process.kill()
                self._process.waitForFinished(3000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
