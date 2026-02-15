"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR EDGE TESTING v1.0
Main Window - PyQt6 GUI
XIII Trading LLC
================================================================================

Terminal-style interface for running indicator edge tests.
================================================================================
"""
import sys
import re
from pathlib import Path
from datetime import datetime, date

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QProgressBar,
    QComboBox, QCheckBox, QGroupBox, QListWidget,
    QListWidgetItem, QAbstractItemView, QDateEdit,
    QStatusBar, QSizePolicy
)
from PyQt6.QtCore import Qt, QProcess, QDate
from PyQt6.QtGui import QFont, QTextCursor, QColor

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import INDICATORS, DEFAULT_INDICATOR_ORDER
from styles import DARK_THEME


class IndicatorEdgeWindow(QMainWindow):
    """Main window for Indicator Edge Testing."""

    def __init__(self):
        super().__init__()
        self.process = None
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Epoch Indicator Edge Testing v1.0")
        self.setMinimumSize(900, 700)
        self.resize(1000, 800)

        # Apply dark theme
        self.setStyleSheet(DARK_THEME)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel("EPOCH INDICATOR EDGE TESTING")
        header.setObjectName("headerLabel")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)

        subtitle = QLabel("Statistical Edge Analysis for M1 Bar Indicators")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #808080; font-size: 11px;")
        main_layout.addWidget(subtitle)

        # Control panel
        control_layout = QHBoxLayout()
        control_layout.setSpacing(16)

        # Left: Indicator selection
        indicator_group = QGroupBox("Indicators")
        indicator_layout = QVBoxLayout(indicator_group)

        self.indicator_list = QListWidget()
        self.indicator_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.indicator_list.setMaximumHeight(150)

        for key in DEFAULT_INDICATOR_ORDER:
            item = QListWidgetItem(INDICATORS[key]['name'])
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setToolTip(INDICATORS[key]['description'])
            item.setSelected(True)  # Select all by default
            self.indicator_list.addItem(item)

        indicator_layout.addWidget(self.indicator_list)

        # Select all / none buttons
        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all_indicators)
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self.select_no_indicators)
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(select_none_btn)
        indicator_layout.addLayout(btn_layout)

        control_layout.addWidget(indicator_group)

        # Middle: Filters
        filter_group = QGroupBox("Filters")
        filter_layout = QVBoxLayout(filter_group)

        # Stop type
        stop_layout = QHBoxLayout()
        stop_layout.addWidget(QLabel("Stop Type:"))
        self.stop_type_combo = QComboBox()
        self.stop_type_combo.addItems(['zone_buffer', 'fractal', 'm5_atr', 'm15_atr', 'prior_m1', 'prior_m5'])
        stop_layout.addWidget(self.stop_type_combo)
        stop_layout.addStretch()
        filter_layout.addLayout(stop_layout)

        # Date range (optional)
        date_layout = QHBoxLayout()
        self.use_date_filter = QCheckBox("Date Range:")
        self.use_date_filter.toggled.connect(self.toggle_date_filter)
        date_layout.addWidget(self.use_date_filter)

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_from.setEnabled(False)
        date_layout.addWidget(self.date_from)

        date_layout.addWidget(QLabel("to"))

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setEnabled(False)
        date_layout.addWidget(self.date_to)

        date_layout.addStretch()
        filter_layout.addLayout(date_layout)

        # Verbose option
        self.verbose_checkbox = QCheckBox("Verbose Output")
        self.verbose_checkbox.setChecked(False)
        filter_layout.addWidget(self.verbose_checkbox)

        # Export option
        self.export_checkbox = QCheckBox("Export Results to Markdown")
        self.export_checkbox.setChecked(False)
        filter_layout.addWidget(self.export_checkbox)

        filter_layout.addStretch()
        control_layout.addWidget(filter_group)

        # Right: Action buttons
        action_group = QGroupBox("Actions")
        action_layout = QVBoxLayout(action_group)

        self.run_button = QPushButton("RUN TESTS")
        self.run_button.setObjectName("runButton")
        self.run_button.setMinimumHeight(40)
        self.run_button.clicked.connect(self.run_tests)
        action_layout.addWidget(self.run_button)

        self.stop_button = QPushButton("STOP")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_process)
        action_layout.addWidget(self.stop_button)

        self.clear_button = QPushButton("CLEAR")
        self.clear_button.setObjectName("clearButton")
        self.clear_button.clicked.connect(self.clear_output)
        action_layout.addWidget(self.clear_button)

        action_layout.addStretch()
        control_layout.addWidget(action_group)

        main_layout.addLayout(control_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        # Terminal output
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 10))
        self.output_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout.addWidget(self.output_text, stretch=1)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # Show welcome message
        self.show_welcome()

    def show_welcome(self):
        """Show welcome message in terminal."""
        welcome = f"""
======================================================================
  EPOCH INDICATOR EDGE TESTING v1.0
  Statistical Edge Analysis for M1 Bar Indicators
  Epoch Trading System - XIII Trading LLC
======================================================================
  Session started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
======================================================================

  Select indicators and click RUN TESTS.

  Available Indicators:
