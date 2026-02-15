"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
M1 Post-Trade Indicator Processor v2 - Configuration
XIII Trading LLC
================================================================================

Self-contained configuration for the m1_post_trade_indicator_2 processor.
Joins trades_2 + m5_atr_stop_2 + m1_indicator_bars_2 to build a 25-bar
post-trade view of indicators after each trade entry.

Data Sources (v2 tables):
- trades_2: Trade metadata (entry-only detection)
- m5_atr_stop_2: Trade outcomes (INNER JOIN - outcome required)
- m1_indicator_bars_2: Pre-computed M1 indicator values

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
    'm1_indicators': 'm1_indicator_bars_2',
}
TARGET_TABLE = "m1_post_trade_indicator_2"

# =============================================================================
# POST-TRADE PARAMETERS
# =============================================================================
POST_TRADE_BARS = 25  # Number of M1 bars after entry (including entry candle)

# =============================================================================
# INDICATOR COLUMNS TO PULL FROM m1_indicator_bars_2
# =============================================================================
INDICATOR_COLUMNS = [
    'open', 'high', 'low', 'close', 'volume',
    'candle_range_pct',
    'vol_delta_raw', 'vol_delta_roll',
    'vol_roc',
    'sma9', 'sma21', 'sma_config', 'sma_spread_pct',
    'sma_momentum_label', 'price_position',
    'cvd_slope',
    'm5_structure', 'm15_structure', 'h1_structure',
    'health_score', 'long_score', 'short_score',
]

# =============================================================================
# PROCESSING
# =============================================================================
BATCH_SIZE = 500  # Rows per execute_values batch
VERBOSE = True
