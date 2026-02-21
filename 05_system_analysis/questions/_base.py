"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 05: SYSTEM ANALYSIS
BaseQuestion — Abstract base class for all question modules
XIII Trading LLC
================================================================================

Every question module in questions/q_*.py must subclass BaseQuestion and
implement query(), render(), and export().

Usage:
    class MyQuestion(BaseQuestion):
        id = "my_question"
        title = "My Question Title"
        question = "What is the answer to my question?"
        category = "Category Name"

        def query(self, provider, time_period): ...
        def render(self, data): ...
        def export(self, data): ...
"""
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Optional

import pandas as pd
from PyQt6.QtWidgets import QWidget


# =============================================================================
# Time period helper
# =============================================================================
TIME_PERIODS = {
    "all_time": "All Time",
    "year": "Year",
    "month": "Month",
    "week": "Week",
}


def get_date_cutoff(time_period: str) -> Optional[date]:
    """Return the earliest date for the given time period, or None for all_time."""
    today = date.today()
    if time_period == "year":
        return today - timedelta(days=365)
    elif time_period == "month":
        return today - timedelta(days=30)
    elif time_period == "week":
        return today - timedelta(days=7)
    return None


# =============================================================================
# BaseQuestion ABC
# =============================================================================
class BaseQuestion(ABC):
    """Abstract base class for all system analysis questions.

    Attributes:
        id:       Unique identifier (e.g., 'model_direction_grid')
        title:    Short display title (e.g., 'Model x Direction Effectiveness')
        question: Full human-readable question the calculation answers
        category: Sidebar grouping label (e.g., 'Model Performance')
    """

    id: str = ""
    title: str = ""
    question: str = ""
    category: str = ""

    @abstractmethod
    def query(self, provider, time_period: str) -> pd.DataFrame:
        """Fetch the data needed to answer this question.

        Args:
            provider: DataProvider instance with active DB connection
            time_period: One of 'all_time', 'year', 'month', 'week'

        Returns:
            DataFrame with the raw data for this question
        """

    @abstractmethod
    def render(self, data: pd.DataFrame) -> QWidget:
        """Build the visual answer for this question.

        Args:
            data: DataFrame returned by query()

        Returns:
            QWidget containing the complete answer (charts, tables, etc.)
        """

    @abstractmethod
    def export(self, data: pd.DataFrame) -> dict:
        """Package the answer as a JSON-serializable dict for Supabase export.

        Args:
            data: DataFrame returned by query()

        Returns:
            Dict ready for JSONB storage in sa_question_results
        """
