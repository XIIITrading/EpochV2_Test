"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR EDGE TESTING v1.0
Configuration Settings
XIII Trading LLC
================================================================================

Centralized configuration for indicator edge testing module.
================================================================================
"""
from pathlib import Path
from datetime import time

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
    "sslmode": "require"
}

# =============================================================================
# STATISTICAL TEST THRESHOLDS
# =============================================================================
P_VALUE_THRESHOLD = 0.05       # Statistical significance threshold
EFFECT_SIZE_THRESHOLD = 3.0    # Minimum effect size (percentage points)
MIN_SAMPLE_SIZE_HIGH = 100     # HIGH confidence threshold
MIN_SAMPLE_SIZE_MEDIUM = 30    # MEDIUM confidence threshold

# =============================================================================
# INDICATOR REGISTRY
# =============================================================================
INDICATORS = {
    'candle_range': {
        'name': 'Candle Range',
        'description': 'Tests candle range thresholds and absorption zone filter',
        'tests': ['threshold', 'quintile', 'absorption']
    },
    'volume_delta': {
        'name': 'Volume Delta',
        'description': 'Tests volume delta sign, alignment, and magnitude',
        'tests': ['sign', 'alignment', 'magnitude', 'signed_quintile']
    },
    'volume_roc': {
        'name': 'Volume ROC',
        'description': 'Tests volume rate of change thresholds',
        'tests': ['threshold', 'quintile', 'elevated']
    },
    'cvd_slope': {
        'name': 'CVD Slope',
        'description': 'Tests cumulative volume delta slope direction',
        'tests': ['direction', 'alignment', 'category']
    },
    'sma_edge': {
        'name': 'SMA Analysis',
        'description': 'Tests SMA spread, momentum, and alignment',
        'tests': ['spread_magnitude', 'spread_direction', 'price_position']
    },
    'structure_edge': {
        'name': 'Market Structure',
        'description': 'Tests H1/M15/M5 structure direction and alignment',
        'tests': ['h1_direction', 'm15_direction', 'm5_direction', 'alignment', 'confluence']
    },
    'vwap_simple': {
        'name': 'VWAP Simple',
        'description': 'Tests VWAP position and alignment',
        'tests': ['position', 'alignment']
    }
}

# Default run order (strongest edges first)
DEFAULT_INDICATOR_ORDER = [
    'candle_range',     # Strongest - 18-29pp edge
    'structure_edge',   # Strong - 24-54pp edge on H1
    'cvd_slope',        # Strong for SHORT - 15-27pp edge
    'volume_delta',     # Good - 10-20pp edge
    'sma_edge',         # Good - 19-25pp edge
    'volume_roc',       # Moderate edge
    'vwap_simple'       # Paradoxical - on hold
]

# =============================================================================
# CANDLE RANGE THRESHOLDS
# =============================================================================
CANDLE_RANGE_CONFIG = {
    "absorption_threshold": 0.12,  # Below = absorption zone (SKIP)
    "normal_threshold": 0.15,      # Above = momentum (TAKE)
    "high_threshold": 0.20,        # Strong signal
}

# =============================================================================
# VOLUME DELTA THRESHOLDS
# =============================================================================
VOLUME_DELTA_CONFIG = {
    "rolling_period": 5,
    "magnitude_threshold": 100000,
}

# =============================================================================
# VOLUME ROC THRESHOLDS
# =============================================================================
VOLUME_ROC_CONFIG = {
    "baseline_period": 20,
    "elevated_threshold": 30,      # Elevated volume
    "high_threshold": 50,          # High volume
}

# =============================================================================
# CVD SLOPE THRESHOLDS
# =============================================================================
CVD_CONFIG = {
    "window": 15,
    "rising_threshold": 0.1,
    "falling_threshold": -0.1,
}

# =============================================================================
# SMA THRESHOLDS
# =============================================================================
SMA_CONFIG = {
    "fast_period": 9,
    "slow_period": 21,
    "wide_spread_threshold": 0.15,
}

# =============================================================================
# STRUCTURE THRESHOLDS
# =============================================================================
STRUCTURE_CONFIG = {
    "lookback": 5,
    "fractal_length": 5,
}

# =============================================================================
# HEALTH SCORE CONFIGURATION
# =============================================================================
HEALTH_CONFIG = {
    "max_score": 10,
    "labels": {
        "strong": {"min": 8, "max": 10, "label": "STRONG"},
        "moderate": {"min": 6, "max": 7, "label": "MODERATE"},
        "weak": {"min": 4, "max": 5, "label": "WEAK"},
        "critical": {"min": 0, "max": 3, "label": "CRITICAL"},
    }
}

# =============================================================================
# SEGMENTS FOR TESTING
# =============================================================================
SEGMENTS = [
    ("ALL", None, "Overall"),
    ("LONG", {"direction": "LONG"}, "Direction"),
    ("SHORT", {"direction": "SHORT"}, "Direction"),
    ("CONTINUATION", {"models": ["EPCH1", "EPCH3"]}, "Trade Type"),
    ("REJECTION", {"models": ["EPCH2", "EPCH4"]}, "Trade Type"),
    ("EPCH1", {"model": "EPCH1"}, "Model"),
    ("EPCH2", {"model": "EPCH2"}, "Model"),
    ("EPCH3", {"model": "EPCH3"}, "Model"),
    ("EPCH4", {"model": "EPCH4"}, "Model"),
]

# =============================================================================
# OUTPUT PATHS
# =============================================================================
MODULE_DIR = Path(__file__).parent
RESULTS_DIR = MODULE_DIR / "results"

# =============================================================================
# VERBOSE OUTPUT
# =============================================================================
VERBOSE = True
