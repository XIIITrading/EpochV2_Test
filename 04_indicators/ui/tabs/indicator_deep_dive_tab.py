"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR ANALYSIS v2.0
Tab 4: Indicator Deep Dive - Per-indicator three-phase analysis
XIII Trading LLC
================================================================================

Focus on one indicator at a time with comprehensive analysis
across all three phases (ramp-up -> entry -> post-trade).
"""
import tempfile
from pathlib import Path
from typing import List

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QFrame
)
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtCore import Qt

from ui.styles import COLORS
from data.provider import DataProvider
from config import ALL_DEEP_DIVE_INDICATORS, RAMP_UP_BARS, POST_TRADE_BARS


class IndicatorDeepDiveTab(QWidget):
    """Indicator Deep Dive: Per-indicator three-phase analysis."""

    def __init__(self, provider: DataProvider, parent=None):
        super().__init__(parent)
        self._provider = provider
        self._trade_ids = []
        self._entry_data = pd.DataFrame()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("Indicator Deep Dive: Three-Phase Progression")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(title)

        # Indicator selector
        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("Select Indicator:"))
        self._indicator_combo = QComboBox()
        for col, name, ind_type in ALL_DEEP_DIVE_INDICATORS:
            self._indicator_combo.addItem(f"{name} ({ind_type})", col)
        self._indicator_combo.currentIndexChanged.connect(self._on_indicator_changed)
        selector_row.addWidget(self._indicator_combo)
        selector_row.addStretch()
        layout.addLayout(selector_row)

        # Three-phase chart
        self._phase_chart_label = QLabel("Select an indicator and load data...")
        self._phase_chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._phase_chart_label.setMinimumHeight(350)
        self._phase_chart_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(self._phase_chart_label)

        # Win rate analysis
        self._winrate_chart_label = QLabel("")
        self._winrate_chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._winrate_chart_label.setMinimumHeight(300)
        self._winrate_chart_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(self._winrate_chart_label)

        # Model breakdown table
        self._breakdown_label = QLabel("")
        self._breakdown_label.setWordWrap(True)
        self._breakdown_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px; "
            f"background-color: {COLORS['bg_secondary']}; padding: 12px; "
            f"border: 1px solid {COLORS['border']};"
        )
        layout.addWidget(self._breakdown_label)

        layout.addStretch()

    def refresh(self, entry_data: pd.DataFrame, trade_ids: List[str]):
        """Refresh with new filtered data."""
        self._entry_data = entry_data
        self._trade_ids = trade_ids
        self._on_indicator_changed()

    def _on_indicator_changed(self):
        """When indicator selection changes, rebuild all charts."""
        if not self._trade_ids:
            return

        col = self._indicator_combo.currentData()
        if not col:
            return

        idx = self._indicator_combo.currentIndex()
        _, name, ind_type = ALL_DEEP_DIVE_INDICATORS[idx]

        # Build three-phase chart (only for continuous)
        if ind_type == 'continuous':
            self._build_three_phase_chart(col, name)
            self._build_quintile_chart(col, name)
        else:
            self._build_state_chart(col, name)
            self._phase_chart_label.setText(
                f"Three-phase progression not available for categorical indicator '{name}'. "
                "See win rate by state below."
            )

        # Build model breakdown
        self._build_model_breakdown(col, name)

    def _build_three_phase_chart(self, col: str, name: str):
        """Build the ramp-up -> entry -> post-trade unified chart."""
        try:
            df = self._provider.get_three_phase_averages(self._trade_ids, col)
            if df.empty:
                self._phase_chart_label.setText("No phase data available")
                return

            fig = go.Figure()

            for is_winner, label, color in [
                (True, 'Winners', '#26a69a'),
                (False, 'Losers', '#ef5350'),
            ]:
                subset = df[df['is_winner'] == is_winner]

                # Ramp-up: bars -24 to -1
                ramp = subset[subset['phase'] == 'ramp_up'].copy()
                if not ramp.empty:
                    ramp['x_pos'] = ramp['bar_sequence'] - RAMP_UP_BARS

                    fig.add_trace(go.Scatter(
                        x=ramp['x_pos'], y=ramp['avg_value'],
                        name=label, line=dict(color=color, width=2),
                        legendgroup=label,
                    ))

                # Post-trade: bars 0 to 24
                post = subset[subset['phase'] == 'post_trade'].copy()
                if not post.empty:
                    fig.add_trace(go.Scatter(
                        x=post['bar_sequence'], y=post['avg_value'],
                        name=None, line=dict(color=color, width=2),
                        legendgroup=label, showlegend=False,
                    ))

            # Entry marker
            fig.add_vline(x=0, line_dash="dash", line_color="#ffc107",
                          annotation_text="ENTRY")

            fig.update_layout(
                title=f"{name}: Ramp-Up → Entry → Post-Trade",
                height=350, width=1100,
                template='plotly_dark',
                paper_bgcolor='#000000',
                plot_bgcolor='#0a0a1a',
                font=dict(color='#e0e0e0', size=10),
                margin=dict(l=60, r=20, t=60, b=40),
                xaxis_title="Bars Relative to Entry (0 = entry candle)",
                yaxis_title=name,
                xaxis=dict(gridcolor='#1a1a3e'),
                yaxis=dict(gridcolor='#1a1a3e'),
            )

            self._render_chart(fig, self._phase_chart_label)
        except Exception as e:
            self._phase_chart_label.setText(f"Error: {e}")

    def _build_quintile_chart(self, col: str, name: str):
        """Build win rate by quintile for continuous indicator."""
        try:
            q_df = self._provider.get_win_rate_by_quintile(self._trade_ids, col)
            if q_df.empty:
                self._winrate_chart_label.setText("No quintile data")
                return

            labels = [f"Q{q}\n{lo:.3f}-{hi:.3f}"
                      for q, lo, hi in zip(q_df['quintile'], q_df['range_min'], q_df['range_max'])]
            colors = ['#26a69a' if wr >= 50 else '#ef5350' for wr in q_df['win_rate']]

            fig = go.Figure(go.Bar(
                x=labels, y=q_df['win_rate'],
                text=[f"{wr:.0f}%\nn={n}" for wr, n in zip(q_df['win_rate'], q_df['trades'])],
                textposition='outside',
                marker_color=colors,
            ))
            fig.add_hline(y=50, line_dash="dot", line_color="#555")
            fig.update_layout(
                title=f"{name}: Win Rate by Quintile at Entry",
                height=300, width=1100,
                template='plotly_dark',
                paper_bgcolor='#000000',
                plot_bgcolor='#0a0a1a',
                font=dict(color='#e0e0e0', size=10),
                margin=dict(l=40, r=20, t=50, b=40),
                yaxis_title="Win Rate %",
                xaxis=dict(gridcolor='#1a1a3e'),
                yaxis=dict(gridcolor='#1a1a3e'),
            )
            self._render_chart(fig, self._winrate_chart_label)
        except Exception as e:
            self._winrate_chart_label.setText(f"Error: {e}")

    def _build_state_chart(self, col: str, name: str):
        """Build win rate by state for categorical indicator."""
        try:
            wr_df = self._provider.get_win_rate_by_state(self._trade_ids, col)
            if wr_df.empty:
                self._winrate_chart_label.setText("No state data")
                return

            colors = ['#26a69a' if wr >= 50 else '#ef5350' for wr in wr_df['win_rate']]

            fig = go.Figure(go.Bar(
                x=wr_df['state'], y=wr_df['win_rate'],
                text=[f"{wr:.0f}%\nn={n}\nR={r:.2f}"
                      for wr, n, r in zip(wr_df['win_rate'], wr_df['trades'], wr_df['avg_r'])],
                textposition='outside',
                marker_color=colors,
            ))
            fig.add_hline(y=50, line_dash="dot", line_color="#555")
            fig.update_layout(
                title=f"{name}: Win Rate by State at Entry",
                height=300, width=1100,
                template='plotly_dark',
                paper_bgcolor='#000000',
                plot_bgcolor='#0a0a1a',
                font=dict(color='#e0e0e0', size=10),
                margin=dict(l=40, r=20, t=50, b=40),
                yaxis_title="Win Rate %",
                xaxis=dict(gridcolor='#1a1a3e'),
                yaxis=dict(gridcolor='#1a1a3e'),
            )
            self._render_chart(fig, self._winrate_chart_label)
        except Exception as e:
            self._winrate_chart_label.setText(f"Error: {e}")

    def _build_model_breakdown(self, col: str, name: str):
        """Build model x direction breakdown table."""
        if self._entry_data.empty:
            self._breakdown_label.setText("")
            return

        lines = [f"Model × Direction Breakdown: {name}"]
        lines.append("─" * 70)

        for model in ['EPCH1', 'EPCH2', 'EPCH3', 'EPCH4']:
            for direction in ['LONG', 'SHORT']:
                subset = self._entry_data[
                    (self._entry_data['model'] == model) &
                    (self._entry_data['direction'] == direction)
                ]
                if len(subset) < 5:
                    continue

                total = len(subset)
                wins = subset['is_winner'].sum()
                wr = wins / total * 100
                avg_val = subset[col].mean() if col in subset.columns else 0

                lines.append(
                    f"  {model} {direction:<6}  n={total:>4}  "
                    f"WR={wr:>5.1f}%  "
                    f"Avg {name}: {avg_val:.4f}"
                )

        self._breakdown_label.setText("\n".join(lines))

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
