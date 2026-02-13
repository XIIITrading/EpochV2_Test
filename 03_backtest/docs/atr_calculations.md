# ATR (Average True Range) — Calculation Engine Overview

**Epoch Trading System v2.0 — XIII Trading LLC**
**Module:** 03_backtest / m1_indicator_bars_2
**Added:** February 2026

---

## 1. Purpose

Three ATR columns have been added to every row in `m1_indicator_bars_2`:

| Column   | Timeframe | What It Measures |
|----------|-----------|------------------|
| `atr_m1` | 1-minute  | Micro-volatility at the bar level |
| `atr_m5` | 5-minute  | Short-term volatility envelope |
| `atr_m15`| 15-minute | Medium-term volatility envelope |

These values will be consumed by future secondary processors that calculate
win/loss outcomes based on ATR-derived stop distances. For now, they are
pre-computed and stored alongside the existing 22 indicators and 3 composite
scores so they are ready when the stop-analysis calculators are built.

---

## 2. The ATR Formula

ATR is a two-step calculation: True Range first, then a Simple Moving Average.

### Step 1 — True Range (per bar)

```
True Range = max(
    high - low,              ← Normal bar range
    |high - prev_close|,     ← Gap up captured
    |low  - prev_close|      ← Gap down captured
)
```

The True Range is always >= 0. It captures the full extent of price movement
including any overnight or intrabar gaps that the simple high-low range would
miss.

**Worked Example:**

```
Previous bar close:  $102.00
Current bar high:    $105.00
Current bar low:     $100.00

  high - low        = $5.00
  |high - prevC|    = |105 - 102| = $3.00
  |low  - prevC|    = |100 - 102| = $2.00

  True Range = max(5.00, 3.00, 2.00) = $5.00
```

**Gap Example (gap up opening):**

```
Previous bar close:  $100.00
Current bar high:    $110.00
Current bar low:     $108.00

  high - low        = $2.00
  |high - prevC|    = |110 - 100| = $10.00    ← Captures the gap
  |low  - prevC|    = |108 - 100| = $8.00

  True Range = max(2.00, 10.00, 8.00) = $10.00
```

Without the gap components, True Range would only report $2.00 — completely
missing the $10 of actual price movement.

### Step 2 — ATR (14-period Simple Moving Average)

```
ATR = SMA(True Range, 14)
    = sum(TR[i-13] ... TR[i]) / 14
```

The 14-period SMA smooths out individual bar noise and gives a stable measure
of "typical range" over the last 14 bars at that timeframe.

**Configuration:** The period (14) is defined in two places:
- Centralized library: `processor/indicators/config.py` → `ATR_CONFIG["period"]`
- Local module config: `m1_indicator_bars_2/config.py` → `ATR_PERIOD`

Both are set to 14 and kept in sync.

---

## 3. Warmup Periods

ATR requires historical data before it can produce values. The first bars in
each session will have `NULL` ATR values until enough data accumulates.

| Column   | Warmup Requirement | Approx. Time Until First Value |
|----------|--------------------|-------------------------------|
| `atr_m1` | 14 M1 bars         | ~14 minutes from session start |
| `atr_m5` | 15 M5 bars (14 TR + 1 for prev_close) | ~75 minutes of M5 data |
| `atr_m15`| 15 M15 bars (14 TR + 1 for prev_close) | ~225 minutes of M15 data |

Note: M5 and M15 ATR use lookback bars from prior trading days (fetched via
Polygon API and cached by the HTF bar fetcher), so in practice they often have
values from early in the session because the lookback window extends into
previous days' data.

---

## 4. Where Each ATR Is Calculated

The three ATR values are computed in different locations because they operate
on different data sources:

### M1 ATR → `indicators.py` (DataFrame-level)

**File:** `m1_indicator_bars_2/indicators.py` → `_add_atr_m1()`

M1 ATR operates on the full M1 bar DataFrame that is already loaded from
`m1_bars_2`. This is the same DataFrame that all other M1 indicators
(SMA, Volume ROC, CVD, etc.) are calculated on.

**How it works:**
1. Shift the `close` column by 1 to get `prev_close` for each bar
2. Apply `calculate_true_range(high, low, prev_close)` to each row
   (using the centralized formula from `processor/indicators/core/atr.py`)
3. Rolling SMA(14) on the True Range series
4. Result stored in `atr_m1` column

This follows the same pattern as every other indicator in the module:
a `_add_xxx()` method that takes the DataFrame, adds columns, and returns it.

