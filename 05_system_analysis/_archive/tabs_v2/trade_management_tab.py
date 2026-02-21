"""
Tab 3: Trade Management
- Time to R1 distribution
- Max R reached distribution
- R-level progression (% reaching 1R, 2R, 3R, 4R, 5R)
- Stop distance analysis (M1 vs M5 ATR)
- MFE/MAE implied from ATR stop data
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPixmap
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import tempfile, os

from ui.styles import COLORS

WIN_COLOR = COLORS["positive"]
LOSS_COLOR = COLORS["negative"]
BG_COLOR = "#0a0a0a"
GRID_COLOR = "#1a1a2e"
ACCENT = "#2196F3"


def _render_plotly(fig, width=1600, height=500) -> QPixmap:
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        fig.write_image(path, format="png", width=width, height=height, scale=2)
        return QPixmap(path)
    finally:
        os.unlink(path)


def _plotly_layout(title: str, height: int = 400) -> dict:
    return dict(
        title=dict(text=title, font=dict(size=14, color="#e8e8e8")),
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=BG_COLOR,
        font=dict(color="#a0a0a0", size=11),
        margin=dict(l=60, r=30, t=50, b=50),
        height=height,
        xaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
        yaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
    )


class TradeManagementTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 20, 20, 20)
        self._layout.setSpacing(16)
        self._build_placeholder()

    def _build_placeholder(self):
        lbl = QLabel("Loading trade management data...")
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(lbl)

    def refresh(self, trades: pd.DataFrame, m5_stops: pd.DataFrame, m1_stops: pd.DataFrame):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if m5_stops.empty:
            self._build_placeholder()
            return

        # 1) R-level progression
        self._layout.addWidget(self._build_r_progression(m5_stops))

        # 2) Time to R1 distribution
        self._layout.addWidget(self._build_time_to_r1(trades))

        # 3) Max R reached distribution
        self._layout.addWidget(self._build_max_r_chart(m5_stops))

        # 4) Stop distance comparison (M1 vs M5)
        if not m1_stops.empty:
            self._layout.addWidget(self._build_stop_comparison(m1_stops, m5_stops))

        # 5) Stop distance stats
        self._layout.addWidget(self._build_stop_stats(m5_stops))

        self._layout.addStretch()

    # ------------------------------------------------------------------
    # R-level progression
    # ------------------------------------------------------------------
    def _build_r_progression(self, df: pd.DataFrame) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("R-Level Progression (% of trades reaching each level)")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        total = len(df)
        r_levels = []
        for r in range(1, 6):
            col = f"r{r}_hit"
            if col in df.columns:
                hits = int(df[col].sum())
                pct = hits / total * 100 if total > 0 else 0
                r_levels.append((f"R{r}", hits, pct))

        if not r_levels:
            layout.addWidget(QLabel("No R-level data"))
            return frame

        labels = [r[0] for r in r_levels]
        pcts = [r[2] for r in r_levels]
        counts = [r[1] for r in r_levels]

        # Gradient from bright to dim
        bar_colors = [
            WIN_COLOR, "#1E9688", "#17796E", "#105C54", "#093F3A"
        ]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels,
            y=pcts,
            marker_color=bar_colors[:len(labels)],
            text=[f"{p:.1f}%\n({c})" for p, c in zip(pcts, counts)],
            textposition="outside",
            textfont=dict(color="#e8e8e8", size=11),
        ))
        fig.update_layout(**_plotly_layout("", height=380))
        fig.update_layout(
            xaxis_title="R-Level Target",
            yaxis_title="% of Trades Reaching",
            yaxis=dict(range=[0, max(pcts) * 1.2 if pcts else 100], gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
            showlegend=False,
        )

        chart_label = QLabel()
        chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = _render_plotly(fig, width=1600, height=380)
        chart_label.setPixmap(pixmap.scaledToWidth(
            min(1400, self.width() - 60) if self.width() > 100 else 1400,
            Qt.TransformationMode.SmoothTransformation
        ))
        layout.addWidget(chart_label)

        # Also show as summary table
        headers = ["R-Level", "Trades Reaching", "% of Total", "Dropoff from Previous"]
        table = QTableWidget(len(r_levels), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        for i in range(len(headers)):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        for row_idx, (name, count, pct) in enumerate(r_levels):
            prev_pct = r_levels[row_idx - 1][2] if row_idx > 0 else 100
            dropoff = prev_pct - pct
            values = [name, str(count), f"{pct:.1f}%", f"-{dropoff:.1f}pp" if row_idx > 0 else "-"]
            for col_idx, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_idx, col_idx, item)

        h = table.horizontalHeader().height() + table.rowHeight(0) * len(r_levels) + 4
        table.setFixedHeight(h)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(table)
        return frame

    # ------------------------------------------------------------------
    # Time to R1
    # ------------------------------------------------------------------
    def _build_time_to_r1(self, trades: pd.DataFrame) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("Time to R1 (minutes) - Winners Only")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        if "minutes_to_r1" not in trades.columns:
            layout.addWidget(QLabel("No time-to-R1 data available"))
            return frame

        winners = trades[trades["is_winner"] == True]
        times = winners["minutes_to_r1"].dropna()
        times = times[times > 0]

        if times.empty:
            layout.addWidget(QLabel("No winning trades with timing data"))
            return frame

        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=times,
            nbinsx=30,
            marker_color=WIN_COLOR,
            opacity=0.8,
        ))
        # Add median line
        median = times.median()
        fig.add_vline(x=median, line_dash="dash", line_color="#FFD600",
                      annotation_text=f"Median: {median:.0f}min",
                      annotation_font_color="#FFD600")

        fig.update_layout(**_plotly_layout("", height=350))
        fig.update_layout(
            xaxis_title="Minutes from Entry to R1",
            yaxis_title="Trade Count",
            showlegend=False,
        )

        chart_label = QLabel()
        chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = _render_plotly(fig, width=1600, height=350)
        chart_label.setPixmap(pixmap.scaledToWidth(
            min(1400, self.width() - 60) if self.width() > 100 else 1400,
            Qt.TransformationMode.SmoothTransformation
        ))
        layout.addWidget(chart_label)

        # Stats summary
        stats_text = (
            f"Median: {median:.0f} min  |  "
            f"Mean: {times.mean():.0f} min  |  "
            f"P25: {times.quantile(0.25):.0f} min  |  "
            f"P75: {times.quantile(0.75):.0f} min  |  "
            f"Max: {times.max():.0f} min"
        )
        stats_lbl = QLabel(stats_text)
        stats_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        stats_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(stats_lbl)
        return frame

    # ------------------------------------------------------------------
    # Max R reached
    # ------------------------------------------------------------------
    def _build_max_r_chart(self, df: pd.DataFrame) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("Max R Reached per Trade")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        if "max_r" not in df.columns:
            layout.addWidget(QLabel("No max_r data available"))
            return frame

        counts = df["max_r"].value_counts().sort_index()
        labels = [f"{int(r)}R" if r >= 0 else f"{int(r)}R (Loss)" for r in counts.index]
        colors = [LOSS_COLOR if r < 0 else WIN_COLOR for r in counts.index]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels,
            y=counts.values,
            marker_color=colors,
            text=[str(int(v)) for v in counts.values],
            textposition="outside",
            textfont=dict(color="#e8e8e8"),
        ))
        fig.update_layout(**_plotly_layout("", height=350))
        fig.update_layout(
            xaxis_title="Max R Achieved",
            yaxis_title="Trade Count",
            showlegend=False,
        )

        chart_label = QLabel()
        chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = _render_plotly(fig, width=1600, height=350)
        chart_label.setPixmap(pixmap.scaledToWidth(
            min(1400, self.width() - 60) if self.width() > 100 else 1400,
            Qt.TransformationMode.SmoothTransformation
        ))
        layout.addWidget(chart_label)
        return frame

    # ------------------------------------------------------------------
    # Stop comparison M1 vs M5
    # ------------------------------------------------------------------
    def _build_stop_comparison(self, m1: pd.DataFrame, m5: pd.DataFrame) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("M1 vs M5 ATR Stop Comparison")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        def _stats(df, label):
            total = len(df)
            wins = int((df["result"] == "WIN").sum()) if "result" in df.columns else 0
            wr = wins / total * 100 if total > 0 else 0
            avg_stop = df["stop_distance_pct"].mean() if "stop_distance_pct" in df.columns else 0
            return [label, total, f"{wr:.1f}%", f"{avg_stop:.3f}%"]

        rows = [_stats(m1, "M1 ATR"), _stats(m5, "M5 ATR")]
        headers = ["Stop Method", "Trades", "Win Rate", "Avg Stop Distance %"]
        table = QTableWidget(2, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        for i in range(len(headers)):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        for row_idx, row_data in enumerate(rows):
            for col_idx, val in enumerate(row_data):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_idx, col_idx, item)

        h = table.horizontalHeader().height() + table.rowHeight(0) * 2 + 4
        table.setFixedHeight(h)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(table)
        return frame

    # ------------------------------------------------------------------
    # Stop distance stats
    # ------------------------------------------------------------------
    def _build_stop_stats(self, df: pd.DataFrame) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("M5 ATR Stop Distance Distribution")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        if "stop_distance_pct" not in df.columns:
            layout.addWidget(QLabel("No stop distance data"))
            return frame

        stops = df["stop_distance_pct"].dropna()
        if stops.empty:
            return frame

        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=stops,
            nbinsx=40,
            marker_color=ACCENT,
            opacity=0.8,
        ))
        median = stops.median()
        fig.add_vline(x=median, line_dash="dash", line_color="#FFD600",
                      annotation_text=f"Median: {median:.3f}%",
                      annotation_font_color="#FFD600")

        fig.update_layout(**_plotly_layout("", height=350))
        fig.update_layout(
            xaxis_title="Stop Distance (% of entry)",
            yaxis_title="Trade Count",
            showlegend=False,
        )

        chart_label = QLabel()
        chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = _render_plotly(fig, width=1600, height=350)
        chart_label.setPixmap(pixmap.scaledToWidth(
            min(1400, self.width() - 60) if self.width() > 100 else 1400,
            Qt.TransformationMode.SmoothTransformation
        ))
        layout.addWidget(chart_label)
        return frame
