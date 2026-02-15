"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR ANALYSIS v2.0
Tab 5: Composite Setup Analysis - Multi-indicator ideal setups
XIII Trading LLC
================================================================================

Shows how indicators work together to identify the ideal entry setup.
Tests combinations, builds a setup score, and ranks by win rate.
"""
import tempfile
from pathlib import Path
from typing import List

import pandas as pd
import plotly.graph_objects as go

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox
)
from PyQt6.QtGui import QFont, QPixmap, QColor
from PyQt6.QtCore import Qt

from ui.styles import COLORS
from data.provider import DataProvider
from config import THRESHOLDS


class CompositeSetupTab(QWidget):
    """Composite Setup Analysis: Multi-indicator ideal setups."""

    def __init__(self, provider: DataProvider, parent=None):
        super().__init__(parent)
        self._provider = provider
        self._entry_data = pd.DataFrame()
        self._trade_ids = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("Composite Setup Analysis: How Indicators Work Together")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(title)

        subtitle = QLabel(
            "Tests indicator state combinations at entry. "
            "Ranks by win rate with minimum sample size filter."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(subtitle)

        # Controls
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("Min trades per combo:"))
        self._min_trades_spin = QSpinBox()
        self._min_trades_spin.setRange(5, 100)
        self._min_trades_spin.setValue(20)
        self._min_trades_spin.valueChanged.connect(self._on_min_trades_changed)
        ctrl_row.addWidget(self._min_trades_spin)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        # Setup score chart
        self._score_chart_label = QLabel("Loading setup analysis...")
        self._score_chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._score_chart_label.setMinimumHeight(350)
        self._score_chart_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(self._score_chart_label)

        # Combinations table
        combo_label = QLabel("Top & Bottom Indicator Combinations")
        combo_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        combo_label.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(combo_label)

        self._combo_table = QTableWidget()
        self._combo_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._combo_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._combo_table.setMinimumHeight(300)
        self._combo_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['bg_secondary']};
                gridline-color: {COLORS['border']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                font-size: 10pt;
            }}
            QTableWidget::item {{
                padding: 2px 4px;
            }}
            QHeaderView::section {{
                background-color: {COLORS['bg_secondary']};
                color: {COLORS['text_secondary']};
                font-size: 10pt;
                font-weight: bold;
                border: 1px solid {COLORS['border']};
                padding: 4px;
            }}
        """)
        layout.addWidget(self._combo_table)

        layout.addStretch()

    def refresh(self, entry_data: pd.DataFrame, trade_ids: List[str]):
        """Refresh the tab with new data."""
        self._entry_data = entry_data
        self._trade_ids = trade_ids

        if entry_data is None or entry_data.empty:
            self._score_chart_label.setText("No entry data available")
            return

        self._build_setup_score_chart()
        self._build_combinations_table()

    def _on_min_trades_changed(self):
        """Rebuild when min trades threshold changes."""
        if self._trade_ids:
            self._build_combinations_table()

    def _build_setup_score_chart(self):
        """Build setup score distribution with win rate overlay."""
        df = self._entry_data.copy()
        if df.empty:
            return

        # Calculate setup score (0-7 based on favorable conditions)
        df['setup_score'] = 0

        # +1 for candle range >= 0.15%
        if 'candle_range_pct' in df.columns:
            df['setup_score'] += (df['candle_range_pct'] >= 0.15).astype(int)

        # +1 for vol_roc >= 30%
        if 'vol_roc' in df.columns:
            df['setup_score'] += (df['vol_roc'] >= 30).astype(int)

        # +1 for SMA spread >= 0.15%
        if 'sma_spread_pct' in df.columns:
            df['setup_score'] += (df['sma_spread_pct'] >= 0.15).astype(int)

        # +1 for SMA config aligned with direction
        if 'sma_config' in df.columns and 'direction' in df.columns:
            aligned = (
                ((df['direction'] == 'LONG') & (df['sma_config'] == 'BULL')) |
                ((df['direction'] == 'SHORT') & (df['sma_config'] == 'BEAR'))
            )
            df['setup_score'] += aligned.astype(int)

        # +1 for M5 structure aligned
        if 'm5_structure' in df.columns and 'direction' in df.columns:
            m5_aligned = (
                ((df['direction'] == 'LONG') & (df['m5_structure'] == 'BULL')) |
                ((df['direction'] == 'SHORT') & (df['m5_structure'] == 'BEAR'))
            )
            df['setup_score'] += m5_aligned.astype(int)

        # +1 for H1 NEUTRAL (strongest edge)
        if 'h1_structure' in df.columns:
            df['setup_score'] += (df['h1_structure'] == 'NEUTRAL').astype(int)

        # +1 for CVD slope aligned with direction
        if 'cvd_slope' in df.columns and 'direction' in df.columns:
            cvd_aligned = (
                ((df['direction'] == 'LONG') & (df['cvd_slope'] > 0.1)) |
                ((df['direction'] == 'SHORT') & (df['cvd_slope'] < -0.1))
            )
            df['setup_score'] += cvd_aligned.astype(int)

        # Group by score
        score_groups = df.groupby('setup_score').agg(
            trades=('is_winner', 'count'),
            wins=('is_winner', 'sum'),
        ).reset_index()
        score_groups['win_rate'] = (score_groups['wins'] / score_groups['trades'] * 100).round(1)

        # Build chart
        fig = go.Figure()

        # Trade count bars
        fig.add_trace(go.Bar(
            x=score_groups['setup_score'],
            y=score_groups['trades'],
            name='Trade Count',
            marker_color='#1a4a7a',
            opacity=0.7,
            yaxis='y',
        ))

        # Win rate line
        fig.add_trace(go.Scatter(
            x=score_groups['setup_score'],
            y=score_groups['win_rate'],
            name='Win Rate %',
            line=dict(color='#ffc107', width=3),
            mode='lines+markers',
            yaxis='y2',
        ))

        fig.add_hline(y=50, line_dash="dot", line_color="#555", yref='y2')

        fig.update_layout(
            title="Setup Score Distribution & Win Rate",
            height=350, width=1100,
            template='plotly_dark',
            paper_bgcolor='#000000',
            plot_bgcolor='#0a0a1a',
            font=dict(color='#e0e0e0', size=10),
            margin=dict(l=60, r=60, t=50, b=40),
            xaxis_title="Setup Score (0-7)",
            yaxis=dict(title="Trade Count", gridcolor='#1a1a3e'),
            yaxis2=dict(
                title="Win Rate %", overlaying='y', side='right',
                range=[0, 100],
            ),
            legend=dict(orientation='h', yanchor='bottom', y=1.02),
            barmode='group',
        )

        self._render_chart(fig, self._score_chart_label)

    def _build_combinations_table(self):
        """Build the top/bottom combinations table."""
        min_trades = self._min_trades_spin.value()

        try:
            combo_df = self._provider.get_setup_combinations(
                self._trade_ids, min_trades=min_trades
            )
        except Exception as e:
            self._combo_table.setRowCount(0)
            return

        if combo_df.empty:
            self._combo_table.setRowCount(0)
            return

        # Show top 10 and bottom 10
        top = combo_df.head(10)
        bottom = combo_df.tail(10)
        display = pd.concat([top, bottom]).drop_duplicates()

        headers = ['SMA Config', 'H1 Struct', 'M15 Struct', 'Vol ROC',
                    'Candle Level', 'Trades', 'Wins', 'Win Rate', 'Avg R']
        self._combo_table.setColumnCount(len(headers))
        self._combo_table.setHorizontalHeaderLabels(headers)
        self._combo_table.setRowCount(len(display))

        cell_font = QFont("Consolas", 10)

        for row_idx, (_, row) in enumerate(display.iterrows()):
            cols = [
                str(row.get('sma_config', '-')),
                str(row.get('h1_structure', '-')),
                str(row.get('m15_structure', '-')),
                str(row.get('vol_roc_level', '-')),
                str(row.get('candle_level', '-')),
                str(int(row.get('trades', 0))),
                str(int(row.get('wins', 0))),
                f"{row.get('win_rate', 0):.1f}%",
                f"{row.get('avg_r', 0):.2f}",
            ]

            wr = float(row.get('win_rate', 0))
            color = QColor('#26a69a') if wr >= 50 else QColor('#ef5350')

            for col_idx, val in enumerate(cols):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFont(cell_font)
                if col_idx >= 7:  # Win Rate and Avg R columns
                    item.setForeground(color)
                self._combo_table.setItem(row_idx, col_idx, item)

        # Resize
        header = self._combo_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

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
