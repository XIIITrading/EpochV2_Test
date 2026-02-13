"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 03: SHARED INDICATORS
Centralized Configuration
XIII Trading LLC
================================================================================

Single source of truth for all indicator parameters.
All modules should import from here instead of defining their own constants.

================================================================================
"""

# =============================================================================
# CANDLE RANGE CONFIGURATION (from EPCH Indicators v1.0)
# =============================================================================
CANDLE_RANGE_CONFIG = {
    "absorption_threshold": 0.12,  # Below this = absorption zone (SKIP)
    "normal_threshold": 0.15,      # Above this = has momentum (TAKE)
    "high_threshold": 0.20,        # Strong signal threshold
}

# =============================================================================
# SMA CONFIGURATION
# =============================================================================
SMA_CONFIG = {
    "fast_period": 9,
    "slow_period": 21,
    "momentum_lookback": 10,
    "widening_threshold": 1.1,
    "narrowing_threshold": 0.9,
    "wide_spread_threshold": 0.15,  # Wide spread threshold (percentage)
}

# =============================================================================
# VOLUME ROC CONFIGURATION (from EPCH Indicators v1.0)
# =============================================================================
VOLUME_ROC_CONFIG = {
    "baseline_period": 20,
    "elevated_threshold": 30,      # Elevated volume (momentum confirmation)
    "high_threshold": 50,          # High volume (strong momentum)
    # Legacy thresholds for health score classification
    "above_avg_threshold": 30,     # Aligned with elevated_threshold
    "below_avg_threshold": -20,
}

# =============================================================================
# VOLUME DELTA CONFIGURATION (from EPCH Indicators v1.0)
# =============================================================================
VOLUME_DELTA_CONFIG = {
    "rolling_period": 5,
    "magnitude_threshold": 100000,  # High magnitude threshold for scoring
}

# =============================================================================
# CVD (CUMULATIVE VOLUME DELTA) CONFIGURATION
# =============================================================================
CVD_CONFIG = {
    "window": 15,
    "rising_threshold": 0.1,
    "falling_threshold": -0.1,
}

# =============================================================================
# ATR CONFIGURATION
# =============================================================================
ATR_CONFIG = {
    "period": 14,
}

# =============================================================================
# MARKET STRUCTURE CONFIGURATION (from EPCH Indicators v1.0)
# =============================================================================
STRUCTURE_CONFIG = {
    "lookback": 5,             # Number of bars for structure analysis
    "fractal_length": 5,       # Fractal detection window (for advanced method)
    "use_simple_method": True, # True = half-bar comparison (reference), False = fractal
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
    },
    "weights": {
        "h4_structure": 1.0,
        "h1_structure": 1.0,
        "m15_structure": 1.0,
        "m5_structure": 1.0,
        "volume_roc": 1.0,
        "volume_delta": 1.0,
        "cvd": 1.0,
        "sma_alignment": 1.0,
        "sma_momentum": 1.0,
        "vwap": 1.0,
    }
}

# =============================================================================
# TIMEZONE
# =============================================================================
DISPLAY_TIMEZONE = "America/New_York"

# =============================================================================
# COMPOSITE SCORE CONFIGURATION (from EPCH Indicators v1.0)
# =============================================================================
SCORE_CONFIG = {
    "max_score": 7,
    "candle_range_threshold": CANDLE_RANGE_CONFIG["normal_threshold"],  # 0.15%
    "volume_roc_threshold": VOLUME_ROC_CONFIG["elevated_threshold"],    # 30%
    "volume_delta_magnitude": VOLUME_DELTA_CONFIG["magnitude_threshold"], # 100k
    "sma_spread_threshold": SMA_CONFIG["wide_spread_threshold"],        # 0.15%
    "h1_neutral_values": ["NEUT", "NEUTRAL"],  # H1 structure values that earn points
}

# =============================================================================
# HEALTH SCORE THRESHOLDS (used by health module)
# =============================================================================
THRESHOLDS = {
    "volume_roc": VOLUME_ROC_CONFIG["above_avg_threshold"],
    "cvd_slope": CVD_CONFIG["rising_threshold"],
}
