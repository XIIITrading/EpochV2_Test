"""
ATR Stop Calculator for Journal Trades
Epoch Trading System - XIII Trading LLC

Computes M1 ATR(14) and M5 ATR(14) stop prices, R-levels (R1-R5),
and R-level hit detection for journal trades at save time.

Matches backtest logic exactly:
    - ATR(14) = SMA of True Range over 14 bars
    - Stop distance = raw ATR (1x, no multiplier)
    - R-target: wick-based (high/low touch)
    - Stop: close-based
    - Same-candle conflict: stop wins

Usage:
    from core.atr_calculator import calculate_atr_stops

    result = calculate_atr_stops(
        ticker="MU", trade_date=date(2026, 2, 13),
        direction="SHORT", entry_price=404.05,
        entry_time=time(9, 30), exit_time=time(9, 31),
        bars_m1=bars_m1, bars_m5=bars_m5,
    )
    # result = {m1_atr_value: 0.35, m1_stop_price: 404.40, ...}
"""

import logging
from datetime import date, time, datetime, timedelta
from typing import Optional, Dict, Tuple

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Configuration
DISPLAY_TIMEZONE = 'America/New_York'
ATR_PERIOD = 14
EOD_CUTOFF = time(15, 30)
R_LEVELS = [1, 2, 3, 4, 5]


# =============================================================================
# Main Entry Point
# =============================================================================

def calculate_atr_stops(
    ticker: str,
    trade_date: date,
    direction: str,
    entry_price: float,
    entry_time: time,
    exit_time: Optional[time],
    bars_m1: pd.DataFrame,
    bars_m5: pd.DataFrame,
    callback=None,
) -> Dict:
    """
    Compute both M1 and M5 ATR stops + R-levels for a single trade.

    Args:
        ticker: Stock symbol
        trade_date: Trade date
        direction: "LONG" or "SHORT"
        entry_price: Trade entry price
        entry_time: Trade entry time
        exit_time: Trade exit time (or None for EOD)
        bars_m1: Pre-fetched M1 bars (shared across trades of same symbol)
        bars_m5: Pre-fetched M5 bars (shared across trades of same symbol)
        callback: Optional callable(message) for progress logging

    Returns:
        Dict with all M1 and M5 ATR columns ready to merge into trade row.
        Keys: m1_atr_value, m1_stop_price, m1_r1_price, ..., m5_atr_value, ...
    """
    result = _empty_result()

    # M1 ATR Stop
    m1_atr = _compute_atr(bars_m1, entry_time, trade_date, period=ATR_PERIOD)
    if m1_atr is not None and m1_atr > 0:
        m1_data = _compute_stop_and_r_levels(
            prefix='m1',
            atr_value=m1_atr,
            direction=direction,
            entry_price=entry_price,
            entry_time=entry_time,
            exit_time=exit_time,
            bars_m1=bars_m1,
            trade_date=trade_date,
        )
        result.update(m1_data)

        if callback:
            callback(
                f"  M1 ATR: ${m1_atr:.4f} | Stop: ${m1_data['m1_stop_price']:.2f} | "
                f"Max R: {m1_data['m1_max_r']}"
            )
    else:
        if callback:
            callback(f"  M1 ATR: insufficient bars")

    # M5 ATR Stop
    m5_atr = _compute_atr(bars_m5, entry_time, trade_date, period=ATR_PERIOD)
    if m5_atr is not None and m5_atr > 0:
        m5_data = _compute_stop_and_r_levels(
            prefix='m5',
            atr_value=m5_atr,
            direction=direction,
            entry_price=entry_price,
            entry_time=entry_time,
            exit_time=exit_time,
            bars_m1=bars_m1,
            trade_date=trade_date,
        )
        result.update(m5_data)

        if callback:
            callback(
                f"  M5 ATR: ${m5_atr:.4f} | Stop: ${m5_data['m5_stop_price']:.2f} | "
                f"Max R: {m5_data['m5_max_r']}"
            )
    else:
        if callback:
            callback(f"  M5 ATR: insufficient bars")

    return result


# =============================================================================
# ATR Calculation
# =============================================================================

