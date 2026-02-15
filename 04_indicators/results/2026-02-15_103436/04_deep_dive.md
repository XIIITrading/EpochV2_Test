# 04 - Indicator Deep Dive: Three-Phase Analysis

Per-indicator breakdown across ramp-up (pre-entry), entry snapshot,
and post-trade (post-entry) phases. Direction-normalized where applicable.

## Three-Phase Progression (Continuous Indicators)

### Candle Range %

**Ramp-Up (pre-entry)** (bars -24 to -1): Winners avg=0.308972, Losers avg=0.295436, Delta=+0.013536
**Post-Trade (post-entry)** (bars 0 to 24): Winners avg=0.277661, Losers avg=0.297496, Delta=-0.019835

### Volume Delta (5-bar)
*Direction-normalized: positive = favorable for trade direction*

**Ramp-Up (pre-entry)** (bars -24 to -1): Winners avg=13425.852396, Losers avg=9905.465985, Delta=+3520.386411
**Post-Trade (post-entry)** (bars 0 to 24): Winners avg=21317.013703, Losers avg=-10417.171134, Delta=+31734.184837

### Volume ROC

**Ramp-Up (pre-entry)** (bars -24 to -1): Winners avg=202.929790, Losers avg=177.815443, Delta=+25.114348
**Post-Trade (post-entry)** (bars 0 to 24): Winners avg=10.788505, Losers avg=23.393229, Delta=-12.604724

### SMA Spread %

**Ramp-Up (pre-entry)** (bars -24 to -1): Winners avg=0.245266, Losers avg=0.213258, Delta=+0.032008
**Post-Trade (post-entry)** (bars 0 to 24): Winners avg=0.238781, Losers avg=0.227467, Delta=+0.011314

### CVD Slope
*Direction-normalized: positive = favorable for trade direction*

**Ramp-Up (pre-entry)** (bars -24 to -1): Winners avg=0.029199, Losers avg=0.016846, Delta=+0.012354
**Post-Trade (post-entry)** (bars 0 to 24): Winners avg=0.060280, Losers avg=-0.024149, Delta=+0.084429

## Model x Direction Breakdown

Per-indicator win rate and average value by model and direction.

### Candle Range %

| Model | Direction | Trades | Win Rate | Avg Value |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 14 | 35.7% | 0.3739 |
| EPCH1 | SHORT | 14 | 42.9% | 0.7063 |
| EPCH2 | LONG | 245 | 43.3% | 0.2877 |
| EPCH2 | SHORT | 201 | 53.7% | 0.3904 |
| EPCH3 | LONG | 29 | 55.2% | 0.4115 |
| EPCH3 | SHORT | 32 | 53.1% | 0.4947 |
| EPCH4 | LONG | 300 | 60.0% | 0.3231 |
| EPCH4 | SHORT | 291 | 61.5% | 0.3986 |

### Volume Delta (5-bar)

| Model | Direction | Trades | Win Rate | Avg Value |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 14 | 35.7% | 118027.5250 |
| EPCH1 | SHORT | 14 | 42.9% | -114248.5700 |
| EPCH2 | LONG | 245 | 43.3% | 42394.0118 |
| EPCH2 | SHORT | 201 | 53.7% | 62711.5942 |
| EPCH3 | LONG | 29 | 55.2% | 139352.3066 |
| EPCH3 | SHORT | 32 | 53.1% | -151832.5569 |
| EPCH4 | LONG | 300 | 60.0% | 40982.1128 |
| EPCH4 | SHORT | 291 | 61.5% | 35767.6623 |

### Volume ROC

| Model | Direction | Trades | Win Rate | Avg Value |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 14 | 35.7% | 26.2853 |
| EPCH1 | SHORT | 14 | 42.9% | 90.8639 |
| EPCH2 | LONG | 245 | 43.3% | 521.1207 |
| EPCH2 | SHORT | 201 | 53.7% | 753.6436 |
| EPCH3 | LONG | 29 | 55.2% | 11.8722 |
| EPCH3 | SHORT | 32 | 53.1% | 48.3069 |
| EPCH4 | LONG | 300 | 60.0% | 268.8109 |
| EPCH4 | SHORT | 291 | 61.5% | 211.8269 |

### SMA Spread %

| Model | Direction | Trades | Win Rate | Avg Value |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 14 | 35.7% | 0.2388 |
| EPCH1 | SHORT | 14 | 42.9% | 0.2950 |
| EPCH2 | LONG | 245 | 43.3% | 0.1689 |
| EPCH2 | SHORT | 201 | 53.7% | 0.2811 |
| EPCH3 | LONG | 29 | 55.2% | 0.2624 |
| EPCH3 | SHORT | 32 | 53.1% | 0.4007 |
| EPCH4 | LONG | 300 | 60.0% | 0.2336 |
| EPCH4 | SHORT | 291 | 61.5% | 0.2951 |

### CVD Slope

