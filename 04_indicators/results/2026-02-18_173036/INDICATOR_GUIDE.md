# Epoch Indicator Guide: How to Use These Indicators When Trading Zones

> Based on 2,019 trades | 47.5% Win Rate | 0.85 Avg R | All Models, All Directions
> Date Range: 2026-02-09 to 2026-02-18
> Generated: 2026-02-18

---

## CRITICAL CHANGE FROM PRIOR ANALYSIS

The dataset has nearly doubled (1,126 -> 2,019 trades) and the results have degraded significantly:

| Metric | Prior (Feb 15) | Current (Feb 18) | Change |
|--------|---------------|-------------------|--------|
| Trades | 1,126 | 2,019 | +79% |
| Win Rate | 54.8% | 47.5% | **-7.3pp** |
| Avg R | 1.23 | 0.85 | **-0.38R** |

**The system is currently below breakeven on raw unfiltered trades.** This makes indicator filtering not just helpful but *essential* for profitability. The good news: the edges within the data are sharper and more reliable with the larger sample.

---

## THE BIG PICTURE: Model Selection + Direction

| What | Win Rate | Avg R | Verdict |
|------|----------|-------|---------|
| EPCH4 SHORT | 55.4% | -- | **Your best edge -- focus here** |
| EPCH3 LONG | 54.2% | -- | Solid secondary |
| EPCH4 LONG | 46.4% | -- | Below breakeven unfiltered -- needs strong confirmation |
| EPCH2 SHORT | 43.9% | -- | Marginal -- heavy filtering required |
| EPCH2 LONG | 41.3% | -- | Avoid or treat as speculative |
| EPCH1 SHORT | 37.5% | -- | **Avoid entirely** |
| EPCH1 LONG | 45.8% | -- | Small sample (24), unreliable |

**Rule #1:** EPCH4 SHORT is your bread and butter (560 trades, 55.4% WR). EPCH3 LONG is your secondary edge (48 trades, 54.2%). Everything else needs aggressive filtering or avoidance.

**Rule #2:** SHORT trades outperform LONG trades across the board (50.7% vs 44.8%). When in doubt, favor the short side.

---

## BEFORE YOU ENTER: The Pre-Entry Checklist

### 1. H1 Structure (Strongest Categorical Edge -- 14.3pp spread)

| H1 Structure | Trades | Win Rate | Avg R | Action |
|-------------|--------|----------|-------|--------|
| BEAR | 998 | **54.8%** | **1.20** | **TAKE IT -- your highest edge filter** |
| BULL | 1,021 | 40.5% | 0.52 | **AVOID unless other conditions are exceptional** |

This is the single most powerful filter in the dataset. H1 BEAR produces a 14.3 percentage point edge over H1 BULL. The prior analysis showed 60.4% vs 50.9% -- the spread has widened, confirming this is real and not noise.

**In plain English:** Your zone entries work best when the hourly structure is bearish. You're catching bounces at high-volume nodes in downtrends, or riding short continuation. When the H1 is bullish, your zone trades become significantly less reliable.

### 2. SMA Configuration (12.9pp spread)

| SMA Config | Trades | Win Rate | Avg R | Action |
|-----------|--------|----------|-------|--------|
| BULL | 1,007 | **53.9%** | **1.05** | **Favorable -- fast SMA above slow** |
| BEAR | 1,008 | 41.0% | 0.66 | Caution -- especially toxic with BULL H1 |

**In plain English:** You want the local M1 momentum (SMA config) to be bullish even when the larger H1 structure is bearish. This is the classic mean-reversion setup: local bullish momentum within a bearish structural context = price recovering toward your zone level.

### 3. Price Position (9.5pp spread between best and worst)

| Position | Trades | Win Rate | Avg R | Action |
|---------|--------|----------|-------|--------|
| ABOVE SMA | 825 | **51.3%** | **1.06** | Good |
| BETWEEN | 351 | **51.9%** | 0.99 | Good |
| BELOW SMA | 839 | 41.8% | 0.59 | **AVOID -- confirmed leak** |

**This was an edge in the prior guide and it holds.** Price below the SMAs at entry is a consistent loser. Skip these trades entirely.

### 4. SMA Spread % (Sweet Spot in Q3)

