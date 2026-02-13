"""
================================================================================
EPOCH TRADING SYSTEM - SECONDARY ANALYSIS
Secondary Analysis Package
XIII Trading LLC
================================================================================

Secondary analysis modules that operate on trades_2 data stored in Supabase.
Each processor is self-contained with its own config, calculator, runner, and schema.

Pipeline Order:
    1. m1_bars/              - M1 Bar Storage (Polygon to Supabase m1_bars_2)
    2. m1_indicator_bars_2/  - M1 Indicator Bars (22 indicators + 3 scores)
    3. m1_atr_stop_2/        - M1 ATR Stop Analysis (R-multiple targets 1R-5R)
    4. m5_atr_stop_2/        - M5 ATR Stop Analysis (R-multiple targets 1R-5R)
    5. trades_m5_r_win_2/    - Trades Consolidated (denormalized for trade_reel)

Version: 2.1.0
================================================================================
"""

__version__ = "2.1.0"
