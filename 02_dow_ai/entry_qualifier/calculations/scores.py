"""
DEPRECATED - SWH-6 (February 2026)
Scoring system has been deprecated per SWH-6.
This module is retained as a placeholder to prevent import errors.
LONG/SHORT composite scores were replaced by multi-timeframe fractal structure.
"""
from typing import Optional, Any


def calculate_long_score(*args, **kwargs) -> int:
    """DEPRECATED: Always returns 0."""
    return 0


def calculate_short_score(*args, **kwargs) -> int:
    """DEPRECATED: Always returns 0."""
    return 0


def calculate_all_scores(bars: list) -> list:
    """DEPRECATED: Returns zero scores for all bars."""
    return [{'long_score': 0, 'short_score': 0} for _ in bars]
