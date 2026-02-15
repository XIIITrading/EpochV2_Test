"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR ANALYSIS v2.0
Main Window - PyQt6 dashboard with filter sidebar and 5 tabs
XIII Trading LLC
================================================================================
"""
import sys
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTabWidget, QComboBox, QFrame, QScrollArea, QPushButton,
    QDateEdit, QApplication, QSplitter, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont
import pandas as pd

from ui.styles import COLORS, DARK_STYLESHEET

from ui.tabs.ramp_up_tab import RampUpTab
from ui.tabs.entry_snapshot_tab import EntrySnapshotTab
from ui.tabs.post_trade_tab import PostTradeTab
from ui.tabs.indicator_deep_dive_tab import IndicatorDeepDiveTab
from ui.tabs.composite_setup_tab import CompositeSetupTab

from data.provider import DataProvider
from data.exporter import ResultsExporter
from config import ENTRY_MODELS, DIRECTIONS, OUTCOMES


# =============================================================================
# Background data loader
# =============================================================================
class DataLoadThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, provider: DataProvider, filters: dict):
        super().__init__()
        self._provider = provider
        self._filters = filters

    def run(self):
        try:
            f = self._filters
            model = f.get("model")
            direction = f.get("direction")
            ticker = f.get("ticker")
            outcome = f.get("outcome")
            date_from = f.get("date_from")
            date_to = f.get("date_to")

            # Get entry data (the core dataset)
            entry_data = self._provider.get_entry_data(
                model=model, direction=direction, ticker=ticker,
                outcome=outcome, date_from=date_from, date_to=date_to
            )

            trade_ids = entry_data["trade_id"].tolist() if not entry_data.empty else []

            # Get phase data using trade_ids
            ramp_up_avgs = self._provider.get_ramp_up_averages(trade_ids)
            post_trade_avgs = self._provider.get_post_trade_averages(trade_ids)

            # Get pending count
            pending = self._provider.get_pending_count(
                model=model, direction=direction,
                date_from=date_from, date_to=date_to
            )

            self.finished.emit({
                "entry_data": entry_data,
                "trade_ids": trade_ids,
                "ramp_up_avgs": ramp_up_avgs,
                "post_trade_avgs": post_trade_avgs,
                "pending_count": pending,
                "filters": f,
            })
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# Main Window
# =============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EPOCH Indicator Analysis v2.0 - XIII Trading LLC")
        self.setMinimumSize(1400, 900)
        self.setStyleSheet(DARK_STYLESHEET)

        self._provider = DataProvider()
        self._exporter = ResultsExporter(self._provider)
        self._load_thread = None
        self._current_data = {}

        self._setup_ui()
        self._connect_and_load()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        main_layout.addWidget(self._create_header())

        # Body = filters + tabs
        body = QSplitter(Qt.Orientation.Horizontal)

        # Left: filter panel
        filter_panel = self._create_filter_panel()
        body.addWidget(filter_panel)

        # Right: tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)

        self.ramp_up_tab = RampUpTab(self._provider)
        self.entry_tab = EntrySnapshotTab(self._provider)
        self.post_trade_tab = PostTradeTab(self._provider)
        self.deep_dive_tab = IndicatorDeepDiveTab(self._provider)
        self.composite_tab = CompositeSetupTab(self._provider)

        self.tab_widget.addTab(self._wrap_scroll(self.ramp_up_tab), "Ramp-Up")
        self.tab_widget.addTab(self._wrap_scroll(self.entry_tab), "Entry Snapshot")
        self.tab_widget.addTab(self._wrap_scroll(self.post_trade_tab), "Post-Trade")
        self.tab_widget.addTab(self._wrap_scroll(self.deep_dive_tab), "Deep Dive")
        self.tab_widget.addTab(self._wrap_scroll(self.composite_tab), "Setup Analysis")

        body.addWidget(self.tab_widget)
        body.setSizes([220, 1180])

        main_layout.addWidget(body, stretch=1)

        # Status bar
        main_layout.addWidget(self._create_status_bar())

    def _create_header(self) -> QFrame:
        header = QFrame()
        header.setStyleSheet(
            f"background-color: {COLORS['bg_header']}; padding: 10px;"
        )
        header.setFixedHeight(55)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 0, 20, 0)

        title = QLabel("EPOCH INDICATOR ANALYSIS")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(title)

        layout.addStretch()

        ver = QLabel("v2.0")
        ver.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(ver)

        return header

    def _create_filter_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("sectionFrame")
        panel.setFixedWidth(220)
        panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        lbl = QLabel("Filters")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(lbl)

        # Model filter
        layout.addWidget(QLabel("Model"))
        self.model_combo = QComboBox()
        self.model_combo.addItem("All Models", None)
        for key, desc in ENTRY_MODELS.items():
            self.model_combo.addItem(f"{key} - {desc}", key)
        layout.addWidget(self.model_combo)

        # Direction filter
        layout.addWidget(QLabel("Direction"))
        self.direction_combo = QComboBox()
        self.direction_combo.addItem("All Directions", None)
        for d in DIRECTIONS:
            self.direction_combo.addItem(d, d)
        layout.addWidget(self.direction_combo)

        # Ticker filter
        layout.addWidget(QLabel("Ticker"))
        self.ticker_combo = QComboBox()
        self.ticker_combo.addItem("All Tickers", None)
        layout.addWidget(self.ticker_combo)

        # Outcome filter
        layout.addWidget(QLabel("Outcome"))
        self.outcome_combo = QComboBox()
        self.outcome_combo.addItem("All Trades", None)
        for o in OUTCOMES:
            self.outcome_combo.addItem(o, o)
        layout.addWidget(self.outcome_combo)

        # Date from
        layout.addWidget(QLabel("Date From"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate(2026, 1, 1))
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.date_from)

        # Date to
        layout.addWidget(QLabel("Date To"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.date_to)

        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("primaryButton")
        self.refresh_btn.clicked.connect(self._on_refresh)
        layout.addWidget(self.refresh_btn)

        # Export button
        self.export_btn = QPushButton("Export Results")
        self.export_btn.setStyleSheet(
            f"QPushButton {{ background-color: #1a4a7a; color: {COLORS['text_primary']}; "
            f"font-weight: bold; padding: 6px; border: 1px solid #2a6ab0; }}"
            f"QPushButton:hover {{ background-color: #2a6ab0; }}"
            f"QPushButton:disabled {{ background-color: #333; color: #666; }}"
        )
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._on_export)
        layout.addWidget(self.export_btn)

        layout.addStretch()

        # Pending analysis warning
        self.pending_label = QLabel("")
        self.pending_label.setWordWrap(True)
        self.pending_label.setStyleSheet(
            "color: #ffc107; font-size: 10px; padding: 4px;"
        )
        self.pending_label.setVisible(False)
        layout.addWidget(self.pending_label)

        # Trade count label
        self.trade_count_label = QLabel("Trades: -")
        self.trade_count_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 11px;"
        )
        layout.addWidget(self.trade_count_label)

        return panel

    def _create_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("statusBar")
        bar.setFixedHeight(28)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 0, 20, 0)

        self.status_label = QLabel("Connecting...")
        self.status_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px;"
        )
        layout.addWidget(self.status_label)

        layout.addStretch()

        self.time_label = QLabel(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.time_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 11px;"
        )
        layout.addWidget(self.time_label)

        return bar

    def _wrap_scroll(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        return scroll

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def _connect_and_load(self):
        self.status_label.setText("Connecting to database...")
        if not self._provider.connect():
            self.status_label.setText("Database connection failed")
            return

        # Load tickers for filter
        try:
            tickers = self._provider.get_tickers()
            for t in tickers:
                self.ticker_combo.addItem(t, t)
        except Exception:
            pass

        # Set date range
        try:
            dr = self._provider.get_date_range()
            if dr["min_date"]:
                self.date_from.setDate(QDate(
                    dr["min_date"].year, dr["min_date"].month, dr["min_date"].day
                ))
            if dr["max_date"]:
                self.date_to.setDate(QDate(
                    dr["max_date"].year, dr["max_date"].month, dr["max_date"].day
                ))
        except Exception:
            pass

        self._on_refresh()

    def _get_filters(self) -> dict:
        model = self.model_combo.currentData()
        direction = self.direction_combo.currentData()
        ticker = self.ticker_combo.currentData()
        outcome = self.outcome_combo.currentData()

        qd_from = self.date_from.date()
        qd_to = self.date_to.date()

        from datetime import date
        return {
            "model": model,
            "direction": direction,
            "ticker": ticker,
            "outcome": outcome,
            "date_from": date(qd_from.year(), qd_from.month(), qd_from.day()),
            "date_to": date(qd_to.year(), qd_to.month(), qd_to.day()),
        }

    def _on_refresh(self):
        self.refresh_btn.setEnabled(False)
        self.status_label.setText("Loading data...")

        self._load_thread = DataLoadThread(self._provider, self._get_filters())
        self._load_thread.finished.connect(self._on_data_loaded)
        self._load_thread.error.connect(self._on_load_error)
        self._load_thread.start()

    def _on_data_loaded(self, data: dict):
        self.refresh_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self._current_data = data

        entry_data = data["entry_data"]
        count = len(entry_data)
        pending = data["pending_count"]

        self.trade_count_label.setText(f"Trades: {count:,}")
        self.status_label.setText(f"Loaded {count:,} trades")
        self.time_label.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # Show/hide pending analysis warning
        if pending > 0:
            self.pending_label.setText(
                f"\u26a0 {pending:,} trades pending outcome analysis "
                f"- run m5_atr_stop processor"
            )
            self.pending_label.setVisible(True)
        else:
            self.pending_label.setVisible(False)

        # Refresh all tabs
        trade_ids = data["trade_ids"]
        self.ramp_up_tab.refresh(data["ramp_up_avgs"], trade_ids)
        self.entry_tab.refresh(entry_data, trade_ids)
        self.post_trade_tab.refresh(data["post_trade_avgs"], trade_ids)
        self.deep_dive_tab.refresh(entry_data, trade_ids)
        self.composite_tab.refresh(entry_data, trade_ids)

    def _on_load_error(self, error_msg: str):
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error_msg}")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _on_export(self):
        if not self._current_data:
            self.status_label.setText("No data to export - refresh first")
            return

        self.export_btn.setEnabled(False)
        self.status_label.setText("Exporting results...")

        try:
            filters = self._current_data.get("filters", self._get_filters())
            export_path = self._exporter.export_all(self._current_data, filters)

            self.status_label.setText(f"Exported to: {export_path}")
            self.export_btn.setEnabled(True)

            # Show confirmation in a brief popup
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox(self)
            msg.setWindowTitle("Export Complete")
            msg.setText(
                f"Analysis exported successfully!\n\n"
                f"Location:\n{export_path}\n\n"
                f"Files:\n"
                f"  _meta.md - Filters & dataset summary\n"
                f"  01_ramp_up.md - Pre-entry analysis\n"
                f"  02_entry_snapshot.md - Entry state analysis\n"
                f"  03_post_trade.md - Post-entry analysis\n"
                f"  04_deep_dive.md - Per-indicator breakdown\n"
                f"  05_composite_setup.md - Setup scoring\n"
                f"  csv/ - Raw data files"
            )
            msg.setStyleSheet(
                f"QMessageBox {{ background-color: {COLORS['bg_primary']}; "
                f"color: {COLORS['text_primary']}; }}"
            )
            msg.exec()
        except Exception as e:
            self.status_label.setText(f"Export error: {e}")
            self.export_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        self._provider.close()
        super().closeEvent(event)
