"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 09: SECONDARY ANALYSIS
M5 ATR Stop Processor v2
XIII Trading LLC
================================================================================

Evaluates trades using M5 ATR-based stop and R-multiple targets (1R-5R).
Reads pre-computed atr_m5 from m1_indicator_bars_2 at the entry candle.
Walks M1 bars for simulation fidelity; only the stop distance uses M5 ATR.

Result: WIN if R1 hit before stop, LOSS otherwise.

Version: 1.0.0
================================================================================
"""

from .calculator import M5AtrStopCalculator
from .config import TARGET_TABLE, SOURCE_TABLES
