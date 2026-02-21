"""
Tab 4: Edge Monitor (ML Integration)
- Current validated edges with health status
- Pending hypotheses from the ML pipeline
- Baseline metrics and drift alerts
- Reads from 10_machine_learning/state/ JSON files
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from typing import Optional, Dict, List

from ui.styles import COLORS

WIN_COLOR = COLORS["positive"]
LOSS_COLOR = COLORS["negative"]
WARN_COLOR = COLORS["status_paused"]

STATUS_COLORS = {
    "HEALTHY": WIN_COLOR,
    "WEAKENING": WARN_COLOR,
    "DEGRADED": LOSS_COLOR,
    "INCONCLUSIVE": COLORS["text_muted"],
}


class EdgeMonitorTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 20, 20, 20)
        self._layout.setSpacing(16)
        self._build_placeholder()

    def _build_placeholder(self):
        lbl = QLabel("Loading edge monitor data...")
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(lbl)

    def refresh(self, system_state: Optional[Dict],
                hypothesis_tracker: Optional[Dict],
                pending_edges: Optional[List]):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not system_state:
            no_data = QLabel(
                "No ML state data found.\n\n"
                "Run the ML workflow to generate state:\n"
                "  python 10_machine_learning/scripts/run_ml_workflow.py cycle"
            )
            no_data.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
            no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(no_data)
            return

        # 1) Baseline metrics
        self._layout.addWidget(self._build_baseline(system_state))

        # 2) Edge health
        self._layout.addWidget(self._build_edge_health(system_state))

        # 3) Drift alerts
        if system_state.get("drift_alerts"):
            self._layout.addWidget(self._build_drift_alerts(system_state))

        # 4) Pending hypotheses
        if hypothesis_tracker:
            self._layout.addWidget(self._build_hypotheses(hypothesis_tracker))

        # 5) Pending edges for approval
        if pending_edges:
            self._layout.addWidget(self._build_pending_edges(pending_edges))

        self._layout.addStretch()

    # ------------------------------------------------------------------
    # Baseline metrics
    # ------------------------------------------------------------------
    def _build_baseline(self, state: Dict) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("ML Baseline Metrics")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        baseline = state.get("baseline", {})
        cards_layout = QHBoxLayout()

        items = [
            ("Total Trades", f"{baseline.get('total_trades', 0):,}", COLORS["text_primary"]),
            ("Win Rate", f"{baseline.get('win_rate', 0):.1f}%",
             WIN_COLOR if baseline.get("win_rate", 0) >= 50 else LOSS_COLOR),
            ("Avg R", f"{baseline.get('avg_r', 0):.3f}",
             WIN_COLOR if baseline.get("avg_r", 0) > 0 else LOSS_COLOR),
            ("Std R", f"{baseline.get('std_r', 0):.3f}", COLORS["text_secondary"]),
            ("Period", f"{baseline.get('period_start', '?')} to {baseline.get('period_end', '?')}",
             COLORS["text_secondary"]),
        ]

        for label, value, color in items:
            card = QFrame()
            card.setStyleSheet(
                f"background-color: #0d0d0d; border: 1px solid {COLORS['border']}; "
                f"border-radius: 4px; padding: 8px;"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 8, 12, 8)
            card_layout.setSpacing(2)

            name = QLabel(label)
            name.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px; border: none;")
            name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(name)

            val = QLabel(value)
            val.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold; border: none;")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(val)

            cards_layout.addWidget(card)

        layout.addLayout(cards_layout)

        updated = state.get("last_updated", "Unknown")
        ts = QLabel(f"Last updated: {updated}")
        ts.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px;")
        layout.addWidget(ts)

        return frame

    # ------------------------------------------------------------------
    # Edge health
    # ------------------------------------------------------------------
    def _build_edge_health(self, state: Dict) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("Validated Edges - Health Status")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        edges = state.get("edge_health", {})
        if not edges:
            layout.addWidget(QLabel("No validated edges"))
            return frame

        headers = ["Edge Name", "Status", "Current Effect", "Stored Effect", "p-value", "Trades", "Confidence"]
        table = QTableWidget(len(edges), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        for i in range(len(headers)):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        for row_idx, (name, info) in enumerate(edges.items()):
            status = info.get("status", "UNKNOWN")
            current = info.get("current_effect_pp", 0)
            stored = info.get("stored_effect_pp", 0)
            p_val = info.get("p_value", 1.0)
            trades = info.get("group_trades", 0)
            conf = info.get("confidence", "LOW")

            values = [
                name, status, f"{current:+.1f}pp", f"{stored:+.1f}pp",
                f"{p_val:.4f}", str(trades), conf
            ]
            for col_idx, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col_idx == 1:  # status
                    item.setForeground(QColor(STATUS_COLORS.get(status, COLORS["text_primary"])))
                    item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                if col_idx == 2:  # current effect
                    item.setForeground(QColor(WIN_COLOR if current > 0 else LOSS_COLOR))
                if col_idx == 4:  # p-value
                    item.setForeground(QColor(WIN_COLOR if p_val < 0.05 else LOSS_COLOR))
                table.setItem(row_idx, col_idx, item)

        h = table.horizontalHeader().height() + table.rowHeight(0) * len(edges) + 4
        table.setFixedHeight(h)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(table)
        return frame

    # ------------------------------------------------------------------
    # Drift alerts
    # ------------------------------------------------------------------
    def _build_drift_alerts(self, state: Dict) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        frame.setStyleSheet(
            f"QFrame#sectionFrame {{ border-color: {WARN_COLOR}; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("Drift Alerts")
        lbl.setObjectName("sectionLabel")
        lbl.setStyleSheet(f"color: {WARN_COLOR}; font-weight: bold;")
        layout.addWidget(lbl)

        for alert in state.get("drift_alerts", []):
            alert_lbl = QLabel(f"  {alert}")
            alert_lbl.setStyleSheet(f"color: {WARN_COLOR};")
            layout.addWidget(alert_lbl)

        return frame

    # ------------------------------------------------------------------
    # Hypotheses
    # ------------------------------------------------------------------
    def _build_hypotheses(self, tracker: Dict) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("Hypothesis Tracker")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        hypotheses = tracker.get("hypotheses", [])
        if not hypotheses:
            layout.addWidget(QLabel("No hypotheses tracked"))
            return frame

        headers = ["ID", "Name", "Status", "Effect (pp)", "p-value", "Trades"]
        table = QTableWidget(len(hypotheses), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        for i in range(len(headers)):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        for row_idx, h in enumerate(hypotheses):
            h_id = h.get("id", "")
            name = h.get("name", h.get("description", ""))
            status = h.get("status", "UNKNOWN")
            effect = h.get("effect_pp", h.get("effect_size_pp", 0))
            p_val = h.get("p_value", 1.0)
            trades = h.get("group_trades", h.get("n", 0))

            values = [h_id, name, status, f"{effect:+.1f}", f"{p_val:.4f}", str(trades)]
            for col_idx, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col_idx == 2:  # status
                    if status == "VALIDATED":
                        item.setForeground(QColor(WIN_COLOR))
                    elif status == "REJECTED":
                        item.setForeground(QColor(LOSS_COLOR))
                    else:
                        item.setForeground(QColor(WARN_COLOR))
                table.setItem(row_idx, col_idx, item)

        h = table.horizontalHeader().height() + table.rowHeight(0) * min(len(hypotheses), 15) + 4
        table.setFixedHeight(min(h, 500))
        layout.addWidget(table)
        return frame

    # ------------------------------------------------------------------
    # Pending edges
    # ------------------------------------------------------------------
    def _build_pending_edges(self, pending: List) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("Pending Edges (Awaiting Approval)")
        lbl.setObjectName("sectionLabel")
        lbl.setStyleSheet(f"color: {WARN_COLOR};")
        layout.addWidget(lbl)

        for edge in pending:
            if isinstance(edge, dict):
                name = edge.get("name", edge.get("edge_name", str(edge)))
                effect = edge.get("effect_pp", "?")
                edge_lbl = QLabel(f"  {name}  ({effect:+.1f}pp)" if isinstance(effect, (int, float)) else f"  {name}")
            else:
                edge_lbl = QLabel(f"  {edge}")
            edge_lbl.setStyleSheet(f"color: {COLORS['text_primary']};")
            layout.addWidget(edge_lbl)

        hint = QLabel("Run: python 10_machine_learning/scripts/run_ml_workflow.py approve-edge <ID>")
        hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px; padding-top: 8px;")
        layout.addWidget(hint)

        return frame
