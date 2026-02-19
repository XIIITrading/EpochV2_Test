# 04 - Indicator Deep Dive: Three-Phase Analysis

Per-indicator breakdown across ramp-up (pre-entry), entry snapshot,
and post-trade (post-entry) phases. Direction-normalized where applicable.

## Three-Phase Progression (Continuous Indicators)

### Candle Range %

**Ramp-Up (pre-entry)** (bars -24 to -1): Winners avg=0.257117, Losers avg=0.234183, Delta=+0.022934
**Post-Trade (post-entry)** (bars 0 to 24): Winners avg=0.240911, Losers avg=0.232574, Delta=+0.008337

### Volume Delta (5-bar)
*Direction-normalized: positive = favorable for trade direction*

**Ramp-Up (pre-entry)** (bars -24 to -1): Winners avg=10638.863582, Losers avg=11755.571577, Delta=-1116.707995
**Post-Trade (post-entry)** (bars 0 to 24): Winners avg=32246.814981, Losers avg=-15544.824907, Delta=+47791.639888

### Volume ROC

**Ramp-Up (pre-entry)** (bars -24 to -1): Winners avg=198.784252, Losers avg=135.863319, Delta=+62.920933
**Post-Trade (post-entry)** (bars 0 to 24): Winners avg=12.842083, Losers avg=18.548416, Delta=-5.706333

### SMA Spread %

**Ramp-Up (pre-entry)** (bars -24 to -1): Winners avg=0.192793, Losers avg=0.176098, Delta=+0.016695
**Post-Trade (post-entry)** (bars 0 to 24): Winners avg=0.212520, Losers avg=0.184666, Delta=+0.027854

### CVD Slope
*Direction-normalized: positive = favorable for trade direction*

**Ramp-Up (pre-entry)** (bars -24 to -1): Winners avg=0.025541, Losers avg=0.017106, Delta=+0.008436
**Post-Trade (post-entry)** (bars 0 to 24): Winners avg=0.067367, Losers avg=-0.031682, Delta=+0.099048

## Model x Direction Breakdown

Per-indicator win rate and average value by model and direction.

### Candle Range %

| Model | Direction | Trades | Win Rate | Avg Value |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 24 | 45.8% | 0.3024 |
| EPCH1 | SHORT | 24 | 37.5% | 0.4923 |
| EPCH2 | LONG | 407 | 41.3% | 0.2534 |
| EPCH2 | SHORT | 305 | 43.9% | 0.3257 |
| EPCH3 | LONG | 48 | 54.2% | 0.3667 |
| EPCH3 | SHORT | 48 | 45.8% | 0.4178 |
| EPCH4 | LONG | 603 | 46.4% | 0.2542 |
| EPCH4 | SHORT | 560 | 55.4% | 0.2886 |

### Volume Delta (5-bar)

| Model | Direction | Trades | Win Rate | Avg Value |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 24 | 45.8% | 114869.7279 |
| EPCH1 | SHORT | 24 | 37.5% | -117149.3583 |
| EPCH2 | LONG | 407 | 41.3% | 15775.0765 |
| EPCH2 | SHORT | 305 | 43.9% | 25836.6029 |
| EPCH3 | LONG | 48 | 54.2% | 133098.7102 |
| EPCH3 | SHORT | 48 | 45.8% | -152378.6094 |
| EPCH4 | LONG | 603 | 46.4% | 31948.0661 |
| EPCH4 | SHORT | 560 | 55.4% | 4825.0937 |

### Volume ROC

| Model | Direction | Trades | Win Rate | Avg Value |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 24 | 45.8% | 30.7951 |
| EPCH1 | SHORT | 24 | 37.5% | 54.9377 |
| EPCH2 | LONG | 407 | 41.3% | 521.1401 |
| EPCH2 | SHORT | 305 | 43.9% | 498.0313 |
| EPCH3 | LONG | 48 | 54.2% | 110.6529 |
| EPCH3 | SHORT | 48 | 45.8% | 40.7577 |
| EPCH4 | LONG | 603 | 46.4% | 249.3727 |
| EPCH4 | SHORT | 560 | 55.4% | 142.5085 |

### SMA Spread %

| Model | Direction | Trades | Win Rate | Avg Value |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 24 | 45.8% | 0.2408 |
| EPCH1 | SHORT | 24 | 37.5% | 0.2432 |
| EPCH2 | LONG | 407 | 41.3% | 0.1498 |
| EPCH2 | SHORT | 305 | 43.9% | 0.2658 |
| EPCH3 | LONG | 48 | 54.2% | 0.2052 |
| EPCH3 | SHORT | 48 | 45.8% | 0.3353 |
| EPCH4 | LONG | 603 | 46.4% | 0.1685 |
| EPCH4 | SHORT | 560 | 55.4% | 0.2210 |

### CVD Slope

