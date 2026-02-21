"""
Tab 1: System Performance
- Overall metrics (win rate, avg R, expectancy, profit factor)
- Breakdown by model, direction, zone type
- Equity curve (cumulative R over time)
- R-distribution histogram
- Monthly performance table
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QPixmap
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import tempfile, os

from ui.styles import COLORS

# Chart colors
WIN_COLOR = COLORS["positive"]
LOSS_COLOR = COLORS["negative"]
NEUTRAL_COLOR = COLORS["text_secondary"]
BG_COLOR = "#0a0a0a"
GRID_COLOR = "#1a1a2e"


def _render_plotly(fig, width=1600, height=500) -> QPixmap:
    """Render a Plotly figure to QPixmap via temp PNG."""
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        fig.write_image(path, format="png", width=width, height=height, scale=2)
        return QPixmap(path)
    finally:
        os.unlink(path)


def _plotly_layout(title: str, height: int = 500) -> dict:
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


class PerformanceTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 20, 20, 20)
        self._layout.setSpacing(16)
        self._build_placeholder()

    def _build_placeholder(self):
        lbl = QLabel("Loading performance data...")
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(lbl)

    # ------------------------------------------------------------------
    # Public refresh
    # ------------------------------------------------------------------
    def refresh(self, trades: pd.DataFrame):
        """Rebuild the entire tab with fresh data."""
        # Clear existing widgets
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if trades.empty:
            self._build_placeholder()
            return

        # 1) Summary metrics cards
        self._layout.addWidget(self._build_summary_cards(trades))

        # 2) Breakdown by model
        self._layout.addWidget(self._build_breakdown_table(
            trades, "model", "Performance by Entry Model"
        ))

        # 3) Breakdown by direction
        self._layout.addWidget(self._build_breakdown_table(
            trades, "direction", "Performance by Direction"
        ))

        # 4) Equity curve
        self._layout.addWidget(self._build_equity_curve(trades))

        # 5) R-distribution histogram
        self._layout.addWidget(self._build_r_distribution(trades))

        # 6) Monthly performance table
        self._layout.addWidget(self._build_monthly_table(trades))

        self._layout.addStretch()

    # ------------------------------------------------------------------
    # Summary cards
    # ------------------------------------------------------------------
    def _build_summary_cards(self, df: pd.DataFrame) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        total = len(df)
        wins = int(df["is_winner"].sum()) if "is_winner" in df.columns else 0
        losses = total - wins
        win_rate = (wins / total * 100) if total > 0 else 0
        avg_r = df["pnl_r"].mean() if "pnl_r" in df.columns else 0
        total_r = df["pnl_r"].sum() if "pnl_r" in df.columns else 0

        # Expectancy = avg_r (it's already in R-multiples)
        expectancy = avg_r

        # Profit factor = gross wins / abs(gross losses)
        if "pnl_r" in df.columns:
            gross_win = df.loc[df["pnl_r"] > 0, "pnl_r"].sum()
            gross_loss = abs(df.loc[df["pnl_r"] < 0, "pnl_r"].sum())
            profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
        else:
            profit_factor = 0

        cards = [
            ("Total Trades", f"{total:,}", COLORS["text_primary"]),
            ("Win Rate", f"{win_rate:.1f}%", WIN_COLOR if win_rate >= 50 else LOSS_COLOR),
            ("Avg R", f"{avg_r:.2f}R", WIN_COLOR if avg_r > 0 else LOSS_COLOR),
            ("Total R", f"{total_r:.1f}R", WIN_COLOR if total_r > 0 else LOSS_COLOR),
            ("Expectancy", f"{expectancy:.3f}R", WIN_COLOR if expectancy > 0 else LOSS_COLOR),
            ("Profit Factor", f"{profit_factor:.2f}" if profit_factor != float("inf") else "N/A",
             WIN_COLOR if profit_factor > 1 else LOSS_COLOR),
            ("W / L", f"{wins} / {losses}", COLORS["text_primary"]),
        ]

        for label, value, color in cards:
            card = self._metric_card(label, value, color)
            layout.addWidget(card)

        return frame

    def _metric_card(self, label: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"background-color: #0d0d0d; border: 1px solid {COLORS['border']}; "
            f"border-radius: 4px; padding: 8px;"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(4)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px; border: none;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl)

        val = QLabel(value)
        val.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: bold; border: none;")
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(val)

        return card

    # ------------------------------------------------------------------
    # Breakdown table
    # ------------------------------------------------------------------
    def _build_breakdown_table(self, df: pd.DataFrame, group_col: str, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel(title)
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        groups = df.groupby(group_col)
        headers = ["Group", "Trades", "Win Rate", "Avg R", "Total R", "Profit Factor", "Best R", "Worst R"]
        table = QTableWidget(len(groups), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        for i in range(len(headers)):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        for row, (name, group) in enumerate(groups):
            total = len(group)
            wins = int(group["is_winner"].sum())
            wr = wins / total * 100 if total > 0 else 0
            avg_r = group["pnl_r"].mean()
            total_r = group["pnl_r"].sum()
            gw = group.loc[group["pnl_r"] > 0, "pnl_r"].sum()
            gl = abs(group.loc[group["pnl_r"] < 0, "pnl_r"].sum())
            pf = gw / gl if gl > 0 else float("inf")
            best = group["pnl_r"].max()
            worst = group["pnl_r"].min()

            values = [
                str(name), str(total), f"{wr:.1f}%", f"{avg_r:.2f}R",
                f"{total_r:.1f}R", f"{pf:.2f}" if pf != float("inf") else "N/A",
                f"{best:.0f}R", f"{worst:.0f}R"
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 2:  # win rate
                    item.setForeground(QColor(WIN_COLOR if wr >= 50 else LOSS_COLOR))
                if col == 3:  # avg r
                    item.setForeground(QColor(WIN_COLOR if avg_r > 0 else LOSS_COLOR))
                table.setItem(row, col, item)

        h = table.horizontalHeader().height() + table.rowHeight(0) * len(groups) + 4
        table.setFixedHeight(h)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(table)
        return frame

    # ------------------------------------------------------------------
    # Equity curve
    # ------------------------------------------------------------------
    def _build_equity_curve(self, df: pd.DataFrame) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("Equity Curve (Cumulative R)")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        sorted_df = df.sort_values(["date", "entry_time"]).reset_index(drop=True)
        sorted_df["cum_r"] = sorted_df["pnl_r"].cumsum()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(range(len(sorted_df))),
            y=sorted_df["cum_r"],
            mode="lines",
            line=dict(color=WIN_COLOR, width=2),
            fill="tozeroy",
            fillcolor="rgba(38, 166, 154, 0.1)",
        ))
        fig.update_layout(**_plotly_layout("", height=400))
        fig.update_layout(
            xaxis_title="Trade #",
            yaxis_title="Cumulative R",
            showlegend=False,
        )

        chart_label = QLabel()
        chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = _render_plotly(fig, width=1600, height=400)
        chart_label.setPixmap(pixmap.scaledToWidth(
            min(1400, self.width() - 60) if self.width() > 100 else 1400,
            Qt.TransformationMode.SmoothTransformation
        ))
        layout.addWidget(chart_label)
        return frame

    # ------------------------------------------------------------------
    # R distribution
    # ------------------------------------------------------------------
    def _build_r_distribution(self, df: pd.DataFrame) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("R-Multiple Distribution")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        r_values = df["pnl_r"].dropna()
        # Bin: -1, 1, 2, 3, 4, 5
        bins = [-1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        labels = ["-1R", "0R", "1R", "2R", "3R", "4R", "5R"]
        counts = pd.cut(r_values, bins=bins, labels=labels).value_counts().reindex(labels, fill_value=0)

        colors = [LOSS_COLOR if l == "-1R" else WIN_COLOR for l in labels]

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
            xaxis_title="R-Multiple",
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
    # Monthly table
    # ------------------------------------------------------------------
    def _build_monthly_table(self, df: pd.DataFrame) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("Monthly Performance")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        df = df.copy()
        df["month"] = pd.to_datetime(df["date"]).dt.to_period("M").astype(str)
        monthly = df.groupby("month").agg(
            trades=("trade_id", "count"),
            wins=("is_winner", "sum"),
            total_r=("pnl_r", "sum"),
            avg_r=("pnl_r", "mean"),
        ).reset_index()
        monthly["win_rate"] = (monthly["wins"] / monthly["trades"] * 100).round(1)

        headers = ["Month", "Trades", "Wins", "Win Rate", "Avg R", "Total R"]
        table = QTableWidget(len(monthly), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        for i in range(len(headers)):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        for row_idx, row in monthly.iterrows():
            values = [
                row["month"], str(int(row["trades"])), str(int(row["wins"])),
                f"{row['win_rate']:.1f}%", f"{row['avg_r']:.2f}R", f"{row['total_r']:.1f}R"
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 3:  # win rate
                    item.setForeground(QColor(WIN_COLOR if row["win_rate"] >= 50 else LOSS_COLOR))
                if col == 5:  # total r
                    item.setForeground(QColor(WIN_COLOR if row["total_r"] > 0 else LOSS_COLOR))
                table.setItem(row_idx, col, item)

        h = table.horizontalHeader().height() + table.rowHeight(0) * max(1, len(monthly)) + 4
        table.setFixedHeight(min(h, 400))
        layout.addWidget(table)
        return frame
