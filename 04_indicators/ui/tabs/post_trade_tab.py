"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR ANALYSIS v2.0
Tab 3: Post-Trade Analysis - Indicator behavior after entry
XIII Trading LLC
================================================================================

Shows how indicators behave in the 25 minutes after entry,
comparing winners vs losers. Identifies early divergence signals.
"""
import tempfile
from pathlib import Path
from typing import List

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtCore import Qt

from ui.styles import COLORS
from data.provider import DataProvider
from config import POST_TRADE_BARS


class PostTradeTab(QWidget):
    """Post-Trade Analysis: Indicator behavior after entry."""

    def __init__(self, provider: DataProvider, parent=None):
        super().__init__(parent)
        self._provider = provider
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("Post-Trade Analysis: What Happens After Entry")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(title)

        subtitle = QLabel(
            f"Average indicator values across {POST_TRADE_BARS} M1 bars after entry. "
            "Bar 0 = entry candle. Vol Delta & CVD Slope are direction-normalized "
            "(+positive = favorable). Key question: Do indicators diverge early?"
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(subtitle)

        # Chart
        self._chart_label = QLabel("Loading post-trade data...")
        self._chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chart_label.setMinimumHeight(600)
        self._chart_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(self._chart_label)

        # Summary
        self._summary_label = QLabel("")
        self._summary_label.setWordWrap(True)
        self._summary_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px; "
            f"background-color: {COLORS['bg_secondary']}; padding: 12px; "
            f"border: 1px solid {COLORS['border']};"
        )
        layout.addWidget(self._summary_label)

        layout.addStretch()

    def refresh(self, post_trade_avgs: pd.DataFrame, trade_ids: List[str]):
        """Refresh the tab with new data."""
        if post_trade_avgs is None or post_trade_avgs.empty:
            self._chart_label.setText("No post-trade data available")
            self._summary_label.setText("")
            return

        fig = self._build_post_trade_chart(post_trade_avgs)
        self._render_chart(fig)
        self._build_divergence_summary(post_trade_avgs, len(trade_ids))

    def _build_post_trade_chart(self, df: pd.DataFrame) -> go.Figure:
        """Build multi-panel post-trade line charts."""
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
            winners = df[df['is_winner'] == True]
            if not winners.empty:
                fig.add_trace(
                    go.Scatter(
                        x=winners['bar_sequence'],
                        y=winners[col],
                        name='Winners' if i == 1 else None,
                        line=dict(color='#26a69a', width=2),
                        showlegend=(i == 1),
                        legendgroup='winners',
                    ),
                    row=i, col=1
                )

            losers = df[df['is_winner'] == False]
            if not losers.empty:
                fig.add_trace(
                    go.Scatter(
                        x=losers['bar_sequence'],
                        y=losers[col],
                        name='Losers' if i == 1 else None,
                        line=dict(color='#ef5350', width=2),
                        showlegend=(i == 1),
                        legendgroup='losers',
                    ),
                    row=i, col=1
                )

            # Entry marker
            fig.add_vline(x=0, line_dash="dash", line_color="#ffc107",
                          annotation_text="Entry", row=i, col=1)

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
            ),
        )

        fig.update_xaxes(
            title_text=f"Bar Sequence (0=entry candle, {POST_TRADE_BARS - 1}=last bar)",
            row=len(indicators), col=1,
            gridcolor='#1a1a3e',
        )
        fig.update_xaxes(gridcolor='#1a1a3e')
        fig.update_yaxes(gridcolor='#1a1a3e')

        return fig

    def _build_divergence_summary(self, df: pd.DataFrame, trade_count: int):
        """Analyze early divergence between winners and losers."""
        lines = [f"Early Divergence Analysis ({trade_count:,} trades)"]
        lines.append("─" * 60)
        lines.append("  First 5 bars after entry - winner vs loser averages:")
        lines.append("")

        first_5 = df[df['bar_sequence'] <= 5]
        if first_5.empty:
            self._summary_label.setText("Insufficient data for divergence analysis")
            return

        for col, name in [
            ('avg_candle_range', 'Candle Range'),
            ('avg_vol_roc', 'Vol ROC'),
            ('avg_cvd_slope', 'CVD Slope'),
        ]:
            w_bars = first_5[first_5['is_winner'] == True]
            l_bars = first_5[first_5['is_winner'] == False]

            w_avg = w_bars[col].mean() if not w_bars.empty else 0
            l_avg = l_bars[col].mean() if not l_bars.empty else 0
            delta = w_avg - l_avg

            direction = "higher" if delta > 0 else "lower"
            lines.append(
                f"  {name:<16} Winners: {w_avg:>8.4f}  Losers: {l_avg:>8.4f}  "
                f"(Winners {abs(delta):.4f} {direction})"
            )

        self._summary_label.setText("\n".join(lines))

    def _render_chart(self, fig: go.Figure):
        """Render Plotly figure to PNG and display in QLabel."""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name
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
