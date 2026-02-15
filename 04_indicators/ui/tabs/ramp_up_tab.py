"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR ANALYSIS v2.0
Tab 1: Ramp-Up Analysis - 25-bar pre-entry indicator progression
XIII Trading LLC
================================================================================

Shows how indicators evolve in the 25 minutes before entry,
comparing winners vs losers with line charts and summary statistics.
"""
import tempfile
from pathlib import Path
from typing import List, Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
)
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtCore import Qt

from ui.styles import COLORS
from data.provider import DataProvider
from config import RAMP_UP_BARS


class RampUpTab(QWidget):
    """Ramp-Up Analysis: 25-bar pre-entry indicator progression."""

    def __init__(self, provider: DataProvider, parent=None):
        super().__init__(parent)
        self._provider = provider
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("Ramp-Up Analysis: Indicator Progression Before Entry")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(title)

        subtitle = QLabel(
            f"Average indicator values across {RAMP_UP_BARS} M1 bars before entry. "
            "Green = Winners, Red = Losers. Shaded area = ramp-up zone (last 10 bars). "
            "Vol Delta & CVD Slope are direction-normalized (+positive = favorable for trade direction)."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(subtitle)

        # Chart container
        self._chart_label = QLabel("Loading ramp-up data...")
        self._chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chart_label.setMinimumHeight(600)
        self._chart_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(self._chart_label)

        # Summary stats
        self._summary_label = QLabel("")
        self._summary_label.setWordWrap(True)
        self._summary_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px; "
            f"background-color: {COLORS['bg_secondary']}; padding: 12px; "
            f"border: 1px solid {COLORS['border']};"
        )
        layout.addWidget(self._summary_label)

        layout.addStretch()

    def refresh(self, ramp_up_avgs: pd.DataFrame, trade_ids: List[str]):
        """Refresh the tab with new data."""
        if ramp_up_avgs is None or ramp_up_avgs.empty:
            self._chart_label.setText("No ramp-up data available")
            self._summary_label.setText("")
            return

        # Build chart
        fig = self._build_ramp_up_chart(ramp_up_avgs)
        self._render_chart(fig)

        # Build summary
        self._build_summary(ramp_up_avgs, len(trade_ids))

    def _build_ramp_up_chart(self, df: pd.DataFrame) -> go.Figure:
        """Build multi-panel ramp-up line charts."""
        indicators = [
            ('avg_candle_range', 'Candle Range %'),
            ('avg_vol_delta', 'Vol Delta (normalized: +favorable)'),
            ('avg_vol_roc', 'Vol ROC %'),
            ('avg_sma_spread', 'SMA Spread %'),
            ('avg_cvd_slope', 'CVD Slope (normalized: +favorable)'),
        ]

        fig = make_subplots(
            rows=len(indicators), cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=[name for _, name in indicators],
        )

        for i, (col, name) in enumerate(indicators, 1):
            # Winners
            winners = df[df['is_winner'] == True]
            if not winners.empty:
                fig.add_trace(
                    go.Scatter(
                        x=winners['bar_sequence'],
                        y=winners[col],
                        name=f'{name} (W)' if i == 1 else None,
                        line=dict(color='#26a69a', width=2),
                        showlegend=(i == 1),
                        legendgroup='winners',
                    ),
                    row=i, col=1
                )

            # Losers
            losers = df[df['is_winner'] == False]
            if not losers.empty:
                fig.add_trace(
                    go.Scatter(
                        x=losers['bar_sequence'],
                        y=losers[col],
                        name=f'{name} (L)' if i == 1 else None,
                        line=dict(color='#ef5350', width=2),
                        showlegend=(i == 1),
                        legendgroup='losers',
                    ),
                    row=i, col=1
                )

            # Shade the last 10 bars (ramp-up zone)
            fig.add_vrect(
                x0=15, x1=24,
                fillcolor='rgba(15, 52, 96, 0.15)',
                line_width=0,
                row=i, col=1
            )

        fig.update_layout(
            height=120 * len(indicators) + 80,
            width=1100,
            template='plotly_dark',
            paper_bgcolor='#000000',
            plot_bgcolor='#0a0a1a',
            font=dict(color='#e0e0e0', size=10),
            margin=dict(l=60, r=20, t=40, b=40),
            legend=dict(
                orientation='h', yanchor='bottom', y=1.02,
                xanchor='left', x=0,
                font=dict(size=11),
            ),
        )

        # Update x-axes
        fig.update_xaxes(
            title_text=f"Bar Sequence (0=oldest, {RAMP_UP_BARS - 1}=just before entry)",
            row=len(indicators), col=1,
            gridcolor='#1a1a3e',
        )
        fig.update_xaxes(gridcolor='#1a1a3e')
        fig.update_yaxes(gridcolor='#1a1a3e')

        return fig

    def _build_summary(self, df: pd.DataFrame, trade_count: int):
        """Build summary statistics text for the last 10 bars."""
        # Focus on last 10 bars (15-24) for summary
        last_10 = df[df['bar_sequence'] >= 15]

        if last_10.empty:
            self._summary_label.setText("Insufficient data for summary")
            return

        winners = last_10[last_10['is_winner'] == True]
        losers = last_10[last_10['is_winner'] == False]

        lines = [f"Summary: Last 10 bars before entry ({trade_count:,} trades)"]
        lines.append("─" * 60)

        for col, name in [
            ('avg_candle_range', 'Candle Range %'),
            ('avg_vol_roc', 'Vol ROC'),
            ('avg_sma_spread', 'SMA Spread %'),
            ('avg_cvd_slope', 'CVD Slope'),
        ]:
            w_avg = winners[col].mean() if not winners.empty else 0
            l_avg = losers[col].mean() if not losers.empty else 0
            delta = w_avg - l_avg
            arrow = "+" if delta > 0 else ""
            lines.append(
                f"  {name:<18}  Winner avg: {w_avg:>8.4f}  |  "
                f"Loser avg: {l_avg:>8.4f}  |  Delta: {arrow}{delta:.4f}"
            )

        self._summary_label.setText("\n".join(lines))

    def _render_chart(self, fig: go.Figure):
        """Render Plotly figure to PNG and display in QLabel."""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name
            # Write outside the with-block so the file handle is closed
            fig.write_image(tmp_path, engine='kaleido')
            pixmap = QPixmap(tmp_path)
            if not pixmap.isNull():
                scaled = pixmap.scaledToWidth(
                    max(self._chart_label.width() - 20, 800),
                    Qt.TransformationMode.SmoothTransformation
                )
                self._chart_label.setPixmap(scaled)
            else:
                self._chart_label.setText("Chart rendering failed")
        except Exception as e:
            self._chart_label.setText(f"Chart error: {e}")
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)
