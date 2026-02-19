"""
HTF Structure Calculations - Thin Adapter
Epoch Trading System - XIII Trading LLC

Delegates structure calculation to shared.indicators.structure (canonical fractal-based).
Preserves the MarketStructure enum, caching classes, and dict-based return format
for backward compatibility with data_worker.

SWH-6: Single source of truth - shared.indicators
"""
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

from shared.indicators.structure import calculate_structure_from_bars
from shared.indicators.config import CONFIG


class MarketStructure(Enum):
    """Market structure states."""
    BULL = "B+"        # Higher highs, higher lows
    BEAR = "B-"        # Lower highs, lower lows
    NEUTRAL = "N"      # Mixed/consolidation


# Map from shared labels to local enum
_STRUCTURE_MAP = {
    "BULL": MarketStructure.BULL,
    "BEAR": MarketStructure.BEAR,
    "NEUTRAL": MarketStructure.NEUTRAL,
}


def calculate_structure(bars: List[dict], lookback: int = 5) -> MarketStructure:
    """
    Determine market structure from bars using canonical fractal-based detection.

    Delegates to shared.indicators.structure.calculate_structure_from_bars.

    Args:
        bars: List of bar dictionaries with 'high', 'low' keys
        lookback: Fractal length (bars each side for fractal detection)

    Returns:
        MarketStructure enum value
    """
    if not bars or len(bars) < 2 * lookback + 1:
        return MarketStructure.NEUTRAL

    result = calculate_structure_from_bars(bars, length=lookback)
    return _STRUCTURE_MAP.get(result.label, MarketStructure.NEUTRAL)


def get_h1_bar_for_timestamp(
    h1_bars: List[dict],
    m1_timestamp: int
) -> Optional[dict]:
    """
    Find the H1 bar that contains a given M1 timestamp.

    Args:
        h1_bars: List of H1 bars with 'timestamp' key (milliseconds)
        m1_timestamp: M1 bar timestamp in milliseconds

    Returns:
        The H1 bar dict, or None if not found
    """
    if not h1_bars:
        return None

    hour_ms = 3600000

    for h1_bar in reversed(h1_bars):
        h1_ts = h1_bar.get('timestamp', 0)
        if h1_ts <= m1_timestamp < h1_ts + hour_ms:
            return h1_bar

    return h1_bars[-1] if h1_bars else None


def calculate_structure_for_bars(
    h1_bars: List[dict],
    m1_bars: List[dict],
    lookback: int = 5
) -> List[dict]:
    """
    Calculate HTF structure for each M1 bar using canonical fractal detection.

    For each M1 bar, finds HTF bars up to that point and calculates
    the structure based on fractal swing analysis.

    Args:
        h1_bars: List of HTF bar dictionaries
        m1_bars: List of M1 bar dictionaries with 'timestamp' key
        lookback: Fractal length (bars each side)

    Returns:
        List of dicts with 'h1_structure' and 'h1_display' keys for each M1 bar
    """
    results = []

    if not h1_bars:
        return [{'h1_structure': MarketStructure.NEUTRAL, 'h1_display': 'N'}
                for _ in m1_bars]

    for m1_bar in m1_bars:
        m1_ts = m1_bar.get('timestamp', 0)

        # Find HTF bars up to this M1 timestamp
        relevant_bars = [b for b in h1_bars if b.get('timestamp', 0) <= m1_ts]

        if len(relevant_bars) >= 2 * lookback + 1:
            structure = calculate_structure(relevant_bars, lookback)
        else:
            structure = MarketStructure.NEUTRAL

        results.append({
            'h1_structure': structure,
            'h1_display': structure.value
        })

    return results


class StructureCache:
    """
    Generic cache for timeframe bar data to minimize API calls.

    Caches bars for any timeframe and refreshes when a new bar closes.
    Used for M5, M15, etc. Parametrized by timeframe duration in milliseconds.
    """

    def __init__(self, timeframe_ms: int):
        self.timeframe_ms = timeframe_ms
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_bars(self, ticker: str) -> Optional[List[dict]]:
        """Get cached bars for a ticker."""
        if ticker in self._cache:
            return self._cache[ticker].get('bars')
        return None

    def set_bars(self, ticker: str, bars: List[dict]):
        """Cache bars for a ticker."""
        last_bar_ts = bars[-1].get('timestamp', 0) if bars else 0
        self._cache[ticker] = {
            'bars': bars,
            'last_update': datetime.now(),
            'last_bar_ts': last_bar_ts
        }

    def needs_refresh(self, ticker: str, current_bar_ts: int) -> bool:
        """Check if data needs to be refreshed."""
        if ticker not in self._cache:
            return True
        cached_ts = self._cache[ticker].get('last_bar_ts', 0)
        return current_bar_ts > cached_ts

    def clear(self, ticker: str = None):
        """Clear cache for a ticker or all tickers."""
        if ticker:
            self._cache.pop(ticker, None)
        else:
            self._cache.clear()


class H1StructureCache:
    """
    Cache for H1 bar data to minimize API calls.
    H1 data is fetched on initial load and refreshed hourly.
    """

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_bars(self, ticker: str) -> Optional[List[dict]]:
        """Get cached H1 bars for a ticker."""
        if ticker in self._cache:
            return self._cache[ticker].get('bars')
        return None

    def set_bars(self, ticker: str, bars: List[dict]):
        """Cache H1 bars for a ticker."""
        last_h1_ts = bars[-1].get('timestamp', 0) if bars else 0
        self._cache[ticker] = {
            'bars': bars,
            'last_update': datetime.now(),
            'last_h1_ts': last_h1_ts
        }

    def needs_refresh(self, ticker: str, current_h1_ts: int) -> bool:
        """Check if H1 data needs to be refreshed."""
        if ticker not in self._cache:
            return True
        cached_ts = self._cache[ticker].get('last_h1_ts', 0)
        return current_h1_ts > cached_ts

    def clear(self, ticker: str = None):
        """Clear cache for a ticker or all tickers."""
        if ticker:
            self._cache.pop(ticker, None)
        else:
            self._cache.clear()
