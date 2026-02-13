"""
Chart Preview Panel for Journal Viewer
Epoch Trading System - XIII Trading LLC

Displays charts in paired 2-up layout (5 rows).
Adapted from 11_trade_reel/ui/chart_preview.py.

Layout:
    Row 1: Daily + H1 Prior (side by side)
    Row 2: H1 + M15 (side by side)
    Row 3: M5 Entry + M1 Action (side by side)
    Row 4: M1 Ramp-Up (full width)
    Row 5: M1 Ramp-Up Indicator Table (45 bars, from m1_indicator_bars_2)
"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import plotly.graph_objects as go

from .config import TV_COLORS, TRADE_REEL_DIR

# Import chart renderer and rampup table from 11_trade_reel
sys.path.insert(0, str(TRADE_REEL_DIR))
from ui.chart_renderer import create_chart_label, render_chart_to_label, RENDER_WIDTH, CHART_HEIGHT
from ui.rampup_table import RampUpTable


class ChartPreview(QFrame):
    """Panel showing charts in paired 2-up layout + rampup indicator table."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area wrapping all content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        self._content_layout = QVBoxLayout(container)
        self._content_layout.setContentsMargins(8, 8, 8, 8)
        self._content_layout.setSpacing(6)

        # Trade summary header
        self._summary = QLabel("Select a trade to view charts")
        self._summary.setFont(QFont("Trebuchet MS", 12))
        self._summary.setStyleSheet(f"color: {TV_COLORS['text_muted']}; padding: 8px;")
        self._summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._summary.setWordWrap(True)
        self._content_layout.addWidget(self._summary)

        _section_style = (
            f"color: {TV_COLORS['text_muted']}; font-size: 11px; "
            f"font-weight: bold; padding: 4px 8px; background: {TV_COLORS['bg_secondary']};"
        )

        # Render width for paired charts (half width each)
        self._pair_render_width = RENDER_WIDTH // 2

        # ---- Row 1: Daily + H1 Prior ----
        row1_label = QLabel("Daily  +  1-Hour Prior")
        row1_label.setStyleSheet(_section_style)
        self._content_layout.addWidget(row1_label)

        row1 = QWidget()
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(4)

        self._daily_chart = create_chart_label(min_height=200)
        self._h1_chart_row1 = create_chart_label(min_height=200)
        row1_layout.addWidget(self._daily_chart, stretch=1)
        row1_layout.addWidget(self._h1_chart_row1, stretch=1)
        self._content_layout.addWidget(row1)

        # ---- Row 2: H1 + M15 ----
        row2_label = QLabel("1-Hour  +  15-Minute")
        row2_label.setStyleSheet(_section_style)
        self._content_layout.addWidget(row2_label)

        row2 = QWidget()
        row2_layout = QHBoxLayout(row2)
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(4)

        self._h1_chart_row2 = create_chart_label(min_height=200)
        self._m15_chart = create_chart_label(min_height=200)
        row2_layout.addWidget(self._h1_chart_row2, stretch=1)
        row2_layout.addWidget(self._m15_chart, stretch=1)
        self._content_layout.addWidget(row2)

        # ---- Row 3: M5 Entry + M1 Action ----
        row3_label = QLabel("5-Minute Entry  +  1-Minute Action")
        row3_label.setStyleSheet(_section_style)
        self._content_layout.addWidget(row3_label)

        row3 = QWidget()
        row3_layout = QHBoxLayout(row3)
        row3_layout.setContentsMargins(0, 0, 0, 0)
        row3_layout.setSpacing(4)

        self._m5_entry_chart = create_chart_label(min_height=200)
        self._m1_chart = create_chart_label(min_height=200)
        row3_layout.addWidget(self._m5_entry_chart, stretch=1)
        row3_layout.addWidget(self._m1_chart, stretch=1)
        self._content_layout.addWidget(row3)

        # ---- Row 4: M1 Ramp-Up (full width) ----
        row4_label = QLabel("1-Minute Ramp-Up")
        row4_label.setStyleSheet(_section_style)
        self._content_layout.addWidget(row4_label)

        self._m1_rampup_chart = create_chart_label(min_height=250)
        self._content_layout.addWidget(self._m1_rampup_chart)

        # ---- Row 5: M1 Ramp-Up Indicator Table ----
        self._rampup_table = RampUpTable()
        self._content_layout.addWidget(self._rampup_table)

        self._content_layout.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def show_charts(
        self,
        daily_fig: go.Figure,
        h1_fig: go.Figure,
        m15_fig: go.Figure,
        m5_entry_fig: go.Figure,
        m1_fig: go.Figure,
        m1_rampup_fig: go.Figure,
        highlight,
        h1_prior_fig: go.Figure = None,
    ):
        """Render charts in paired 2-up layout."""
        self._update_summary(highlight)

        pair_w = self._pair_render_width
        pair_h = 340

        # Row 1: Daily + H1 Prior
        h1_row1 = h1_prior_fig if h1_prior_fig is not None else h1_fig
        render_chart_to_label(daily_fig, self._daily_chart, width=pair_w, height=pair_h)
        render_chart_to_label(h1_row1, self._h1_chart_row1, width=pair_w, height=pair_h)

        # Row 2: H1 (full trade day) + M15
        render_chart_to_label(h1_fig, self._h1_chart_row2, width=pair_w, height=pair_h)
        render_chart_to_label(m15_fig, self._m15_chart, width=pair_w, height=pair_h)

        # Row 3: M5 Entry + M1 Action
        render_chart_to_label(m5_entry_fig, self._m5_entry_chart, width=pair_w, height=pair_h)
        render_chart_to_label(m1_fig, self._m1_chart, width=pair_w, height=pair_h)

        # Row 4: M1 Ramp-Up (full width)
        render_chart_to_label(m1_rampup_fig, self._m1_rampup_chart, width=RENDER_WIDTH, height=380)

    def show_rampup(self, rampup_df):
        """Populate the Row 5 rampup indicator table."""
        if rampup_df is not None and not rampup_df.empty:
            self._rampup_table.update_data(rampup_df)
        else:
            self._rampup_table.clear()

    def show_loading(self):
        """Show loading state."""
        self._summary.setText("Loading charts...")
        self._summary.setStyleSheet(f"color: {TV_COLORS['accent']}; padding: 8px;")
        self._daily_chart.setText("Loading Daily...")
        self._h1_chart_row1.setText("Loading H1 Prior...")
        self._h1_chart_row2.setText("Loading H1...")
        self._m15_chart.setText("Loading M15...")
        self._m5_entry_chart.setText("Loading M5 Entry...")
        self._m1_chart.setText("Loading M1...")
        self._m1_rampup_chart.setText("Loading M1 Ramp-Up...")
        self._rampup_table.clear()

    def show_placeholder(self):
        """Show placeholder state."""
        self._summary.setText("Select a trade to view charts")
        self._summary.setStyleSheet(f"color: {TV_COLORS['text_muted']}; padding: 8px;")
        self._daily_chart.setText("Daily chart will appear here")
        self._h1_chart_row1.setText("H1 Prior chart will appear here")
        self._h1_chart_row2.setText("H1 chart will appear here")
        self._m15_chart.setText("M15 chart will appear here")
        self._m5_entry_chart.setText("M5 Entry chart will appear here")
        self._m1_chart.setText("M1 chart will appear here")
        self._m1_rampup_chart.setText("M1 Ramp-Up chart will appear here")
        self._rampup_table.clear()

    def show_error(self, message: str):
        """Show error state."""
        self._summary.setText(f"Error: {message}")
        self._summary.setStyleSheet(f"color: {TV_COLORS['bear']}; padding: 8px;")

    def _update_summary(self, hl):
        """Update trade summary header."""
        dir_color = TV_COLORS['bull'] if hl.direction == 'LONG' else TV_COLORS['bear']
        outcome_color = TV_COLORS['bull'] if hl.is_winner else TV_COLORS['bear']
        pnl_str = f"{hl.pnl_r:+.2f}R" if hl.pnl_r else ""
        pnl_dollar_str = f"${hl.pnl_dollars:+.2f}" if hl.pnl_dollars else ""

        # Build exit info
        exit_info = ""
        if hl.exit_price:
            exit_info = f"Exit ${hl.exit_price:.2f}"
            if hl.exit_time:
                exit_info += f" @ {hl.exit_time.strftime('%H:%M')}"

        summary_html = (
            f"<span style='color:{dir_color}; font-weight:bold; font-size:16px;'>"
            f"{hl.ticker}</span>"
            f"<span style='color:{TV_COLORS['text_muted']};'>  |  {hl.date}  |  </span>"
            f"<span style='color:{dir_color};'>{hl.direction}</span>"
            f"<span style='color:{TV_COLORS['text_muted']};'>  |  "
            f"Entry ${hl.entry_price:.2f} @ {hl.entry_time.strftime('%H:%M') if hl.entry_time else '?'}  |  </span>"
            f"<span style='color:{TV_COLORS['text_muted']};'>{exit_info}  |  </span>"
            f"<span style='color:{outcome_color}; font-weight:bold;'>"
            f"{hl.star_display} {pnl_str} {pnl_dollar_str}</span>"
        )

        self._summary.setText(summary_html)
        self._summary.setStyleSheet(f"color: {TV_COLORS['text_primary']}; padding: 8px;")
