"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 03: SHARED INDICATORS
Shared Data Types
XIII Trading LLC
================================================================================

Unified dataclasses for indicator results.
All modules should use these types for consistency.

================================================================================
"""

from dataclasses import dataclass
from typing import List, Optional


# =============================================================================
# CANDLE RANGE TYPES (EPCH Indicators v1.0)
# =============================================================================
@dataclass
class CandleRangeResult:
    """Candle range calculation result."""
    candle_range_pct: float
    classification: str  # 'ABSORPTION', 'LOW', 'NORMAL', 'HIGH'
    is_absorption: bool
    has_momentum: bool  # True if >= 0.15%


# =============================================================================
# VWAP TYPES
# =============================================================================
@dataclass
class VWAPResult:
    """VWAP calculation result."""
    vwap: Optional[float]
    price_diff: Optional[float]
    price_pct: Optional[float]
    side: Optional[str]  # 'ABOVE', 'BELOW', 'AT'


# =============================================================================
# SMA TYPES
# =============================================================================
@dataclass
class SMAResult:
    """SMA spread calculation result."""
    sma9: Optional[float]
    sma21: Optional[float]
    spread: Optional[float]
    alignment: Optional[str]  # 'BULLISH', 'BEARISH'
    cross_estimate: Optional[float]


@dataclass
class SMAMomentumResult:
    """SMA momentum calculation result."""
    spread_now: Optional[float]
    spread_prev: Optional[float]
    momentum: str  # 'WIDENING', 'NARROWING', 'FLAT'
    ratio: Optional[float]


# =============================================================================
# VOLUME DELTA TYPES
# =============================================================================
@dataclass
class VolumeDeltaResult:
    """Single bar volume delta result."""
    bar_delta: float
    bar_position: float
    delta_multiplier: float


@dataclass
class RollingDeltaResult:
    """Rolling volume delta result."""
    rolling_delta: float
    signal: str  # 'Bullish', 'Bearish', 'Neutral'
    bar_count: int


# =============================================================================
# VOLUME ROC TYPES
# =============================================================================
@dataclass
class VolumeROCResult:
    """Volume Rate of Change result."""
    roc: Optional[float]
    signal: str  # 'Above Avg', 'Below Avg', 'Average'
    current_volume: int
    baseline_avg: Optional[float]


# =============================================================================
# CVD TYPES
# =============================================================================
@dataclass
class CVDResult:
    """Cumulative Volume Delta slope result."""
    slope: float
    trend: str  # 'Rising', 'Falling', 'Flat'
    cvd_values: List[float]
    window_size: int


# =============================================================================
# ATR TYPES
# =============================================================================
@dataclass
class ATRResult:
    """ATR calculation result."""
    atr: Optional[float]
    true_range: Optional[float]
    period: int


# =============================================================================
# STRUCTURE TYPES
# =============================================================================
@dataclass
class StructureResult:
    """Market structure detection result."""
    structure: str  # 'BULL', 'BEAR', 'NEUTRAL'
    swing_high: Optional[float]
    swing_low: Optional[float]
    prev_swing_high: Optional[float]
    prev_swing_low: Optional[float]
    confidence: str  # 'HIGH', 'MEDIUM', 'LOW'


# =============================================================================
# HEALTH SCORE TYPES
# =============================================================================
@dataclass
class HealthScoreResult:
    """10-factor health score result."""
    score: int
    max_score: int
    label: str  # 'STRONG', 'MODERATE', 'WEAK', 'CRITICAL'
    h4_structure_healthy: bool = False
    h1_structure_healthy: bool = False
    m15_structure_healthy: bool = False
    m5_structure_healthy: bool = False
    volume_roc_healthy: bool = False
    volume_delta_healthy: bool = False
    cvd_healthy: bool = False
    sma_alignment_healthy: bool = False
    sma_momentum_healthy: bool = False
    vwap_healthy: bool = False
    htf_aligned: bool = False
    mtf_aligned: bool = False
    volume_aligned: bool = False
    indicator_aligned: bool = False

    @property
    def score_pct(self) -> float:
        """Return score as percentage."""
        return (self.score / self.max_score) * 100


# =============================================================================
# COMPOSITE SCORE TYPES (EPCH Indicators v1.0)
# =============================================================================
@dataclass
class ScoreResult:
    """Composite score calculation result for LONG and SHORT."""
    long_score: int
    short_score: int
    max_score: int = 7

    # Component breakdowns for LONG
    long_candle_points: int = 0
    long_h1_points: int = 0
    long_vol_roc_points: int = 0
    long_vol_delta_points: int = 0
    long_sma_points: int = 0

    # Component breakdowns for SHORT
    short_candle_points: int = 0
    short_h1_points: int = 0
    short_vol_roc_points: int = 0
    short_vol_delta_points: int = 0
    short_sma_points: int = 0