def _compute_atr(
    bars: pd.DataFrame,
    entry_time: time,
    trade_date: date,
    period: int = 14,
) -> Optional[float]:
    """
    Calculate ATR on bars at the entry candle time.

    ATR(14) = Simple Moving Average of True Range over 14 bars.
    True Range = max(H-L, |H-prev_close|, |L-prev_close|)

    Args:
        bars: DataFrame with OHLCV, datetime index (any timeframe)
        entry_time: Entry time to compute ATR at
        trade_date: Trade date
        period: ATR lookback period

    Returns:
        ATR value, or None if insufficient data
    """
    if bars is None or bars.empty:
        return None

    try:
        import pytz
        tz = pytz.timezone(DISPLAY_TIMEZONE)

        entry_dt = tz.localize(datetime.combine(trade_date, entry_time))

        # Filter bars up to and including entry time
        filtered = bars[bars.index <= entry_dt]

        if len(filtered) < period + 1:
            return None

        high = filtered['high'].values
        low = filtered['low'].values
        close = filtered['close'].values

        # True Range
        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]

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
        logger.error(f"Error computing ATR: {e}")
        return None


# =============================================================================
# Stop + R-Level Computation + Hit Detection
# =============================================================================

def _compute_stop_and_r_levels(
    prefix: str,
    atr_value: float,
    direction: str,
    entry_price: float,
    entry_time: time,
    exit_time: Optional[time],
    bars_m1: pd.DataFrame,
    trade_date: date,
) -> Dict:
    """
    Compute stop price, R-level prices, and detect R-level hits.

    Args:
        prefix: 'm1' or 'm5' (column name prefix)
        atr_value: Computed ATR value
        direction: "LONG" or "SHORT"
        entry_price: Trade entry price
        entry_time: Trade entry time
        exit_time: Trade exit time (or None)
        bars_m1: M1 bars for R-level hit detection
        trade_date: Trade date

    Returns:
        Dict with prefixed keys (e.g., m5_atr_value, m5_stop_price, ...)
    """
    is_long = direction.upper() == 'LONG'
    stop_distance = atr_value

    # Stop and R-level prices
    if is_long:
        stop_price = entry_price - stop_distance
        r_prices = {n: entry_price + n * stop_distance for n in R_LEVELS}
    else:
        stop_price = entry_price + stop_distance
        r_prices = {n: entry_price - n * stop_distance for n in R_LEVELS}

    result = {
        f'{prefix}_atr_value': atr_value,
        f'{prefix}_stop_price': stop_price,
        f'{prefix}_stop_distance': stop_distance,
    }

    # R-level prices
    for n in R_LEVELS:
        result[f'{prefix}_r{n}_price'] = r_prices[n]

    # Initialize R-level hits
    for n in R_LEVELS:
        result[f'{prefix}_r{n}_hit'] = False
        result[f'{prefix}_r{n}_time'] = None

    result[f'{prefix}_stop_hit'] = False
    result[f'{prefix}_stop_hit_time'] = None
    result[f'{prefix}_max_r'] = 0
    result[f'{prefix}_pnl_r'] = None

    # Detect R-level hits from M1 bars
    if bars_m1 is not None and not bars_m1.empty:
        hits = _detect_r_hits(
            bars_m1=bars_m1,
            direction=direction,
            entry_time=entry_time,
            exit_time=exit_time,
            stop_price=stop_price,
            r_prices=r_prices,
            trade_date=trade_date,
        )
        result.update({f'{prefix}_{k}': v for k, v in hits.items()})

    # Compute PnL in R terms from actual exit
    if exit_time is not None and stop_distance > 0:
        # We need the exit price but don't have it here directly.
        # The caller will compute pnl_r from the trade's actual exit price.
        pass

    return result


