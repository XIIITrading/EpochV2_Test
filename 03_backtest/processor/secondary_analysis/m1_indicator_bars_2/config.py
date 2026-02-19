"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
M1 Indicator Bars v2 - Configuration
XIII Trading LLC
================================================================================

Self-contained configuration for the M1 Indicator Bars v2 calculation module.
Reads raw M1 bars from m1_bars_2 (pre-fetched), computes entry qualifier
standard indicators + extended analysis, writes to m1_indicator_bars_2.

Key difference from v1: No Polygon API calls for M1 data. All M1 bars
come from the m1_bars_2 database table (populated by the m1_bars processor).
Structure detection still uses Polygon API for native HTF bars (M5/M15/H1/H4).

Version: 2.0.0
================================================================================
"""

from pathlib import Path

# =============================================================================
# MODULE PATHS
# =============================================================================
MODULE_DIR = Path(__file__).parent
SCHEMA_DIR = MODULE_DIR / "schema"

# =============================================================================
# SUPABASE CONFIGURATION
# =============================================================================
SUPABASE_HOST = "db.pdbmcskznoaiybdiobje.supabase.co"
SUPABASE_PORT = 5432
SUPABASE_DATABASE = "postgres"
SUPABASE_USER = "postgres"
SUPABASE_PASSWORD = "guid-saltation-covet"

# Connection dict for psycopg2.connect()
DB_CONFIG = {
    "host": SUPABASE_HOST,
    "port": SUPABASE_PORT,
    "database": SUPABASE_DATABASE,
    "user": SUPABASE_USER,
    "password": SUPABASE_PASSWORD,
    "sslmode": "require"
}

# =============================================================================
# POLYGON API CONFIGURATION
# (Only used for HTF structure detection - M5/M15/H1/H4 native bars)
# =============================================================================
POLYGON_API_KEY = "f4vzZl0gWXkv9hiKJprpsVRqbwrydf4_"
POLYGON_BASE_URL = "https://api.polygon.io"

# Rate limiting
API_DELAY = 0.0  # No delay needed for unlimited tier
API_RETRIES = 3
API_RETRY_DELAY = 1.0

# =============================================================================
# TABLE CONFIGURATION
# =============================================================================
SOURCE_TABLE = "trades_2"               # Get unique ticker+dates from here
M1_BARS_TABLE = "m1_bars_2"            # Read raw M1 bar data from here
TARGET_TABLE = "m1_indicator_bars_2"   # Write indicator bars here

# =============================================================================
# INDICATOR CALCULATION PARAMETERS
# =============================================================================

# SMA Configuration
SMA_FAST_PERIOD = 9
SMA_SLOW_PERIOD = 21
SMA_MOMENTUM_LOOKBACK = 10
SMA_WIDENING_THRESHOLD = 1.1  # Ratio indicating widening
SMA_NARROWING_THRESHOLD = 0.9  # Ratio indicating narrowing

# Volume ROC Configuration
VOLUME_ROC_BASELINE_PERIOD = 20

# Volume Delta Configuration
VOLUME_DELTA_ROLLING_PERIOD = 5

# CVD Configuration
CVD_WINDOW = 15

# ATR Configuration
ATR_PERIOD = 14

# Structure Configuration
FRACTAL_LENGTH = 5  # Bars on each side for fractal detection

# =============================================================================
# HEALTH SCORE THRESHOLDS
# =============================================================================
HEALTH_VOL_ROC_THRESHOLD = 50.0       # Volume ROC above this is healthy
HEALTH_CVD_SLOPE_THRESHOLD = 0.0      # CVD slope sign alignment
HEALTH_SMA_SPREAD_THRESHOLD = 0.0     # SMA spread sign for alignment

# =============================================================================
# STRUCTURE LABELS
# =============================================================================
STRUCTURE_LABELS = {
    1: 'BULL',
    -1: 'BEAR',
    0: 'NEUTRAL',
    None: 'ERROR'
}

# =============================================================================
# HTF BAR REQUIREMENTS (for structure detection)
# =============================================================================

# How many bars we need for each timeframe to calculate structure
HTF_BARS_NEEDED = {
    'M1': 100,   # ~1.5 hours of 1-min bars
    'M5': 100,   # ~8 hours of 5-min bars
    'M15': 100,  # ~25 hours of 15-min bars
    'H1': 100,   # ~100 hours of 1-hour bars
    'H4': 50,    # ~200 hours of 4-hour bars
}

# Lookback days for fetching HTF bars from Polygon
# M5/M15 need enough days to survive 3-day weekends + holiday gaps
# (e.g., Sat/Sun/Presidents' Day = 3 non-trading days before Tuesday open)
HTF_LOOKBACK_DAYS = {
    'M1': 1,
    'M5': 5,
    'M15': 10,
    'H1': 14,
    'H4': 30,
}

# =============================================================================
# BATCH CONFIGURATION
# =============================================================================
BATCH_INSERT_SIZE = 500  # Insert bars in batches of 500

# =============================================================================
# LOGGING
# =============================================================================
VERBOSE = True

# =============================================================================
# VERSION
# =============================================================================
CALCULATION_VERSION = "2.0"