### M5 and M15 ATR → `calculator.py` (per-bar loop)

**File:** `m1_indicator_bars_2/calculator.py` → `_calculate_htf_atr()`

M5 and M15 ATR need higher-timeframe bars that come from the Polygon API.
These bars are already fetched and cached by `HTFBarFetcher` for the
multi-timeframe structure detection (fractal BOS/ChoCH). The ATR calculation
simply reuses the same cached bar data — **no additional API calls are made**.

**How it works (for each M1 bar in the session):**
1. Call `fetcher.fetch_bars(ticker, timeframe, trade_date, bar_time)`
   - Returns all M5 or M15 bars up to `bar_time` from cache
2. If fewer than 15 bars available, return `None` (insufficient warmup)
3. Loop through bars, calculate True Range for each using prev bar's close
4. Take the last 14 True Range values, compute their average
5. Return the ATR value

**Cache Key Pattern:** `{ticker}_{timeframe}_{YYYYMMDD}`
- Example: `AAPL_M5_20260210`
- One API call per ticker-timeframe-date populates the cache
- All subsequent calls to `fetch_bars()` for the same key return filtered
  results from cache

---

## 5. Centralized Library

The core True Range formula lives in the centralized indicator library so it
can be reused by any Epoch module, not just m1_indicator_bars_2.

### File: `processor/indicators/core/atr.py`

**Functions:**

| Function | Purpose | Used By |
|----------|---------|---------|
| `calculate_true_range(high, low, prev_close)` | Single-bar True Range | indicators.py (_add_atr_m1) |
| `calculate_atr(bars, period, up_to_index)` | ATR from bar list, returns ATRResult | Available for future modules |
| `calculate_atr_series(highs, lows, closes, period)` | ATR for full price arrays | Available for future modules |

**Data Type:** `ATRResult` (dataclass)
```
ATRResult:
    atr:         float or None    — The ATR value
    true_range:  float or None    — Last True Range in the window
    period:      int              — Period used (default 14)
```

**Registration Chain:**
```
config.py          → ATR_CONFIG = {"period": 14}
indicator_types.py → ATRResult dataclass
_internal.py       → Exports ATR_CONFIG and ATRResult
core/__init__.py   → Exports calculate_true_range, calculate_atr, calculate_atr_series
core/atr.py        → Implementation (imports from _internal)
```

---

## 6. Database Schema

### New Columns in `m1_indicator_bars_2`

```sql
-- ATR (Average True Range, 14-period)
atr_m1  NUMERIC(12, 6),    -- 14-period ATR on M1 bars
atr_m5  NUMERIC(12, 6),    -- 14-period ATR on M5 bars
atr_m15 NUMERIC(12, 6),    -- 14-period ATR on M15 bars
```

**Type Choice:** `NUMERIC(12, 6)` provides 6 decimal places of precision.
ATR values are price-denominated (e.g., $0.15 for a stock at $150), so the
range and precision match other price-related columns in the table.

**Position:** Between the Composite Scores block and the Metadata block.

### Migration (already applied)

```sql
ALTER TABLE m1_indicator_bars_2 ADD COLUMN IF NOT EXISTS atr_m1 NUMERIC(12, 6);
ALTER TABLE m1_indicator_bars_2 ADD COLUMN IF NOT EXISTS atr_m5 NUMERIC(12, 6);
ALTER TABLE m1_indicator_bars_2 ADD COLUMN IF NOT EXISTS atr_m15 NUMERIC(12, 6);
```

---

## 7. Data Flow Summary

