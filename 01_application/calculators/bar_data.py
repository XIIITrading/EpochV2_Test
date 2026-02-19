"""
Bar Data Calculator - Unified OHLC and Technical Level Calculations

Ported and consolidated from:
- 02_zone_system/03_bar_data/calculations/m1_metrics.py
- 02_zone_system/03_bar_data/calculations/w1_metrics.py
- 02_zone_system/03_bar_data/calculations/d1_metrics.py
- 02_zone_system/03_bar_data/calculations/on_calculator.py
- 02_zone_system/03_bar_data/calculations/atr_calculator.py
- 02_zone_system/03_bar_data/calculations/camarilla_calculator.py
"""
import logging
import calendar
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd
import pytz

from data import get_polygon_client, cache, get_cache_key
from core import BarData, OHLCData, CamarillaLevels
from config import CACHE_TTL_DAILY

logger = logging.getLogger(__name__)

# Eastern timezone for market time calculations
ET_TIMEZONE = ZoneInfo("America/New_York")


class BarDataCalculator:
    """
    Unified calculator for all bar data metrics.
    Calculates M1, W1, D1 OHLC, overnight, ATR, and Camarilla levels.
    """

    # Market hours in UTC (9:30 AM - 4:00 PM ET = 13:30 - 20:00 UTC during EST)
    MARKET_OPEN_UTC = (13, 30)   # 13:30 UTC
    MARKET_CLOSE_UTC = (20, 0)   # 20:00 UTC

    # Minimum trading days for period completeness
    MIN_MONTH_DAYS = 5
    MIN_WEEK_DAYS = 4

    def __init__(self):
        """Initialize calculator with Polygon client."""
        self.client = get_polygon_client()

    # =========================================================================
    # MONTHLY METRICS (M1)
    # =========================================================================

    def calculate_monthly_metrics(
        self,
        ticker: str,
        analysis_date: date
    ) -> Tuple[OHLCData, OHLCData]:
        """
        Calculate current and prior month OHLC.
        Uses prior closed month if current month has <5 trading days.

        Args:
            ticker: Stock symbol
            analysis_date: Reference date

        Returns:
            Tuple of (current_month_ohlc, prior_month_ohlc)
        """
        # Get current month range
        curr_start = analysis_date.replace(day=1)
        curr_end = analysis_date.replace(
            day=calendar.monthrange(analysis_date.year, analysis_date.month)[1]
        )

        # Fetch current month data
        df_current = self.client.fetch_daily_bars(ticker, curr_start, curr_end)

        # Check if current month is incomplete
        use_prior = len(df_current) < self.MIN_MONTH_DAYS

        if use_prior:
            # Use prior month as "current"
            prior_end = curr_start - timedelta(days=1)
            prior_start = prior_end.replace(day=1)
            df_current = self.client.fetch_daily_bars(ticker, prior_start, prior_end)
            curr_start, curr_end = prior_start, prior_end

            # Get month before that for "prior"
            prior_prior_end = prior_start - timedelta(days=1)
            prior_prior_start = prior_prior_end.replace(day=1)
            df_prior = self.client.fetch_daily_bars(ticker, prior_prior_start, prior_prior_end)
        else:
            # Normal prior month
            prior_end = curr_start - timedelta(days=1)
            prior_start = prior_end.replace(day=1)
            df_prior = self.client.fetch_daily_bars(ticker, prior_start, prior_end)

        current_ohlc = self._df_to_ohlc(df_current)
        prior_ohlc = self._df_to_ohlc(df_prior)

        return current_ohlc, prior_ohlc

    # =========================================================================
    # WEEKLY METRICS (W1)
    # =========================================================================

    def calculate_weekly_metrics(
        self,
        ticker: str,
        analysis_date: date
    ) -> Tuple[OHLCData, OHLCData]:
        """
        Calculate current and prior week OHLC.
        Uses prior closed week if current week has <4 trading days.

        Args:
            ticker: Stock symbol
            analysis_date: Reference date

        Returns:
            Tuple of (current_week_ohlc, prior_week_ohlc)
        """
        # Get current week range (Monday to Sunday)
        days_since_monday = analysis_date.weekday()
        curr_start = analysis_date - timedelta(days=days_since_monday)
        curr_end = curr_start + timedelta(days=6)

        # Fetch current week data
        df_current = self.client.fetch_daily_bars(ticker, curr_start, curr_end)

        # Check if current week is incomplete
        use_prior = len(df_current) < self.MIN_WEEK_DAYS

        if use_prior:
            # Use prior week as "current"
            prior_start = curr_start - timedelta(days=7)
            prior_end = curr_start - timedelta(days=1)
            df_current = self.client.fetch_daily_bars(ticker, prior_start, prior_end)
            curr_start, curr_end = prior_start, prior_end

            # Get week before that for "prior"
            prior_prior_start = prior_start - timedelta(days=7)
            prior_prior_end = prior_start - timedelta(days=1)
            df_prior = self.client.fetch_daily_bars(ticker, prior_prior_start, prior_prior_end)
        else:
            # Normal prior week
            prior_start = curr_start - timedelta(days=7)
            prior_end = curr_start - timedelta(days=1)
            df_prior = self.client.fetch_daily_bars(ticker, prior_start, prior_end)

        current_ohlc = self._df_to_ohlc(df_current)
        prior_ohlc = self._df_to_ohlc(df_prior)

        return current_ohlc, prior_ohlc

    # =========================================================================
    # DAILY METRICS (D1)
    # =========================================================================

    def calculate_daily_metrics(
        self,
        ticker: str,
        analysis_date: date
    ) -> Tuple[OHLCData, OHLCData]:
        """
        Calculate current and prior day OHLC from minute bars.

        Args:
            ticker: Stock symbol
            analysis_date: Reference date

        Returns:
            Tuple of (current_day_ohlc, prior_day_ohlc)
        """
        # Fetch minute data for current day
        df_current = self.client.fetch_minute_bars(ticker, analysis_date, analysis_date)

        # Find prior trading day
        prior_date = self._get_prior_trading_day(ticker, analysis_date)
        if prior_date:
            df_prior = self.client.fetch_minute_bars(ticker, prior_date, prior_date)
        else:
            df_prior = pd.DataFrame()

        current_ohlc = self._df_to_ohlc(df_current)
        prior_ohlc = self._df_to_ohlc(df_prior)

        return current_ohlc, prior_ohlc

    # =========================================================================
    # OVERNIGHT METRICS
    # =========================================================================

    def calculate_overnight_metrics(
        self,
        ticker: str,
        analysis_date: date
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate overnight high and low.
        Time range: 20:00 UTC prior day to 12:00 UTC current day.

        Args:
            ticker: Stock symbol
            analysis_date: Reference date

        Returns:
            Tuple of (overnight_high, overnight_low)
        """
        # Build time range using milliseconds for Polygon API
        prior_day = analysis_date - timedelta(days=1)
        start_time = datetime(
            prior_day.year, prior_day.month, prior_day.day,
            20, 0, 0, tzinfo=timezone.utc
        )
        end_time = datetime(
            analysis_date.year, analysis_date.month, analysis_date.day,
            12, 0, 0, tzinfo=timezone.utc
        )

        # Fetch 5-minute bars for overnight session
        df = self.client.fetch_minute_bars(
            ticker,
            prior_day,
            analysis_date,
            multiplier=5
        )

        if df.empty:
            return None, None

        # Filter to overnight time range
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        if df['timestamp'].dt.tz is None:
            df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')

        mask = (df['timestamp'] >= start_time) & (df['timestamp'] <= end_time)
        df_overnight = df[mask]

        if df_overnight.empty:
            return None, None

        overnight_high = float(df_overnight['high'].max())
        overnight_low = float(df_overnight['low'].min())

        return overnight_high, overnight_low

    # =========================================================================
    # ATR CALCULATIONS
    # =========================================================================

    def calculate_d1_atr(self, ticker: str, analysis_date: date, period: int = 24) -> Optional[float]:
        """
        Calculate daily ATR using Simple Average Range.

        Matches Excel system (atr_calculator.py):
        - Uses simple range (High - Low) for each bar
        - Averages over 24 daily bars
        - Uses prior trading day as end date

        Args:
            ticker: Stock symbol
            analysis_date: Reference date
            period: ATR lookback period (default 24 bars to match Excel)

        Returns:
            ATR value, or None if calculation fails
        """
        # Get prior trading day (same as Excel: adjust for weekends)
        prior_date = analysis_date - timedelta(days=1)
        if prior_date.weekday() == 6:  # Sunday -> Friday
            prior_date -= timedelta(days=2)
        elif prior_date.weekday() == 5:  # Saturday -> Friday
            prior_date -= timedelta(days=1)

        # Fetch 24 daily bars ending at prior_date (Excel uses 40 days lookback to get 24 bars)
        start_date = prior_date - timedelta(days=40)
        df = self.client.fetch_daily_bars(ticker, start_date, prior_date)

        if df.empty:
            return None

        # Take the most recent 24 bars (Excel: sort="desc", limit=24)
        df = df.tail(period)

        if df.empty:
            return None

        # Calculate simple average range (Excel: sum(high - low) / count)
        ranges = df['high'] - df['low']
        return float(ranges.mean())

    def calculate_h1_atr(
        self,
        ticker: str,
        analysis_date: date,
        utc_hour: int = 11
    ) -> Optional[float]:
        """Calculate hourly ATR from 24 hourly bars before specified UTC hour."""
        start_date = analysis_date - timedelta(days=4)
        df = self.client.fetch_hourly_bars(ticker, start_date, analysis_date)

        if df.empty:
            return None

        # Filter to bars before anchor time
        anchor = datetime(
            analysis_date.year, analysis_date.month, analysis_date.day,
            utc_hour, 0, 0, tzinfo=timezone.utc
        )

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        if df['timestamp'].dt.tz is None:
            df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')

        df = df[df['timestamp'] <= anchor].tail(24)
        return self._calculate_atr_from_df(df)

    def calculate_m15_atr(self, ticker: str, analysis_date: date) -> Optional[float]:
        """Calculate M15 ATR from prior trading day's market hours."""
        return self._calculate_intraday_atr(ticker, analysis_date, multiplier=15)

    def calculate_m5_atr(self, ticker: str, analysis_date: date) -> Optional[float]:
        """Calculate M5 ATR from prior trading day's market hours."""
        return self._calculate_intraday_atr(ticker, analysis_date, multiplier=5)

    def calculate_m1_atr(self, ticker: str, analysis_date: date) -> Optional[float]:
        """Calculate M1 ATR from prior trading day's market hours."""
        return self._calculate_intraday_atr(ticker, analysis_date, multiplier=1)

    def _calculate_intraday_atr(
        self,
        ticker: str,
        analysis_date: date,
        multiplier: int
    ) -> Optional[float]:
        """Calculate intraday ATR for market hours only."""
        # Try up to 5 days back to find a valid trading day
        for days_back in range(1, 6):
            prior_date = analysis_date - timedelta(days=days_back)

            # Skip weekends
            if prior_date.weekday() >= 5:
                continue

            df = self.client.fetch_minute_bars(
                ticker, prior_date, prior_date, multiplier=multiplier
            )

            if df.empty:
                continue

            # Filter to market hours (13:30 - 20:00 UTC)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            if df['timestamp'].dt.tz is None:
                df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')

            market_open_minutes = self.MARKET_OPEN_UTC[0] * 60 + self.MARKET_OPEN_UTC[1]
            market_close_minutes = self.MARKET_CLOSE_UTC[0] * 60 + self.MARKET_CLOSE_UTC[1]

            df['time_minutes'] = df['timestamp'].dt.hour * 60 + df['timestamp'].dt.minute
            df_market = df[
                (df['time_minutes'] >= market_open_minutes) &
                (df['time_minutes'] <= market_close_minutes)
            ]

            if not df_market.empty:
                return self._calculate_atr_from_df(df_market)

        return None

    def _calculate_atr_from_df(self, df: pd.DataFrame) -> Optional[float]:
        """
        Calculate ATR from DataFrame using True Range (SWH-6 standardization).

        True Range = max(high - low, |high - prev_close|, |low - prev_close|)
        ATR = mean of True Range values
        """
        if df.empty:
            return None
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        n = len(high)
        if n < 2:
            return float(high[0] - low[0]) if n == 1 else None
        tr = [high[0] - low[0]]  # First bar: simple range (no prev close)
        for i in range(1, n):
            tr.append(max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            ))
        return float(sum(tr) / len(tr))

    # =========================================================================
    # CAMARILLA PIVOTS
    # =========================================================================

    def calculate_camarilla_levels(
        self,
        ticker: str,
        analysis_date: date
    ) -> Tuple[CamarillaLevels, CamarillaLevels, CamarillaLevels]:
        """
        Calculate Camarilla pivot levels for D1, W1, M1 timeframes.

        Camarilla Formula:
        - Range = High - Low
        - S3/R3 = Close ± (Range × 0.500)
        - S4/R4 = Close ± (Range × 0.618)
        - S6/R6 = Close ± (Range × 1.000)

        Args:
            ticker: Stock symbol
            analysis_date: Reference date

        Returns:
            Tuple of (daily_cam, weekly_cam, monthly_cam)
        """
        # Daily Camarilla
        daily_ohlc = self._get_prior_period_ohlc(ticker, analysis_date, 'daily')
        daily_cam = self._calc_cam_from_ohlc(daily_ohlc)

        # Weekly Camarilla
        weekly_ohlc = self._get_prior_period_ohlc(ticker, analysis_date, 'weekly')
        weekly_cam = self._calc_cam_from_ohlc(weekly_ohlc)

        # Monthly Camarilla
        monthly_ohlc = self._get_prior_period_ohlc(ticker, analysis_date, 'monthly')
        monthly_cam = self._calc_cam_from_ohlc(monthly_ohlc)

        return daily_cam, weekly_cam, monthly_cam

    def _get_prior_period_ohlc(
        self,
        ticker: str,
        analysis_date: date,
        timeframe: str
    ) -> Optional[Dict[str, float]]:
        """Get prior period OHLC for Camarilla calculations."""
        if timeframe == 'daily':
            prior_date = self._get_prior_trading_day(ticker, analysis_date)
            if not prior_date:
                return None
            df = self.client.fetch_daily_bars(ticker, prior_date, prior_date)

        elif timeframe == 'weekly':
            # Get prior complete week
            start = analysis_date - timedelta(days=30)
            df = self.client.fetch_weekly_bars(ticker, start, analysis_date)
            if len(df) >= 2:
                df = df.iloc[[-2]]  # Second to last = prior complete week
            elif len(df) == 1:
                pass  # Use the only week we have
            else:
                return None

        elif timeframe == 'monthly':
            # Get prior complete month
            start = analysis_date - timedelta(days=120)
            df = self.client.fetch_monthly_bars(ticker, start, analysis_date)
            if len(df) >= 2:
                df = df.iloc[[-2]]  # Second to last = prior complete month
            elif len(df) == 1:
                pass  # Use the only month we have
            else:
                return None
        else:
            return None

        if df.empty:
            return None

        return {
            'high': float(df.iloc[-1]['high']),
            'low': float(df.iloc[-1]['low']),
            'close': float(df.iloc[-1]['close'])
        }

    def _calc_cam_from_ohlc(self, ohlc: Optional[Dict[str, float]]) -> CamarillaLevels:
        """Calculate Camarilla levels from OHLC data."""
        if not ohlc:
            return CamarillaLevels()

        high, low, close = ohlc['high'], ohlc['low'], ohlc['close']
        price_range = high - low

        return CamarillaLevels(
            s6=round(close - (price_range * 1.000), 2),
            s4=round(close - (price_range * 0.618), 2),
            s3=round(close - (price_range * 0.500), 2),
            r3=round(close + (price_range * 0.500), 2),
            r4=round(close + (price_range * 0.618), 2),
            r6=round(close + (price_range * 1.000), 2)
        )

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _df_to_ohlc(self, df: pd.DataFrame) -> OHLCData:
        """Convert DataFrame to OHLCData object."""
        if df.empty:
            return OHLCData()

        return OHLCData(
            open=float(df.iloc[0]['open']),
            high=float(df['high'].max()),
            low=float(df['low'].min()),
            close=float(df.iloc[-1]['close'])
        )

    def _get_prior_trading_day(
        self,
        ticker: str,
        reference_date: date
    ) -> Optional[date]:
        """Find the previous trading day before the given date."""
        for i in range(1, 10):
            check_date = reference_date - timedelta(days=i)

            # Skip weekends
            if check_date.weekday() >= 5:
                continue

            df = self.client.fetch_daily_bars(ticker, check_date, check_date)
            if not df.empty:
                return check_date

        return None

    def get_price_at_timestamp(
        self,
        ticker: str,
        end_timestamp: datetime
    ) -> Optional[float]:
        """
        Get the closing price at a specific timestamp.

        Args:
            ticker: Stock symbol
            end_timestamp: Cutoff timestamp (timezone-aware)

        Returns:
            Close price of the last bar before the timestamp
        """
        # Fetch hourly data up to end_timestamp
        start_date = end_timestamp.date() - timedelta(days=1)
        df = self.client.fetch_hourly_bars(
            ticker, start_date, end_timestamp=end_timestamp
        )

        if df.empty:
            logger.warning(f"No price data for {ticker} at {end_timestamp}")
            return None

        return float(df.iloc[-1]['close'])


