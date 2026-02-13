"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
M5 ATR Stop Processor v2 - Configuration
XIII Trading LLC
================================================================================

Self-contained configuration for the M5 ATR Stop calculation module.
Evaluates trades using M5 ATR as the stop distance (1R) and tracks
R-multiple targets (1R-5R) to determine win/loss outcomes.

Stop distance comes from atr_m5 (wider than M1 ATR), but the bar-by-bar
simulation still walks M1 bars from m1_bars_2 for maximum fidelity.

Data Sources (v2 tables):
- trades_2: Trade metadata (entry-only detection)
- m1_bars_2: Raw M1 OHLCV bars for bar-by-bar simulation
- m1_indicator_bars_2: Pre-computed atr_m5 at entry candle time

Version: 1.0.0
================================================================================
"""

from datetime import time
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
# TRADING SESSION TIMES (Eastern Time)
# =============================================================================
MARKET_OPEN = time(9, 30)      # Regular trading hours start
EOD_CUTOFF = time(15, 30)      # End of day cutoff for trade evaluation
MARKET_CLOSE = time(16, 0)     # Regular trading hours end

# =============================================================================
# R-LEVEL CONFIGURATION
# =============================================================================
R_LEVELS = [1, 2, 3, 4, 5]    # R-multiples to track

# =============================================================================
# TABLE CONFIGURATION (v2 tables)
# =============================================================================
SOURCE_TABLES = {
    'trades': 'trades_2',
    'm1_bars': 'm1_bars_2',
    'm1_indicator_bars': 'm1_indicator_bars_2',
}
TARGET_TABLE = "m5_atr_stop_2"

# =============================================================================
# LOGGING
# =============================================================================
VERBOSE = True