```
                       ┌──────────────────────────────────────┐
                       │         m1_bars_2 (database)         │
                       │   Raw M1 OHLCV bars per ticker-date  │
                       └──────────────┬───────────────────────┘
                                      │
                                      ▼
                       ┌──────────────────────────────────────┐
                       │     indicators.py                    │
                       │     M1IndicatorCalculator            │
                       │     ─────────────────                │
                       │     _add_atr_m1():                   │
                       │       prev_close = close.shift(1)    │
                       │       TR = calculate_true_range(     │
                       │              H, L, prev_close)       │
                       │       atr_m1 = SMA(TR, 14)          │
                       └──────────────┬───────────────────────┘
                                      │
                                      ▼
          ┌──────────────────────────────────────────────────────┐
          │  calculator.py — per-bar loop                        │
          │  M1IndicatorBarsCalculator                           │
          │  ─────────────────────────                           │
          │  For each M1 bar:                                    │
          │    1. Read atr_m1 from DataFrame (already computed)  │
          │    2. _calculate_htf_atr(ticker, date, time, 'M5')  │
          │       └─ fetch_bars() from cache → TR → SMA(14)     │
          │    3. _calculate_htf_atr(ticker, date, time, 'M15') │
          │       └─ fetch_bars() from cache → TR → SMA(14)     │
          │    4. Build M1IndicatorBarResult with all 3 ATRs     │
          └──────────────────┬───────────────────────────────────┘
                             │
                             ▼
          ┌──────────────────────────────────────────────────────┐
          │  populator.py                                        │
          │  M1IndicatorBarsPopulator                            │
          │  ─────────────────────────                           │
          │  INSERT INTO m1_indicator_bars_2 (                   │
          │    ... existing 28 columns ...,                      │
          │    atr_m1, atr_m5, atr_m15,                         │
          │    bars_in_calculation                               │
          │  )                                                   │
          └──────────────────┬───────────────────────────────────┘
                             │
                             ▼
          ┌──────────────────────────────────────────────────────┐
          │  m1_indicator_bars_2 (database)                      │
          │  34 columns: OHLCV(5) + PK(3) + Indicators(9) +    │
          │  Extended(5) + Structure(5) + Scores(3) + ATR(3) +  │
          │  Meta(1)                                             │
          └──────────────────────────────────────────────────────┘
```

---

## 8. Interpreting ATR Values

### What the number means

ATR is expressed in **price units** (dollars for US equities). An ATR of 0.25
on a $150 stock means the average range over the last 14 bars at that
timeframe is $0.25.

### Typical ranges by timeframe

| Timeframe | Typical ATR Range (equities $100-$500) | Interpretation |
|-----------|----------------------------------------|----------------|
| M1        | $0.03 - $0.50                         | Micro-volatility per minute |
| M5        | $0.10 - $1.50                         | Short-term volatility |
| M15       | $0.20 - $3.00                         | Medium-term volatility |

Higher ATR = wider stops needed. Lower ATR = tighter stops possible.

### Future use (stop-analysis calculators)

The intended workflow for future secondary processors:

```
Entry detected at price P
  → Read atr_m1, atr_m5, atr_m15 at entry bar
  → Calculate stop distances:
      Stop_M1  = P - (N * atr_m1)     for LONG
      Stop_M5  = P - (N * atr_m5)     for LONG
      Stop_M15 = P - (N * atr_m15)    for LONG
  → Track M1 bars forward to determine win/loss at each stop level
```

The multiplier `N` (e.g., 1.5x, 2.0x, 3.0x ATR) will be configured in those
future processors. The raw ATR values stored here provide the foundation.

---

## 9. Files Modified

| File | Change |
|------|--------|
| `processor/indicators/core/atr.py` | **NEW** — Centralized ATR functions |
| `processor/indicators/indicator_types.py` | Added `ATRResult` dataclass |
| `processor/indicators/config.py` | Added `ATR_CONFIG = {"period": 14}` |
| `processor/indicators/_internal.py` | Exports `ATR_CONFIG` and `ATRResult` |
| `processor/indicators/core/__init__.py` | Registered 3 ATR functions |
| `m1_indicator_bars_2/config.py` | Added `ATR_PERIOD = 14` |
| `m1_indicator_bars_2/indicators.py` | Added `_add_atr_m1()` method |
| `m1_indicator_bars_2/calculator.py` | Added `_calculate_htf_atr()`, 3 dataclass fields |
| `m1_indicator_bars_2/populator.py` | Added 3 columns to INSERT query |
| `m1_indicator_bars_2/schema/m1_indicator_bars_2.sql` | Added 3 ATR columns to DDL |

---

## 10. No Additional API Calls

A key design decision: M5 and M15 ATR calculations reuse bars that are
**already cached** by `HTFBarFetcher` for the structure detection step.

The structure calculator fetches M5 and M15 bars from Polygon once per
ticker-timeframe-date and caches them in memory. When the ATR calculator
runs immediately after, `fetch_bars()` returns the cached data instantly.

**API call budget (unchanged from before ATR was added):**
- M5 bars: 1 call per ticker-date (already fetched for M5 structure)
- M15 bars: 1 call per ticker-date (already fetched for M15 structure)
- H1 bars: 1 call per ticker-date (from h1_bars DB table)
- H4 bars: 1 call per ticker-date (from Polygon API)
- M1 bars: 0 calls (read from m1_bars_2 database)

**Total: ~4 API calls per ticker-date — same as before ATR was added.**
