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
| 0 | 55 | 30 | 54.5% | 1.24 |
| 1 | 146 | 95 | 65.1% | 1.38 |
| 2 | 276 | 148 | 53.6% | 1.21 |
| 3 | 300 | 177 | 59.0% | 1.43 |
| 4 | 258 | 122 | 47.3% | 1.00 |
| 5 | 76 | 38 | 50.0% | 0.92 |
| 6 | 15 | 7 | 46.7% | 1.47 |

## Indicator State Combinations

Win rate for specific indicator state combinations (min 20 trades).

### Top 10 Combinations (Highest Win Rate)

| SMA Config | H1 | M15 | Vol ROC | Candle | Trades | Win Rate | Avg R |
|------------|-----|-----|---------|--------|--------|----------|-------|
| BEAR | BEAR | BULL | NORMAL | ABSORPTION | 25 | 80.0% | 2.16 |
| BULL | BULL | BULL | NORMAL | ABSORPTION | 27 | 77.8% | 2.48 |
| BULL | BEAR | BEAR | NORMAL | NORMAL | 75 | 73.3% | 1.93 |
| BULL | BEAR | BULL | NORMAL | ABSORPTION | 23 | 69.6% | 1.96 |
| BULL | BULL | BEAR | NORMAL | ABSORPTION | 58 | 69.0% | 1.21 |
| BEAR | BEAR | BEAR | NORMAL | NORMAL | 57 | 66.7% | 1.96 |
| BULL | BULL | BEAR | ELEVATED | NORMAL | 39 | 66.7% | 2.21 |
| BULL | BULL | BEAR | NORMAL | NORMAL | 117 | 62.4% | 1.41 |
| BEAR | BEAR | BEAR | ELEVATED | NORMAL | 36 | 61.1% | 1.92 |
| BULL | BEAR | BULL | NORMAL | NORMAL | 22 | 59.1% | 1.73 |

### Bottom 10 Combinations (Lowest Win Rate)

| SMA Config | H1 | M15 | Vol ROC | Candle | Trades | Win Rate | Avg R |
|------------|-----|-----|---------|--------|--------|----------|-------|
| BEAR | BULL | BULL | NORMAL | ABSORPTION | 36 | 52.8% | 0.61 |
| BEAR | BEAR | BEAR | NORMAL | ABSORPTION | 21 | 52.4% | 1.14 |
| BEAR | BULL | BEAR | NORMAL | NORMAL | 43 | 48.8% | 1.42 |
| BULL | BULL | BEAR | NORMAL | LOW | 25 | 48.0% | 0.32 |
| BULL | BULL | BULL | NORMAL | NORMAL | 93 | 46.2% | 0.39 |
| BULL | BULL | BULL | ELEVATED | NORMAL | 31 | 45.2% | 0.68 |
| BEAR | BULL | BEAR | NORMAL | ABSORPTION | 21 | 33.3% | 0.24 |
| BEAR | BULL | BULL | ELEVATED | NORMAL | 29 | 31.0% | 0.62 |
| BEAR | BULL | BULL | NORMAL | NORMAL | 89 | 27.0% | 0.12 |
| BEAR | BEAR | BULL | ELEVATED | NORMAL | 34 | 11.8% | -0.56 |

## Key Observations for AI Analysis

When analyzing composite setup data, consider:
1. **Optimal score**: What setup score threshold gives the best risk-adjusted returns?
2. **Diminishing returns**: Does win rate plateau after a certain score?
3. **Required conditions**: Are there any must-have conditions regardless of score?
4. **Avoid combinations**: Which specific combos should be filtered out entirely?
5. **Actionable rules**: Propose 2-3 concrete pre-entry filter rules based on this data.