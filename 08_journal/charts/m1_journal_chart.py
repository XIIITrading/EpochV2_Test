"""
Epoch Trading System - M1 Journal Action Chart Builder
1-minute candlestick: 30 bars before entry, full trade, 30 bars after last exit.

Journal-specific differences from trade_reel M1 chart:
  1. Window slicing: first_fill - 30 bars to last_fill + 30 bars
  2. DAS-style fill triangles: every fill (entry, add, exit) gets a marker
  3. R-level lines always drawn: all dotted/1px/30% opacity
  4. R diamonds only on hit levels (same as trade_reel)

Position-based rendering (fills_json):
  - ENTRY: large triangle (size=12), direction-colored
  - ADD: medium triangle (size=10), direction-colored
  - EXIT: medium triangle (size=10), opposite direction/color
  Falls back to legacy entry marker + exit_portions if no fills data.
"""

import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta, time
from typing import List, Optional
import pytz

import sys
from pathlib import Path

# Import Plotly theme from trade_reel
_TRADE_REEL_DIR = Path(__file__).resolve().parent.parent.parent / "11_trade_reel"
sys.path.insert(0, str(_TRADE_REEL_DIR))

from charts.theme import register_tv_dark_template  # noqa: F401 (registers on import)
from charts.volume_profile import add_volume_bars, CANDLE_DOMAIN_BOTTOM, VOL_CLEARANCE_FRAC

# Timezone
DISPLAY_TIMEZONE = 'America/New_York'
_TZ = pytz.timezone(DISPLAY_TIMEZONE)

# Chart colors (TradingView dark, matching trade_reel/config.py)
CHART_COLORS = {
    'candle_up': '#13534D',
    'candle_down': '#782A28',
    'bull': '#089981',
    'bear': '#F23645',
    'stop': '#F23645',
}

# R-level colors (specified in requirements)
R_COLORS = {
    1: '#4CAF50',   # Green
    2: '#2196F3',   # Blue
    3: '#FF9800',   # Orange
    4: '#9C27B0',   # Purple
    5: '#F44336',   # Red
}

# Zone POC styling
PRIMARY_COLOR = '#00BCD4'     # Cyan
SECONDARY_COLOR = '#DC143C'   # Crimson
POC_COLOR = '#FFFFFF'         # White (HVN fallback)
POC_OPACITY = 0.3
POC_WIDTH = 1.0
POC_DASH = 'dot'

# Window context
BARS_BEFORE_ENTRY = 30
BARS_AFTER_LAST_EXIT = 30


def build_m1_journal_chart(
    bars_m1: pd.DataFrame,
    highlight,          # JournalHighlight (duck-types HighlightTrade)
    zones: list = None,
    pocs: list = None,
) -> go.Figure:
    """
    Build M1 journal candlestick chart.

    Window: 30 bars before entry to 30 bars after last exit.
    Draws multiple exit triangles, all R-level lines (hit + unhit),
    and R-level diamond markers only on hit levels.

    Args:
        bars_m1: Full-day M1 DataFrame with OHLCV, datetime index
        highlight: JournalHighlight duck-typing HighlightTrade
        zones: Optional zone dicts with setup_type and hvn_poc keys
        pocs: Optional flat list of HVN POC prices (white dotted lines)

    Returns:
        Plotly Figure
    """
    fig = go.Figure()

    # Slice bars to the relevant window
    df = _slice_to_window(bars_m1, highlight)

    if not df.empty:
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            increasing_line_color=CHART_COLORS['candle_up'],
            decreasing_line_color=CHART_COLORS['candle_down'],
            increasing_fillcolor=CHART_COLORS['candle_up'],
            decreasing_fillcolor=CHART_COLORS['candle_down'],
            showlegend=False,
            name='M1',
        ))

    # Volume bars (TradingView-style, bottom of chart)
    if not df.empty:
        add_volume_bars(fig, df)

    # Zone POC lines + flat HVN POC lines
    _add_zone_poc_lines(fig, zones)
    _add_poc_lines(fig, pocs)

    # Fill markers -- DAS-style triangles for every fill (entry, add, exit)
    # Falls back to legacy entry + exit_portions if no fills data
    _add_fill_markers(fig, highlight)

    # R-level lines -- ALL R1-R5 drawn (hit=solid, unhit=dotted)
    _add_r_level_lines(fig, highlight)

    # R-level hit markers -- diamonds only on hit levels
    _add_r_hit_diamonds(fig, highlight)

    # Stop line
    if highlight.stop_price:
        fig.add_hline(
            y=highlight.stop_price,
            line_color=CHART_COLORS['stop'],
            line_width=1,
            line_dash='dash',
            opacity=0.5,
        )

    # Layout
    title_text = f"1-Minute  |  {highlight.ticker}  |  {highlight.date}"

    fig.update_layout(
        title=dict(text=title_text, font=dict(size=14), x=0.5, xanchor='center'),
        height=380,
        showlegend=False,
        margin=dict(l=10, r=60, t=45, b=30),
        xaxis_rangeslider_visible=False,
        yaxis=dict(domain=[CANDLE_DOMAIN_BOTTOM, 1.0]),
    )

    fig.update_xaxes(
        rangebreaks=[
            dict(bounds=["sat", "mon"]),
            dict(bounds=[20, 4], pattern="hour"),
        ],
        type='date',
        tickformat='%H:%M',
        tickangle=0,
        showgrid=False,
    )

    # Auto Y-range with 10px buffer
    y_range = _calc_y_range(df, 380, 10)
    if y_range:
        fig.update_yaxes(side='right', range=y_range)
    else:
        fig.update_yaxes(side='right')

    return fig


