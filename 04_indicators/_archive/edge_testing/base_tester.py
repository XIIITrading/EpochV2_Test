"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR EDGE TESTING v1.0
Base Infrastructure for Edge Testing
XIII Trading LLC
================================================================================

Provides database access, statistical tests, and result structures.
================================================================================
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from scipy import stats
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import psycopg2

# Add parent to path for config imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    DB_CONFIG,
    P_VALUE_THRESHOLD,
    EFFECT_SIZE_THRESHOLD,
    MIN_SAMPLE_SIZE_HIGH,
    MIN_SAMPLE_SIZE_MEDIUM
)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class EdgeTestResult:
    """Results from a single indicator edge test."""
    indicator: str              # e.g., "Volume Delta"
    test_name: str              # e.g., "Vol Delta Sign"
    segment: str                # e.g., "ALL", "CONTINUATION", "REJECTION"
    has_edge: bool              # Statistical + practical significance
    p_value: float              # From chi-square or spearman
    effect_size: float          # Win rate difference in percentage points
    groups: Dict[str, Dict]     # {group_name: {trades: n, wins: n, win_rate: pct}}
    baseline_win_rate: float    # Overall win rate for comparison
    confidence: str             # HIGH/MEDIUM/LOW based on min group sample size
    test_type: str              # "chi_square" or "spearman"
    recommendation: str         # Action to take
    total_trades: int = 0       # Total trades in segment

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'indicator': self.indicator,
            'test_name': self.test_name,
            'segment': self.segment,
            'has_edge': self.has_edge,
            'p_value': self.p_value,
            'effect_size': self.effect_size,
            'groups': self.groups,
            'baseline_win_rate': self.baseline_win_rate,
            'confidence': self.confidence,
            'test_type': self.test_type,
            'recommendation': self.recommendation,
            'total_trades': self.total_trades
        }


# =============================================================================
# DATABASE FUNCTIONS
# =============================================================================

def get_db_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        database=DB_CONFIG['database'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        sslmode=DB_CONFIG.get('sslmode', 'require')
    )


def fetch_indicator_data(
    models: List[str] = None,
    directions: List[str] = None,
    date_from: str = None,
    date_to: str = None,
    stop_type: str = 'zone_buffer'
) -> pd.DataFrame:
    """
    Fetch trade data joined with indicator values from prior M1 bar.

    Join Logic:
    - Entry at S15 means we use the PRIOR completed M1 bar
    - For entry at 09:35:15, use m1_indicator_bars at 09:34:00
    - This avoids look-ahead bias

    Returns DataFrame with all indicator columns needed for edge testing.
    """
    query = """
    WITH trade_with_prior_bar AS (
        SELECT
            t.trade_id,
            t.date,
            t.ticker,
            t.model,
            t.direction,
            t.entry_price,
            t.entry_time,
            (date_trunc('minute', ('2000-01-01'::date + t.entry_time)) - INTERVAL '1 minute')::time AS prior_bar_time
        FROM trades t
        WHERE t.entry_time IS NOT NULL
    )
    SELECT
        twpb.trade_id,
        twpb.date,
        twpb.ticker,
        twpb.model,
        twpb.direction,
        twpb.entry_price,
        twpb.entry_time,
        twpb.prior_bar_time,
        -- M1 Indicator values
        m1.vol_delta,
        m1.vol_roc,
        m1.cvd_slope,
        m1.vwap,
        m1.sma9,
        m1.sma21,
        m1.sma_spread,
        m1.sma_momentum_label,
        m1.health_score,
        m1.open as bar_open,
        m1.high as bar_high,
        m1.low as bar_low,
        m1.close as bar_close,
        -- Entry indicator snapshots
        ei.h4_structure,
        ei.h1_structure,
        ei.m15_structure,
        ei.m5_structure,
        -- Outcome from stop_analysis
        CASE WHEN sa.outcome = 'WIN' THEN TRUE ELSE FALSE END as is_winner,
        sa.outcome as outcome_detail,
        sa.r_achieved
    FROM trade_with_prior_bar twpb
    LEFT JOIN m1_indicator_bars m1
        ON m1.ticker = twpb.ticker
        AND m1.bar_date = twpb.date
        AND m1.bar_time = twpb.prior_bar_time
    LEFT JOIN entry_indicators ei
        ON ei.trade_id = twpb.trade_id
    JOIN stop_analysis sa
        ON sa.trade_id = twpb.trade_id
    WHERE sa.stop_type = %s
      AND sa.stop_price IS NOT NULL
    """

    params = [stop_type]

    # Add optional filters
    if models:
        query += " AND twpb.model = ANY(%s)"
        params.append(models)

    if directions:
        query += " AND twpb.direction = ANY(%s)"
        params.append(directions)

    if date_from:
        query += " AND twpb.date >= %s"
        params.append(date_from)

    if date_to:
        query += " AND twpb.date <= %s"
        params.append(date_to)

    query += " ORDER BY twpb.date, twpb.entry_time"

    conn = get_db_connection()
    try:
        df = pd.read_sql_query(query, conn, params=params)

        # If no data returned, provide diagnostic information
        if df.empty:
            cursor = conn.cursor()
            # Check if the stop_type exists
            cursor.execute("SELECT DISTINCT stop_type FROM stop_analysis")
            available_stop_types = [row[0] for row in cursor.fetchall()]
            print(f"  Available stop types in database: {available_stop_types}")
            print(f"  Requested stop type: {stop_type}")
            if stop_type not in available_stop_types:
                print(f"  WARNING: '{stop_type}' is not a valid stop type!")
            cursor.close()

        return df
    finally:
        conn.close()


