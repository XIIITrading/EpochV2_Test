"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR EDGE TESTING v1.0
Individual Edge Test Functions
XIII Trading LLC
================================================================================

Contains test functions for each indicator type.
================================================================================
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from .base_tester import (
    EdgeTestResult,
    calculate_win_rates,
    chi_square_test,
    spearman_monotonic_test,
    get_confidence_level,
    determine_edge,
    calculate_candle_range,
    calculate_volume_delta_metrics,
    calculate_volume_roc_metrics,
    calculate_cvd_slope_metrics,
    calculate_sma_metrics,
    calculate_structure_metrics
)


# =============================================================================
# CANDLE RANGE TESTS
# =============================================================================

def test_candle_range_threshold(df: pd.DataFrame, segment: str = "ALL") -> EdgeTestResult:
    """Test if candle range threshold affects win rate."""
    df = calculate_candle_range(df)

    baseline_wr = df['is_winner'].mean() * 100

    # Create category
    from config import CANDLE_RANGE_CONFIG
    df['range_category'] = np.where(
        df['candle_range_pct'] < CANDLE_RANGE_CONFIG['absorption_threshold'], 'ABSORPTION',
        np.where(
            df['candle_range_pct'] >= CANDLE_RANGE_CONFIG['high_threshold'], 'HIGH',
            np.where(
                df['candle_range_pct'] >= CANDLE_RANGE_CONFIG['normal_threshold'], 'NORMAL', 'LOW'
            )
        )
    )

    groups = calculate_win_rates(df, 'range_category')
    chi2, p_value, effect_size = chi_square_test(df, 'range_category')

    min_group_size = min(g['trades'] for g in groups.values()) if groups else 0
    confidence = get_confidence_level(min_group_size)
    has_edge, recommendation = determine_edge(p_value, effect_size, confidence)

    return EdgeTestResult(
        indicator="Candle Range",
        test_name="Range Threshold Categories",
        segment=segment,
        has_edge=has_edge,
        p_value=p_value,
        effect_size=effect_size,
        groups=groups,
        baseline_win_rate=baseline_wr,
        confidence=confidence,
        test_type="chi_square",
        recommendation=recommendation,
        total_trades=len(df)
    )


def test_candle_range_quintile(df: pd.DataFrame, segment: str = "ALL") -> EdgeTestResult:
    """Test monotonic relationship between candle range quintiles and win rate."""
    df = calculate_candle_range(df)

    baseline_wr = df['is_winner'].mean() * 100
    groups = calculate_win_rates(df, 'range_quintile')

    quintile_order = ['Q1_Smallest', 'Q2', 'Q3', 'Q4', 'Q5_Largest']
    correlation, p_value, effect_size = spearman_monotonic_test(
        df, 'range_quintile', bucket_order=quintile_order
    )

    min_group_size = min(g['trades'] for g in groups.values()) if groups else 0
    confidence = get_confidence_level(min_group_size)
    has_edge, recommendation = determine_edge(p_value, effect_size, confidence)

    if has_edge:
        direction = "higher" if correlation > 0 else "lower"
        recommendation = f"EDGE DETECTED - {direction} range correlates with higher win rate (r={correlation:.3f})"

    return EdgeTestResult(
        indicator="Candle Range",
        test_name="Range Magnitude (Quintiles)",
        segment=segment,
        has_edge=has_edge,
        p_value=p_value,
        effect_size=effect_size,
        groups=groups,
        baseline_win_rate=baseline_wr,
        confidence=confidence,
        test_type="spearman",
        recommendation=recommendation,
        total_trades=len(df)
    )


def test_candle_range_absorption(df: pd.DataFrame, segment: str = "ALL") -> EdgeTestResult:
    """Test absorption zone filter effect."""
    df = calculate_candle_range(df)

    baseline_wr = df['is_winner'].mean() * 100

    df['absorption_category'] = np.where(df['is_absorption'], 'ABSORPTION', 'NORMAL')
    groups = calculate_win_rates(df, 'absorption_category')
    chi2, p_value, effect_size = chi_square_test(df, 'absorption_category')

    min_group_size = min(g['trades'] for g in groups.values()) if groups else 0
    confidence = get_confidence_level(min_group_size)
    has_edge, recommendation = determine_edge(p_value, effect_size, confidence)

    return EdgeTestResult(
        indicator="Candle Range",
        test_name="Absorption Zone Filter",
        segment=segment,
        has_edge=has_edge,
        p_value=p_value,
        effect_size=effect_size,
        groups=groups,
        baseline_win_rate=baseline_wr,
        confidence=confidence,
        test_type="chi_square",
        recommendation=recommendation,
        total_trades=len(df)
    )


