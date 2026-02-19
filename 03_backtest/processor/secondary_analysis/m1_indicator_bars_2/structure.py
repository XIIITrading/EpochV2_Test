"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
M1 Indicator Bars v2 - Market Structure Detection
XIII Trading LLC
================================================================================

Multi-timeframe market structure calculation (H4, H1, M15, M5, M1).
Detects fractals, identifies BOS/ChoCH, and determines market direction.

Direction-agnostic: Labels are BULL, BEAR, or NEUTRAL.
Adapted from m1_indicator_bars/structure.py for v2 module.

Note: Structure detection still uses Polygon API for native HTF bars
(M5, M15, H4) and h1_bars DB table for H1. M1 structure uses bars
passed through the calculator from m1_bars_2.

Version: 2.0.0
================================================================================
"""

from typing import Dict, List, Optional, Tuple, NamedTuple
import numpy as np
from datetime import datetime, date, time, timedelta
import requests
import time as time_module
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import pytz

# Timezone constants for Polygon timestamp conversion
_ET = pytz.timezone('America/New_York')
_UTC = pytz.UTC

# Use explicit path imports to avoid collisions with 03_indicators modules
import importlib.util
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent

# Load local config
_config_spec = importlib.util.spec_from_file_location("local_config", _MODULE_DIR / "config.py")
_config = importlib.util.module_from_spec(_config_spec)
_config_spec.loader.exec_module(_config)

FRACTAL_LENGTH = _config.FRACTAL_LENGTH
STRUCTURE_LABELS = _config.STRUCTURE_LABELS
POLYGON_API_KEY = _config.POLYGON_API_KEY
POLYGON_BASE_URL = _config.POLYGON_BASE_URL
API_DELAY = _config.API_DELAY
API_RETRIES = _config.API_RETRIES
API_RETRY_DELAY = _config.API_RETRY_DELAY
HTF_BARS_NEEDED = _config.HTF_BARS_NEEDED
HTF_LOOKBACK_DAYS = _config.HTF_LOOKBACK_DAYS
DB_CONFIG = _config.DB_CONFIG


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class StructureResult(NamedTuple):
    """Result of market structure calculation."""
    direction: int  # 1 = BULL, -1 = BEAR, 0 = NEUTRAL
    direction_label: str  # 'BULL', 'BEAR', 'NEUTRAL', 'ERROR'
    last_break_label: Optional[str]  # 'BOS' or 'ChoCH'
    strong_level: Optional[float]  # Invalidation level
    weak_level: Optional[float]  # Continuation level


# =============================================================================
# MARKET STRUCTURE CALCULATOR
# =============================================================================

class MarketStructureCalculator:
    """
    Calculates market structure (Bull/Bear) from OHLC data.
    Based on fractal detection and Break of Structure (BOS) / Change of Character (ChoCH).
    """

    def __init__(self, fractal_length: int = None):
        """
        Initialize market structure calculator.

        Args:
            fractal_length: Number of bars on each side for fractal detection
        """
        self.length = fractal_length or FRACTAL_LENGTH
        self.p = int(self.length / 2)

    def _detect_fractals(self, bars: List[Dict]) -> Tuple[List[bool], List[bool]]:
        """
        Detect bullish and bearish fractals in the price data.

        Args:
            bars: List of bar dictionaries with 'high' and 'low' keys

        Returns:
            Tuple of (bullish_fractals, bearish_fractals) as boolean lists
        """
        n = len(bars)
        p = self.p

        bullf = [False] * n
        bearf = [False] * n

        if n < self.length:
            return bullf, bearf

        for i in range(p, n - p):
            high_i = float(bars[i].get('high', 0))
            low_i = float(bars[i].get('low', 0))

            # Bearish fractal (local high)
            before_lower = all(
                float(bars[i - j].get('high', 0)) < high_i
                for j in range(1, p + 1)
            )
            after_lower = all(
                float(bars[i + j].get('high', 0)) < high_i
                for j in range(1, p + 1)
            )

            if before_lower and after_lower:
                bearf[i] = True

            # Bullish fractal (local low)
            before_higher = all(
                float(bars[i - j].get('low', 0)) > low_i
                for j in range(1, p + 1)
            )
            after_higher = all(
                float(bars[i + j].get('low', 0)) > low_i
                for j in range(1, p + 1)
            )

            if before_higher and after_higher:
                bullf[i] = True

        return bullf, bearf

    def calculate(self, bars: List[Dict]) -> StructureResult:
        """
        Calculate market structure from OHLC data.

        Args:
            bars: List of bar dictionaries with 'open', 'high', 'low', 'close'

        Returns:
            StructureResult with direction, levels, etc.
        """
        if not bars or len(bars) < 50:
            return StructureResult(
                direction=0,
                direction_label='NEUTRAL',
                last_break_label=None,
                strong_level=None,
                weak_level=None
            )

        bullf, bearf = self._detect_fractals(bars)

        # Track structure state
        upper_value = None
        upper_crossed = False
        lower_value = None
        lower_crossed = False
        current_structure = 0
        last_break_label = None
        bull_continuation_high = None
        bear_continuation_low = None

        for i in range(len(bars)):
            close = float(bars[i].get('close', 0))
            high = float(bars[i].get('high', 0))
            low = float(bars[i].get('low', 0))

            # Update fractal levels
            if bearf[i]:
                upper_value = high
                upper_crossed = False

            if bullf[i]:
                lower_value = low
                lower_crossed = False

            # Check for structure breaks
            if upper_value is not None and not upper_crossed:
                if close > upper_value:
                    if current_structure == -1:
                        last_break_label = 'ChoCH'
                    else:
                        last_break_label = 'BOS'
                    current_structure = 1
                    upper_crossed = True
                    bull_continuation_high = high

            if lower_value is not None and not lower_crossed:
                if close < lower_value:
                    if current_structure == 1:
                        last_break_label = 'ChoCH'
                    else:
                        last_break_label = 'BOS'
                    current_structure = -1
                    lower_crossed = True
                    bear_continuation_low = low

            # Update continuation levels
            if current_structure == 1:
                if bull_continuation_high is None or high > bull_continuation_high:
                    bull_continuation_high = high
            elif current_structure == -1:
                if bear_continuation_low is None or low < bear_continuation_low:
                    bear_continuation_low = low

        # Determine strong and weak levels
        strong_level = None
        weak_level = None

        if current_structure == 1:  # Bull
            strong_level = lower_value  # Support that if broken = ChoCH
            weak_level = bull_continuation_high
        elif current_structure == -1:  # Bear
            strong_level = upper_value  # Resistance that if broken = ChoCH
            weak_level = bear_continuation_low

        return StructureResult(
            direction=current_structure,
            direction_label=STRUCTURE_LABELS.get(current_structure, 'NEUTRAL'),
            last_break_label=last_break_label,
            strong_level=strong_level,
            weak_level=weak_level
        )


# =============================================================================
# HTF BAR FETCHER
# =============================================================================

class HTFBarFetcher:
    """
    Fetches higher timeframe bars for structure detection.

    H1 bars are fetched from the h1_bars database table for performance.
    Other timeframes (M1, M5, M15, H4) are fetched from Polygon API.
    """

    # Timeframe to Polygon API parameters
    TIMEFRAME_CONFIG = {
        'M1': {'multiplier': 1, 'timespan': 'minute'},
        'M5': {'multiplier': 5, 'timespan': 'minute'},
        'M15': {'multiplier': 15, 'timespan': 'minute'},
        'H1': {'multiplier': 1, 'timespan': 'hour'},
        'H4': {'multiplier': 4, 'timespan': 'hour'},
    }

    def __init__(self, api_key: str = None, db_config: dict = None):
        """
        Initialize the HTF bar fetcher.

        Args:
            api_key: Polygon API key (defaults to config value)
            db_config: Database configuration dict (defaults to config value)
        """
        self.api_key = api_key or POLYGON_API_KEY
        self.base_url = POLYGON_BASE_URL
        self.db_config = db_config or DB_CONFIG
        self.last_request_time = 0
        self._cache: Dict[str, List[Dict]] = {}

    def _rate_limit(self):
        """Enforce rate limiting between API calls."""
        if API_DELAY > 0:
            elapsed = time_module.time() - self.last_request_time
            if elapsed < API_DELAY:
                time_module.sleep(API_DELAY - elapsed)
        self.last_request_time = time_module.time()

    def _get_cache_key(self, ticker: str, timeframe: str, trade_date: date) -> str:
        """Generate cache key."""
        return f"{ticker}_{timeframe}_{trade_date.strftime('%Y%m%d')}"

    def fetch_bars(
        self,
        ticker: str,
        timeframe: str,
        trade_date: date,
        end_time: time = None
    ) -> List[Dict]:
        """
        Fetch HTF bars for structure calculation.

        H1 bars are fetched from the h1_bars database table for performance.
        Other timeframes are fetched from Polygon API.

        Args:
            ticker: Stock symbol
            timeframe: 'M1', 'M5', 'M15', 'H1', or 'H4'
            trade_date: The trading date
            end_time: Optional end time to filter bars up to

        Returns:
            List of bar dictionaries
        """
        if timeframe not in self.TIMEFRAME_CONFIG:
            return []

        cache_key = self._get_cache_key(ticker, timeframe, trade_date)

        # Check cache
        if cache_key in self._cache:
            bars = self._cache[cache_key]
            if end_time:
                bars = self._filter_bars_by_time(bars, trade_date, end_time)
            return bars

        # For H1, use the database table instead of API
        if timeframe == 'H1':
            bars = self._fetch_h1_from_database(ticker, trade_date)
            if bars:
                self._cache[cache_key] = bars
                if end_time:
                    bars = self._filter_bars_by_time(bars, trade_date, end_time)
                return bars
            # Fall back to API if no database data

        # Calculate date range for API fetch
        lookback_days = HTF_LOOKBACK_DAYS.get(timeframe, 7)
        from_date = trade_date - timedelta(days=lookback_days)
        to_date = trade_date

        config = self.TIMEFRAME_CONFIG[timeframe]
        multiplier = config['multiplier']
        timespan = config['timespan']

        url = f"{self.base_url}/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}"

        params = {
            'apiKey': self.api_key,
            'adjusted': 'true',
            'sort': 'asc',
            'limit': 50000
        }

        for attempt in range(API_RETRIES):
            try:
                self._rate_limit()
                response = requests.get(url, params=params, timeout=30)

                if response.status_code == 429:  # Rate limited
                    wait_time = API_RETRY_DELAY * (attempt + 1)
                    time_module.sleep(wait_time)
                    continue

                if response.status_code != 200:
                    return []

                data = response.json()

                if data.get('status') not in ['OK', 'DELAYED']:
                    return []

                if 'results' not in data or not data['results']:
                    return []

                bars = []
                for result in data['results']:
                    # Convert Polygon UTC timestamp to Eastern Time
                    # (matches m1_bars_storage.py conversion pattern)
                    ts_ms = result['t']
                    ts_utc = datetime.utcfromtimestamp(ts_ms / 1000).replace(tzinfo=_UTC)
                    ts = ts_utc.astimezone(_ET)

                    bar = {
                        'timestamp': ts,
                        'bar_date': ts.date(),
                        'bar_time': ts.time().replace(tzinfo=None),
                        'open': result['o'],
                        'high': result['h'],
                        'low': result['l'],
                        'close': result['c'],
                        'volume': int(result['v']),
                        'vwap': result.get('vw')
                    }
                    bars.append(bar)

                # Cache the full result
                self._cache[cache_key] = bars

                # Filter by end_time if specified
                if end_time:
                    bars = self._filter_bars_by_time(bars, trade_date, end_time)

                return bars

            except requests.exceptions.Timeout:
                time_module.sleep(API_RETRY_DELAY)
            except Exception as e:
                return []

        return []

    def _fetch_h1_from_database(
        self,
        ticker: str,
        trade_date: date
    ) -> List[Dict]:
        """
        Fetch H1 bars from the h1_bars database table.

        Fetches bars with lookback period for structure calculation.

        Args:
            ticker: Stock symbol
            trade_date: The trading date

        Returns:
            List of bar dictionaries sorted by timestamp
        """
        lookback_days = HTF_LOOKBACK_DAYS.get('H1', 14)
        from_date = trade_date - timedelta(days=lookback_days)

        query = """
            SELECT
                ticker, bar_date, bar_time, bar_timestamp,
                open, high, low, close, volume, vwap
            FROM h1_bars
            WHERE ticker = %s
              AND bar_date >= %s
              AND bar_date <= %s
            ORDER BY bar_timestamp ASC
        """

        try:
            conn = psycopg2.connect(**self.db_config)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (ticker, from_date, trade_date))
                rows = cur.fetchall()
            conn.close()

            if not rows:
                return []

            bars = []
            for row in rows:
                bar = {
                    'timestamp': row['bar_timestamp'],
                    'bar_date': row['bar_date'],
                    'bar_time': row['bar_time'],
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': int(row['volume']),
                    'vwap': float(row['vwap']) if row['vwap'] else None
                }
                bars.append(bar)

            return bars

        except Exception as e:
            # Log error but don't crash - will fall back to API
            return []

    def _filter_bars_by_time(self, bars: List[Dict], trade_date: date, end_time: time) -> List[Dict]:
        """Filter bars to only include those before end_time on the trading date."""
        filtered = []
        for bar in bars:
            bar_date = bar.get('bar_date')
            ts = bar.get('timestamp')

            # Include all bars before trade_date
            if bar_date and bar_date < trade_date:
                filtered.append(bar)
            # For trade_date, filter by time
            elif bar_date and bar_date == trade_date:
                bar_time = bar.get('bar_time')
                if bar_time and bar_time <= end_time:
                    filtered.append(bar)

        return filtered

    def clear_cache(self):
        """Clear the bar cache."""
        self._cache.clear()


# =============================================================================
# STRUCTURE ANALYZER
# =============================================================================

class StructureAnalyzer:
    """
    High-level analyzer that fetches HTF bars and calculates structure.
    """

    def __init__(self, fetcher: HTFBarFetcher = None):
        """
        Initialize the structure analyzer.

        Args:
            fetcher: HTFBarFetcher instance (creates one if not provided)
        """
        self.fetcher = fetcher or HTFBarFetcher()
        self.calculator = MarketStructureCalculator()

    def get_structure(
        self,
        ticker: str,
        timeframe: str,
        trade_date: date,
        bar_time: time
    ) -> StructureResult:
        """
        Get market structure for a specific timeframe at a given time.

        Args:
            ticker: Stock symbol
            timeframe: 'M1', 'M5', 'M15', 'H1', or 'H4'
            trade_date: Trading date
            bar_time: Bar time (filter bars before this)

        Returns:
            StructureResult
        """
        bars = self.fetcher.fetch_bars(ticker, timeframe, trade_date, bar_time)

        if not bars:
            return StructureResult(
                direction=0,
                direction_label='NEUTRAL',
                last_break_label=None,
                strong_level=None,
                weak_level=None
            )

        return self.calculator.calculate(bars)

    def get_all_structures(
        self,
        ticker: str,
        trade_date: date,
        bar_time: time
    ) -> Dict[str, StructureResult]:
        """
        Get market structure for all HTF timeframes (including M1).

        Args:
            ticker: Stock symbol
            trade_date: Trading date
            bar_time: Bar time

        Returns:
            Dict mapping timeframe to StructureResult
        """
        results = {}

        for timeframe in ['M1', 'M5', 'M15', 'H1', 'H4']:
            results[timeframe] = self.get_structure(ticker, timeframe, trade_date, bar_time)

        return results

    def clear_cache(self):
        """Clear the bar cache."""
        self.fetcher.clear_cache()