"""
        for key in DEFAULT_INDICATOR_ORDER:
            welcome += f"    - {INDICATORS[key]['name']}: {INDICATORS[key]['description']}\n"

        welcome += """
  Each indicator is tested across multiple segments:
    - ALL trades
    - LONG / SHORT direction
    - CONTINUATION / REJECTION trade type

======================================================================
"""
        self.output_text.setPlainText(welcome)

    def select_all_indicators(self):
        """Select all indicators."""
        for i in range(self.indicator_list.count()):
            self.indicator_list.item(i).setSelected(True)

    def select_no_indicators(self):
        """Deselect all indicators."""
        for i in range(self.indicator_list.count()):
            self.indicator_list.item(i).setSelected(False)

    def toggle_date_filter(self, checked):
        """Toggle date filter enabled state."""
        self.date_from.setEnabled(checked)
        self.date_to.setEnabled(checked)

    def run_tests(self):
        """Run the edge tests via subprocess."""
        # Get selected indicators
        selected_items = self.indicator_list.selectedItems()
        if not selected_items:
            self.append_output("ERROR: No indicators selected\n", color="#ef5350")
            return

        indicators = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]

        # Build command
        script_path = Path(__file__).parent.parent / "scripts" / "run_edge_tests.py"

        args = [
            sys.executable,
            str(script_path),
            '--indicators', ','.join(indicators),
            '--stop-type', self.stop_type_combo.currentText()
        ]

        if self.use_date_filter.isChecked():
            args.extend(['--date-from', self.date_from.date().toString('yyyy-MM-dd')])
            args.extend(['--date-to', self.date_to.date().toString('yyyy-MM-dd')])

        if self.verbose_checkbox.isChecked():
            args.append('--verbose')

        if self.export_checkbox.isChecked():
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            args.extend(['--export', f'edge_results_{timestamp}.md'])

        # Clear and show start message
        self.output_text.clear()
        self.append_output("=" * 70 + "\n")
        self.append_output(f"Starting edge tests for {len(indicators)} indicator(s)\n")
        self.append_output(f"Script: {script_path}\n")
        self.append_output("=" * 70 + "\n\n")

        # Update UI state
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Running tests...")

        # Start process
        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.handle_output)
        self.process.finished.connect(self.process_finished)

        self.process.start(args[0], args[1:])

    def handle_output(self):
        """Handle output from the subprocess."""
        if self.process:
            data = self.process.readAllStandardOutput()
            text = bytes(data).decode('utf-8', errors='replace')

            for line in text.splitlines(keepends=True):
                self.process_line(line)

    def process_line(self, line: str):
        """Process a single line of output with color coding."""
        # Progress tracking: [X/N] pattern
        progress_match = re.search(r'\[(\d+)/(\d+)\]', line)
        if progress_match:
            current = int(progress_match.group(1))
            total = int(progress_match.group(2))
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)

        # Color coding
        if any(word in line for word in ['ERROR', 'FAILED', 'Traceback']):
            self.append_output(line, color="#ef5350")  # Red
        elif any(word in line for word in ['EDGE DETECTED', 'EDGE', '[+]', 'SUCCESS']):
            self.append_output(line, color="#26a69a")  # Green
        elif any(word in line for word in ['WARNING', 'NO_EDGE', 'LOW_DATA', '[~]']):
            self.append_output(line, color="#ff9800")  # Orange
        elif line.startswith('===') or line.startswith('---'):
            self.append_output(line, color="#808080")  # Gray
        else:
            self.append_output(line)  # Default white

    def append_output(self, text: str, color: str = None):
        """Append text to output with optional color."""
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        if color:
            format = cursor.charFormat()
            format.setForeground(QColor(color))
            cursor.setCharFormat(format)
            cursor.insertText(text)
            format.setForeground(QColor("#e8e8e8"))
            cursor.setCharFormat(format)
        else:
            cursor.insertText(text)

        self.output_text.setTextCursor(cursor)
        self.output_text.ensureCursorVisible()

    def process_finished(self, exit_code, exit_status):
        """Handle process completion."""
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setValue(100)

        if exit_code == 0:
            self.append_output("\n" + "=" * 70 + "\n")
            self.append_output("Edge tests complete!\n", color="#26a69a")
            self.status_bar.showMessage("Tests completed successfully")
        else:
            self.append_output("\n" + "=" * 70 + "\n")
            self.append_output(f"Tests finished with exit code {exit_code}\n", color="#ef5350")
            self.status_bar.showMessage(f"Tests completed with errors (exit code {exit_code})")

        self.process = None

    def stop_process(self):
        """Stop the running process."""
        if self.process:
            self.process.kill()
            self.append_output("\n--- Process stopped by user ---\n", color="#ff9800")
            self.status_bar.showMessage("Process stopped")

    def clear_output(self):
        """Clear the output terminal."""
        self.output_text.clear()
        self.progress_bar.setValue(0)
        self.show_welcome()

    def closeEvent(self, event):
        """Handle window close."""
        if self.process:
            self.process.kill()
        event.accept()