| Condition | Range | Trades | Win Rate | Avg R | Action |
|-----------|-------|--------|----------|-------|--------|
| Q3 (sweet spot) | 0.07% - 0.13% | 403 | **51.9%** | **1.07** | **IDEAL -- clear trend developing** |
| Q4 | 0.13% - 0.31% | 403 | 47.1% | 1.07 | Neutral -- decent R but coin-flip WR |
| Q1 (flat) | < 0.03% | 403 | 47.9% | 0.75 | Weak -- no trend established |
| Q2 | 0.03% - 0.07% | 403 | 43.2% | 0.63 | **AVOID -- worst quintile** |

**Ramp-up confirmation:** Winners have SMA spread climbing from ~0.17% to ~0.21% in the 25 bars before entry. Losers stay flatter at ~0.15% to ~0.18%. Look for the SMAs to be separating (not just separated).

### 5. Volume Delta (U-Shaped -- Conviction Matters)

| Quintile | Range | Trades | Win Rate | Avg R | Action |
|----------|-------|--------|----------|-------|--------|
| Q1 (strong negative) | < -79K | 404 | **55.4%** | **1.34** | **BEST -- strong directional conviction** |
| Q5 (strong positive) | > 97K | 403 | 50.6% | 1.10 | Good -- strong other direction |
| Q3 (middle) | -12K to +19K | 404 | 40.3% | 0.48 | **WORST -- indecisive, avoid** |

**In plain English:** The U-shape pattern from the prior guide is confirmed and even more pronounced. Decisive order flow in either direction (you trade both longs and shorts) produces winners. The indecisive middle is where your losses accumulate. If vol delta is wishy-washy near zero, step aside.

### 6. Candle Range % (Large or Tight -- Avoid the Middle)

| Quintile | Range | Trades | Win Rate | Avg R | Action |
|----------|-------|--------|----------|-------|--------|
| Q5 (large) | > 0.39% | 403 | **52.1%** | **1.18** | **Good -- strong momentum candles** |
| Q2 | 0.08% - 0.13% | 404 | 51.0% | 0.89 | Decent |
| Q1 (tight) | < 0.08% | 404 | 48.0% | 0.85 | OK but not the standout it was prior |
| Q4 | 0.22% - 0.39% | 404 | 44.6% | 0.76 | Weak |
| Q3 (mid-range) | 0.13% - 0.22% | 404 | **42.1%** | **0.58** | **WORST -- choppy, avoid** |

**Shift from prior analysis:** Tight absorption candles (Q1) are no longer the standout winner they were before (dropped from 63.7% to 48.0%). Large candles now have a slight edge. The mid-range "mushy middle" remains the worst. The composite data below tells the fuller story -- ABSORPTION candles still dominate in specific combos.

### 7. Volume ROC (Steady is Best)

| Quintile | Range | Trades | Win Rate | Avg R | Action |
|----------|-------|--------|----------|-------|--------|
| Q2 | -38% to -18% | 403 | **51.9%** | 0.94 | **BEST -- volume declining moderately** |
| Q1 | < -38% | 403 | 48.6% | 0.78 | OK |
| Q3 | -18% to +4% | 403 | 47.4% | 0.79 | Neutral |
| Q5 (surging) | > 40% | 403 | 45.9% | 0.95 | Decent R but lower WR |
| Q4 | +4% to +40% | 403 | **43.4%** | 0.80 | **Weak -- avoid** |

**Confirmed from prior guide:** Entering when volume is steady or slightly declining remains better than chasing volume spikes. The best entries happen during relative calm (Q2), not during surges.

### 8. CVD Slope (Weak Standalone, Strong in Context)

| Quintile | Range | Trades | Win Rate | Avg R |
|----------|-------|--------|----------|-------|
| Q4 | +0.07 to +0.24 | 404 | 48.8% | 0.95 |
| Q3 | -0.05 to +0.07 | 404 | 48.0% | 0.80 |
| Q5 | > +0.24 | 403 | 47.9% | 0.83 |
| Q2 | -0.16 to -0.05 | 404 | 46.8% | 0.79 |
| Q1 | < -0.17 | 404 | 46.3% | 0.90 |

CVD slope at entry shows minimal standalone edge across quintiles. However, the **ramp-up and post-trade data tell the real story:**

- **Pre-entry:** Winners show CVD slope at +0.040 by bar 24 vs losers at +0.020 -- the slope is building in the trade direction
- **Post-entry:** Winners surge to +0.10 by bar 5; losers drop to -0.01 by bar 4 -- this is your confirmation/exit signal

Use CVD slope as a **trend confirmation** tool, not a threshold filter.

