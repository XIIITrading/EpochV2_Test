"""
Epoch Trading System - M1 Ramp-Up Indicator Table (Trade Reel)
QTableWidget showing 7 indicator rows x N bar columns, up to entry.
Data sourced from m1_indicator_bars_2 table.

Reuses formatter/color logic from 06_training/components/rampup_chart.py.
"""

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date, time
from decimal import Decimal
from typing import Optional
import logging

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy,
)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_CONFIG, TV_COLORS

logger = logging.getLogger(__name__)

# Number of M1 bars before entry to show
RAMPUP_BARS = 120

# Indicator row labels
INDICATOR_LABELS = [
    'Candle %',
    'Vol Delta',
    'Vol ROC',
    'SMA',
    'M5 Struct',
    'M15 Struct',
    'H1 Struct',
]


# =============================================================================
# COLOR HELPERS (TradingView Dark palette)
# =============================================================================

def _to_float(val) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _color_candle_range(pct) -> str:
    pct = _to_float(pct)
    if pct is None:
        return TV_COLORS['text_muted']
    if pct >= 0.15:
        return TV_COLORS['bull']
    elif pct >= 0.12:
        return TV_COLORS['text_muted']
    return TV_COLORS['bear']


def _color_vol_delta(val) -> str:
    val = _to_float(val)
    if val is None:
        return TV_COLORS['text_muted']
    return TV_COLORS['bull'] if val > 0 else TV_COLORS['bear']


def _color_vol_roc(val) -> str:
    val = _to_float(val)
    if val is None:
        return TV_COLORS['text_muted']
    if val >= 30:
        return TV_COLORS['bull']
    elif val >= 0:
        return '#FFC107'  # Yellow
    return TV_COLORS['bear']


def _color_sma(spread) -> str:
    spread = _to_float(spread)
    if spread is None:
        return TV_COLORS['text_muted']
    return TV_COLORS['bull'] if spread > 0 else TV_COLORS['bear']


def _color_structure(val) -> str:
    if val is None:
        return TV_COLORS['text_muted']
    s = str(val).upper()
    if s == 'BULL':
        return TV_COLORS['bull']
    elif s == 'BEAR':
        return TV_COLORS['bear']
    return TV_COLORS['text_muted']


def _color_score(val) -> str:
    if val is None:
        return TV_COLORS['text_muted']
    try:
        s = int(val)
    except (TypeError, ValueError):
        return TV_COLORS['text_muted']
    if s >= 5:
        return TV_COLORS['bull']
    elif s >= 3:
        return '#FFC107'
    return TV_COLORS['bear']


# =============================================================================
# VALUE FORMATTERS
# =============================================================================

def _fmt_candle_range(pct) -> str:
    pct = _to_float(pct)
    return f"{pct:.2f}" if pct is not None else '-'


def _fmt_vol_delta(val) -> str:
    val = _to_float(val)
    if val is None:
        return '-'
    prefix = '+' if val > 0 else ''
    a = abs(val)
    if a >= 1_000_000:
        return f"{prefix}{val / 1_000_000:.1f}M"
    elif a >= 1_000:
        return f"{prefix}{val / 1_000:.0f}K"
    return f"{prefix}{val:.0f}"


def _fmt_vol_roc(val) -> str:
    val = _to_float(val)
    if val is None:
        return '-'
    return f"{'+' if val > 0 else ''}{val:.0f}%"


def _fmt_sma(spread, close) -> str:
    spread = _to_float(spread)
    close = _to_float(close)
    if spread is None or close is None or close == 0:
        return '-'
    config = 'B' if spread > 0 else 'S'
    pct = abs(spread) / close * 100
    return f"{config}{pct:.2f}"


def _fmt_structure(val) -> str:
    if val is None:
        return '-'
    s = str(val).upper()
    if s == 'BULL':
        return '\u25B2'
    elif s == 'BEAR':
        return '\u25BC'
    return '\u2500'


def _fmt_score(val) -> str:
    if val is None:
        return '-'
    try:
        return str(int(val))
    except (TypeError, ValueError):
        return '-'


# =============================================================================
# DATA FETCH
# =============================================================================

