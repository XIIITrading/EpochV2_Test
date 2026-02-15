"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR ANALYSIS v2.0
Tab 2: Entry Snapshot - Indicator state at the moment of entry
XIII Trading LLC
================================================================================

Shows indicator values at entry, win rate by indicator state,
and best/worst entry profiles comparison.
"""
import tempfile
from pathlib import Path
from typing import List, Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy
)
from PyQt6.QtGui import QFont, QPixmap, QColor
from PyQt6.QtCore import Qt

from ui.styles import COLORS
from data.provider import DataProvider
from config import CATEGORICAL_INDICATORS, CONTINUOUS_INDICATORS


class EntrySnapshotTab(QWidget):
    """Entry Snapshot: Indicator state at the exact moment of entry."""

    def __init__(self, provider: DataProvider, parent=None):
        super().__init__(parent)
        self._provider = provider
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("Entry Snapshot: Indicator State at Entry")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(title)

        subtitle = QLabel(
            "Win rate breakdown by each indicator's state at the M1 bar "
            "just before entry. Uses entry data from m1_trade_indicator_2."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(subtitle)

        # Indicator cards row
        self._cards_frame = QFrame()
        self._cards_layout = QHBoxLayout(self._cards_frame)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(8)
        layout.addWidget(self._cards_frame)

        # Win rate charts (categorical)
        self._cat_chart_label = QLabel("Loading categorical indicators...")
        self._cat_chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cat_chart_label.setMinimumHeight(400)
        self._cat_chart_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(self._cat_chart_label)

        # Win rate charts (continuous quintiles)
        self._cont_chart_label = QLabel("Loading continuous indicators...")
        self._cont_chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cont_chart_label.setMinimumHeight(400)
        self._cont_chart_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(self._cont_chart_label)

        layout.addStretch()

    def refresh(self, entry_data: pd.DataFrame, trade_ids: List[str]):
        """Refresh the tab with new data."""
        if entry_data is None or entry_data.empty:
            self._cat_chart_label.setText("No entry data available")
            self._cont_chart_label.setText("")
            return

        self._update_cards(entry_data)
        self._build_categorical_charts(trade_ids)
        self._build_continuous_charts(trade_ids)

    def _update_cards(self, df: pd.DataFrame):
        """Update indicator summary cards."""
        # Clear existing cards
        while self._cards_layout.count():
            child = self._cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        total = len(df)
        winners = df['is_winner'].sum() if 'is_winner' in df.columns else 0
        win_rate = (winners / total * 100) if total > 0 else 0

        cards_data = [
            ("Total Trades", f"{total:,}", COLORS['text_primary']),
            ("Win Rate", f"{win_rate:.1f}%",
             COLORS['positive'] if win_rate >= 50 else COLORS['negative']),
            ("Avg R", f"{df['pnl_r'].mean():.2f}" if 'pnl_r' in df.columns else "-",
             COLORS['positive'] if df.get('pnl_r', pd.Series([0])).mean() > 0 else COLORS['negative']),
        ]

        for label, value, color in cards_data:
            card = QFrame()
            card.setStyleSheet(
                f"background-color: {COLORS['bg_secondary']}; "
                f"border: 1px solid {COLORS['border']}; padding: 8px;"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 8, 12, 8)

            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px;")
            card_layout.addWidget(lbl)

            val = QLabel(value)
            val.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
            val.setStyleSheet(f"color: {color};")
            card_layout.addWidget(val)

            self._cards_layout.addWidget(card)

        self._cards_layout.addStretch()

    def _build_categorical_charts(self, trade_ids: List[str]):
        """Build win rate bar charts for categorical indicators."""
        cat_indicators = [
            ('sma_config', 'SMA Configuration'),
            ('h1_structure', 'H1 Structure'),
            ('m15_structure', 'M15 Structure'),
            ('m5_structure', 'M5 Structure'),
            ('price_position', 'Price Position'),
            ('sma_momentum_label', 'SMA Momentum'),
        ]

        fig = make_subplots(
            rows=2, cols=3,
            subplot_titles=[name for _, name in cat_indicators],
            vertical_spacing=0.12,
            horizontal_spacing=0.08,
        )

        for idx, (col, name) in enumerate(cat_indicators):
            row = idx // 3 + 1
            col_pos = idx % 3 + 1

            try:
                wr_df = self._provider.get_win_rate_by_state(trade_ids, col)
                if not wr_df.empty:
                    colors = [
                        '#26a69a' if wr >= 50 else '#ef5350'
                        for wr in wr_df['win_rate']
                    ]
                    fig.add_trace(
                        go.Bar(
                            x=wr_df['state'],
                            y=wr_df['win_rate'],
                            text=[f"{wr:.0f}%<br>n={n}" for wr, n in
                                  zip(wr_df['win_rate'], wr_df['trades'])],
                            textposition='outside',
                            marker_color=colors,
                            showlegend=False,
                        ),
                        row=row, col=col_pos
                    )
                    fig.add_hline(y=50, line_dash="dot", line_color="#555",
                                  row=row, col=col_pos)
            except Exception:
                pass

        fig.update_layout(
            height=500, width=1100,
            template='plotly_dark',
            paper_bgcolor='#000000',
            plot_bgcolor='#0a0a1a',
            font=dict(color='#e0e0e0', size=10),
            margin=dict(l=40, r=20, t=40, b=40),
        )
        fig.update_yaxes(title_text="Win Rate %", gridcolor='#1a1a3e')
        fig.update_xaxes(gridcolor='#1a1a3e')

        self._render_chart(fig, self._cat_chart_label)

    def _build_continuous_charts(self, trade_ids: List[str]):
        """Build win rate bar charts for continuous indicator quintiles."""
        cont_indicators = [
            ('candle_range_pct', 'Candle Range %'),
            ('vol_roc', 'Vol ROC'),
            ('vol_delta_roll', 'Vol Delta'),
            ('sma_spread_pct', 'SMA Spread %'),
            ('cvd_slope', 'CVD Slope'),
        ]

        fig = make_subplots(
            rows=2, cols=3,
            subplot_titles=[name for _, name in cont_indicators] + [''],
            vertical_spacing=0.12,
            horizontal_spacing=0.08,
        )

        for idx, (col, name) in enumerate(cont_indicators):
            row = idx // 3 + 1
            col_pos = idx % 3 + 1

            try:
                q_df = self._provider.get_win_rate_by_quintile(trade_ids, col)
                if not q_df.empty:
                    labels = [
                        f"Q{q}\n{lo:.2f}-{hi:.2f}"
                        for q, lo, hi in zip(
                            q_df['quintile'], q_df['range_min'], q_df['range_max']
                        )
                    ]
                    colors = [
                        '#26a69a' if wr >= 50 else '#ef5350'
                        for wr in q_df['win_rate']
                    ]
                    fig.add_trace(
                        go.Bar(
                            x=labels,
                            y=q_df['win_rate'],
                            text=[f"{wr:.0f}%" for wr in q_df['win_rate']],
                            textposition='outside',
                            marker_color=colors,
                            showlegend=False,
                        ),
                        row=row, col=col_pos
                    )
                    fig.add_hline(y=50, line_dash="dot", line_color="#555",
                                  row=row, col=col_pos)
            except Exception:
                pass

        fig.update_layout(
            height=500, width=1100,
            template='plotly_dark',
            paper_bgcolor='#000000',
            plot_bgcolor='#0a0a1a',
            font=dict(color='#e0e0e0', size=10),
            margin=dict(l=40, r=20, t=40, b=40),
        )
        fig.update_yaxes(title_text="Win Rate %", gridcolor='#1a1a3e')
        fig.update_xaxes(gridcolor='#1a1a3e')

        self._render_chart(fig, self._cont_chart_label)

    def _render_chart(self, fig: go.Figure, label: QLabel):
        """Render Plotly figure to PNG and display in QLabel."""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name
            fig.write_image(tmp_path, engine='kaleido')
            pixmap = QPixmap(tmp_path)
            if not pixmap.isNull():
                scaled = pixmap.scaledToWidth(
                    max(label.width() - 20, 800),
                    Qt.TransformationMode.SmoothTransformation
                )
                label.setPixmap(scaled)
            else:
                label.setText("Chart rendering failed")
        except Exception as e:
            label.setText(f"Chart error: {e}")
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)