# =============================================================================
# Window Slicing
# =============================================================================

def _slice_to_window(
    bars_m1: pd.DataFrame,
    highlight,
) -> pd.DataFrame:
    """
    Slice M1 bars to window:
      - 30 bars before entry
      - All candles of the trade
      - 30 bars after the last exit time

    Fallback: 30 bars after entry if no exit time available.
    """
    if bars_m1.empty:
        return bars_m1

    entry_dt = _TZ.localize(datetime.combine(highlight.date, highlight.entry_time))
    start_dt = entry_dt - timedelta(minutes=BARS_BEFORE_ENTRY)

    # Determine last fill time from fills, exit_portions, or highlight.exit_time
    last_exit_time = _get_last_fill_time(highlight)

    if last_exit_time:
        last_exit_dt = _TZ.localize(datetime.combine(highlight.date, last_exit_time))
        end_dt = last_exit_dt + timedelta(minutes=BARS_AFTER_LAST_EXIT)
    else:
        # Fallback: entry + 30 bars
        end_dt = entry_dt + timedelta(minutes=BARS_BEFORE_ENTRY)

    # Slice
    mask = (bars_m1.index >= start_dt) & (bars_m1.index <= end_dt)
    sliced = bars_m1.loc[mask]

    # Safety: cap at 400 bars
    if len(sliced) > 400:
        sliced = sliced.head(400)

    return sliced


def _get_last_fill_time(highlight) -> Optional[time]:
    """
    Determine the last fill time from fills, exit_portions, or highlight.exit_time.
    Returns None if none are available.
    """
    # Try fills first (position-based: last fill of any type)
    fills = getattr(highlight, 'fills', None)
    if fills:
        times = []
        for f in fills:
            t = getattr(f, 'time', None)
            if t is None and isinstance(f, dict):
                t = f.get('time')
                if isinstance(t, str):
                    try:
                        t = datetime.strptime(t, '%H:%M:%S').time()
                    except (ValueError, TypeError):
                        t = None
            if t is not None:
                times.append(t)
        if times:
            return max(times)

    # Try exit_portions (FIFO legacy)
    exit_portions = getattr(highlight, 'exit_portions', None)
    if exit_portions:
        times = []
        for p in exit_portions:
            t = getattr(p, 'time', None)
            if t is None and isinstance(p, dict):
                t = p.get('time')
                if isinstance(t, str):
                    try:
                        t = datetime.strptime(t, '%H:%M:%S').time()
                    except (ValueError, TypeError):
                        t = None
            if t is not None:
                times.append(t)
        if times:
            return max(times)

    # Fall back to highlight.exit_time
    exit_time = getattr(highlight, 'exit_time', None)
    if exit_time:
        return exit_time

    return None


# =============================================================================
# Fill Markers (Position-Based: DAS-Style Triangles for Every Fill)
# =============================================================================

