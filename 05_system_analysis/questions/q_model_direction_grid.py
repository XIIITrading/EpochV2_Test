"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 05: SYSTEM ANALYSIS
Question: Model x Direction Effectiveness Grid
XIII Trading LLC
================================================================================

Answers: How does win rate and expectancy differ across EPCH1-4 x Long/Short?
"""
import os
import tempfile

import pandas as pd
import plotly.graph_objects as go
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap

from questions._base import BaseQuestion, get_date_cutoff
from config import TABLE_TRADES, ENTRY_MODELS
from ui.styles import COLORS


class ModelDirectionGrid(BaseQuestion):
    id = "model_direction_grid"
    title = "Model x Direction Effectiveness"
    question = "How does win rate and expectancy differ across entry models (EPCH1-4) and trade direction (Long/Short)?"
    category = "Model Performance"

    def query(self, provider, time_period: str) -> pd.DataFrame:
        cutoff = get_date_cutoff(time_period)
        sql = f"SELECT model, direction, is_winner, pnl_r FROM {TABLE_TRADES} WHERE 1=1"
        params = []
        if cutoff:
            sql += " AND date >= %s"
            params.append(cutoff)
        sql += " ORDER BY date, entry_time"
        return provider.query(sql, params if params else None)

    def render(self, data: pd.DataFrame) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        if data.empty:
            empty = QLabel("No trades found for this time period")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)
            return widget

        grid = self._compute_grid(data)

        layout.addWidget(self._build_heatmap(grid))
        layout.addWidget(self._build_table(grid))
        layout.addWidget(self._build_insight(grid))

        layout.addStretch()
        return widget

    def export(self, data: pd.DataFrame) -> dict:
        if data.empty:
            return {"grid": [], "sample_size": 0}

        grid = self._compute_grid(data)
        rows = grid.to_dict("records")

        best = grid.loc[grid["win_rate"].idxmax()]
        worst = grid.loc[grid["win_rate"].idxmin()]

        return {
            "grid": rows,
            "best": {
                "model": best["model"],
                "direction": best["direction"],
                "win_rate": round(best["win_rate"], 1),
            },
            "worst": {
                "model": worst["model"],
                "direction": worst["direction"],
                "win_rate": round(worst["win_rate"], 1),
            },
            "sample_size": int(data.shape[0]),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _compute_grid(self, df: pd.DataFrame) -> pd.DataFrame:
        grouped = df.groupby(["model", "direction"]).agg(
            trades=("pnl_r", "count"),
            wins=("is_winner", "sum"),
            avg_r=("pnl_r", "mean"),
            total_r=("pnl_r", "sum"),
            gross_win=("pnl_r", lambda x: x[x > 0].sum()),
            gross_loss=("pnl_r", lambda x: abs(x[x < 0].sum())),
        ).reset_index()

        grouped["win_rate"] = (grouped["wins"] / grouped["trades"] * 100).round(1)
        grouped["profit_factor"] = grouped.apply(
            lambda r: round(r["gross_win"] / r["gross_loss"], 2) if r["gross_loss"] > 0 else float("inf"),
            axis=1,
        )
        grouped["avg_r"] = grouped["avg_r"].round(2)
        grouped["total_r"] = grouped["total_r"].round(1)

        return grouped

    def _build_heatmap(self, grid: pd.DataFrame) -> QLabel:
        models = list(ENTRY_MODELS.keys())
        directions = ["LONG", "SHORT"]

        z = []
        text = []
        for d in directions:
            row_z = []
            row_t = []
            for m in models:
                match = grid[(grid["model"] == m) & (grid["direction"] == d)]
                if not match.empty:
                    wr = match.iloc[0]["win_rate"]
                    trades = int(match.iloc[0]["trades"])
                    avg_r = match.iloc[0]["avg_r"]
                    row_z.append(wr)
                    row_t.append(f"{wr:.1f}%<br>{trades} trades<br>Avg R: {avg_r:.2f}")
                else:
                    row_z.append(None)
                    row_t.append("No data")
            z.append(row_z)
            text.append(row_t)

        fig = go.Figure(data=go.Heatmap(
            z=z,
            x=models,
            y=directions,
            text=text,
            texttemplate="%{text}",
            textfont=dict(size=13, color="white"),
            colorscale=[
                [0, COLORS["negative"]],
                [0.5, "#333333"],
                [1, COLORS["positive"]],
            ],
            zmin=30,
            zmax=70,
            showscale=True,
            colorbar=dict(
                title=dict(text="Win %", font=dict(color="#a0a0a0")),
                tickfont=dict(color="#a0a0a0"),
            ),
        ))

        fig.update_layout(
            title=dict(text="Win Rate by Model x Direction", font=dict(size=14, color="#e8e8e8")),
            paper_bgcolor="#0a0a0a",
            plot_bgcolor="#0a0a0a",
            font=dict(color="#a0a0a0", size=12),
            margin=dict(l=80, r=30, t=50, b=50),
            height=280,
            xaxis=dict(title="Entry Model", side="top"),
            yaxis=dict(title="Direction", autorange="reversed"),
        )

        return self._render_plotly(fig, width=900, height=280)

    def _build_table(self, grid: pd.DataFrame) -> QTableWidget:
        cols = ["Model", "Direction", "Trades", "Win %", "Avg R", "Total R", "Profit Factor"]
        table = QTableWidget(len(grid), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setMaximumHeight(40 + len(grid) * 30)

        for row_idx, (_, r) in enumerate(grid.iterrows()):
            values = [
                r["model"], r["direction"], str(int(r["trades"])),
                f"{r['win_rate']:.1f}%", f"{r['avg_r']:.2f}",
                f"{r['total_r']:.1f}", f"{r['profit_factor']:.2f}",
            ]
            for col_idx, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                if col_idx == 3:  # Win %
                    wr = r["win_rate"]
                    item.setForeground(
                        Qt.GlobalColor.green if wr >= 55 else
                        Qt.GlobalColor.red if wr < 45 else
                        Qt.GlobalColor.white
                    )
                elif col_idx == 4:  # Avg R
                    item.setForeground(
                        Qt.GlobalColor.green if r["avg_r"] > 0 else Qt.GlobalColor.red
                    )

                table.setItem(row_idx, col_idx, item)

        return table

    def _build_insight(self, grid: pd.DataFrame) -> QLabel:
        if grid.empty:
            return QLabel("")

        best = grid.loc[grid["win_rate"].idxmax()]
        worst = grid.loc[grid["win_rate"].idxmin()]

        text = (
            f"Strongest: {best['model']} {best['direction']} — "
            f"{best['win_rate']:.1f}% win rate, {best['avg_r']:.2f} avg R, "
            f"{int(best['trades'])} trades\n"
            f"Weakest:   {worst['model']} {worst['direction']} — "
            f"{worst['win_rate']:.1f}% win rate, {worst['avg_r']:.2f} avg R, "
            f"{int(worst['trades'])} trades"
        )

        label = QLabel(text)
        label.setFont(QFont("Consolas", 11))
        label.setStyleSheet(
            f"color: {COLORS['text_primary']}; background-color: {COLORS['bg_table']}; "
            f"padding: 12px; border-radius: 4px;"
        )
        return label

    # ------------------------------------------------------------------
    # Plotly rendering
    # ------------------------------------------------------------------
    @staticmethod
    def _render_plotly(fig, width=1600, height=500) -> QLabel:
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            fig.write_image(path, format="png", width=width, height=height, scale=2)
            pixmap = QPixmap(path)
            label = QLabel()
            label.setPixmap(pixmap.scaledToWidth(
                min(width, 1200),
                Qt.TransformationMode.SmoothTransformation,
            ))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return label
        finally:
            os.unlink(path)