# =============================================================================
# STATISTICAL TEST FUNCTIONS
# =============================================================================

def get_confidence_level(min_group_size: int) -> str:
    """
    Determine confidence level based on minimum group sample size.

    HIGH: n >= 100 per group (reliable)
    MEDIUM: n >= 30 per group (usable with caution)
    LOW: n < 30 per group (insufficient for conclusions)
    """
    if min_group_size >= MIN_SAMPLE_SIZE_HIGH:
        return "HIGH"
    elif min_group_size >= MIN_SAMPLE_SIZE_MEDIUM:
        return "MEDIUM"
    else:
        return "LOW"


def calculate_win_rates(
    df: pd.DataFrame,
    group_col: str,
    outcome_col: str = 'is_winner'
) -> Dict[str, Dict]:
    """
    Calculate win rate statistics by group.

    Returns: {
        'GROUP_A': {'trades': 100, 'wins': 45, 'win_rate': 45.0},
        'GROUP_B': {'trades': 120, 'wins': 60, 'win_rate': 50.0}
    }
    """
    grouped = df.groupby(group_col, observed=True)[outcome_col].agg(['sum', 'count'])

    result = {}
    for group_name, row in grouped.iterrows():
        wins = int(row['sum'])
        trades = int(row['count'])
        win_rate = (wins / trades * 100) if trades > 0 else 0.0
        result[str(group_name)] = {
            'trades': trades,
            'wins': wins,
            'win_rate': round(win_rate, 2)
        }

    return result


def chi_square_test(
    df: pd.DataFrame,
    group_col: str,
    outcome_col: str = 'is_winner'
) -> Tuple[float, float, float]:
    """
    Run chi-square test for independence between group and outcome.

    Returns: (chi2_statistic, p_value, effect_size)
    Effect size = max win rate - min win rate (in percentage points)
    """
    # Create contingency table
    contingency = pd.crosstab(df[group_col], df[outcome_col])

    # Need at least 2 groups and both outcomes
    if contingency.shape[0] < 2 or contingency.shape[1] < 2:
        return 0.0, 1.0, 0.0

    # Chi-square test
    chi2, p_value, dof, expected = stats.chi2_contingency(contingency)

    # Calculate effect size (win rate difference)
    win_rates = calculate_win_rates(df, group_col, outcome_col)
    rates = [g['win_rate'] for g in win_rates.values()]
    effect_size = max(rates) - min(rates) if rates else 0.0

    return chi2, p_value, effect_size


def spearman_monotonic_test(
    df: pd.DataFrame,
    bucket_col: str,
    outcome_col: str = 'is_winner',
    bucket_order: List[str] = None
) -> Tuple[float, float, float]:
    """
    Test for monotonic relationship between ordered buckets and win rate.

    Returns: (correlation, p_value, effect_size)
    Effect size = first bucket win rate - last bucket win rate
    """
    win_rates = calculate_win_rates(df, bucket_col, outcome_col)

    if bucket_order is None:
        bucket_order = sorted(win_rates.keys())

    # Filter to only buckets that exist
    bucket_order = [b for b in bucket_order if b in win_rates]

    if len(bucket_order) < 3:
        return 0.0, 1.0, 0.0

    # Create arrays for correlation
    positions = list(range(len(bucket_order)))
    rates = [win_rates[b]['win_rate'] for b in bucket_order]

    # Spearman correlation
    correlation, p_value = stats.spearmanr(positions, rates)

    # Effect size: difference between first and last
    effect_size = abs(rates[-1] - rates[0])

    return correlation, p_value, effect_size