def _add_fill_markers(fig: go.Figure, highlight):
    """
    Draw DAS Trader-style triangles for every fill in the position.

    Uses highlight.fills (from fills_json) when available.
    Falls back to legacy entry marker + exit_portions if no fills data.

    Marker styling:
      ENTRY: large triangle (size=12), direction-colored, white border
      ADD:   medium triangle (size=10), direction-colored, white border
      EXIT:  medium triangle (size=10), opposite direction/color, white border
    """
    fills = getattr(highlight, 'fills', None) or []

    if fills:
        _add_position_fill_markers(fig, highlight, fills)
    else:
        # Legacy fallback: single entry marker + exit_portions
        _add_legacy_entry_marker(fig, highlight)
        _add_exit_markers(fig, highlight)


def _add_position_fill_markers(fig: go.Figure, highlight, fills: list):
    """
    Draw a triangle for each fill in fills_json.

    fills is a list of dicts: {"side","type","price","qty","time","position_after"}
    """
    is_long = highlight.direction in ('LONG', 'B')

    # Direction-colored markers for entries/adds
    entry_marker_symbol = 'triangle-up' if is_long else 'triangle-down'
    entry_color = CHART_COLORS['bull'] if is_long else CHART_COLORS['bear']

    # Opposite markers for exits
    exit_marker_symbol = 'triangle-down' if is_long else 'triangle-up'
    exit_color = CHART_COLORS['bear'] if is_long else CHART_COLORS['bull']

    for f in fills:
        # Extract fields (support both dict and object)
        f_type = f.get('type') if isinstance(f, dict) else getattr(f, 'fill_type', None)
        f_price = f.get('price') if isinstance(f, dict) else getattr(f, 'price', None)
        f_time = f.get('time') if isinstance(f, dict) else getattr(f, 'time', None)
        f_qty = f.get('qty') if isinstance(f, dict) else getattr(f, 'qty', None)
        f_pos = f.get('position_after') if isinstance(f, dict) else getattr(f, 'position_after', None)

        if f_price is None or f_time is None:
            continue

        # Parse string time if needed
        if isinstance(f_time, str):
            try:
                f_time = datetime.strptime(f_time, '%H:%M:%S').time()
            except (ValueError, TypeError):
                continue

        # Handle FillType enum values
        if hasattr(f_type, 'value'):
            f_type = f_type.value

        fill_dt = _TZ.localize(datetime.combine(highlight.date, f_time))

        if f_type in ('ENTRY', 'ADD'):
            marker_sym = entry_marker_symbol
            color = entry_color
            size = 6 if f_type == 'ENTRY' else 5
            label = "Entry" if f_type == 'ENTRY' else "Add"
        elif f_type == 'EXIT':
            marker_sym = exit_marker_symbol
            color = exit_color
            size = 5
            label = "Exit"
        else:
            continue

        hover = f"{label} ${f_price:.2f}"
        if f_qty:
            hover += f" x{f_qty}"
        if f_pos is not None:
            hover += f" (pos: {f_pos})"

        fig.add_trace(go.Scatter(
            x=[fill_dt],
            y=[f_price],
            mode='markers',
            marker=dict(
                symbol=marker_sym,
                size=size,
                color=color,
                line=dict(color='white', width=1),
            ),
            showlegend=False,
            hoverinfo='text',
            hovertext=hover,
        ))


def _add_legacy_entry_marker(fig: go.Figure, highlight):
    """Legacy single entry marker (used when fills_json is not available)."""
    if highlight.entry_time and highlight.entry_price:
        entry_dt = _TZ.localize(datetime.combine(highlight.date, highlight.entry_time))
        is_long = highlight.direction in ('LONG', 'B')
        entry_symbol = 'triangle-up' if is_long else 'triangle-down'
        entry_color = CHART_COLORS['bull'] if is_long else CHART_COLORS['bear']

        fig.add_trace(go.Scatter(
            x=[entry_dt],
            y=[highlight.entry_price],
            mode='markers',
            marker=dict(symbol=entry_symbol, size=6, color=entry_color,
                        line=dict(color='white', width=1)),
            showlegend=False,
            hoverinfo='text',
            hovertext=f"Entry ${highlight.entry_price:.2f}",
        ))