def fetch_rampup_data(
    ticker: str,
    trade_date: date,
    entry_time: time,
    num_bars: int = RAMPUP_BARS,
) -> pd.DataFrame:
    """Fetch M1 indicator bars up to (but not including) entry time."""
    query = """
        SELECT
            ticker, bar_date, bar_time,
            open, high, low, close, volume,
            vwap, sma9, sma21, sma_spread,
            vol_roc, vol_delta_roll,
            m5_structure, m15_structure, h1_structure,
            candle_range_pct
        FROM m1_indicator_bars_2
        WHERE ticker = %s
          AND bar_date = %s
          AND bar_time < %s
        ORDER BY bar_time DESC
        LIMIT %s
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (ticker.upper(), trade_date, entry_time, num_bars))
            rows = cur.fetchall()
        conn.close()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame([dict(r) for r in rows])
        df = df.iloc[::-1].reset_index(drop=True)
        return df

    except Exception as e:
        logger.error(f"Error fetching rampup data: {e}")
        return pd.DataFrame()


# =============================================================================
# QT WIDGET
# =============================================================================

class RampUpTable(QFrame):
    """M1 ramp-up indicator table: 7 rows x N bar columns, color-coded."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        self._title = QLabel("M1 Ramp-Up Indicators")
        self._title.setFont(QFont("Trebuchet MS", 11, QFont.Weight.Bold))
        self._title.setStyleSheet(f"color: {TV_COLORS['text_primary']}; padding: 2px 0;")
        layout.addWidget(self._title)

        self._table = QTableWidget()
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setMinimumSectionSize(36)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {TV_COLORS['bg_primary']};
                gridline-color: {TV_COLORS['border']};
                color: {TV_COLORS['text_primary']};
                border: 1px solid {TV_COLORS['border']};
                font-size: 11pt;
            }}
            QTableWidget::item {{
                padding: 1px 2px;
            }}
            QHeaderView::section {{
                background-color: {TV_COLORS['bg_secondary']};
                color: {TV_COLORS['text_muted']};
                font-size: 11pt;
                border: 1px solid {TV_COLORS['border']};
                padding: 2px;
            }}
        """)
        layout.addWidget(self._table)

    def update_data(self, df: pd.DataFrame):
        """Populate the table from M1 indicator bar DataFrame."""
        if df is None or df.empty:
            self._table.setRowCount(0)
            self._table.setColumnCount(0)
            self._title.setText("M1 Ramp-Up Indicators - No data")
            return

        num_bars = len(df)
        num_ind = len(INDICATOR_LABELS)

        self._table.setRowCount(num_ind)
        self._table.setColumnCount(num_bars)

        # Column headers = time labels
        time_labels = []
        for _, row in df.iterrows():
            bt = row.get('bar_time')
            if bt and hasattr(bt, 'strftime'):
                time_labels.append(bt.strftime('%H:%M'))
            else:
                time_labels.append(str(bt)[:5] if bt else '-')
        self._table.setHorizontalHeaderLabels(time_labels)

        # Row headers = indicator names
        self._table.setVerticalHeaderLabels(INDICATOR_LABELS)
        self._table.verticalHeader().setVisible(True)
        self._table.verticalHeader().setDefaultSectionSize(26)
        self._table.verticalHeader().setFixedWidth(75)
        self._table.verticalHeader().setStyleSheet(f"""
            QHeaderView::section {{
                background-color: {TV_COLORS['bg_secondary']};
                color: {TV_COLORS['text_muted']};
                font-size: 11pt;
                font-weight: bold;
                border: 1px solid {TV_COLORS['border']};
                padding: 2px 4px;
            }}
        """)

        cell_font = QFont("Consolas", 11)
        cell_font.setBold(True)

        for col_idx, (_, row) in enumerate(df.iterrows()):
            for row_idx, ind_name in enumerate(INDICATOR_LABELS):
                value, color = self._cell(ind_name, row)
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFont(cell_font)
                item.setForeground(QColor(color))
                self._table.setItem(row_idx, col_idx, item)

        # Sizing
        header = self._table.horizontalHeader()
        header.setMinimumSectionSize(36)
        header.setDefaultSectionSize(48)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        row_h = 26
        total_h = (num_ind * row_h) + 32
        self._table.setFixedHeight(total_h)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._title.setText(f"M1 Ramp-Up Indicators ({num_bars} bars to entry)")

    def clear(self):
        self._table.setRowCount(0)
        self._table.setColumnCount(0)
        self._title.setText("M1 Ramp-Up Indicators")

    def _cell(self, ind_name: str, row: pd.Series) -> tuple:
        """Return (formatted_value, hex_color) for a cell."""
        if ind_name == 'Candle %':
            return _fmt_candle_range(row.get('candle_range_pct')), _color_candle_range(row.get('candle_range_pct'))
        elif ind_name == 'Vol Delta':
            return _fmt_vol_delta(row.get('vol_delta_roll')), _color_vol_delta(row.get('vol_delta_roll'))
        elif ind_name == 'Vol ROC':
            return _fmt_vol_roc(row.get('vol_roc')), _color_vol_roc(row.get('vol_roc'))
        elif ind_name == 'SMA':
            return _fmt_sma(row.get('sma_spread'), row.get('close')), _color_sma(row.get('sma_spread'))
        elif ind_name == 'M5 Struct':
            return _fmt_structure(row.get('m5_structure')), _color_structure(row.get('m5_structure'))
        elif ind_name == 'M15 Struct':
            return _fmt_structure(row.get('m15_structure')), _color_structure(row.get('m15_structure'))
        elif ind_name == 'H1 Struct':
            return _fmt_structure(row.get('h1_structure')), _color_structure(row.get('h1_structure'))
        return '-', TV_COLORS['text_muted']
