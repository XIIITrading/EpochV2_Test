# 02 - Entry Snapshot: Indicator State at Entry

Win rate breakdown by each indicator's state at the M1 bar just before entry.

**Total Trades:** 1,126 | **Win Rate:** 54.8% | **Avg R:** 1.23

## Categorical Indicator Win Rates

Win rate for each state of categorical indicators at entry.

### SMA Configuration

| State | Trades | Wins | Win Rate | Avg R |
|-------|--------|------|----------|-------|
| BULL | 612 | 374 | 61.1% | 1.35 |
| BEAR | 514 | 243 | 47.3% | 1.08 |

### H1 Structure

| State | Trades | Wins | Win Rate | Avg R |
|-------|--------|------|----------|-------|
| BEAR | 460 | 278 | 60.4% | 1.65 |
| BULL | 666 | 339 | 50.9% | 0.94 |

### M15 Structure

| State | Trades | Wins | Win Rate | Avg R |
|-------|--------|------|----------|-------|
| BEAR | 624 | 374 | 59.9% | 1.45 |
| BULL | 502 | 243 | 48.4% | 0.95 |

### M5 Structure

| State | Trades | Wins | Win Rate | Avg R |
|-------|--------|------|----------|-------|
| BULL | 477 | 298 | 62.5% | 1.63 |
| BEAR | 649 | 319 | 49.2% | 0.94 |

### Price Position

| State | Trades | Wins | Win Rate | Avg R |
|-------|--------|------|----------|-------|
| BTWN | 222 | 133 | 59.9% | 1.32 |
| ABOVE | 524 | 307 | 58.6% | 1.47 |
| BELOW | 380 | 177 | 46.6% | 0.84 |

### SMA Momentum

| State | Trades | Wins | Win Rate | Avg R |
|-------|--------|------|----------|-------|
| STABLE | 81 | 45 | 55.6% | 1.27 |
| WIDENING | 522 | 287 | 55.0% | 1.15 |
| NARROWING | 522 | 284 | 54.4% | 1.29 |

## Continuous Indicator Win Rates (by Quintile)

Win rate for each quintile (20% bucket) of continuous indicators at entry.

### Candle Range %

| Quintile | Range Min | Range Max | Trades | Win Rate | Avg R |
|----------|----------|----------|--------|----------|-------|
| Q1 | 0.0000 | 0.0974 | 226 | 63.7% | 1.47 |
| Q2 | 0.0977 | 0.1780 | 225 | 55.6% | 1.30 |
| Q3 | 0.1783 | 0.2764 | 225 | 47.6% | 0.82 |
| Q4 | 0.2764 | 0.5023 | 225 | 50.7% | 1.12 |
| Q5 | 0.5049 | 4.6730 | 225 | 56.4% | 1.43 |

### Volume Delta (5-bar)

| Quintile | Range Min | Range Max | Trades | Win Rate | Avg R |
|----------|----------|----------|--------|----------|-------|
| Q1 | -956643.9200 | -68874.3700 | 226 | 58.4% | 1.57 |
| Q2 | -68874.3700 | -10919.7500 | 225 | 58.7% | 1.12 |
| Q3 | -10919.7500 | 30769.4100 | 225 | 47.1% | 0.97 |
| Q4 | 30769.4100 | 136186.0700 | 225 | 52.4% | 1.09 |
| Q5 | 136186.0700 | 1407598.6900 | 225 | 57.3% | 1.39 |

### Volume ROC

| Quintile | Range Min | Range Max | Trades | Win Rate | Avg R |
|----------|----------|----------|--------|----------|-------|
| Q1 | -96.2495 | -37.9405 | 226 | 56.6% | 1.19 |
| Q2 | -37.9405 | -17.3710 | 225 | 59.1% | 1.24 |
| Q3 | -17.3710 | 4.5485 | 225 | 60.0% | 1.43 |
| Q4 | 4.5550 | 42.7924 | 225 | 51.1% | 1.14 |
| Q5 | 42.7924 | 67062.9031 | 225 | 47.1% | 1.13 |

### SMA Spread %

| Quintile | Range Min | Range Max | Trades | Win Rate | Avg R |
|----------|----------|----------|--------|----------|-------|
| Q1 | 0.0010 | 0.0436 | 226 | 54.9% | 1.00 |
| Q2 | 0.0443 | 0.0939 | 225 | 52.4% | 1.16 |
| Q3 | 0.0942 | 0.1823 | 225 | 61.8% | 1.63 |
| Q4 | 0.1827 | 0.3671 | 225 | 47.1% | 1.35 |
| Q5 | 0.3678 | 3.7650 | 225 | 57.8% | 1.00 |

### CVD Slope

| Quintile | Range Min | Range Max | Trades | Win Rate | Avg R |
|----------|----------|----------|--------|----------|-------|
| Q1 | -0.6927 | -0.1444 | 226 | 58.8% | 1.59 |
| Q2 | -0.1444 | -0.0216 | 225 | 55.6% | 1.32 |
| Q3 | -0.0215 | 0.0989 | 225 | 53.8% | 1.08 |
| Q4 | 0.0993 | 0.2583 | 225 | 55.1% | 1.23 |
| Q5 | 0.2589 | 1.0923 | 225 | 50.7% | 0.92 |

## Key Observations for AI Analysis

When analyzing entry snapshot data, consider:
1. **Strongest categorical edges**: Which indicator states have the highest win rates with sufficient sample size?
2. **Quintile sweet spots**: Are there clear 'golden zones' where win rate jumps?
3. **Avoid zones**: Which states/quintiles should be avoided (low win rate + negative R)?
4. **Direction asymmetry**: Do edges differ between LONG and SHORT trades?
5. **Model differences**: Do different entry models (EPCH1-4) favor different indicator states?