### 9. SMA Momentum (New Signal)

| Momentum | Trades | Win Rate | Avg R | Action |
|----------|--------|----------|-------|--------|
| STABLE | 133 | **52.6%** | 0.98 | Best but small sample |
| WIDENING | 964 | 50.2% | 0.93 | Good -- trend accelerating |
| NARROWING | 903 | 44.4% | 0.78 | **Avoid -- momentum fading** |

**New insight not in prior guide:** When the SMAs are narrowing (converging), trades perform worse. You want the SMAs stable or widening at entry. Narrowing SMAs signal the trend is losing steam right as you're entering.

---

## STRUCTURAL CONTEXT: Categorical Indicators Ranked by Edge

| Indicator | Best State | Win Rate | Worst State | Win Rate | Spread |
|-----------|-----------|----------|-------------|----------|--------|
| H1 Structure | BEAR | 54.8% | BULL | 40.5% | **14.3pp** |
| SMA Config | BULL | 53.9% | BEAR | 41.0% | **12.9pp** |
| Price Position | BTWN | 51.9% | BELOW | 41.8% | **10.1pp** |
| SMA Momentum | STABLE | 52.6% | NARROWING | 44.4% | **8.2pp** |
| M5 Structure | BULL | 50.0% | BEAR | 45.2% | **4.8pp** |
| M15 Structure | BEAR | 48.6% | BULL | 46.1% | **2.5pp** |

**H1 Structure and SMA Config are your two most powerful filters.** M15 and M5 structure have much weaker standalone edges and should be used only in combination.

---

## THE IDEAL SETUP (What the Data Says to Look For)

### A-Grade Setups (60%+ Win Rate, 20+ trades)

| # | SMA Config | H1 | M15 | Vol ROC | Candle | Trades | Win Rate | Avg R |
|---|------------|-----|-----|---------|--------|--------|----------|-------|
| 1 | BULL | BULL | BULL | NORMAL | ABSORPTION | 39 | **71.8%** | **2.28** |
| 2 | BEAR | BEAR | BEAR | ELEVATED | NORMAL | 67 | **64.2%** | 1.48 |
| 3 | BULL | BULL | BEAR | ELEVATED | NORMAL | 41 | **63.4%** | 2.05 |
| 4 | BULL | BULL | BEAR | NORMAL | NORMAL | 131 | **61.8%** | 1.35 |
| 5 | BULL | BEAR | BULL | NORMAL | ABSORPTION | 81 | **61.7%** | 1.35 |
| 6 | BULL | BEAR | BULL | NORMAL | NORMAL | 26 | 61.5% | 1.85 |

### The Pattern in the Winners:
- **BULL SMA Config** appears in 5 of the top 6 combos
- **NORMAL volume** dominates -- don't chase volume spikes
- **ABSORPTION candles** appear in 3 of the top 6 -- tight price action at the zone
- The **#1 combo** (BULL SMA + BULL H1 + BULL M15 + Normal Vol + Absorption) produces a massive 71.8% WR / 2.28R on 39 trades
- **#4** is the largest reliable sample: BULL SMA + BULL H1 + BEAR M15 + Normal Vol + Normal candles at 61.8% on 131 trades

### AVOID These (Under 30% Win Rate) -- CRITICAL

| # | SMA Config | H1 | M15 | Vol ROC | Candle | Trades | Win Rate | Avg R |
|---|------------|-----|-----|---------|--------|--------|----------|-------|
| 1 | BEAR | BULL | BEAR | NORMAL | ABSORPTION | 74 | **9.5%** | **-0.65** |
| 2 | BEAR | BULL | BULL | ELEVATED | NORMAL | 67 | **20.9%** | -0.06 |
| 3 | BEAR | BULL | BULL | NORMAL | NORMAL | 129 | **23.3%** | -0.05 |
| 4 | BEAR | BULL | BEAR | NORMAL | NORMAL | 73 | **28.8%** | 0.42 |

### The Pattern in the Losers -- YOUR BIGGEST LEAK:
- **BEAR SMA + BULL H1** appears in ALL 4 worst combos (combined: 343 trades, ~21% WR)
- This is **17% of all trades** being taken at a ~21% win rate -- it's destroying your overall numbers
- The #1 worst combo (9.5% on 74 trades!) is BEAR SMA + BULL H1 with ABSORPTION candles -- what looks like "tight price action at the zone" in a bearish momentum / bullish structure context is actually a trap
- **ELEVATED volume + BULL H1** is also toxic

