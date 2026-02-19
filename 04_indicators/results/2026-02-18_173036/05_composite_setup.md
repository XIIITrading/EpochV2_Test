# 05 - Composite Setup Analysis: Multi-Indicator Scoring

Tests how indicators work together to identify ideal entry setups.
Setup score is 0-7 based on favorable conditions present at entry.

## Setup Score Components (0-7)

- +1 if Candle Range >= 0.15%
- +1 if Vol ROC >= 30%
- +1 if SMA Spread >= 0.15%
- +1 if SMA Config aligned with direction (BULL/LONG or BEAR/SHORT)
- +1 if M5 Structure aligned with direction
- +1 if H1 Structure is NEUTRAL
- +1 if CVD Slope aligned with direction (>0.1 for LONG, <-0.1 for SHORT)

## Setup Score Distribution & Win Rate

| Score | Trades | Wins | Win Rate | Avg R |
|-------|--------|------|----------|-------|
| 0 | 144 | 73 | 50.7% | 0.88 |
| 1 | 369 | 164 | 44.4% | 0.62 |
| 2 | 466 | 223 | 47.9% | 0.89 |
| 3 | 510 | 274 | 53.7% | 1.10 |
| 4 | 346 | 151 | 43.6% | 0.77 |
| 5 | 159 | 66 | 41.5% | 0.67 |
| 6 | 25 | 9 | 36.0% | 0.80 |

## Indicator State Combinations

Win rate for specific indicator state combinations (min 20 trades).

### Top 10 Combinations (Highest Win Rate)

| SMA Config | H1 | M15 | Vol ROC | Candle | Trades | Win Rate | Avg R |
|------------|-----|-----|---------|--------|--------|----------|-------|
| BULL | BULL | BULL | NORMAL | ABSORPTION | 39 | 71.8% | 2.28 |
| BEAR | BEAR | BEAR | ELEVATED | NORMAL | 67 | 64.2% | 1.48 |
| BULL | BULL | BEAR | ELEVATED | NORMAL | 41 | 63.4% | 2.05 |
| BULL | BULL | BEAR | NORMAL | NORMAL | 131 | 61.8% | 1.35 |
| BULL | BEAR | BULL | NORMAL | ABSORPTION | 81 | 61.7% | 1.35 |
| BULL | BEAR | BULL | NORMAL | NORMAL | 26 | 61.5% | 1.85 |
| BEAR | BEAR | BULL | NORMAL | NORMAL | 42 | 59.5% | 1.95 |
| BEAR | BEAR | BEAR | NORMAL | ABSORPTION | 100 | 58.0% | 1.24 |
| BEAR | BEAR | BULL | NORMAL | ABSORPTION | 57 | 57.9% | 0.96 |
| BULL | BEAR | BEAR | ELEVATED | NORMAL | 37 | 56.8% | 1.57 |

### Bottom 10 Combinations (Lowest Win Rate)

| SMA Config | H1 | M15 | Vol ROC | Candle | Trades | Win Rate | Avg R |
|------------|-----|-----|---------|--------|--------|----------|-------|
| BULL | BULL | BEAR | NORMAL | ABSORPTION | 105 | 43.8% | 0.51 |
| BEAR | BULL | BEAR | ELEVATED | NORMAL | 21 | 42.9% | 0.71 |
| BEAR | BEAR | BULL | ELEVATED | ABSORPTION | 26 | 42.3% | 1.08 |
| BULL | BULL | BEAR | NORMAL | LOW | 31 | 41.9% | 0.13 |
| BEAR | BEAR | BEAR | NORMAL | LOW | 36 | 41.7% | 1.11 |
| BEAR | BEAR | BULL | ELEVATED | NORMAL | 43 | 30.2% | 0.47 |
| BEAR | BULL | BEAR | NORMAL | NORMAL | 73 | 28.8% | 0.42 |
| BEAR | BULL | BULL | NORMAL | NORMAL | 129 | 23.3% | -0.05 |
| BEAR | BULL | BULL | ELEVATED | NORMAL | 67 | 20.9% | -0.06 |
| BEAR | BULL | BEAR | NORMAL | ABSORPTION | 74 | 9.5% | -0.65 |

## Key Observations for AI Analysis

When analyzing composite setup data, consider:
1. **Optimal score**: What setup score threshold gives the best risk-adjusted returns?
2. **Diminishing returns**: Does win rate plateau after a certain score?
3. **Required conditions**: Are there any must-have conditions regardless of score?
4. **Avoid combinations**: Which specific combos should be filtered out entirely?
5. **Actionable rules**: Propose 2-3 concrete pre-entry filter rules based on this data.