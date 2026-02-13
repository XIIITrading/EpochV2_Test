"""
Polygon API Bar Fetcher for Journal Viewer
Epoch Trading System - XIII Trading LLC

Extracted from 11_trade_reel/ui/main_window.py into standalone module.
Provides bar fetching + M5 ATR(14) calculation for trade analysis.

Functions:
    fetch_bars()       - Intraday bars (M1, M5, M15, H1)
    fetch_daily_bars() - Daily bars
    calculate_m5_atr() - ATR(14) on M5 bars at a given entry time
"""

import logging
import time as time_module
from datetime import date, time, timedelta
from typing import Optional

import pandas as pd
import numpy as np
import requests

from .config import POLYGON_API_KEY, API_DELAY, API_RETRIES, API_RETRY_DELAY, DISPLAY_TIMEZONE

logger = logging.getLogger(__name__)


# =============================================================================
# Bar Fetching (Polygon API)
# =============================================================================

def fetch_bars(
    ticker: str,
    end_date: date,
    tf_minutes: int,
    lookback_days: int,
) -> pd.DataFrame:
    """
    Fetch intraday bars from Polygon API for a single timeframe.

    Args:
        ticker: Stock ticker symbol
        end_date: End date for the range
        tf_minutes: Timeframe in minutes (1, 5, 15, 60)
        lookback_days: Number of days to look back from end_date

    Returns:
        DataFrame with columns [open, high, low, close, volume],
        datetime index in Eastern time. Empty DataFrame on failure.
    """
    start = end_date - timedelta(days=lookback_days)
    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range"
        f"/{tf_minutes}/minute/{start:%Y-%m-%d}/{end_date:%Y-%m-%d}"
    )
    params = {
        'apiKey': POLYGON_API_KEY,
        'adjusted': 'true',
        'sort': 'asc',
        'limit': 50000,
    }

    for attempt in range(API_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if data.get('status') != 'OK' or not data.get('results'):
                return pd.DataFrame()

            df = pd.DataFrame(data['results'])
            df = df.rename(columns={
                't': 'timestamp', 'o': 'open', 'h': 'high',
                'l': 'low', 'c': 'close', 'v': 'volume',
            })
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df['timestamp'] = df['timestamp'].dt.tz_convert(DISPLAY_TIMEZONE)
            df.set_index('timestamp', inplace=True)
            df = df[['open', 'high', 'low', 'close', 'volume']]

            time_module.sleep(API_DELAY)
            return df

        except requests.exceptions.RequestException as e:
            logger.warning(f"Bar fetch attempt {attempt + 1} failed: {e}")
            if attempt < API_RETRIES - 1:
                time_module.sleep(API_RETRY_DELAY)
        except Exception as e:
            logger.error(f"Unexpected bar fetch error: {e}")
            break

    return pd.DataFrame()


def fetch_daily_bars(
    ticker: str,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """
    Fetch daily bars from Polygon API for a date range.

    Args:
        ticker: Stock ticker symbol
        start_date: Start date
        end_date: End date

    Returns:
        DataFrame with columns [open, high, low, close, volume],
        datetime index in Eastern time. Empty DataFrame on failure.
    """
    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range"
        f"/1/day/{start_date:%Y-%m-%d}/{end_date:%Y-%m-%d}"
    )
    params = {
        'apiKey': POLYGON_API_KEY,
        'adjusted': 'true',
        'sort': 'asc',
        'limit': 50000,
    }

    for attempt in range(API_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if data.get('status') != 'OK' or not data.get('results'):
                return pd.DataFrame()

            df = pd.DataFrame(data['results'])
            df = df.rename(columns={
                't': 'timestamp', 'o': 'open', 'h': 'high',
                'l': 'low', 'c': 'close', 'v': 'volume',
            })
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df['timestamp'] = df['timestamp'].dt.tz_convert(DISPLAY_TIMEZONE)
            df.set_index('timestamp', inplace=True)
            df = df[['open', 'high', 'low', 'close', 'volume']]

            time_module.sleep(API_DELAY)
            return df

        except requests.exceptions.RequestException as e:
            logger.warning(f"Daily bar fetch attempt {attempt + 1} failed: {e}")
            if attempt < API_RETRIES - 1:
                time_module.sleep(API_RETRY_DELAY)
        except Exception as e:
            logger.error(f"Unexpected daily bar fetch error: {e}")
            break

    return pd.DataFrame()


# =============================================================================
# M5 ATR(14) Calculation
# =============================================================================

def calculate_m5_atr(
    bars_m5: pd.DataFrame,
    entry_time: time,
    trade_date: date,
    period: int = 14,
) -> Optional[float]:
    """
    Calculate ATR(14) on M5 bars at the entry candle time.

    Replicates logic from 03_backtest/processor/secondary_analysis/m5_atr_stop_2/calculator.py:
    1. Filter M5 bars up to and including the entry candle
    2. Calculate True Range for each bar
    3. ATR = SMA of True Range over `period` bars

    Args:
        bars_m5: M5 DataFrame with OHLCV, datetime index (Eastern time)
        entry_time: Trade entry time (HH:MM:SS)
        trade_date: Trade date
        period: ATR lookback period (default 14)

    Returns:
        ATR value at entry, or None if insufficient data
    """
    if bars_m5 is None or bars_m5.empty:
        return None

    try:
        import pytz
        tz = pytz.timezone(DISPLAY_TIMEZONE)

        # Build entry datetime for filtering
        from datetime import datetime
        entry_dt = tz.localize(datetime.combine(trade_date, entry_time))

        # Filter bars up to and including entry time
        bars = bars_m5[bars_m5.index <= entry_dt].copy()

        if len(bars) < period + 1:
            logger.warning(
                f"Insufficient M5 bars for ATR({period}): "
                f"have {len(bars)}, need {period + 1}"
            )
            return None

        # Calculate True Range
        high = bars['high'].values
        low = bars['low'].values
        close = bars['close'].values

        # TR = max(H-L, |H-prev_close|, |L-prev_close|)
        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]  # First bar: use own close

        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(high - prev_close),
                np.abs(low - prev_close),
            ),
        )

        # ATR = SMA of last `period` True Range values
        atr_value = float(np.mean(tr[-period:]))

        return atr_value

    except Exception as e:
        logger.error(f"Error calculating M5 ATR: {e}")
        return None