### **MANDATORY FILTER: If SMA Config = BEAR and H1 = BULL, DO NOT TAKE THE TRADE.**

Applying this single rule would eliminate ~343 trades at ~21% win rate, which would increase the remaining 1,676 trades to approximately **52.9% WR / 0.98 Avg R** -- a meaningful improvement from the unfiltered 47.5%.

---

## AFTER ENTRY: Early Warning Signs

The post-trade data provides the clearest signals in the entire dataset.

### Volume Delta -- The Strongest Post-Entry Signal

| Bar After Entry | Winner Avg | Loser Avg | Gap |
|----------------|-----------|----------|-----|
| Bar 0 (entry) | +55,803 | +20,985 | 34,818 |
| Bar 1 | +69,611 | **-7,656** | **77,267** |
| Bar 2 | +78,974 | -21,344 | 100,318 |
| Bar 3 | +81,471 | -38,212 | 119,683 |
| Bar 4 | +88,330 | -45,057 | **133,387** |
| Bar 5 | +60,631 | -67,108 | 127,739 |

**By bar 1**, losers have already flipped to negative vol delta. By bar 3, the gap is over 119K. This is your fastest exit signal.

### CVD Slope -- Confirms Within 4 Bars

| Bar After Entry | Winner CVD Slope | Loser CVD Slope | Gap |
|----------------|-----------------|----------------|-----|
| Bar 0 | +0.053 | +0.017 | 0.036 |
| Bar 1 | +0.065 | +0.017 | 0.048 |
| Bar 2 | +0.076 | +0.014 | 0.062 |
| Bar 3 | +0.087 | **+0.006** | 0.081 |
| Bar 4 | +0.095 | **-0.004** | **0.099** |
| Bar 5 | +0.101 | -0.014 | 0.115 |

Winners: CVD slope accelerates from +0.05 to +0.10 in 5 bars.
Losers: CVD slope stalls at +0.02, then goes negative by bar 4.

### SMA Spread -- Divergence by Bar 3

Winners: SMA spread holds ~0.21% and slowly widens to 0.24% by bar 9.
Losers: SMA spread starts at 0.185% and barely changes, then declines after bar 9.

### Practical Trade Management Rules:

> **2-Bar Rule:** If vol delta hasn't turned favorable (positive for your direction) within 2 bars of entry, the trade is more likely a loser. Tighten stop or reduce size.

> **4-Bar Confirmation:** If CVD slope is still positive and climbing at bar 4, the trade has a high probability of continuation. Consider holding for higher R targets.

> **Exit Signal:** If vol delta is negative AND CVD slope is declining at bar 3, exit at market. Don't wait for your stop.

---

## RAMP-UP: What Winners Look Like Before Entry

The 25-bar pre-entry progression reveals how winners build into the trade:

| Indicator | Winner Pattern (Last 10 Bars) | Loser Pattern (Last 10 Bars) |
|-----------|-------------------------------|------------------------------|
| SMA Spread | Climbing from 0.21% -> 0.21% (steady) | Flat at ~0.18% |
| Vol Delta | Recovers from negative dip, turns positive ~bar 19-21 | Stays positive but weaker magnitude |
| CVD Slope | Builds from +0.01 -> +0.04 (accelerating) | Stays flat ~+0.02 |
| Vol ROC | Higher but settling (136-220% range) | Lower (163-372% range, more erratic) |
| Candle Range | Slightly larger (0.28-0.30%) | Slightly smaller (0.26-0.27%) |

**Key ramp-up signals:**
1. **CVD Slope building:** Winners show CVD slope accelerating from +0.01 to +0.04 in the final 10 bars. If you don't see the slope building in your direction, confidence drops.
2. **Vol Delta turning positive:** Winners show vol delta going from negative (bars 9-14) back to positive by bar 18+. This "recovery" pattern -- dipping then building back -- is the setup completing.
3. **SMA Spread advantage:** Winners maintain a +0.03% SMA spread advantage throughout the ramp-up. Wider SMA separation = stronger trend.

---

## SETUP SCORE: Non-Linear Pattern

