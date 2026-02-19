"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
M1 Trade Indicator Processor v2 - Configuration
XIII Trading LLC
================================================================================

Self-contained configuration for the m1_trade_indicator_2 processor.
Joins trades_2 + m5_atr_stop_2 + m1_indicator_bars_2 into a single
denormalized table with indicator values at the M1 bar just before entry.

Data Sources (v2 tables):
- trades_2: Trade metadata (entry-only detection)
- m5_atr_stop_2: Trade outcomes (result, max_r)
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
    'm1_indicators': 'm1_indicator_bars_2',
}
TARGET_TABLE = "m1_trade_indicator_2"

# =============================================================================
# INDICATOR COLUMNS TO PULL FROM m1_indicator_bars_2
# =============================================================================
INDICATOR_COLUMNS = [
    'open', 'high', 'low', 'close', 'volume',
    'candle_range_pct',
    'vol_delta_raw', 'vol_delta_roll', 'vol_delta_norm',
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