| Model | Direction | Trades | Win Rate | Avg Value |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 24 | 45.8% | 0.1219 |
| EPCH1 | SHORT | 24 | 37.5% | -0.1084 |
| EPCH2 | LONG | 407 | 41.3% | 0.0223 |
| EPCH2 | SHORT | 305 | 43.9% | 0.0222 |
| EPCH3 | LONG | 48 | 54.2% | 0.1288 |
| EPCH3 | SHORT | 48 | 45.8% | -0.0797 |
| EPCH4 | LONG | 603 | 46.4% | 0.0544 |
| EPCH4 | SHORT | 560 | 55.4% | -0.0038 |

### SMA Configuration

| Model | Direction | Trades | Win Rate | Most Common |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 24 | 45.8% | BULL |
| EPCH1 | SHORT | 24 | 37.5% | BEAR |
| EPCH2 | LONG | 407 | 41.3% | BEAR |
| EPCH2 | SHORT | 305 | 43.9% | BULL |
| EPCH3 | LONG | 48 | 54.2% | BULL |
| EPCH3 | SHORT | 48 | 45.8% | BEAR |
| EPCH4 | LONG | 603 | 46.4% | BULL |
| EPCH4 | SHORT | 560 | 55.4% | BEAR |

### SMA Momentum

| Model | Direction | Trades | Win Rate | Most Common |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 24 | 45.8% | NARROWING |
| EPCH1 | SHORT | 24 | 37.5% | WIDENING |
| EPCH2 | LONG | 407 | 41.3% | WIDENING |
| EPCH2 | SHORT | 305 | 43.9% | WIDENING |
| EPCH3 | LONG | 48 | 54.2% | NARROWING |
| EPCH3 | SHORT | 48 | 45.8% | WIDENING |
| EPCH4 | LONG | 603 | 46.4% | WIDENING |
| EPCH4 | SHORT | 560 | 55.4% | NARROWING |

### Price Position

| Model | Direction | Trades | Win Rate | Most Common |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 24 | 45.8% | ABOVE |
| EPCH1 | SHORT | 24 | 37.5% | BELOW |
| EPCH2 | LONG | 407 | 41.3% | BELOW |
| EPCH2 | SHORT | 305 | 43.9% | ABOVE |
| EPCH3 | LONG | 48 | 54.2% | ABOVE |
| EPCH3 | SHORT | 48 | 45.8% | BELOW |
| EPCH4 | LONG | 603 | 46.4% | ABOVE |
| EPCH4 | SHORT | 560 | 55.4% | BELOW |

### M5 Structure

| Model | Direction | Trades | Win Rate | Most Common |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 24 | 45.8% | BULL |
| EPCH1 | SHORT | 24 | 37.5% | BEAR |
| EPCH2 | LONG | 407 | 41.3% | BULL |
| EPCH2 | SHORT | 305 | 43.9% | BEAR |
| EPCH3 | LONG | 48 | 54.2% | BEAR |
| EPCH3 | SHORT | 48 | 45.8% | BEAR |
| EPCH4 | LONG | 603 | 46.4% | BEAR |
| EPCH4 | SHORT | 560 | 55.4% | BULL |

### M15 Structure

| Model | Direction | Trades | Win Rate | Most Common |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 24 | 45.8% | BEAR |
| EPCH1 | SHORT | 24 | 37.5% | BEAR |
| EPCH2 | LONG | 407 | 41.3% | BEAR |
| EPCH2 | SHORT | 305 | 43.9% | BEAR |
| EPCH3 | LONG | 48 | 54.2% | BEAR |
| EPCH3 | SHORT | 48 | 45.8% | BEAR |
| EPCH4 | LONG | 603 | 46.4% | BEAR |
| EPCH4 | SHORT | 560 | 55.4% | BEAR |

### H1 Structure

| Model | Direction | Trades | Win Rate | Most Common |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 24 | 45.8% | BULL |
| EPCH1 | SHORT | 24 | 37.5% | BULL |
| EPCH2 | LONG | 407 | 41.3% | BULL |
| EPCH2 | SHORT | 305 | 43.9% | BULL |
| EPCH3 | LONG | 48 | 54.2% | BEAR |
| EPCH3 | SHORT | 48 | 45.8% | BEAR |
| EPCH4 | LONG | 603 | 46.4% | BEAR |
| EPCH4 | SHORT | 560 | 55.4% | BEAR |

## Key Observations for AI Analysis

When analyzing deep dive data, consider:
1. **Strongest predictor**: Which single indicator has the most consistent winner/loser separation across all phases?
2. **Phase transitions**: Does any indicator 'flip' behavior between ramp-up and post-trade?
3. **Model-specific edges**: Do some models benefit more from certain indicators?
4. **Direction asymmetry**: After normalization, are LONGs and SHORTs equally predictable?
5. **Leading indicators**: Which indicators diverge earliest in the ramp-up phase?