# =============================================================================
# Exit Markers (Legacy: Multiple Triangles from exit_portions)
# =============================================================================

def _add_exit_markers(fig: go.Figure, highlight):
    """
    Draw one exit triangle per partial exit from exit_portions.
    Falls back to a single exit marker at highlight.exit_price/exit_time.

    Exit triangles are the OPPOSITE direction of entry:
      LONG trade  => exit = triangle-down (closing a long)
      SHORT trade => exit = triangle-up   (covering a short)
    Color matches the closing action:
      LONG exit  = red (selling)
      SHORT exit = green (buying to cover)
    """
    is_long = highlight.direction in ('LONG', 'B')
    # Exit arrows oppose entry: LONG exit = sell (down/red), SHORT exit = cover (up/green)
    exit_symbol = 'triangle-down' if is_long else 'triangle-up'
    exit_color = CHART_COLORS['bear'] if is_long else CHART_COLORS['bull']

    exit_portions = getattr(highlight, 'exit_portions', None) or []

    # Parse exit_portions (can be list of objects, dicts, or JSON-parsed dicts)
    exits_drawn = False
    for p in exit_portions:
        p_price = getattr(p, 'price', None)
        p_time = getattr(p, 'time', None)

        # Dict fallback (e.g., from JSON)
        if p_price is None and isinstance(p, dict):
            p_price = p.get('price')
        if p_time is None and isinstance(p, dict):
            p_time = p.get('time')
            if isinstance(p_time, str):
                try:
                    p_time = datetime.strptime(p_time, '%H:%M:%S').time()
                except (ValueError, TypeError):
                    p_time = None

        if p_price and p_time and highlight.date:
            exit_dt = _TZ.localize(datetime.combine(highlight.date, p_time))
            p_qty = getattr(p, 'qty', None)
            if p_qty is None and isinstance(p, dict):
                p_qty = p.get('qty')

            hover = f"Exit ${p_price:.2f}"
            if p_qty:
                hover += f" x{p_qty}"

            fig.add_trace(go.Scatter(
                x=[exit_dt],
                y=[p_price],
                mode='markers',
                marker=dict(symbol=exit_symbol, size=10, color=exit_color,
                            line=dict(color='white', width=1)),
                showlegend=False,
                hoverinfo='text',
                hovertext=hover,
            ))
            exits_drawn = True

    # Fallback: single exit marker if no portions drawn
    if not exits_drawn:
        exit_price = getattr(highlight, 'exit_price', None)
        exit_time = getattr(highlight, 'exit_time', None)
        if exit_price and exit_time and highlight.date:
            exit_dt = _TZ.localize(datetime.combine(highlight.date, exit_time))
            fig.add_trace(go.Scatter(
                x=[exit_dt],
                y=[exit_price],
                mode='markers',
                marker=dict(symbol=exit_symbol, size=10, color=exit_color,
                            line=dict(color='white', width=1)),
                showlegend=False,
                hoverinfo='text',
                hovertext=f"Exit ${exit_price:.2f}",
            ))


# =============================================================================
# R-Level Lines (All R1-R5, hit + unhit styling)
# =============================================================================

def _add_r_level_lines(fig: go.Figure, highlight):
    """
    Draw ALL R1-R5 lines regardless of hit status.
    All lines: dotted, 1px width, 30% opacity.
    R-label annotation on the right.
    """
    r_levels = [
        (1, highlight.r1_price, highlight.r1_hit),
        (2, highlight.r2_price, highlight.r2_hit),
        (3, highlight.r3_price, highlight.r3_hit),
        (4, highlight.r4_price, highlight.r4_hit),
        (5, highlight.r5_price, highlight.r5_hit),
    ]

    for r_num, price, hit in r_levels:
        if not price:
            continue

        color = R_COLORS.get(r_num, '#787B86')

        fig.add_hline(
            y=price,
            line_color=color,
            line_width=1,
            line_dash='dot',
            opacity=0.3,
            annotation_text=f"R{r_num}",
            annotation_position="right",
            annotation_font_color=color,
            annotation_font_size=9,
        )


# =============================================================================
# R-Level Hit Diamonds (only on hit levels)
# =============================================================================

