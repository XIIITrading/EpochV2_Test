"""
Tab 2: Entry Quality
- Indicator state at entry correlated with win/loss
- Health score vs win rate (bucket chart)
- Long/Short score effectiveness
- Structure alignment at entry
- SMA config, volume ROC, CVD at entry
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


class EntryQualityTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 20, 20, 20)
        self._layout.setSpacing(16)
        self._build_placeholder()

    def _build_placeholder(self):
        lbl = QLabel("Loading entry quality data...")
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(lbl)

    def refresh(self, df: pd.DataFrame):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if df.empty:
            self._build_placeholder()
            return

        # 1) Health score vs win rate
        if "health_score" in df.columns:
            self._layout.addWidget(self._build_health_chart(df))

        # 2) Directional score effectiveness
        if "long_score" in df.columns and "short_score" in df.columns:
            self._layout.addWidget(self._build_directional_scores(df))

        # 3) Indicator state breakdown table
        self._layout.addWidget(self._build_indicator_breakdown(df))

        # 4) Structure alignment chart
        if "h1_structure" in df.columns:
            self._layout.addWidget(self._build_structure_chart(df))

        self._layout.addStretch()

    # ------------------------------------------------------------------
    # Health score vs win rate
    # ------------------------------------------------------------------
    def _build_health_chart(self, df: pd.DataFrame) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("Health Score vs Win Rate")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        valid = df.dropna(subset=["health_score", "is_winner"])
        if valid.empty:
            layout.addWidget(QLabel("No indicator data available (join may have failed)"))
            return frame

        buckets = valid.groupby("health_score").agg(
            trades=("is_winner", "count"),
            wins=("is_winner", "sum"),
        ).reset_index()
        buckets["win_rate"] = (buckets["wins"] / buckets["trades"] * 100).round(1)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=buckets["health_score"],
            y=buckets["win_rate"],
            marker_color=[
                COLORS["score_high"] if s >= 7 else COLORS["score_mid"] if s >= 4 else COLORS["score_low"]
                for s in buckets["health_score"]
            ],
            text=[f"{wr:.0f}%<br>n={n}" for wr, n in zip(buckets["win_rate"], buckets["trades"])],
            textposition="outside",
            textfont=dict(color="#e8e8e8", size=10),
        ))
        fig.update_layout(**_plotly_layout("", height=380))
        fig.update_layout(
            xaxis_title="Health Score (0-10)",
            yaxis_title="Win Rate %",
            yaxis=dict(range=[0, 100], gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
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
        return frame

    # ------------------------------------------------------------------
    # Directional scores
    # ------------------------------------------------------------------
    def _build_directional_scores(self, df: pd.DataFrame) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("Directional Score vs Win Rate")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        # For longs, use long_score; for shorts, use short_score
        charts_layout = QHBoxLayout()

        for direction, score_col, color in [
            ("LONG", "long_score", WIN_COLOR),
            ("SHORT", "short_score", LOSS_COLOR),
        ]:
            subset = df[df["direction"] == direction].dropna(subset=[score_col, "is_winner"])
            if subset.empty:
                continue
            buckets = subset.groupby(score_col).agg(
                trades=("is_winner", "count"),
                wins=("is_winner", "sum"),
            ).reset_index()
            buckets["win_rate"] = (buckets["wins"] / buckets["trades"] * 100).round(1)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=buckets[score_col],
                y=buckets["win_rate"],
                marker_color=color,
                text=[f"{wr:.0f}%<br>n={n}" for wr, n in zip(buckets["win_rate"], buckets["trades"])],
                textposition="outside",
                textfont=dict(color="#e8e8e8", size=10),
            ))
            fig.update_layout(**_plotly_layout(f"{direction} Score", height=350))
            fig.update_layout(
                xaxis_title=f"{score_col} (0-7)",
                yaxis_title="Win Rate %",
                yaxis=dict(range=[0, 100], gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
                showlegend=False,
            )

            chart_label = QLabel()
            chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = _render_plotly(fig, width=800, height=350)
            chart_label.setPixmap(pixmap.scaledToWidth(
                650, Qt.TransformationMode.SmoothTransformation
            ))
            charts_layout.addWidget(chart_label)

        layout.addLayout(charts_layout)
        return frame

    # ------------------------------------------------------------------
    # Indicator state breakdown
    # ------------------------------------------------------------------
    def _build_indicator_breakdown(self, df: pd.DataFrame) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("Indicator State at Entry vs Win Rate")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        # Analyze categorical indicators
        indicators = [
            ("sma_config", "SMA Config"),
            ("price_position", "Price Position"),
            ("sma_momentum_label", "SMA Momentum"),
        ]

        rows = []
        for col, name in indicators:
            if col not in df.columns:
                continue
            valid = df.dropna(subset=[col, "is_winner"])
            for state, group in valid.groupby(col):
                total = len(group)
                if total < 5:
                    continue
                wins = int(group["is_winner"].sum())
                wr = wins / total * 100
                avg_r = group["pnl_r"].mean() if "pnl_r" in group.columns else 0
                rows.append([name, str(state), total, f"{wr:.1f}%", f"{avg_r:.2f}R"])

        if not rows:
            layout.addWidget(QLabel("No categorical indicator data available"))
            return frame

        headers = ["Indicator", "State", "Trades", "Win Rate", "Avg R"]
        table = QTableWidget(len(rows), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        for i in range(len(headers)):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        for row_idx, row_data in enumerate(rows):
            for col_idx, val in enumerate(row_data):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col_idx == 3:  # win rate
                    wr_val = float(val.replace("%", ""))
                    item.setForeground(QColor(WIN_COLOR if wr_val >= 50 else LOSS_COLOR))
                table.setItem(row_idx, col_idx, item)

        h = table.horizontalHeader().height() + table.rowHeight(0) * max(1, len(rows)) + 4
        table.setFixedHeight(min(h, 500))
        layout.addWidget(table)
        return frame

    # ------------------------------------------------------------------
    # Structure alignment chart
    # ------------------------------------------------------------------
    def _build_structure_chart(self, df: pd.DataFrame) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("Market Structure at Entry vs Win Rate")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        timeframes = [
            ("h4_structure", "H4"),
            ("h1_structure", "H1"),
            ("m15_structure", "M15"),
            ("m5_structure", "M5"),
        ]

        rows = []
        for col, tf_name in timeframes:
            if col not in df.columns:
                continue
            valid = df.dropna(subset=[col, "is_winner"])
            for state, group in valid.groupby(col):
                total = len(group)
                if total < 5:
                    continue
                wins = int(group["is_winner"].sum())
                wr = wins / total * 100
                avg_r = group["pnl_r"].mean() if "pnl_r" in group.columns else 0
                rows.append([tf_name, str(state), total, f"{wr:.1f}%", f"{avg_r:.2f}R"])

        if not rows:
            layout.addWidget(QLabel("No structure data available"))
            return frame

        headers = ["Timeframe", "Structure", "Trades", "Win Rate", "Avg R"]
        table = QTableWidget(len(rows), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        for i in range(len(headers)):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        for row_idx, row_data in enumerate(rows):
            for col_idx, val in enumerate(row_data):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col_idx == 3:
                    wr_val = float(val.replace("%", ""))
                    item.setForeground(QColor(WIN_COLOR if wr_val >= 50 else LOSS_COLOR))
                if col_idx == 1:
                    if val == "BULL":
                        item.setForeground(QColor(WIN_COLOR))
                    elif val == "BEAR":
                        item.setForeground(QColor(LOSS_COLOR))
                table.setItem(row_idx, col_idx, item)

        h = table.horizontalHeader().height() + table.rowHeight(0) * max(1, len(rows)) + 4
        table.setFixedHeight(min(h, 500))
        layout.addWidget(table)
        return frame
