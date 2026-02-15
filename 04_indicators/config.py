"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR ANALYSIS v2.0
Configuration
XIII Trading LLC
================================================================================
"""
from pathlib import Path

# =============================================================================
# DATABASE CONFIGURATION
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
    "sslmode": "require",
}

# =============================================================================
# PATHS
# =============================================================================
MODULE_ROOT = Path(__file__).parent

# =============================================================================
# DATA TABLES (from 03_backtest pipeline)
# =============================================================================
TABLE_TRADES = "trades_2"
TABLE_M5_ATR = "m5_atr_stop_2"
TABLE_RAMP_UP = "m1_ramp_up_indicator_2"
TABLE_TRADE_IND = "m1_trade_indicator_2"
TABLE_POST_TRADE = "m1_post_trade_indicator_2"
TABLE_INDICATORS = "m1_indicator_bars_2"

# =============================================================================
# MODELS & LABELS
# =============================================================================
ENTRY_MODELS = {
    "EPCH1": "Continuation (Primary)",
    "EPCH2": "Rejection (Primary)",
    "EPCH3": "Continuation (Secondary)",
    "EPCH4": "Rejection (Secondary)",
}

DIRECTIONS = ["LONG", "SHORT"]
ZONE_TYPES = ["PRIMARY", "SECONDARY"]
OUTCOMES = ["Winners", "Losers"]

# =============================================================================
# INDICATOR CONFIGURATION
# =============================================================================
INDICATOR_LABELS = ['Candle %', 'Vol Delta', 'Vol ROC', 'SMA', 'CVD Slope',
                    'M5 Struct', 'M15 Struct', 'H1 Struct']

CONTINUOUS_INDICATORS = [
    'candle_range_pct',
    'vol_delta_roll',
    'vol_roc',
    'sma_spread_pct',
    'cvd_slope',
]

CATEGORICAL_INDICATORS = [
    'sma_config',
    'sma_momentum_label',
    'price_position',
    'm5_structure',
    'm15_structure',
    'h1_structure',
]

ALL_DEEP_DIVE_INDICATORS = [
    ('candle_range_pct', 'Candle Range %', 'continuous'),
    ('vol_delta_roll', 'Volume Delta (5-bar)', 'continuous'),
    ('vol_roc', 'Volume ROC', 'continuous'),
    ('sma_spread_pct', 'SMA Spread %', 'continuous'),
    ('cvd_slope', 'CVD Slope', 'continuous'),
    ('sma_config', 'SMA Configuration', 'categorical'),
    ('sma_momentum_label', 'SMA Momentum', 'categorical'),
    ('price_position', 'Price Position', 'categorical'),
    ('m5_structure', 'M5 Structure', 'categorical'),
    ('m15_structure', 'M15 Structure', 'categorical'),
    ('h1_structure', 'H1 Structure', 'categorical'),
]

# Thresholds for indicator coloring
THRESHOLDS = {
    'candle_range_pct': {
        'good': 0.15,
        'low': 0.12,
    },
    'vol_roc': {
        'elevated': 30.0,
        'normal': 0.0,
    },
    'sma_spread_pct': {
        'wide': 0.15,
    },
}

# =============================================================================
# RAMP-UP / POST-TRADE PARAMETERS
# =============================================================================
RAMP_UP_BARS = 25
POST_TRADE_BARS = 25