# =============================================================================
# VOLUME DELTA TESTS
# =============================================================================

def test_vol_delta_sign(df: pd.DataFrame, segment: str = "ALL") -> EdgeTestResult:
    """Test POSITIVE vs NEGATIVE volume delta effect on win rate."""
    df = calculate_volume_delta_metrics(df)
    df_valid = df[df['vol_delta_sign'].notna()].copy()

    if len(df_valid) < 30:
        return _empty_result("Volume Delta", "Vol Delta Sign", segment, len(df_valid))

    baseline_wr = df_valid['is_winner'].mean() * 100
    groups = calculate_win_rates(df_valid, 'vol_delta_sign')
    chi2, p_value, effect_size = chi_square_test(df_valid, 'vol_delta_sign')

    min_group_size = min(g['trades'] for g in groups.values()) if groups else 0
    confidence = get_confidence_level(min_group_size)
    has_edge, recommendation = determine_edge(p_value, effect_size, confidence)

    return EdgeTestResult(
        indicator="Volume Delta",
        test_name="Vol Delta Sign (Pos/Neg)",
        segment=segment,
        has_edge=has_edge,
        p_value=p_value,
        effect_size=effect_size,
        groups=groups,
        baseline_win_rate=baseline_wr,
        confidence=confidence,
        test_type="chi_square",
        recommendation=recommendation,
        total_trades=len(df_valid)
    )


def test_vol_delta_alignment(df: pd.DataFrame, segment: str = "ALL") -> EdgeTestResult:
    """Test alignment between delta direction and trade direction."""
    df = calculate_volume_delta_metrics(df)
    df_valid = df[df['vol_delta_aligned_str'].notna()].copy()

    if len(df_valid) < 30:
        return _empty_result("Volume Delta", "Vol Delta Alignment", segment, len(df_valid))

    baseline_wr = df_valid['is_winner'].mean() * 100
    groups = calculate_win_rates(df_valid, 'vol_delta_aligned_str')
    chi2, p_value, effect_size = chi_square_test(df_valid, 'vol_delta_aligned_str')

    min_group_size = min(g['trades'] for g in groups.values()) if groups else 0
    confidence = get_confidence_level(min_group_size)
    has_edge, recommendation = determine_edge(p_value, effect_size, confidence)

    return EdgeTestResult(
        indicator="Volume Delta",
        test_name="Vol Delta Alignment",
        segment=segment,
        has_edge=has_edge,
        p_value=p_value,
        effect_size=effect_size,
        groups=groups,
        baseline_win_rate=baseline_wr,
        confidence=confidence,
        test_type="chi_square",
        recommendation=recommendation,
        total_trades=len(df_valid)
    )


def test_vol_delta_magnitude(df: pd.DataFrame, segment: str = "ALL") -> EdgeTestResult:
    """Test monotonic relationship between delta magnitude and win rate."""
    df = calculate_volume_delta_metrics(df)
    df_valid = df[df['vol_delta_quintile'].notna()].copy()

    if len(df_valid) < 30:
        return _empty_result("Volume Delta", "Vol Delta Magnitude", segment, len(df_valid))

    baseline_wr = df_valid['is_winner'].mean() * 100
    groups = calculate_win_rates(df_valid, 'vol_delta_quintile')

    quintile_order = ['Q1_Smallest', 'Q2', 'Q3', 'Q4', 'Q5_Largest']
    correlation, p_value, effect_size = spearman_monotonic_test(
        df_valid, 'vol_delta_quintile', bucket_order=quintile_order
    )

    min_group_size = min(g['trades'] for g in groups.values()) if groups else 0
    confidence = get_confidence_level(min_group_size)
    has_edge, recommendation = determine_edge(p_value, effect_size, confidence)

    if has_edge:
        direction = "higher" if correlation > 0 else "lower"
        recommendation = f"EDGE DETECTED - {direction} magnitude correlates with higher win rate (r={correlation:.3f})"

    return EdgeTestResult(
        indicator="Volume Delta",
        test_name="Vol Delta Magnitude (Quintiles)",
        segment=segment,
        has_edge=has_edge,
        p_value=p_value,
        effect_size=effect_size,
        groups=groups,
        baseline_win_rate=baseline_wr,
        confidence=confidence,
        test_type="spearman",
        recommendation=recommendation,
        total_trades=len(df_valid)
    )


