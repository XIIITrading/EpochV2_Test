"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 05: SYSTEM ANALYSIS v2.0
Main Window - Question navigator with sidebar + content panel
XIII Trading LLC
================================================================================

Layout:
  Header
  +-- Sidebar (240px) --+-- Content Panel -------------------------+
  | QUESTIONS            |  Question Title                          |
  |                      |  Full question text...                   |
  | Category             |  [ All Time ] [ Year ] [ Month ] [ Week]|
  |   > Question 1       |                                         |
  |   > Question 2       |  (scrollable answer area)               |
  |                      |                                         |
  |                      |             [ Export to Supabase ]       |
  +----------------------+-----------------------------------------+
  Status bar
"""
import uuid
from datetime import datetime
from typing import Optional

import pandas as pd
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QPushButton, QSplitter, QSizePolicy,
    QProgressDialog, QApplication,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from ui.styles import COLORS, DARK_STYLESHEET
from data.provider import DataProvider
from questions import get_all_questions
from questions._base import BaseQuestion, TIME_PERIODS


# =============================================================================
# Background question loader
# =============================================================================
class QuestionLoadThread(QThread):
    """Runs question.query() on a background thread."""
    finished = pyqtSignal(object)  # pd.DataFrame
    error = pyqtSignal(str)

    def __init__(self, question: BaseQuestion, provider: DataProvider, time_period: str):
        super().__init__()
        self._question = question
        self._provider = provider
        self._time_period = time_period

    def run(self):
        try:
            data = self._question.query(self._provider, self._time_period)
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# Main Window
# =============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EPOCH System Analysis v2.0 - XIII Trading LLC")
        self.setMinimumSize(1400, 900)
        self.setStyleSheet(DARK_STYLESHEET)

        self._provider = DataProvider()
        self._questions = get_all_questions()
        self._load_thread: Optional[QuestionLoadThread] = None

        # State
        self._current_question: Optional[BaseQuestion] = None
        self._current_data: Optional[pd.DataFrame] = None
        self._current_time_period: str = "all_time"
        self._question_buttons: dict[str, QPushButton] = {}
        self._period_buttons: dict[str, QPushButton] = {}

        self._setup_ui()
        self._connect_db()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._create_header())

        body = QSplitter(Qt.Orientation.Horizontal)
        body.addWidget(self._create_sidebar())
        body.addWidget(self._create_content_panel())
        body.setSizes([240, 1160])
        main_layout.addWidget(body, stretch=1)

        main_layout.addWidget(self._create_status_bar())

    def _create_header(self) -> QFrame:
        header = QFrame()
        header.setStyleSheet(
            f"background-color: {COLORS['bg_header']}; padding: 10px;"
        )
        header.setFixedHeight(55)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 0, 20, 0)

        title = QLabel("EPOCH SYSTEM ANALYSIS")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(title)

        layout.addStretch()

        ver = QLabel("v2.0")
        ver.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(ver)

        return header

    # ------------------------------------------------------------------
    # Left sidebar
    # ------------------------------------------------------------------
    def _create_sidebar(self) -> QFrame:
        panel = QFrame()
        panel.setFixedWidth(240)
        panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        panel.setStyleSheet(f"background-color: {COLORS['bg_primary']}; border-right: 1px solid {COLORS['border']};")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(4)

        # Header
        header = QLabel("QUESTIONS")
        header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {COLORS['text_muted']}; letter-spacing: 2px;")
        layout.addWidget(header)
        layout.addSpacing(8)

        if not self._questions:
            empty = QLabel("No questions loaded\n\nAdd q_*.py modules to\nquestions/ directory")
            empty.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; padding: 12px;")
            empty.setWordWrap(True)
            layout.addWidget(empty)
        else:
            current_category = None
            for q in self._questions:
                if q.category != current_category:
                    current_category = q.category
                    if current_category != self._questions[0].category:
                        layout.addSpacing(12)
                    cat_label = QLabel(current_category.upper())
                    cat_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                    cat_label.setStyleSheet(f"color: {COLORS['text_muted']}; padding-left: 4px;")
                    layout.addWidget(cat_label)
                    layout.addSpacing(2)

                btn = QPushButton(f"  {q.title}")
                btn.setFont(QFont("Segoe UI", 10))
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedHeight(32)
                btn.setStyleSheet(self._sidebar_btn_style(selected=False))
                btn.clicked.connect(lambda checked, question=q: self._on_question_selected(question))
                layout.addWidget(btn)
                self._question_buttons[q.id] = btn

        layout.addStretch()
        scroll.setWidget(container)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.addWidget(scroll)

        return panel

    def _sidebar_btn_style(self, selected: bool) -> str:
        if selected:
            return (
                f"QPushButton {{ background-color: {COLORS['bg_header']}; color: {COLORS['text_primary']}; "
                f"border: none; border-radius: 4px; text-align: left; padding-left: 8px; }}"
            )
        return (
            f"QPushButton {{ background-color: transparent; color: {COLORS['text_secondary']}; "
            f"border: none; border-radius: 4px; text-align: left; padding-left: 8px; }}"
            f"QPushButton:hover {{ background-color: {COLORS['border']}; color: {COLORS['text_primary']}; }}"
        )

    # ------------------------------------------------------------------
    # Right content panel
    # ------------------------------------------------------------------
    def _create_content_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(0)

        # Question title
        self._title_label = QLabel("Select a question")
        self._title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._title_label.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(self._title_label)

        # Question text
        self._question_label = QLabel("Choose a question from the sidebar to see its answer.")
        self._question_label.setFont(QFont("Segoe UI", 11))
        self._question_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        self._question_label.setWordWrap(True)
        layout.addWidget(self._question_label)
        layout.addSpacing(16)

        # Time period toggle bar
        period_bar = QHBoxLayout()
        period_bar.setSpacing(4)
        for key, label in TIME_PERIODS.items():
            btn = QPushButton(label)
            btn.setFont(QFont("Segoe UI", 10))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.setFixedWidth(90)
            btn.setStyleSheet(self._period_btn_style(selected=(key == self._current_time_period)))
            btn.clicked.connect(lambda checked, period=key: self._on_time_period_changed(period))
            period_bar.addWidget(btn)
            self._period_buttons[key] = btn
        period_bar.addStretch()
        layout.addLayout(period_bar)
        layout.addSpacing(16)

        # Scrollable content area
        self._content_scroll = QScrollArea()
        self._content_scroll.setWidgetResizable(True)
        self._content_scroll.setStyleSheet("QScrollArea { border: none; }")

        self._content_placeholder = self._create_welcome_widget()
        self._content_scroll.setWidget(self._content_placeholder)
        layout.addWidget(self._content_scroll, stretch=1)

        # Bottom bar with export buttons
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 12, 0, 0)
        bottom_bar.addStretch()

        # Export All button — exports every question for current time period
        self._export_all_btn = QPushButton("Export All to Supabase")
        self._export_all_btn.setFont(QFont("Segoe UI", 10))
        self._export_all_btn.setFixedHeight(34)
        self._export_all_btn.setFixedWidth(200)
        self._export_all_btn.setEnabled(bool(self._questions))
        self._export_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_all_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['border']}; color: {COLORS['text_secondary']}; "
            f"border: none; border-radius: 4px; }}"
            f"QPushButton:enabled {{ background-color: {COLORS['bg_header']}; color: {COLORS['text_primary']}; }}"
            f"QPushButton:enabled:hover {{ background-color: #1a4a80; }}"
            f"QPushButton:disabled {{ background-color: {COLORS['border']}; color: {COLORS['text_muted']}; }}"
        )
        self._export_all_btn.clicked.connect(self._on_export_all)
        bottom_bar.addWidget(self._export_all_btn)
        bottom_bar.addSpacing(8)

        # Single-question export button
        self._export_btn = QPushButton("Export to Supabase")
        self._export_btn.setFont(QFont("Segoe UI", 10))
        self._export_btn.setFixedHeight(34)
        self._export_btn.setFixedWidth(180)
        self._export_btn.setEnabled(False)
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['border']}; color: {COLORS['text_secondary']}; "
            f"border: none; border-radius: 4px; }}"
            f"QPushButton:enabled {{ background-color: {COLORS['bg_header']}; color: {COLORS['text_primary']}; }}"
            f"QPushButton:enabled:hover {{ background-color: #1a4a80; }}"
            f"QPushButton:disabled {{ background-color: {COLORS['border']}; color: {COLORS['text_muted']}; }}"
        )
        self._export_btn.clicked.connect(self._on_export)
        bottom_bar.addWidget(self._export_btn)

        layout.addLayout(bottom_bar)

        return panel

    def _create_welcome_widget(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("?")
        icon.setFont(QFont("Segoe UI", 48, QFont.Weight.Light))
        icon.setStyleSheet(f"color: {COLORS['text_muted']};")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        count = len(self._questions)
        if count == 0:
            msg = QLabel("No questions loaded yet\n\nAdd question modules to questions/q_*.py")
        else:
            msg = QLabel(f"{count} question{'s' if count != 1 else ''} available\n\nSelect one from the sidebar")
        msg.setFont(QFont("Segoe UI", 14))
        msg.setStyleSheet(f"color: {COLORS['text_muted']};")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(msg)

        return w

    def _period_btn_style(self, selected: bool) -> str:
        if selected:
            return (
                f"QPushButton {{ background-color: {COLORS['bg_header']}; color: {COLORS['text_primary']}; "
                f"border: none; border-radius: 4px; font-weight: bold; }}"
            )
        return (
            f"QPushButton {{ background-color: transparent; color: {COLORS['text_muted']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: {COLORS['border']}; color: {COLORS['text_primary']}; }}"
        )

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _create_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("statusBar")
        bar.setFixedHeight(28)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 0, 20, 0)

        self.status_label = QLabel("Connecting...")
        self.status_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        self._time_label = QLabel(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self._time_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        layout.addWidget(self._time_label)

        return bar

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_question_selected(self, question: BaseQuestion):
        """User clicked a question in the sidebar."""
        self._current_question = question
        self._current_data = None
        self._export_btn.setEnabled(False)

        # Update sidebar selection
        for qid, btn in self._question_buttons.items():
            btn.setStyleSheet(self._sidebar_btn_style(selected=(qid == question.id)))

        # Update content header
        self._title_label.setText(question.title)
        self._question_label.setText(question.question)

        # Load the question
        self._load_question()

    def _on_time_period_changed(self, period: str):
        """User clicked a time period button."""
        self._current_time_period = period

        # Update period button styles
        for key, btn in self._period_buttons.items():
            btn.setStyleSheet(self._period_btn_style(selected=(key == period)))

        # Reload if a question is selected
        if self._current_question:
            self._load_question()

    def _load_question(self):
        """Run the current question's query on a background thread."""
        if not self._current_question:
            return

        self.status_label.setText(f"Loading: {self._current_question.title}...")
        self._export_btn.setEnabled(False)

        # Show loading state
        loading = QLabel("Loading...")
        loading.setFont(QFont("Segoe UI", 14))
        loading.setStyleSheet(f"color: {COLORS['text_muted']};")
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._content_scroll.setWidget(loading)

        self._load_thread = QuestionLoadThread(
            self._current_question, self._provider, self._current_time_period
        )
        self._load_thread.finished.connect(self._on_question_loaded)
        self._load_thread.error.connect(self._on_load_error)
        self._load_thread.start()

    def _on_question_loaded(self, data: pd.DataFrame):
        """Background load completed — render the answer."""
        self._current_data = data
        self._time_label.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        if self._current_question:
            try:
                widget = self._current_question.render(data)
                self._content_scroll.setWidget(widget)
                self._export_btn.setEnabled(True)
                count = len(data) if data is not None else 0
                self.status_label.setText(
                    f"{self._current_question.title} — {count:,} records"
                )
            except Exception as e:
                self._show_error(f"Render error: {e}")
        else:
            self.status_label.setText("Ready")

    def _on_load_error(self, error_msg: str):
        """Background load failed."""
        self._show_error(f"Query error: {error_msg}")

    def _on_export(self):
        """Export current question results to Supabase."""
        if not self._current_question or self._current_data is None:
            return
        try:
            result = self._current_question.export(self._current_data)

            metadata = {
                "time_period_label": TIME_PERIODS.get(self._current_time_period, self._current_time_period),
                "record_count": len(self._current_data) if self._current_data is not None else 0,
            }

            success = self._provider.export_question_result(
                question_id=self._current_question.id,
                question_text=self._current_question.question,
                time_period=self._current_time_period,
                result=result,
                metadata=metadata,
            )

            if success:
                self.status_label.setText(
                    f"Exported: {self._current_question.title} "
                    f"({self._current_time_period}) → sa_question_results"
                )
            else:
                self.status_label.setText("Export failed — check console for errors")
        except Exception as e:
            self.status_label.setText(f"Export error: {e}")

    def _on_export_all(self):
        """Export all registered questions for the current time period to Supabase.

        Generates a shared batch_id (UUID) so every row from this export
        session can be queried as a group.
        """
        if not self._questions:
            return

        batch_id = str(uuid.uuid4())
        total = len(self._questions)
        succeeded = 0
        failed_questions = []

        # Disable buttons during export
        self._export_btn.setEnabled(False)
        self._export_all_btn.setEnabled(False)

        # Progress dialog
        progress = QProgressDialog("Exporting questions...", "Cancel", 0, total, self)
        progress.setWindowTitle("Export All")
        progress.setMinimumDuration(0)
        progress.setMinimumWidth(400)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setStyleSheet(
            f"QProgressDialog {{ background-color: {COLORS['bg_primary']}; color: {COLORS['text_primary']}; }}"
            f"QLabel {{ color: {COLORS['text_primary']}; }}"
            f"QPushButton {{ background-color: {COLORS['bg_header']}; color: {COLORS['text_primary']}; "
            f"border: none; border-radius: 4px; padding: 6px 16px; }}"
        )

        for i, question in enumerate(self._questions):
            if progress.wasCanceled():
                break

            progress.setLabelText(
                f"Exporting question {i + 1}/{total}:\n{question.title}"
            )
            progress.setValue(i)
            QApplication.processEvents()

            try:
                data = question.query(self._provider, self._current_time_period)
                result = question.export(data)

                metadata = {
                    "time_period_label": TIME_PERIODS.get(
                        self._current_time_period, self._current_time_period
                    ),
                    "record_count": len(data) if data is not None else 0,
                }

                success = self._provider.export_question_result(
                    question_id=question.id,
                    question_text=question.question,
                    time_period=self._current_time_period,
                    result=result,
                    metadata=metadata,
                    batch_id=batch_id,
                )

                if success:
                    succeeded += 1
                else:
                    failed_questions.append(question.title)
            except Exception as e:
                print(f"[ExportAll] Failed to export '{question.title}': {e}")
                failed_questions.append(question.title)

        progress.setValue(total)

        # Status message
        if succeeded == total:
            self.status_label.setText(
                f"Exported {succeeded}/{total} questions to Supabase "
                f"(batch: {batch_id[:8]}...)"
            )
        elif succeeded > 0:
            self.status_label.setText(
                f"Exported {succeeded}/{total} questions — "
                f"{len(failed_questions)} failed: {', '.join(failed_questions)}"
            )
        else:
            self.status_label.setText(
                f"Export All failed — 0/{total} questions exported"
            )

        # Re-enable buttons
        self._export_all_btn.setEnabled(bool(self._questions))
        if self._current_question and self._current_data is not None:
            self._export_btn.setEnabled(True)

    def _show_error(self, message: str):
        """Display an error in the content area."""
        self.status_label.setText(message)
        error_label = QLabel(message)
        error_label.setFont(QFont("Segoe UI", 12))
        error_label.setStyleSheet(f"color: {COLORS['negative']};")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setWordWrap(True)
        self._content_scroll.setWidget(error_label)

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    def _connect_db(self):
        if self._provider.connect():
            self._provider.ensure_export_table()
            dr = self._provider.get_date_range()
            total = dr.get("total", 0)
            self.status_label.setText(f"Connected — {total:,} trades available")
        else:
            self.status_label.setText("Database connection failed")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        self._provider.close()
        super().closeEvent(event)
