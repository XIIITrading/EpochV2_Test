"""
Journal Viewer Main Window
Epoch Trading System - XIII Trading LLC

PyQt6 window with trade table + chart preview.
Replicates the 11_trade_reel UI with journal trade data.

Layout:
    JournalViewerWindow (QMainWindow, 1600x950)
    +-- Left Panel (380px fixed)
    |   +-- Filter Controls (Date From/To, Symbol, Direction, Load btn)
    |   +-- Trade Table (sortable rows from journal_trades)
    +-- Right Panel (expandable)
    |   +-- Trade Summary Header
    |   +-- Chart Preview (scrollable, 5 rows of charts + indicator table)
    +-- Status Bar

Threading:
    - TradeLoadThread:  Background DB query for journal trades
    - BarFetchThread:   Fetch bars + zones + POCs + rampup indicators + ATR/R-levels
    - Cache:            {trade_id: (bars + computed highlight + rampup_df)} for instant revisit
"""

import sys
import logging
from typing import List, Optional, Dict
from pathlib import Path
from datetime import datetime, date, time, timedelta

import pandas as pd
import pytz

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QComboBox, QDateEdit, QPushButton, QStatusBar, QFrame,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QDate
from PyQt6.QtGui import QFont

from .config import TV_COLORS, TV_DARK_QSS, DISPLAY_TIMEZONE, TRADE_REEL_DIR
from .trade_table import TradeTable
from .chart_preview import ChartPreview
from .trade_adapter import build_journal_highlight, JournalHighlight
from .bar_fetcher import fetch_bars, fetch_daily_bars

# Add 11_trade_reel to path for chart imports
sys.path.insert(0, str(TRADE_REEL_DIR))

# Import chart builders from 11_trade_reel (no duplication)
from charts import theme  # noqa: F401 - registers tradingview_dark template
from charts.volume_profile import build_volume_profile
from charts.daily_chart import build_daily_chart
from charts.h1_chart import build_h1_chart
from charts.m15_chart import build_m15_chart
from charts.m5_entry_chart import build_m5_entry_chart
from charts.m1_chart import build_m1_chart
from charts.m1_rampup_chart import build_m1_rampup_chart
from ui.rampup_table import fetch_rampup_data

# Import JournalDB from data layer
sys.path.insert(0, str(Path(__file__).parent.parent))
from data.journal_db import JournalDB

logger = logging.getLogger(__name__)


# =============================================================================
# BACKGROUND THREADS
# =============================================================================

class TradeLoadThread(QThread):
    """Load journal trades from database in background."""

    finished = pyqtSignal(list)     # List[Dict] (trade rows)
    error = pyqtSignal(str)

    def __init__(self, date_from: date, date_to: date,
                 symbol: str = None, direction: str = None, parent=None):
        super().__init__(parent)
        self._date_from = date_from
        self._date_to = date_to
        self._symbol = symbol
        self._direction = direction

    def run(self):
        try:
            with JournalDB() as db:
                trades = db.get_trades_by_range(
                    date_from=self._date_from,
                    date_to=self._date_to,
                    symbol=self._symbol,
                )

            # Filter by direction if specified
            if self._direction and self._direction != 'ALL':
                trades = [t for t in trades
                          if (t.get('direction') or '').upper() == self._direction.upper()]

            self.finished.emit(trades)
        except Exception as e:
            self.error.emit(str(e))


