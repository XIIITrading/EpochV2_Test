"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
Trades M5 R Win Consolidation Processor v2 - Configuration
XIII Trading LLC
================================================================================

Self-contained configuration for the trades consolidation module.
Joins trades_2 + m5_atr_stop_2 into a single denormalized table
with derived fields for the 11_trade_reel highlight viewer.

Data Sources (v2 tables):
- trades_2: Trade metadata (entry-only detection) - zone_high, zone_low
- m5_atr_stop_2: M5 ATR stop outcomes with R-level tracking
- m1_bars_2: Raw M1 OHLCV bars for eod_price lookup

Version: 1.0.0
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
# TABLE CONFIGURATION (v2 tables)
# =============================================================================
SOURCE_TABLES = {
    'trades': 'trades_2',
    'm5_atr_stop': 'm5_atr_stop_2',
    'm1_bars': 'm1_bars_2',
}
TARGET_TABLE = "trades_m5_r_win_2"

# =============================================================================
# DERIVED FIELD CONSTANTS
# =============================================================================
OUTCOME_METHOD = "M5_ATR"

# =============================================================================
# LOGGING
# =============================================================================
VERBOSE = True