| Model | Direction | Trades | Win Rate | Avg Value |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 14 | 35.7% | 0.1585 |
| EPCH1 | SHORT | 14 | 42.9% | -0.0234 |
| EPCH2 | LONG | 245 | 43.3% | 0.0706 |
| EPCH2 | SHORT | 201 | 53.7% | 0.0492 |
| EPCH3 | LONG | 29 | 55.2% | 0.1346 |
| EPCH3 | SHORT | 32 | 53.1% | -0.0565 |
| EPCH4 | LONG | 300 | 60.0% | 0.0936 |
| EPCH4 | SHORT | 291 | 61.5% | 0.0063 |

### SMA Configuration

| Model | Direction | Trades | Win Rate | Most Common |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 14 | 35.7% | BULL |
| EPCH1 | SHORT | 14 | 42.9% | BEAR |
| EPCH2 | LONG | 245 | 43.3% | BULL |
| EPCH2 | SHORT | 201 | 53.7% | BULL |
| EPCH3 | LONG | 29 | 55.2% | BULL |
| EPCH3 | SHORT | 32 | 53.1% | BEAR |
| EPCH4 | LONG | 300 | 60.0% | BULL |
| EPCH4 | SHORT | 291 | 61.5% | BEAR |

### SMA Momentum

| Model | Direction | Trades | Win Rate | Most Common |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 14 | 35.7% | NARROWING |
| EPCH1 | SHORT | 14 | 42.9% | NARROWING |
| EPCH2 | LONG | 245 | 43.3% | NARROWING |
| EPCH2 | SHORT | 201 | 53.7% | WIDENING |
| EPCH3 | LONG | 29 | 55.2% | NARROWING |
| EPCH3 | SHORT | 32 | 53.1% | WIDENING |
| EPCH4 | LONG | 300 | 60.0% | WIDENING |
| EPCH4 | SHORT | 291 | 61.5% | NARROWING |

### Price Position

| Model | Direction | Trades | Win Rate | Most Common |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 14 | 35.7% | ABOVE |
| EPCH1 | SHORT | 14 | 42.9% | BELOW |
| EPCH2 | LONG | 245 | 43.3% | ABOVE |
| EPCH2 | SHORT | 201 | 53.7% | ABOVE |
| EPCH3 | LONG | 29 | 55.2% | ABOVE |
| EPCH3 | SHORT | 32 | 53.1% | BELOW |
| EPCH4 | LONG | 300 | 60.0% | ABOVE |
| EPCH4 | SHORT | 291 | 61.5% | ABOVE |

### M5 Structure

| Model | Direction | Trades | Win Rate | Most Common |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 14 | 35.7% | BEAR |
| EPCH1 | SHORT | 14 | 42.9% | BEAR |
| EPCH2 | LONG | 245 | 43.3% | BULL |
| EPCH2 | SHORT | 201 | 53.7% | BEAR |
| EPCH3 | LONG | 29 | 55.2% | BEAR |
| EPCH3 | SHORT | 32 | 53.1% | BEAR |
| EPCH4 | LONG | 300 | 60.0% | BEAR |
| EPCH4 | SHORT | 291 | 61.5% | BEAR |

### M15 Structure

| Model | Direction | Trades | Win Rate | Most Common |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 14 | 35.7% | BEAR |
| EPCH1 | SHORT | 14 | 42.9% | BULL |
| EPCH2 | LONG | 245 | 43.3% | BEAR |
| EPCH2 | SHORT | 201 | 53.7% | BULL |
| EPCH3 | LONG | 29 | 55.2% | BEAR |
| EPCH3 | SHORT | 32 | 53.1% | BEAR |
| EPCH4 | LONG | 300 | 60.0% | BEAR |
| EPCH4 | SHORT | 291 | 61.5% | BEAR |

### H1 Structure

| Model | Direction | Trades | Win Rate | Most Common |
|-------|-----------|--------|----------|-----------|
| EPCH1 | LONG | 14 | 35.7% | BULL |
| EPCH1 | SHORT | 14 | 42.9% | BULL |
| EPCH2 | LONG | 245 | 43.3% | BULL |
| EPCH2 | SHORT | 201 | 53.7% | BULL |
| EPCH3 | LONG | 29 | 55.2% | BEAR |
| EPCH3 | SHORT | 32 | 53.1% | BEAR |
| EPCH4 | LONG | 300 | 60.0% | BEAR |
| EPCH4 | SHORT | 291 | 61.5% | BEAR |

## Key Observations for AI Analysis

When analyzing deep dive data, consider:
1. **Strongest predictor**: Which single indicator has the most consistent winner/loser separation across all phases?
2. **Phase transitions**: Does any indicator 'flip' behavior between ramp-up and post-trade?
3. **Model-specific edges**: Do some models benefit more from certain indicators?
4. **Direction asymmetry**: After normalization, are LONGs and SHORTs equally predictable?
5. **Leading indicators**: Which indicators diverge earliest in the ramp-up phase?