class BarFetchThread(QThread):
    """
    Fetch bars + zones + POCs + rampup indicators from Polygon + DB,
    then compute ATR/R-levels.

    Emits: (highlight, bars_daily, bars_h1, bars_m15, bars_m5, bars_m1,
            zones, pocs, vbp_bars, anchor_date, rampup_df)
    """

    finished = pyqtSignal(
        object, object, object, object, object, object,
        list, list, object, object, object,
    )
    error = pyqtSignal(str)

    def __init__(self, trade_row: Dict, parent=None):
        super().__init__(parent)
        self._trade_row = trade_row

    def run(self):
        try:
            row = self._trade_row
            ticker = (row.get('symbol') or '').upper().strip()
            trade_date = row.get('trade_date') or row.get('date')

            logger.info(f"Fetching bars for {ticker} {trade_date}...")

            # Fetch zones and POCs from DB
            zones = []
            pocs = []
            anchor_date = None

            with JournalDB() as db:
                zones = db.get_zones_for_ticker(ticker, trade_date)

            # Fetch POCs and anchor_date from hvn_pocs (via direct query)
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                from data.journal_db import DB_CONFIG

                conn = psycopg2.connect(**DB_CONFIG)
                try:
                    with conn.cursor() as cur:
                        # Fetch POCs
                        cur.execute("""
                            SELECT poc_1, poc_2, poc_3, poc_4, poc_5,
                                   poc_6, poc_7, poc_8, poc_9, poc_10
                            FROM hvn_pocs
                            WHERE ticker = %s AND date = %s
                            LIMIT 1
                        """, (ticker, trade_date))
                        poc_row = cur.fetchone()
                        if poc_row:
                            pocs = [float(p) for p in poc_row if p is not None]

                        # Fetch anchor date
                        cur.execute("""
                            SELECT epoch_start_date FROM hvn_pocs
                            WHERE ticker = %s AND date = %s
                            LIMIT 1
                        """, (ticker, trade_date))
                        anchor_row = cur.fetchone()
                        if anchor_row and anchor_row[0]:
                            anchor_date = anchor_row[0]
                finally:
                    conn.close()
            except Exception as e:
                logger.warning(f"Could not fetch POCs/anchor: {e}")

            # Fetch daily bars (epoch anchor -> day before trade)
            bars_daily = pd.DataFrame()
            if anchor_date:
                day_before = trade_date - timedelta(days=1)
                bars_daily = fetch_daily_bars(ticker, anchor_date, day_before)
                logger.info(f"Daily: {ticker} {anchor_date} -> {day_before} ({len(bars_daily)} bars)")

            # Fetch intraday bars for 4 timeframes
            bars_h1 = fetch_bars(ticker, trade_date, tf_minutes=60, lookback_days=50)
            bars_m15 = fetch_bars(ticker, trade_date, tf_minutes=15, lookback_days=18)
            bars_m5 = fetch_bars(ticker, trade_date, tf_minutes=5, lookback_days=3)
            bars_m1 = fetch_bars(ticker, trade_date, tf_minutes=1, lookback_days=2)

            # Fetch VbP bars from epoch anchor
            vbp_bars = pd.DataFrame()
            if anchor_date:
                lookback = (trade_date - anchor_date).days + 1
                vbp_bars = fetch_bars(ticker, trade_date, tf_minutes=15, lookback_days=lookback)
                logger.info(f"VbP: {ticker} anchor={anchor_date} -> {trade_date} ({lookback}d, {len(vbp_bars)} bars)")

            # Build JournalHighlight with ATR + R-level computation
            highlight = build_journal_highlight(
                row=row,
                bars_m5=bars_m5,
                bars_m1=bars_m1,
                zones=zones,
            )

            # Fetch rampup indicator data from m1_indicator_bars_2 (45 bars)
            rampup_df = pd.DataFrame()
            entry_time = row.get('entry_time')
            if entry_time is not None:
                try:
                    rampup_df = fetch_rampup_data(
                        ticker=ticker,
                        trade_date=trade_date,
                        entry_time=entry_time,
                        num_bars=45,
                    )
                    logger.info(f"Rampup: {ticker} {trade_date} -> {len(rampup_df)} indicator bars")
                except Exception as e:
                    logger.warning(f"Could not fetch rampup data: {e}")

            self.finished.emit(
                highlight, bars_daily, bars_h1, bars_m15, bars_m5, bars_m1,
                zones, pocs, vbp_bars, anchor_date, rampup_df,
            )

        except Exception as e:
            logger.error(f"BarFetchThread error: {e}", exc_info=True)
            self.error.emit(str(e))


# =============================================================================
# H1 PRIOR BUILDER
# =============================================================================

def _build_h1_prior_fig(bars_h1, highlight, zones, pocs, vp_dict):
    """Build H1 chart sliced to end at the H1 candle before entry."""
    _tz = pytz.timezone(DISPLAY_TIMEZONE)

    if bars_h1 is None or (isinstance(bars_h1, pd.DataFrame) and bars_h1.empty):
        return build_h1_chart(bars_h1, highlight, zones, pocs=pocs, volume_profile_dict=vp_dict)

    entry_hour = highlight.entry_time.hour if highlight.entry_time else 9
    cutoff_hour = max(entry_hour - 1, 4)
    cutoff = _tz.localize(datetime.combine(
        highlight.date,
        datetime.min.time().replace(hour=cutoff_hour, minute=0),
    ))
    h1_prior = bars_h1[bars_h1.index <= cutoff]

    if h1_prior.empty:
        return build_h1_chart(bars_h1, highlight, zones, pocs=pocs, volume_profile_dict=vp_dict)

    return build_h1_chart(h1_prior, highlight, zones, pocs=pocs, volume_profile_dict=vp_dict)


# =============================================================================
# MAIN WINDOW
# =============================================================================