# =========================================================================
# UNIFIED CALCULATION FUNCTION
# =========================================================================

def calculate_bar_data(
    ticker: str,
    analysis_date: date,
    price: Optional[float] = None,
    end_timestamp: datetime = None
) -> BarData:
    """
    Calculate all bar data metrics for a ticker.

    This is the main entry point that calculates:
    - Monthly OHLC (current and prior)
    - Weekly OHLC (current and prior)
    - Daily OHLC (current and prior)
    - Overnight high/low
    - ATR values (M5, M15, H1, D1)
    - Camarilla pivot levels (D1, W1, M1)

    Args:
        ticker: Stock symbol
        analysis_date: Reference date for calculations
        price: Current price (fetched if not provided)
        end_timestamp: Optional precise end timestamp for pre/post market mode

    Returns:
        BarData object with all calculated metrics
    """
    calc = BarDataCalculator()
    ticker = ticker.upper()

    # Get price at specific timestamp if end_timestamp provided, otherwise get current
    if price is None:
        if end_timestamp is not None:
            price = calc.get_price_at_timestamp(ticker, end_timestamp)
            if price is None:
                price = 0.0
        else:
            price = calc.client.get_current_price(ticker)
            if price is None:
                price = 0.0

    # Generate ticker_id
    ticker_id = f"{ticker}_{analysis_date.strftime('%m%d%y')}"

    # Calculate all metrics
    logger.info(f"Calculating bar data for {ticker} on {analysis_date}")

    # Monthly
    m1_current, m1_prior = calc.calculate_monthly_metrics(ticker, analysis_date)

    # Weekly
    w1_current, w1_prior = calc.calculate_weekly_metrics(ticker, analysis_date)

    # Daily
    d1_current, d1_prior = calc.calculate_daily_metrics(ticker, analysis_date)

    # Overnight
    overnight_high, overnight_low = calc.calculate_overnight_metrics(ticker, analysis_date)

    # ATR values
    m1_atr = calc.calculate_m1_atr(ticker, analysis_date)
    m5_atr = calc.calculate_m5_atr(ticker, analysis_date)
    m15_atr = calc.calculate_m15_atr(ticker, analysis_date)
    h1_atr = calc.calculate_h1_atr(ticker, analysis_date)
    d1_atr = calc.calculate_d1_atr(ticker, analysis_date)

    # Camarilla levels
    cam_daily, cam_weekly, cam_monthly = calc.calculate_camarilla_levels(ticker, analysis_date)

    # Build BarData object
    bar_data = BarData(
        ticker=ticker,
        ticker_id=ticker_id,
        analysis_date=analysis_date,
        price=price,
        # Monthly
        m1_current=m1_current,
        m1_prior=m1_prior,
        # Weekly
        w1_current=w1_current,
        w1_prior=w1_prior,
        # Daily
        d1_current=d1_current,
        d1_prior=d1_prior,
        # Overnight
        overnight_high=overnight_high,
        overnight_low=overnight_low,
        # ATR
        m1_atr=m1_atr,
        m5_atr=m5_atr,
        m15_atr=m15_atr,
        h1_atr=h1_atr,
        d1_atr=d1_atr,
        # Camarilla
        camarilla_daily=cam_daily,
        camarilla_weekly=cam_weekly,
        camarilla_monthly=cam_monthly
    )

    logger.info(f"Bar data calculation complete for {ticker}")
    return bar_data
