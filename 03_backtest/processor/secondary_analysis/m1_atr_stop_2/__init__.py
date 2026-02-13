"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
M1 ATR Stop Processor v2
XIII Trading LLC
================================================================================

Evaluates trades using M1 ATR-based stop and R-multiple targets (1R-5R).
Reads pre-computed atr_m1 from m1_indicator_bars_2 at the entry candle.

Result: WIN if R1 hit before stop, LOSS otherwise.

Version: 1.0.0
================================================================================
"""

from .calculator import M1AtrStopCalculator
from .config import TARGET_TABLE, SOURCE_TABLES