# =============================================================================
# VOLUME ROC TESTS
# =============================================================================

def test_vol_roc_category(df: pd.DataFrame, segment: str = "ALL") -> EdgeTestResult:
    """Test volume ROC category effect on win rate."""
    df = calculate_volume_roc_metrics(df)
    df_valid = df[df['vol_roc_category'].notna()].copy()

    if len(df_valid) < 30:
        return _empty_result("Volume ROC", "Vol ROC Category", segment, len(df_valid))

    baseline_wr = df_valid['is_winner'].mean() * 100
    groups = calculate_win_rates(df_valid, 'vol_roc_category')
    chi2, p_value, effect_size = chi_square_test(df_valid, 'vol_roc_category')

    min_group_size = min(g['trades'] for g in groups.values()) if groups else 0
    confidence = get_confidence_level(min_group_size)
    has_edge, recommendation = determine_edge(p_value, effect_size, confidence)

    return EdgeTestResult(
        indicator="Volume ROC",
        test_name="Vol ROC Category",
        segment=segment,
        has_edge=has_edge,
        p_value=p_value,
        effect_size=effect_size,
        groups=groups,
        baseline_win_rate=baseline_wr,
        confidence=confidence,
        test_type="chi_square",
        recommendation=recommendation,
        total_trades=len(df_valid)
    )


def test_vol_roc_quintile(df: pd.DataFrame, segment: str = "ALL") -> EdgeTestResult:
    """Test monotonic relationship between volume ROC quintiles and win rate."""
    df = calculate_volume_roc_metrics(df)
    df_valid = df[df['vol_roc_quintile'].notna()].copy()

    if len(df_valid) < 30:
        return _empty_result("Volume ROC", "Vol ROC Quintile", segment, len(df_valid))

    baseline_wr = df_valid['is_winner'].mean() * 100
    groups = calculate_win_rates(df_valid, 'vol_roc_quintile')

    quintile_order = ['Q1_Lowest', 'Q2', 'Q3', 'Q4', 'Q5_Highest']
    correlation, p_value, effect_size = spearman_monotonic_test(
        df_valid, 'vol_roc_quintile', bucket_order=quintile_order
    )

    min_group_size = min(g['trades'] for g in groups.values()) if groups else 0
    confidence = get_confidence_level(min_group_size)
    has_edge, recommendation = determine_edge(p_value, effect_size, confidence)

    return EdgeTestResult(
        indicator="Volume ROC",
        test_name="Vol ROC Magnitude (Quintiles)",
        segment=segment,
        has_edge=has_edge,
        p_value=p_value,
        effect_size=effect_size,
        groups=groups,
        baseline_win_rate=baseline_wr,
        confidence=confidence,
        test_type="spearman",
        recommendation=recommendation,
        total_trades=len(df_valid)
    )


# =============================================================================
# CVD SLOPE TESTS
# =============================================================================

def test_cvd_slope_direction(df: pd.DataFrame, segment: str = "ALL") -> EdgeTestResult:
    """Test CVD slope direction effect on win rate."""
    df = calculate_cvd_slope_metrics(df)
    df_valid = df[df['cvd_direction'].notna()].copy()

    if len(df_valid) < 30:
        return _empty_result("CVD Slope", "CVD Direction", segment, len(df_valid))

    baseline_wr = df_valid['is_winner'].mean() * 100
    groups = calculate_win_rates(df_valid, 'cvd_direction')
    chi2, p_value, effect_size = chi_square_test(df_valid, 'cvd_direction')

    min_group_size = min(g['trades'] for g in groups.values()) if groups else 0
    confidence = get_confidence_level(min_group_size)
    has_edge, recommendation = determine_edge(p_value, effect_size, confidence)

    return EdgeTestResult(
        indicator="CVD Slope",
        test_name="CVD Direction",
        segment=segment,
        has_edge=has_edge,
        p_value=p_value,
        effect_size=effect_size,
        groups=groups,
        baseline_win_rate=baseline_wr,
        confidence=confidence,
        test_type="chi_square",
        recommendation=recommendation,
        total_trades=len(df_valid)
    )