def determine_edge(
    p_value: float,
    effect_size: float,
    confidence: str,
    p_threshold: float = None,
    effect_threshold: float = None
) -> Tuple[bool, str]:
    """
    Determine if edge exists and generate recommendation.

    Edge requires:
    - p_value < 0.05 (statistically significant)
    - effect_size > 3.0pp (practically significant)
    - confidence not LOW (sufficient sample size)

    Returns: (has_edge, recommendation)
    """
    p_threshold = p_threshold or P_VALUE_THRESHOLD
    effect_threshold = effect_threshold or EFFECT_SIZE_THRESHOLD

    if confidence == "LOW":
        return False, "INSUFFICIENT DATA - Need more trades for reliable conclusion"

    if p_value >= p_threshold:
        return False, f"NO EDGE - Not statistically significant (p={p_value:.4f})"

    if effect_size < effect_threshold:
        return False, f"NO EDGE - Effect too small ({effect_size:.1f}pp < {effect_threshold}pp threshold)"

    return True, f"EDGE DETECTED - Implement filter (p={p_value:.4f}, effect={effect_size:.1f}pp)"


# =============================================================================
# METRIC CALCULATION HELPERS
# =============================================================================

def calculate_candle_range(df: pd.DataFrame) -> pd.DataFrame:
    """Add candle range metrics to dataframe."""
    df = df.copy()

    # Calculate candle range percentage
    df['candle_range_pct'] = ((df['bar_high'] - df['bar_low']) / df['bar_open'] * 100).fillna(0)

    # Thresholds
    from config import CANDLE_RANGE_CONFIG
    df['is_absorption'] = df['candle_range_pct'] < CANDLE_RANGE_CONFIG['absorption_threshold']
    df['has_momentum'] = df['candle_range_pct'] >= CANDLE_RANGE_CONFIG['normal_threshold']
    df['high_momentum'] = df['candle_range_pct'] >= CANDLE_RANGE_CONFIG['high_threshold']

    # Quintiles
    try:
        df['range_quintile'] = pd.qcut(
            df['candle_range_pct'],
            q=5,
            labels=['Q1_Smallest', 'Q2', 'Q3', 'Q4', 'Q5_Largest'],
            duplicates='drop'
        )
    except ValueError:
        df['range_quintile'] = 'UNKNOWN'

    return df


def calculate_volume_delta_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add Volume Delta-derived columns for edge testing."""
    df = df.copy()

    # Filter rows with vol_delta
    mask = df['vol_delta'].notna()

    # Sign classification
    df.loc[mask, 'vol_delta_sign'] = np.where(df.loc[mask, 'vol_delta'] >= 0, 'POSITIVE', 'NEGATIVE')

    # Absolute value
    df.loc[mask, 'vol_delta_abs'] = df.loc[mask, 'vol_delta'].abs()

    # Alignment
    df.loc[mask, 'vol_delta_aligned'] = (
        ((df.loc[mask, 'direction'] == 'LONG') & (df.loc[mask, 'vol_delta'] > 0)) |
        ((df.loc[mask, 'direction'] == 'SHORT') & (df.loc[mask, 'vol_delta'] < 0))
    )
    df['vol_delta_aligned_str'] = df['vol_delta_aligned'].map({True: 'ALIGNED', False: 'MISALIGNED'})

    # Magnitude quintiles
    try:
        df.loc[mask, 'vol_delta_quintile'] = pd.qcut(
            df.loc[mask, 'vol_delta_abs'],
            q=5,
            labels=['Q1_Smallest', 'Q2', 'Q3', 'Q4', 'Q5_Largest'],
            duplicates='drop'
        )
    except ValueError:
        df.loc[mask, 'vol_delta_quintile'] = 'UNKNOWN'

    return df


def calculate_volume_roc_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add Volume ROC metrics for edge testing."""
    df = df.copy()

    mask = df['vol_roc'].notna()

    from config import VOLUME_ROC_CONFIG

    # Threshold tests
    df.loc[mask, 'vol_roc_elevated'] = df.loc[mask, 'vol_roc'] >= VOLUME_ROC_CONFIG['elevated_threshold']
    df.loc[mask, 'vol_roc_high'] = df.loc[mask, 'vol_roc'] >= VOLUME_ROC_CONFIG['high_threshold']

    # Category
    df.loc[mask, 'vol_roc_category'] = np.where(
        df.loc[mask, 'vol_roc'] >= VOLUME_ROC_CONFIG['high_threshold'], 'HIGH',
        np.where(
            df.loc[mask, 'vol_roc'] >= VOLUME_ROC_CONFIG['elevated_threshold'], 'ELEVATED', 'NORMAL'
        )
    )

    # Quintiles
    try:
        df.loc[mask, 'vol_roc_quintile'] = pd.qcut(
            df.loc[mask, 'vol_roc'],
            q=5,
            labels=['Q1_Lowest', 'Q2', 'Q3', 'Q4', 'Q5_Highest'],
            duplicates='drop'
        )
    except ValueError:
        df.loc[mask, 'vol_roc_quintile'] = 'UNKNOWN'

    return df