def _add_r_hit_diamonds(fig: go.Figure, highlight):
    """
    Draw diamond markers only on R-levels that were actually hit.
    Highest R gets a text label; all use small diamonds.
    """
    r_hits = [
        (1, highlight.r1_time, highlight.r1_price, highlight.r1_hit),
        (2, highlight.r2_time, highlight.r2_price, highlight.r2_hit),
        (3, highlight.r3_time, highlight.r3_price, highlight.r3_hit),
        (4, highlight.r4_time, highlight.r4_price, highlight.r4_hit),
        (5, highlight.r5_time, highlight.r5_price, highlight.r5_hit),
    ]

    for r_num, r_time, r_price, r_hit in r_hits:
        if r_hit and r_time and r_price:
            r_dt = _TZ.localize(datetime.combine(highlight.date, r_time))
            color = R_COLORS.get(r_num, '#787B86')
            is_highest = (r_num == highlight.max_r_achieved)

            fig.add_trace(go.Scatter(
                x=[r_dt],
                y=[r_price],
                mode='markers+text',
                marker=dict(
                    symbol='diamond',
                    size=7,
                    color=color,
                    line=dict(color='white', width=0.5),
                ),
                text=[f"R{r_num}" if is_highest else ''],
                textposition='top center',
                textfont=dict(color=color, size=11,
                              family='Arial Black'),
                showlegend=False,
                hovertext=f"R{r_num} hit at {r_time.strftime('%H:%M')} | ${r_price:.2f}",
                hoverinfo='text',
            ))


# =============================================================================
# Zone / POC Line Helpers
# =============================================================================

def _add_zone_poc_lines(fig: go.Figure, zones: Optional[list] = None):
    """
    Add zone HVN POC lines, color-coded by setup_type.
      - PRIMARY: cyan (#00BCD4) solid line
      - SECONDARY: crimson (#DC143C) solid line
    """
    if not zones:
        return

    for zone in zones:
        poc_price = zone.get('hvn_poc')
        if not poc_price or float(poc_price) <= 0:
            continue

        setup_type = (zone.get('setup_type') or '').upper()
        if setup_type == 'PRIMARY':
            color = PRIMARY_COLOR
        elif setup_type == 'SECONDARY':
            color = SECONDARY_COLOR
        else:
            color = POC_COLOR

        is_zone = setup_type in ('PRIMARY', 'SECONDARY')
        fig.add_hline(
            y=float(poc_price),
            line_color=color,
            line_width=POC_WIDTH,
            line_dash='solid' if is_zone else POC_DASH,
            opacity=1.0 if is_zone else POC_OPACITY,
        )


def _add_poc_lines(fig: go.Figure, pocs: Optional[list] = None):
    """
    Add flat HVN POC lines (white dotted, 30% opacity).
    """
    if not pocs:
        return

    for price in pocs:
        if price and float(price) > 0:
            fig.add_hline(
                y=float(price),
                line_color=POC_COLOR,
                line_width=POC_WIDTH,
                line_dash=POC_DASH,
                opacity=POC_OPACITY,
            )


# =============================================================================
# Y-Range Calculation
# =============================================================================

def _calc_y_range(df: pd.DataFrame, chart_height: int, buffer_px: int):
    """
    Calculate Y-axis range with pixel buffer and volume bar clearance.

    Extends the bottom of the y-range so the lowest candle sits above the
    volume bars (which occupy the bottom VOL_BAR_MAX_HEIGHT of the chart).
    Top gets a standard pixel buffer.
    """
    if df is None or df.empty:
        return None

    data_low = df['low'].min()
    data_high = df['high'].max()
    price_range = data_high - data_low

    if price_range <= 0:
        return None

    # Top buffer: convert pixels to price units
    usable_px = chart_height - 45 - 30
    if usable_px <= 0:
        usable_px = chart_height
    price_per_px = price_range / usable_px
    top_buffer = buffer_px * price_per_px

    # Bottom buffer: extend y-range so data_low maps to VOL_CLEARANCE_FRAC
    visible_range = price_range + top_buffer
    total_range = visible_range / (1.0 - VOL_CLEARANCE_FRAC)
    bottom_extension = total_range - visible_range

    return [data_low - bottom_extension, data_high + top_buffer]