class JournalViewerWindow(QMainWindow):
    """Journal Viewer - Trade chart viewer for FIFO journal trades."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Epoch Journal Viewer")
        self.resize(1600, 950)
        self.setStyleSheet(TV_DARK_QSS)

        self._current_highlight: Optional[JournalHighlight] = None
        self._cache: Dict = {}  # {trade_id: (highlight, daily, h1, m15, m5, m1, zones, pocs, vbp, anchor, rampup_df)}
        self._active_threads: list = []

        self._setup_ui()
        self._connect_signals()

    # =========================================================================
    # UI SETUP
    # =========================================================================

    def _setup_ui(self):
        """Build the main layout."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Splitter: left (filters + table) | right (charts)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- Left Panel ----
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

        # Header
        header = QLabel("JOURNAL VIEWER")
        header.setFont(QFont("Trebuchet MS", 14, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {TV_COLORS['text_primary']}; padding: 4px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(header)

        # Filter controls frame
        filter_frame = QFrame()
        filter_frame.setStyleSheet(
            f"QFrame {{ background: {TV_COLORS['bg_secondary']}; "
            f"border: 1px solid {TV_COLORS['border']}; border-radius: 4px; }}"
        )
        filter_layout = QVBoxLayout(filter_frame)
        filter_layout.setContentsMargins(8, 8, 8, 8)
        filter_layout.setSpacing(6)

        # Date From
        date_from_row = QHBoxLayout()
        date_from_label = QLabel("From:")
        date_from_label.setFixedWidth(45)
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDate(QDate.currentDate().addDays(-30))
        self._date_from.setDisplayFormat("yyyy-MM-dd")
        date_from_row.addWidget(date_from_label)
        date_from_row.addWidget(self._date_from)
        filter_layout.addLayout(date_from_row)

        # Date To
        date_to_row = QHBoxLayout()
        date_to_label = QLabel("To:")
        date_to_label.setFixedWidth(45)
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDate(QDate.currentDate())
        self._date_to.setDisplayFormat("yyyy-MM-dd")
        date_to_row.addWidget(date_to_label)
        date_to_row.addWidget(self._date_to)
        filter_layout.addLayout(date_to_row)

        # Symbol filter
        symbol_row = QHBoxLayout()
        symbol_label = QLabel("Symbol:")
        symbol_label.setFixedWidth(45)
        self._symbol_combo = QComboBox()
        self._symbol_combo.addItem("ALL")
        self._symbol_combo.setMinimumWidth(100)
        symbol_row.addWidget(symbol_label)
        symbol_row.addWidget(self._symbol_combo)
        filter_layout.addLayout(symbol_row)

        # Direction filter
        dir_row = QHBoxLayout()
        dir_label = QLabel("Dir:")
        dir_label.setFixedWidth(45)
        self._dir_combo = QComboBox()
        self._dir_combo.addItems(["ALL", "LONG", "SHORT"])
        self._dir_combo.setMinimumWidth(100)
        dir_row.addWidget(dir_label)
        dir_row.addWidget(self._dir_combo)
        filter_layout.addLayout(dir_row)

        # Load button
        self._load_btn = QPushButton("LOAD TRADES")
        self._load_btn.setFont(QFont("Trebuchet MS", 11, QFont.Weight.Bold))
        self._load_btn.setMinimumHeight(36)
        filter_layout.addWidget(self._load_btn)

        # Results info
        self._results_label = QLabel("")
        self._results_label.setStyleSheet(f"color: {TV_COLORS['text_muted']}; font-size: 11px;")
        self._results_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        filter_layout.addWidget(self._results_label)

        left_layout.addWidget(filter_frame)

        # Trade table
        self._trade_table = TradeTable()
        left_layout.addWidget(self._trade_table, stretch=1)

        left_panel.setFixedWidth(380)

        # ---- Right Panel (Chart Preview) ----
        self._chart_preview = ChartPreview()

        splitter.addWidget(left_panel)
        splitter.addWidget(self._chart_preview)
        splitter.setSizes([380, 1220])

        main_layout.addWidget(splitter, stretch=1)

        # Status bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready - Select date range and click LOAD TRADES")

    def _connect_signals(self):
        """Wire up signals."""
        self._load_btn.clicked.connect(self._on_load_trades)
        self._trade_table.selection_changed.connect(self._on_trade_selected)

    # =========================================================================
    # LOAD TRADES
    # =========================================================================

    def _on_load_trades(self):
        """Start background trade loading."""
        date_from = self._date_from.date().toPyDate()
        date_to = self._date_to.date().toPyDate()

        symbol = self._symbol_combo.currentText()
        if symbol == "ALL":
            symbol = None

        direction = self._dir_combo.currentText()
        if direction == "ALL":
            direction = None

        self._load_btn.setEnabled(False)
        self._load_btn.setText("Loading...")
        self._chart_preview.show_placeholder()
        self._results_label.setText("Loading trades...")
        self.statusBar().showMessage(f"Loading trades {date_from} to {date_to}...")

        thread = TradeLoadThread(date_from, date_to, symbol, direction, parent=self)
        thread.finished.connect(self._on_trades_loaded)
        thread.error.connect(self._on_trades_error)
        thread.finished.connect(lambda: self._cleanup_thread(thread))
        thread.error.connect(lambda: self._cleanup_thread(thread))
        self._active_threads.append(thread)
        thread.start()

    def _on_trades_loaded(self, trades: List[Dict]):
        """Handle loaded trades."""
        self._load_btn.setEnabled(True)
        self._load_btn.setText("LOAD TRADES")

        self._trade_table.set_trades(trades)
        self._results_label.setText(f"{len(trades)} trades found")

        # Update symbol dropdown
        tickers = sorted(set(
            (t.get('symbol') or '').upper()
            for t in trades if t.get('symbol')
        ))
        current = self._symbol_combo.currentText()
        self._symbol_combo.clear()
        self._symbol_combo.addItem("ALL")
        self._symbol_combo.addItems(tickers)
        if current in tickers:
            self._symbol_combo.setCurrentText(current)

        if trades:
            self.statusBar().showMessage(f"Loaded {len(trades)} trades")
        else:
            self.statusBar().showMessage("No trades found for the selected filters")

    def _on_trades_error(self, error: str):
        """Handle trade loading error."""
        self._load_btn.setEnabled(True)
        self._load_btn.setText("LOAD TRADES")
        self._results_label.setText(f"Error: {error}")
        self.statusBar().showMessage(f"Error: {error}")
        logger.error(f"Trade load error: {error}")

    # =========================================================================
    # SELECT TRADE -> FETCH BARS -> RENDER CHARTS
    # =========================================================================

    def _on_trade_selected(self, trade_row):
        """Handle table row selection - fetch bars and render charts."""
        if trade_row is None:
            self._chart_preview.show_placeholder()
            self._current_highlight = None
            return

        trade_id = trade_row.get('trade_id', '')

        # Check cache
        if trade_id in self._cache:
            cached = self._cache[trade_id]
            highlight, bars_daily, bars_h1, bars_m15, bars_m5, bars_m1, zones, pocs, vbp_bars, anchor_date, rampup_df = cached
            self._current_highlight = highlight
            self._render_charts(highlight, bars_daily, bars_h1, bars_m15, bars_m5, bars_m1, zones, pocs, vbp_bars, anchor_date, rampup_df)

            # Update the R column in the table
            self._trade_table.update_trade_r(trade_id, highlight.max_r_achieved, highlight.pnl_r)
            return

        # Fetch bars in background
        self._chart_preview.show_loading()
        ticker = (trade_row.get('symbol') or '').upper()
        trade_date = trade_row.get('trade_date')
        self.statusBar().showMessage(f"Fetching bars for {ticker} {trade_date}...")

        thread = BarFetchThread(trade_row, parent=self)
        thread.finished.connect(
            lambda hl, d, h1, m15, m5, m1, z, p, vbp, anch, ramp:
                self._on_bars_fetched(trade_row, hl, d, h1, m15, m5, m1, z, p, vbp, anch, ramp)
        )
        thread.error.connect(self._on_bars_error)
        thread.finished.connect(lambda *_: self._cleanup_thread(thread))
        thread.error.connect(lambda: self._cleanup_thread(thread))
        self._active_threads.append(thread)
        thread.start()

    def _on_bars_fetched(self, trade_row, highlight, bars_daily, bars_h1, bars_m15,
                         bars_m5, bars_m1, zones, pocs, vbp_bars, anchor_date, rampup_df):
        """Handle fetched bar data."""
        trade_id = trade_row.get('trade_id', '')

        # Cache the results (including rampup indicator data)
        self._cache[trade_id] = (
            highlight, bars_daily, bars_h1, bars_m15, bars_m5, bars_m1,
            zones, pocs, vbp_bars, anchor_date, rampup_df,
        )

        # Update the R column in the table
        self._trade_table.update_trade_r(trade_id, highlight.max_r_achieved, highlight.pnl_r)

        # Only render if this is still the selected trade
        selected = self._trade_table.get_selected_trade()
        if selected and selected.get('trade_id') == trade_id:
            self._current_highlight = highlight
            self._render_charts(
                highlight, bars_daily, bars_h1, bars_m15, bars_m5, bars_m1,
                zones, pocs, vbp_bars, anchor_date, rampup_df,
            )

    def _render_charts(self, highlight, bars_daily, bars_h1, bars_m15, bars_m5,
                       bars_m1, zones, pocs=None, vbp_bars=None, anchor_date=None,
                       rampup_df=None):
        """Build and display all 7 charts + rampup indicator table for a trade."""
        try:
            if bars_m5 is None or (isinstance(bars_m5, pd.DataFrame) and bars_m5.empty):
                self._chart_preview.show_error("No M5 bar data available")
                return

            # Compute volume profile ONCE from VbP source bars
            vbp_source = vbp_bars if (vbp_bars is not None and not vbp_bars.empty) else None
            vp_dict = build_volume_profile(vbp_source) if vbp_source is not None else {}

            # Build all 6 chart figures
            daily_fig = build_daily_chart(
                bars_daily, highlight, zones,
                pocs=pocs, anchor_date=anchor_date, volume_profile_dict=vp_dict,
            )
            h1_fig = build_h1_chart(
                bars_h1, highlight, zones,
                pocs=pocs, volume_profile_dict=vp_dict,
            )
            m15_fig = build_m15_chart(
                bars_m15, highlight, zones,
                pocs=pocs, volume_profile_dict=vp_dict,
            )
            m5_entry_fig = build_m5_entry_chart(
                bars_m5, highlight, zones,
                pocs=pocs, volume_profile_dict=vp_dict,
            )
            m1_fig = build_m1_chart(bars_m1, highlight, zones)

            # M1 rampup CHART (Row 4): uses Polygon M1 bars leading up to entry
            rampup_chart_df = self._build_rampup_df(bars_m1, highlight)
            m1_rampup_fig = build_m1_rampup_chart(rampup_chart_df, highlight, zones, pocs=pocs)

            # Build H1 prior figure
            h1_prior_fig = _build_h1_prior_fig(bars_h1, highlight, zones, pocs, vp_dict)

            # Render to preview
            self._chart_preview.show_charts(
                daily_fig, h1_fig, m15_fig, m5_entry_fig, m1_fig, m1_rampup_fig,
                highlight, h1_prior_fig=h1_prior_fig,
            )

            # Row 5: Rampup indicator table (from m1_indicator_bars_2 DB data)
            self._chart_preview.show_rampup(rampup_df)

            self.statusBar().showMessage(
                f"{highlight.ticker} {highlight.date} - {highlight.star_display} | "
                f"{highlight.direction} | "
                f"Entry ${highlight.entry_price:.2f} | "
                f"ATR: {'${:.4f}'.format(highlight.m5_atr_value) if highlight.m5_atr_value else 'N/A'}"
            )

        except Exception as e:
            self._chart_preview.show_error(str(e))
            logger.error(f"Chart render error: {e}", exc_info=True)

    def _build_rampup_df(self, bars_m1, highlight) -> Optional[pd.DataFrame]:
        """
        Build a rampup-style DataFrame from M1 bars leading up to entry.

        The m1_rampup_chart expects a DataFrame with columns:
        bar_date, bar_time, open, high, low, close, volume.
        We extract the 45 M1 bars before entry time.
        """
        if bars_m1 is None or bars_m1.empty or highlight.entry_time is None:
            return None

        try:
            _tz = pytz.timezone(DISPLAY_TIMEZONE)
            entry_dt = _tz.localize(datetime.combine(highlight.date, highlight.entry_time))

            # Get 45 bars before entry
            pre_entry = bars_m1[bars_m1.index < entry_dt].tail(45)

            if pre_entry.empty:
                return None

            # Build DataFrame in the format m1_rampup_chart expects
            df = pre_entry.copy()
            df['bar_date'] = df.index.date
            df['bar_time'] = df.index.time
            df = df.reset_index(drop=True)

            return df

        except Exception as e:
            logger.warning(f"Error building rampup df: {e}")
            return None

    def _on_bars_error(self, error: str):
        """Handle bar fetch error."""
        self._chart_preview.show_error(error)
        self.statusBar().showMessage(f"Error fetching bars: {error}")

    # =========================================================================
    # CLEANUP
    # =========================================================================

    def _cleanup_thread(self, thread):
        """Remove finished thread from active list."""
        if thread in self._active_threads:
            self._active_threads.remove(thread)

    def closeEvent(self, event):
        """Clean up on window close."""
        for thread in self._active_threads:
            thread.quit()
            thread.wait(2000)
        self._active_threads.clear()
        super().closeEvent(event)