| Score | Trades | Win Rate | Avg R | Verdict |
|-------|--------|----------|-------|---------|
| 0 | 144 | 50.7% | 0.88 | Baseline |
| 1 | 369 | 44.4% | 0.62 | Below baseline |
| 2 | 466 | 47.9% | 0.89 | Near baseline |
| **3** | **510** | **53.7%** | **1.10** | **SWEET SPOT -- best combo of WR + R + sample** |
| 4 | 346 | 43.6% | 0.77 | Below baseline |
| 5 | 159 | 41.5% | 0.67 | Poor |
| 6 | 25 | 36.0% | 0.80 | Worst (small sample) |

**Score 3 is the clear winner** -- the only score above breakeven with a meaningful sample. The prior guide showed sweet spots at 1 and 3; now only 3 holds up. Higher scores (4-6) continue to perform worse, confirming that "too many favorable conditions" may signal crowded or over-obvious setups.

**Recommendation:** Target setups where exactly 3 of the 7 score conditions are met.

---

## QUICK REFERENCE: Pre-Entry Decision Tree

```
1. Is SMA Config = BEAR and H1 = BULL?
   YES -> HARD STOP. Do not take the trade. (~21% WR on 343 trades)
   NO -> Continue

2. Is this EPCH4 SHORT or EPCH3 LONG?
   YES -> Continue (your edge models)
   EPCH4 LONG -> Proceed with caution, needs strong confirmation
   EPCH1/2 -> Need VERY strong indicators; consider skipping

3. Check H1 Structure
   BEAR -> Strong edge (+54.8% WR, +1.20R)
   BULL -> Need SMA Config = BULL and other confirmation

4. Check SMA Config
   BULL (fast > slow) -> Good (+53.9% WR, +1.05R)
   BEAR -> Only proceed if H1 is also BEAR

5. Check Price Position
   ABOVE or BETWEEN -> Proceed
   BELOW -> Skip trade (41.8% WR, 0.59R)

6. Check SMA Momentum
   WIDENING or STABLE -> Good
   NARROWING -> Lower confidence, need other confirmation

7. Check Vol Delta
   Strongly directional (Q1 or Q5) -> TAKE IT
   Indecisive near zero (Q3) -> SKIP (40.3% WR)

8. Check Vol ROC
   Steady/declining (Q2) -> Best entries
   Moderate positive (Q4, +4% to +40%) -> Weakest zone

9. ENTER if passing Steps 1-5 plus at least 2 of Steps 6-8
```

---

## WHAT CHANGED FROM THE PRIOR GUIDE (Feb 15)

| Finding | Prior Guide (1,126 trades) | Current (2,019 trades) | Status |
|---------|--------------------------|------------------------|--------|
| EPCH4 is best model | 60.7% WR | 50.7% overall, **55.4% SHORT** | **Refined -- EPCH4 SHORT specifically** |
| H1 BEAR = edge | 60.4% WR | 54.8% WR | **CONFIRMED, stronger contrast** |
| BEAR SMA + BULL H1 = toxic | ~27% WR (89 trades) | ~21% WR (343 trades) | **CONFIRMED, even worse** |
| Absorption candles best | 63.7% WR | 48.0% (standalone) | **WEAKENED standalone -- still strong in combos** |
| Vol ROC steady = best | 59-60% WR | 51.9% WR | **CONFIRMED but weaker** |
| Short bias | 57.6% WR | 50.7% WR | **CONFIRMED** |
| Score 3 sweet spot | 59.0% WR | 53.7% WR | **CONFIRMED** |
| Price below SMA = bad | 46.6% WR | 41.8% WR | **CONFIRMED, even worse** |
| CVD slope = ramp-up signal | Climb to +0.05 pre-entry | Climb to +0.04 pre-entry | **CONFIRMED** |
| SMA Momentum | Not tracked | NARROWING = 44.4% | **NEW finding** |

---

## SUMMARY: Three Rules to Live By (Updated)

1. **NEVER trade BEAR SMA + BULL H1.** This is your single biggest leak. It accounts for ~17% of all trades at ~21% win rate. Eliminating it alone boosts the remaining pool to ~53% WR. Tape it to your monitor.

2. **Focus on EPCH4 SHORT in H1 BEAR structure with BULL SMA config, price ABOVE or BETWEEN the SMAs, and SMA WIDENING.** This is your highest-conviction setup. When you see it with normal volume and absorption/tight candles at the zone, you're looking at 60%+ win rates.

3. **Use post-entry vol delta as your 2-bar kill switch.** If vol delta hasn't turned favorable within 2 bars, the trade is likely a loser. Don't hope -- manage. Winners show immediate order flow confirmation; losers flip negative by bar 1. This is the most actionable post-entry signal in the dataset.