def _detect_r_hits(
    bars_m1: pd.DataFrame,
    direction: str,
    entry_time: time,
    exit_time: Optional[time],
    stop_price: float,
    r_prices: Dict[int, float],
    trade_date: date,
) -> Dict:
    """
    Walk M1 bars to detect R-level hits and stop trigger.

    Matches backtest logic exactly:
    - R-target: LONG -> bar.high >= r_price, SHORT -> bar.low <= r_price
    - Stop: LONG -> bar.close <= stop_price, SHORT -> bar.close >= stop_price
    - Same-candle conflict: stop wins (R hits on that bar invalidated)
    - Walk stops at stop trigger or end of window

    Returns:
        Dict with unprefixed keys: r1_hit, r1_time, ..., stop_hit, stop_hit_time, max_r
    """
    import pytz
    tz = pytz.timezone(DISPLAY_TIMEZONE)

    result = {}
    for n in R_LEVELS:
        result[f'r{n}_hit'] = False
        result[f'r{n}_time'] = None
    result['stop_hit'] = False
    result['stop_hit_time'] = None
    result['max_r'] = 0

    if entry_time is None:
        return result

    # Build time window
    entry_dt = tz.localize(datetime.combine(trade_date, entry_time))

    if exit_time:
        end_dt = tz.localize(datetime.combine(trade_date, exit_time))
    else:
        end_dt = tz.localize(datetime.combine(trade_date, EOD_CUTOFF))

    # Filter M1 bars within window
    window = bars_m1[(bars_m1.index >= entry_dt) & (bars_m1.index <= end_dt)]

    if window.empty:
        return result

    is_long = direction.upper() == 'LONG'
    stop_triggered = False

    for idx, bar in window.iterrows():
        bar_time = idx.time() if hasattr(idx, 'time') else None

        if stop_triggered:
            break

        # Check stop FIRST (same-candle conflict: stop wins)
        stop_on_this_bar = False
        if is_long:
            if bar['close'] <= stop_price:
                stop_on_this_bar = True
        else:
            if bar['close'] >= stop_price:
                stop_on_this_bar = True

        if stop_on_this_bar:
            result['stop_hit'] = True
            result['stop_hit_time'] = bar_time
            stop_triggered = True
            # Do NOT credit R-level hits on this bar (stop wins)
            break

        # Check R-levels (wick-based: high/low touch)
        for r_num in R_LEVELS:
            r_price = r_prices.get(r_num)
            if r_price is None:
                continue

            if result[f'r{r_num}_hit']:
                continue  # Already hit

            hit = False
            if is_long:
                hit = bar['high'] >= r_price
            else:
                hit = bar['low'] <= r_price

            if hit:
                result[f'r{r_num}_hit'] = True
                result[f'r{r_num}_time'] = bar_time

    # Compute max_r
    max_r = 0
    for r_num in range(5, 0, -1):
        if result[f'r{r_num}_hit']:
            max_r = r_num
            break

    result['max_r'] = max_r

    return result


# =============================================================================
# Helpers
# =============================================================================

def _empty_result() -> Dict:
    """Return a dict with all ATR columns set to None/defaults."""
    result = {}
    for prefix in ('m1', 'm5'):
        result[f'{prefix}_atr_value'] = None
        result[f'{prefix}_stop_price'] = None
        result[f'{prefix}_stop_distance'] = None
        for n in R_LEVELS:
            result[f'{prefix}_r{n}_price'] = None
            result[f'{prefix}_r{n}_hit'] = False
            result[f'{prefix}_r{n}_time'] = None
        result[f'{prefix}_stop_hit'] = False
        result[f'{prefix}_stop_hit_time'] = None
        result[f'{prefix}_max_r'] = 0
        result[f'{prefix}_pnl_r'] = None
    return result


def compute_pnl_r(
    direction: str,
    entry_price: float,
    exit_price: float,
    stop_distance: float,
) -> Optional[float]:
    """
    Compute PnL in R-multiples from actual trade exit.

    Args:
        direction: "LONG" or "SHORT"
        entry_price: Entry price
        exit_price: Exit price
        stop_distance: ATR stop distance (1R)

    Returns:
        PnL in R terms, or None if stop_distance is zero
    """
    if stop_distance is None or stop_distance <= 0:
        return None

    if direction.upper() == 'LONG':
        return (exit_price - entry_price) / stop_distance
    else:
        return (entry_price - exit_price) / stop_distance
