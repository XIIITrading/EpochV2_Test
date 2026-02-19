# 02 - Entry Snapshot: Indicator State at Entry

Win rate breakdown by each indicator's state at the M1 bar just before entry.

**Total Trades:** 2,019 | **Win Rate:** 47.5% | **Avg R:** 0.85

## Categorical Indicator Win Rates

Win rate for each state of categorical indicators at entry.

### SMA Configuration

| State | Trades | Wins | Win Rate | Avg R |
|-------|--------|------|----------|-------|
| BULL | 1007 | 543 | 53.9% | 1.05 |
| BEAR | 1008 | 413 | 41.0% | 0.66 |

### H1 Structure

| State | Trades | Wins | Win Rate | Avg R |
|-------|--------|------|----------|-------|
| BEAR | 998 | 547 | 54.8% | 1.20 |
| BULL | 1021 | 413 | 40.5% | 0.52 |

### M15 Structure

| State | Trades | Wins | Win Rate | Avg R |
|-------|--------|------|----------|-------|
| BEAR | 1196 | 581 | 48.6% | 0.89 |
| BULL | 823 | 379 | 46.1% | 0.80 |

### M5 Structure

| State | Trades | Wins | Win Rate | Avg R |
|-------|--------|------|----------|-------|
| BULL | 996 | 498 | 50.0% | 0.92 |
| BEAR | 1023 | 462 | 45.2% | 0.79 |

### Price Position

| State | Trades | Wins | Win Rate | Avg R |
|-------|--------|------|----------|-------|
| BTWN | 351 | 182 | 51.9% | 0.99 |
| ABOVE | 825 | 423 | 51.3% | 1.06 |
| BELOW | 839 | 351 | 41.8% | 0.59 |

### SMA Momentum

| State | Trades | Wins | Win Rate | Avg R |
|-------|--------|------|----------|-------|
| STABLE | 133 | 70 | 52.6% | 0.98 |
| WIDENING | 964 | 484 | 50.2% | 0.93 |
| NARROWING | 903 | 401 | 44.4% | 0.78 |

## Continuous Indicator Win Rates (by Quintile)

Win rate for each quintile (20% bucket) of continuous indicators at entry.

### Candle Range %

| Quintile | Range Min | Range Max | Trades | Win Rate | Avg R |
|----------|----------|----------|--------|----------|-------|
| Q1 | 0.0000 | 0.0753 | 404 | 48.0% | 0.85 |
| Q2 | 0.0759 | 0.1334 | 404 | 51.0% | 0.89 |
| Q3 | 0.1334 | 0.2231 | 404 | 42.1% | 0.58 |
| Q4 | 0.2232 | 0.3894 | 404 | 44.6% | 0.76 |
| Q5 | 0.3907 | 4.6730 | 403 | 52.1% | 1.18 |

### Volume Delta (5-bar)

| Quintile | Range Min | Range Max | Trades | Win Rate | Avg R |
|----------|----------|----------|--------|----------|-------|
| Q1 | -957475.3400 | -79020.9500 | 404 | 55.4% | 1.34 |
| Q2 | -78602.9200 | -12443.2500 | 404 | 44.3% | 0.51 |
| Q3 | -12443.2500 | 19001.0400 | 404 | 40.3% | 0.48 |
| Q4 | 19077.5400 | 96706.8200 | 404 | 47.0% | 0.85 |
| Q5 | 97630.8400 | 1407598.6900 | 403 | 50.6% | 1.10 |

### Volume ROC

| Quintile | Range Min | Range Max | Trades | Win Rate | Avg R |
|----------|----------|----------|--------|----------|-------|
| Q1 | -96.2495 | -37.9702 | 403 | 48.6% | 0.78 |
| Q2 | -37.9405 | -17.6525 | 403 | 51.9% | 0.94 |
| Q3 | -17.6020 | 4.4638 | 403 | 47.4% | 0.79 |
| Q4 | 4.4638 | 39.3958 | 403 | 43.4% | 0.80 |
| Q5 | 39.8843 | 67062.9031 | 403 | 45.9% | 0.95 |

### SMA Spread %

| Quintile | Range Min | Range Max | Trades | Win Rate | Avg R |
|----------|----------|----------|--------|----------|-------|
| Q1 | 0.0002 | 0.0337 | 403 | 47.9% | 0.75 |
| Q2 | 0.0337 | 0.0706 | 403 | 43.2% | 0.63 |
| Q3 | 0.0707 | 0.1331 | 403 | 51.9% | 1.07 |
| Q4 | 0.1336 | 0.3098 | 403 | 47.1% | 1.07 |
| Q5 | 0.3127 | 3.7650 | 403 | 47.1% | 0.75 |

### CVD Slope

| Quintile | Range Min | Range Max | Trades | Win Rate | Avg R |
|----------|----------|----------|--------|----------|-------|
| Q1 | -0.7534 | -0.1655 | 404 | 46.3% | 0.90 |
| Q2 | -0.1648 | -0.0481 | 404 | 46.8% | 0.79 |
| Q3 | -0.0476 | 0.0678 | 404 | 48.0% | 0.80 |
| Q4 | 0.0679 | 0.2367 | 404 | 48.8% | 0.95 |
| Q5 | 0.2371 | 1.0923 | 403 | 47.9% | 0.83 |

## Key Observations for AI Analysis

When analyzing entry snapshot data, consider:
1. **Strongest categorical edges**: Which indicator states have the highest win rates with sufficient sample size?
2. **Quintile sweet spots**: Are there clear 'golden zones' where win rate jumps?
3. **Avoid zones**: Which states/quintiles should be avoided (low win rate + negative R)?
4. **Direction asymmetry**: Do edges differ between LONG and SHORT trades?
5. **Model differences**: Do different entry models (EPCH1-4) favor different indicator states?