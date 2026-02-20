"""
Entry Qualifier Configuration
Epoch Trading System v1 - XIII Trading LLC

Configuration settings for the Entry Qualifier application.
"""

# Rolling window settings
ROLLING_BARS = 25
REFRESH_INTERVAL_MS = 60000  # 60 seconds
FETCH_DELAY_MS = 5000  # 5s delay after minute boundary for Polygon to finalize candle
VOL_DELTA_ROLL_PERIOD = 5
VOL_ROC_LOOKBACK = 20  # 20-bar lookback for volume ROC
M5_BARS_NEEDED = 50   # 50 M5 bars for structure analysis (~4 hours)
M15_BARS_NEEDED = 30  # 30 M15 bars for structure analysis (~7.5 hours)
H1_BARS_NEEDED = 25   # 25 H1 bars for structure analysis
MAX_TICKERS = 4

# Pre-population: fetch extra bars to ensure valid calculations
# Need 20 bars for VOL_ROC lookback + 25 display bars = 45 minimum
PREFETCH_BARS = 50

# UI Settings
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080

# Number formatting thresholds
MILLION_THRESHOLD = 1_000_000
THOUSAND_THRESHOLD = 1_000

# Color scheme (for reference - actual colors in styles.py)
COLORS = {
    'green': '#00C853',
    'yellow': '#FFD600',
    'red': '#FF1744',
    'gray': '#9E9E9E',
    'bg_green': '#1B5E20',
    'bg_yellow': '#F57F17',
    'bg_red': '#B71C1C',
}
