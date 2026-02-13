"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
Trades M5 R Win Consolidation Processor v2
XIII Trading LLC
================================================================================

Consolidates trades_2 + m5_atr_stop_2 + m1_bars_2 into a single denormalized
table (trades_m5_r_win_2) for downstream consumption by 11_trade_reel.

No simulation logic — pure JOIN + derive + INSERT.

Version: 1.0.0
================================================================================
"""

from .calculator import TradesM5RWin2Calculator
from .config import TARGET_TABLE, SOURCE_TABLES