def test_cvd_slope_alignment(df: pd.DataFrame, segment: str = "ALL") -> EdgeTestResult:
    """Test CVD slope alignment effect on win rate."""
    df = calculate_cvd_slope_metrics(df)
    df_valid = df[df['cvd_aligned_str'].notna()].copy()

    if len(df_valid) < 30:
        return _empty_result("CVD Slope", "CVD Alignment", segment, len(df_valid))

    baseline_wr = df_valid['is_winner'].mean() * 100
    groups = calculate_win_rates(df_valid, 'cvd_aligned_str')
    chi2, p_value, effect_size = chi_square_test(df_valid, 'cvd_aligned_str')

    min_group_size = min(g['trades'] for g in groups.values()) if groups else 0
    confidence = get_confidence_level(min_group_size)
    has_edge, recommendation = determine_edge(p_value, effect_size, confidence)

    return EdgeTestResult(
        indicator="CVD Slope",
        test_name="CVD Alignment",
        segment=segment,
        has_edge=has_edge,
        p_value=p_value,
        effect_size=effect_size,
        groups=groups,
        baseline_win_rate=baseline_wr,
        confidence=confidence,
        test_type="chi_square",
        recommendation=recommendation,
        total_trades=len(df_valid)
    )


# =============================================================================
# SMA TESTS
# =============================================================================

def test_sma_spread_direction(df: pd.DataFrame, segment: str = "ALL") -> EdgeTestResult:
    """Test SMA spread direction effect on win rate."""
    df = calculate_sma_metrics(df)
    df_valid = df[df['sma_spread_direction'].notna()].copy()

    if len(df_valid) < 30:
        return _empty_result("SMA", "SMA Spread Direction", segment, len(df_valid))

    baseline_wr = df_valid['is_winner'].mean() * 100
    groups = calculate_win_rates(df_valid, 'sma_spread_direction')
    chi2, p_value, effect_size = chi_square_test(df_valid, 'sma_spread_direction')

    min_group_size = min(g['trades'] for g in groups.values()) if groups else 0
    confidence = get_confidence_level(min_group_size)
    has_edge, recommendation = determine_edge(p_value, effect_size, confidence)

    return EdgeTestResult(
        indicator="SMA",
        test_name="SMA Spread Direction",
        segment=segment,
        has_edge=has_edge,
        p_value=p_value,
        effect_size=effect_size,
        groups=groups,
        baseline_win_rate=baseline_wr,
        confidence=confidence,
        test_type="chi_square",
        recommendation=recommendation,
        total_trades=len(df_valid)
    )


def test_sma_price_position(df: pd.DataFrame, segment: str = "ALL") -> EdgeTestResult:
    """Test price position vs SMAs effect on win rate."""
    df = calculate_sma_metrics(df)
    df_valid = df[df['price_vs_sma'].notna()].copy()

    if len(df_valid) < 30:
        return _empty_result("SMA", "Price vs SMA Position", segment, len(df_valid))

    baseline_wr = df_valid['is_winner'].mean() * 100
    groups = calculate_win_rates(df_valid, 'price_vs_sma')
    chi2, p_value, effect_size = chi_square_test(df_valid, 'price_vs_sma')

    min_group_size = min(g['trades'] for g in groups.values()) if groups else 0
    confidence = get_confidence_level(min_group_size)
    has_edge, recommendation = determine_edge(p_value, effect_size, confidence)

    return EdgeTestResult(
        indicator="SMA",
        test_name="Price vs SMA Position",
        segment=segment,
        has_edge=has_edge,
        p_value=p_value,
        effect_size=effect_size,
        groups=groups,
        baseline_win_rate=baseline_wr,
        confidence=confidence,
        test_type="chi_square",
        recommendation=recommendation,
        total_trades=len(df_valid)
    )


# =============================================================================
# STRUCTURE TESTS
# =============================================================================

def test_h1_structure(df: pd.DataFrame, segment: str = "ALL") -> EdgeTestResult:
    """Test H1 structure direction effect on win rate."""
    df = calculate_structure_metrics(df)
    df_valid = df[df['h1_structure'].notna() & (df['h1_structure'] != 'UNKNOWN')].copy()

    if len(df_valid) < 30:
        return _empty_result("Structure", "H1 Structure", segment, len(df_valid))

    baseline_wr = df_valid['is_winner'].mean() * 100
    groups = calculate_win_rates(df_valid, 'h1_structure')
    chi2, p_value, effect_size = chi_square_test(df_valid, 'h1_structure')

    min_group_size = min(g['trades'] for g in groups.values()) if groups else 0
    confidence = get_confidence_level(min_group_size)
    has_edge, recommendation = determine_edge(p_value, effect_size, confidence)

    return EdgeTestResult(
        indicator="Structure",
        test_name="H1 Structure Direction",
        segment=segment,
        has_edge=has_edge,
        p_value=p_value,
        effect_size=effect_size,
        groups=groups,
        baseline_win_rate=baseline_wr,
        confidence=confidence,
        test_type="chi_square",
        recommendation=recommendation,
        total_trades=len(df_valid)
    )


