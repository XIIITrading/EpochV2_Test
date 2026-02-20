"""
Polygon API Client
Epoch Trading System v1 - XIII Trading LLC

Fetches bar data from Polygon.io API for the Entry Qualifier.
Based on the existing polygon_fetcher.py pattern.
"""
import requests
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pytz
import sys
from pathlib import Path

# Add parent directory (04_dow_ai) to path for config imports
# Insert at position 1 so it's after entry_qualifier but before site-packages
_parent_dir = str(Path(__file__).parent.parent.parent.resolve())
if _parent_dir not in sys.path:
    sys.path.insert(1, _parent_dir)

from config import (
    POLYGON_API_KEY,
    POLYGON_BASE_URL,
    API_RATE_LIMIT_DELAY,
    API_MAX_RETRIES,
    API_RETRY_DELAY,
    TIMEZONE
)


class PolygonClient:
    """
    Lightweight Polygon API client for fetching M1 bars.
    Follows the pattern established in polygon_fetcher.py.
    """

    def __init__(self, api_key: str = None):
        """
        Initialize Polygon client.

        Args:
            api_key: Polygon API key (uses config if not provided)
        """
        self.api_key = api_key or POLYGON_API_KEY
        self.base_url = POLYGON_BASE_URL
        self.tz = pytz.timezone(TIMEZONE)
        self._last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting between API calls."""
        elapsed = time.time() - self._last_request_time
        if elapsed < API_RATE_LIMIT_DELAY:
            time.sleep(API_RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _make_request(self, url: str, params: dict) -> Optional[dict]:
        """
        Make API request with retry logic.

        Args:
            url: API endpoint URL
            params: Query parameters

        Returns:
            JSON response data or None if failed
        """
        params['apiKey'] = self.api_key

        for attempt in range(API_MAX_RETRIES):
            try:
                self._rate_limit()
                response = requests.get(url, params=params, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') in ['OK', 'DELAYED']:
                        return data
                    else:
                        return None

                elif response.status_code == 429:
                    # Rate limit hit
                    time.sleep(API_RETRY_DELAY * (attempt + 1))
                    continue

                else:
                    if attempt < API_MAX_RETRIES - 1:
                        time.sleep(API_RETRY_DELAY)
                        continue
                    return None

            except requests.exceptions.Timeout:
                if attempt < API_MAX_RETRIES - 1:
                    time.sleep(API_RETRY_DELAY)
                    continue
                return {'error': 'timeout'}

            except requests.exceptions.RequestException as e:
                if attempt < API_MAX_RETRIES - 1:
                    time.sleep(API_RETRY_DELAY)
                    continue
                return {'error': 'network'}

        return None

    def _to_epoch_ms(self, dt: datetime) -> int:
        """Convert datetime to milliseconds since epoch for Polygon API."""
        return int(dt.timestamp() * 1000)

    def fetch_m1_bars(
        self,
        ticker: str,
        bars_needed: int = 30
    ) -> Dict[str, Any]:
        """
        Fetch M1 (1-minute) bars for a ticker.

        Args:
            ticker: Stock symbol (e.g., 'SPY')
            bars_needed: Number of bars to fetch

        Returns:
            Dict with 'bars' list or 'error' string
        """
        # Calculate date range - use 2 days lookback for M1 data
        end_datetime = datetime.now(self.tz)
        start_datetime = end_datetime - timedelta(days=2)

        # Use millisecond timestamps so Polygon returns bars up to current moment
        from_ts = self._to_epoch_ms(start_datetime)
        to_ts = self._to_epoch_ms(end_datetime)

        # Build URL with ms timestamps for precise range
        url = f"{self.base_url}/v2/aggs/ticker/{ticker}/range/1/minute/{from_ts}/{to_ts}"

        params = {
            'adjusted': 'true',
            'sort': 'asc',
            'limit': 50000
        }

        # Make request
        data = self._make_request(url, params)

        if data is None:
            return {'error': 'api_error', 'bars': []}

        if 'error' in data:
            return {'error': data['error'], 'bars': []}

        if 'results' not in data or not data['results']:
            return {'error': 'no_data', 'bars': []}

        # Process results
        bars = []
        for result in data['results']:
            bar = {
                'timestamp': result.get('t'),  # milliseconds
                'open': result.get('o'),
                'high': result.get('h'),
                'low': result.get('l'),
                'close': result.get('c'),
                'volume': result.get('v')
            }
            bars.append(bar)

        # Return most recent bars_needed
        bars = bars[-bars_needed:] if len(bars) > bars_needed else bars

        return {'bars': bars, 'error': None}

    def fetch_h1_bars(
        self,
        ticker: str,
        bars_needed: int = 25
    ) -> Dict[str, Any]:
        """
        Fetch H1 (1-hour) bars for a ticker.

        Args:
            ticker: Stock symbol (e.g., 'SPY')
            bars_needed: Number of bars to fetch (default 25 for 25 hours)

        Returns:
            Dict with 'bars' list or 'error' string
        """
        # Calculate date range - use 5 days lookback for H1 data
        # (covers weekends and holidays)
        end_datetime = datetime.now(self.tz)
        start_datetime = end_datetime - timedelta(days=5)

        # Use millisecond timestamps so Polygon returns bars up to current moment
        from_ts = self._to_epoch_ms(start_datetime)
        to_ts = self._to_epoch_ms(end_datetime)

        # Build URL for 1-hour bars with ms timestamps
        url = f"{self.base_url}/v2/aggs/ticker/{ticker}/range/1/hour/{from_ts}/{to_ts}"

        params = {
            'adjusted': 'true',
            'sort': 'asc',
            'limit': 5000
        }

        # Make request
        data = self._make_request(url, params)

        if data is None:
            return {'error': 'api_error', 'bars': []}

        if 'error' in data:
            return {'error': data['error'], 'bars': []}

        if 'results' not in data or not data['results']:
            return {'error': 'no_data', 'bars': []}

        # Process results
        bars = []
        for result in data['results']:
            bar = {
                'timestamp': result.get('t'),  # milliseconds
                'open': result.get('o'),
                'high': result.get('h'),
                'low': result.get('l'),
                'close': result.get('c'),
                'volume': result.get('v')
            }
            bars.append(bar)

        # Return most recent bars_needed
        bars = bars[-bars_needed:] if len(bars) > bars_needed else bars

        return {'bars': bars, 'error': None}

    def fetch_m5_bars(
        self,
        ticker: str,
        bars_needed: int = 50
    ) -> Dict[str, Any]:
        """
        Fetch M5 (5-minute) bars for a ticker.

        Args:
            ticker: Stock symbol (e.g., 'SPY')
            bars_needed: Number of bars to fetch (default 50 for ~4 hours)

        Returns:
            Dict with 'bars' list or 'error' string
        """
        end_datetime = datetime.now(self.tz)
        start_datetime = end_datetime - timedelta(days=2)

        from_ts = self._to_epoch_ms(start_datetime)
        to_ts = self._to_epoch_ms(end_datetime)

        url = f"{self.base_url}/v2/aggs/ticker/{ticker}/range/5/minute/{from_ts}/{to_ts}"

        params = {
            'adjusted': 'true',
            'sort': 'asc',
            'limit': 10000
        }

        data = self._make_request(url, params)

        if data is None:
            return {'error': 'api_error', 'bars': []}

        if 'error' in data:
            return {'error': data['error'], 'bars': []}

        if 'results' not in data or not data['results']:
            return {'error': 'no_data', 'bars': []}

        bars = []
        for result in data['results']:
            bar = {
                'timestamp': result.get('t'),
                'open': result.get('o'),
                'high': result.get('h'),
                'low': result.get('l'),
                'close': result.get('c'),
                'volume': result.get('v')
            }
            bars.append(bar)

        bars = bars[-bars_needed:] if len(bars) > bars_needed else bars

        return {'bars': bars, 'error': None}

    def fetch_m15_bars(
        self,
        ticker: str,
        bars_needed: int = 30
    ) -> Dict[str, Any]:
        """
        Fetch M15 (15-minute) bars for a ticker.

        Args:
            ticker: Stock symbol (e.g., 'SPY')
            bars_needed: Number of bars to fetch (default 30 for ~7.5 hours)

        Returns:
            Dict with 'bars' list or 'error' string
        """
        end_datetime = datetime.now(self.tz)
        start_datetime = end_datetime - timedelta(days=3)

        from_ts = self._to_epoch_ms(start_datetime)
        to_ts = self._to_epoch_ms(end_datetime)

        url = f"{self.base_url}/v2/aggs/ticker/{ticker}/range/15/minute/{from_ts}/{to_ts}"

        params = {
            'adjusted': 'true',
            'sort': 'asc',
            'limit': 5000
        }

        data = self._make_request(url, params)

        if data is None:
            return {'error': 'api_error', 'bars': []}

        if 'error' in data:
            return {'error': data['error'], 'bars': []}

        if 'results' not in data or not data['results']:
            return {'error': 'no_data', 'bars': []}

        bars = []
        for result in data['results']:
            bar = {
                'timestamp': result.get('t'),
                'open': result.get('o'),
                'high': result.get('h'),
                'low': result.get('l'),
                'close': result.get('c'),
                'volume': result.get('v')
            }
            bars.append(bar)

        bars = bars[-bars_needed:] if len(bars) > bars_needed else bars

        return {'bars': bars, 'error': None}

    def validate_ticker(self, ticker: str) -> bool:
        """
        Validate that a ticker exists and has data.

        Args:
            ticker: Stock symbol to validate

        Returns:
            True if ticker is valid, False otherwise
        """
        result = self.fetch_m1_bars(ticker, bars_needed=5)
        return result.get('error') is None and len(result.get('bars', [])) > 0