def calculate_cvd_slope_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add CVD Slope metrics for edge testing."""
    df = df.copy()

    mask = df['cvd_slope'].notna()

    from config import CVD_CONFIG

    # Direction
    df.loc[mask, 'cvd_direction'] = np.where(
        df.loc[mask, 'cvd_slope'] > CVD_CONFIG['rising_threshold'], 'RISING',
        np.where(
            df.loc[mask, 'cvd_slope'] < CVD_CONFIG['falling_threshold'], 'FALLING', 'FLAT'
        )
    )

    # Alignment
    df.loc[mask, 'cvd_aligned'] = (
        ((df.loc[mask, 'direction'] == 'LONG') & (df.loc[mask, 'cvd_slope'] > 0)) |
        ((df.loc[mask, 'direction'] == 'SHORT') & (df.loc[mask, 'cvd_slope'] < 0))
    )
    df['cvd_aligned_str'] = df['cvd_aligned'].map({True: 'ALIGNED', False: 'MISALIGNED'})

    # Category by magnitude
    abs_slope = df.loc[mask, 'cvd_slope'].abs()
    q75 = abs_slope.quantile(0.75) if len(abs_slope) > 0 else 0
    df.loc[mask, 'cvd_category'] = np.where(
        abs_slope >= q75, 'EXTREME',
        np.where(abs_slope >= abs_slope.median(), 'MODERATE', 'WEAK')
    )

    return df


def calculate_sma_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add SMA-derived metrics for edge testing."""
    df = df.copy()

    # Calculate SMA spread if not present
    if 'sma_spread' not in df.columns or df['sma_spread'].isna().all():
        mask = df['sma9'].notna() & df['sma21'].notna()
        df.loc[mask, 'sma_spread'] = df.loc[mask, 'sma9'] - df.loc[mask, 'sma21']

    mask = df['sma_spread'].notna()

    from config import SMA_CONFIG

    # Spread direction
    df.loc[mask, 'sma_spread_direction'] = np.where(
        df.loc[mask, 'sma_spread'] > 0, 'BULLISH', 'BEARISH'
    )

    # Spread magnitude
    df.loc[mask, 'sma_spread_abs'] = df.loc[mask, 'sma_spread'].abs()

    # Wide spread threshold
    df.loc[mask, 'sma_spread_wide'] = df.loc[mask, 'sma_spread_abs'] >= SMA_CONFIG['wide_spread_threshold']

    # Price position relative to SMAs
    price_mask = mask & df['bar_close'].notna()
    df.loc[price_mask, 'price_vs_sma'] = np.where(
        (df.loc[price_mask, 'bar_close'] > df.loc[price_mask, 'sma9']) &
        (df.loc[price_mask, 'bar_close'] > df.loc[price_mask, 'sma21']),
        'ABOVE_BOTH',
        np.where(
            (df.loc[price_mask, 'bar_close'] < df.loc[price_mask, 'sma9']) &
            (df.loc[price_mask, 'bar_close'] < df.loc[price_mask, 'sma21']),
            'BELOW_BOTH',
            'BETWEEN'
        )
    )

    return df


def calculate_structure_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add structure-derived metrics for edge testing."""
    df = df.copy()

    # Standardize structure values
    for col in ['h4_structure', 'h1_structure', 'm15_structure', 'm5_structure']:
        if col in df.columns:
            df[col] = df[col].fillna('UNKNOWN').str.upper()
            # Standardize variations
            df[col] = df[col].replace({
                'NEUT': 'NEUTRAL',
                'BULL': 'BULLISH',
                'BEAR': 'BEARISH'
            })

    # Check alignment (all timeframes same direction, excluding NEUTRAL)
    structure_cols = ['h1_structure', 'm15_structure', 'm5_structure']
    available_cols = [c for c in structure_cols if c in df.columns]

    if len(available_cols) >= 2:
        def check_alignment(row):
            values = [row[c] for c in available_cols if row[c] not in ['NEUTRAL', 'UNKNOWN']]
            if len(values) < 2:
                return 'NEUTRAL'
            return 'ALIGNED' if len(set(values)) == 1 else 'NOT_ALIGNED'

        df['structure_alignment'] = df.apply(check_alignment, axis=1)

    # Confluence score (H1 x 1.5 + M15 x 1.0 + M5 x 0.5)
    def calc_confluence(row):
        score = 0
        weights = {'h1_structure': 1.5, 'm15_structure': 1.0, 'm5_structure': 0.5}
        for col, weight in weights.items():
            if col in row and row[col] == 'BULLISH':
                score += weight
            elif col in row and row[col] == 'BEARISH':
                score -= weight
        return score

    df['confluence_score'] = df.apply(calc_confluence, axis=1)

    return df