def test_m15_structure(df: pd.DataFrame, segment: str = "ALL") -> EdgeTestResult:
    """Test M15 structure direction effect on win rate."""
    df = calculate_structure_metrics(df)
    df_valid = df[df['m15_structure'].notna() & (df['m15_structure'] != 'UNKNOWN')].copy()

    if len(df_valid) < 30:
        return _empty_result("Structure", "M15 Structure", segment, len(df_valid))

    baseline_wr = df_valid['is_winner'].mean() * 100
    groups = calculate_win_rates(df_valid, 'm15_structure')
    chi2, p_value, effect_size = chi_square_test(df_valid, 'm15_structure')

    min_group_size = min(g['trades'] for g in groups.values()) if groups else 0
    confidence = get_confidence_level(min_group_size)
    has_edge, recommendation = determine_edge(p_value, effect_size, confidence)

    return EdgeTestResult(
        indicator="Structure",
        test_name="M15 Structure Direction",
        segment=segment,
        has_edge=has_edge,
        p_value=p_value,
        effect_size=effect_size,
        groups=groups,
        baseline_win_rate=baseline_wr,
        confidence=confidence,
        test_type="chi_square",
        recommendation=recommendation,
        total_trades=len(df_valid)
    )


def test_structure_alignment(df: pd.DataFrame, segment: str = "ALL") -> EdgeTestResult:
    """Test multi-timeframe structure alignment effect on win rate."""
    df = calculate_structure_metrics(df)
    df_valid = df[df['structure_alignment'].notna()].copy()

    if len(df_valid) < 30:
        return _empty_result("Structure", "MTF Alignment", segment, len(df_valid))

    baseline_wr = df_valid['is_winner'].mean() * 100
    groups = calculate_win_rates(df_valid, 'structure_alignment')
    chi2, p_value, effect_size = chi_square_test(df_valid, 'structure_alignment')

    min_group_size = min(g['trades'] for g in groups.values()) if groups else 0
    confidence = get_confidence_level(min_group_size)
    has_edge, recommendation = determine_edge(p_value, effect_size, confidence)

    return EdgeTestResult(
        indicator="Structure",
        test_name="MTF Structure Alignment",
        segment=segment,
        has_edge=has_edge,
        p_value=p_value,
        effect_size=effect_size,
        groups=groups,
        baseline_win_rate=baseline_wr,
        confidence=confidence,
        test_type="chi_square",
        recommendation=recommendation,
        total_trades=len(df_valid)
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _empty_result(indicator: str, test_name: str, segment: str, n_trades: int) -> EdgeTestResult:
    """Create an empty result for insufficient data."""
    return EdgeTestResult(
        indicator=indicator,
        test_name=test_name,
        segment=segment,
        has_edge=False,
        p_value=1.0,
        effect_size=0.0,
        groups={},
        baseline_win_rate=0.0,
        confidence="LOW",
        test_type="none",
        recommendation=f"INSUFFICIENT DATA - Only {n_trades} trades available",
        total_trades=n_trades
    )


# =============================================================================
# ALL TESTS REGISTRY
# =============================================================================

ALL_TESTS = {
    'candle_range': [
        ('Threshold Categories', test_candle_range_threshold),
        ('Magnitude Quintiles', test_candle_range_quintile),
        ('Absorption Filter', test_candle_range_absorption),
    ],
    'volume_delta': [
        ('Sign (Pos/Neg)', test_vol_delta_sign),
        ('Alignment', test_vol_delta_alignment),
        ('Magnitude Quintiles', test_vol_delta_magnitude),
    ],
    'volume_roc': [
        ('Category', test_vol_roc_category),
        ('Magnitude Quintiles', test_vol_roc_quintile),
    ],
    'cvd_slope': [
        ('Direction', test_cvd_slope_direction),
        ('Alignment', test_cvd_slope_alignment),
    ],
    'sma_edge': [
        ('Spread Direction', test_sma_spread_direction),
        ('Price Position', test_sma_price_position),
    ],
    'structure_edge': [
        ('H1 Structure', test_h1_structure),
        ('M15 Structure', test_m15_structure),
        ('MTF Alignment', test_structure_alignment),
    ],
}
