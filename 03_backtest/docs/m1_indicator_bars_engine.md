# M1 Indicator Bars Engine - Technical Reference

**Epoch Trading System v4.1 | XIII Trading LLC**

---

## What This Document Covers

This walks through the two-stage secondary processor pipeline that transforms raw Polygon API data into enriched, analysis-ready 1-minute indicator bars:

```
Stage 1:  Polygon API  ──>  m1_bars_2 table      (raw M1 OHLCV storage)
Stage 2:  m1_bars_2    ──>  m1_indicator_bars_2   (22 indicators + 5 structure + 3 scores)
```

Both stages are self-contained processors with their own configs, runners, and schemas. They sit under `processor/secondary_analysis/`.

---

## Stage 1: Raw M1 Bar Storage

**Location:** `processor/secondary_analysis/m1_bars/`

### What It Does

Fetches 1-minute OHLCV bars from Polygon.io and stores them in the `m1_bars_2` database table. This is a raw data capture step — no calculations, no transformations, just faithful storage of market data.

### The Time Window

Every ticker-date gets bars for a **24-hour extended session**:

```
Prior Trading Day                    Trade Day
       |                                |
    16:00 ──────> 20:00    04:00 ──────> 09:30 ──────> 16:00
    [after-hours]          [pre-market]   [RTH]

    <───── All captured in a single Polygon API call ─────>
```

- **Prior day 16:00-20:00**: After-hours from the previous session
- **Trade day 04:00-09:30**: Pre-market
- **Trade day 09:30-16:00**: Regular trading hours

All bars are stored under `bar_date = trade_date` regardless of which calendar day they occurred on. This groups the entire extended session under one date for easy querying.

### How It Knows What to Fetch

The processor is driven by the `trades_2` table (the entry detection output):

```
1. Query trades_2 for all unique (ticker, date) pairs
2. Query m1_bars_2 for all unique (ticker, bar_date) pairs already stored
3. Subtract: missing = required - already_loaded
4. For each missing pair, fetch from Polygon and insert
```

This means it only fetches data for tickers that had entries detected. No entries = no M1 bars fetched. And it's incremental — running it again only fetches what's missing.

### The Fetch Process

**Class:** `M1BarFetcher` in `m1_bars_storage.py`

```
For each missing (ticker, date):

  1. Calculate prior trading day (skip weekends)
  2. Single Polygon API call:
     GET /v2/aggs/ticker/{ticker}/range/1/minute/{prior_day}/{trade_day}
     Params: adjusted=true, sort=asc, limit=50000
  3. Convert Polygon timestamps (Unix ms) to Eastern Time datetimes
  4. Filter to window: prior_day >= 16:00 AND trade_day <= 16:00
  5. Batch insert into m1_bars_2 (500 rows per batch)
     ON CONFLICT (ticker, bar_timestamp) DO NOTHING
```

**Rate limiting:** Configured at 0.0 seconds (unlimited Polygon tier), with retry logic for 429 responses (exponential backoff: 1s, 2s, 3s).

**Typical output:** ~360-390 bars per ticker-date (one per minute across the extended session).

### The `m1_bars_2` Table

```sql
CREATE TABLE m1_bars_2 (
    id              BIGSERIAL PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL,
    bar_date        DATE NOT NULL,               -- Always the trade date
    bar_time        TIME NOT NULL,               -- Bar start time (ET)
    bar_timestamp   TIMESTAMPTZ NOT NULL,        -- Full timestamp with TZ
    open            NUMERIC(12,4) NOT NULL,
    high            NUMERIC(12,4) NOT NULL,
    low             NUMERIC(12,4) NOT NULL,
    close           NUMERIC(12,4) NOT NULL,
    volume          BIGINT NOT NULL,
    vwap            NUMERIC(12,4),
    transactions    INTEGER,
    fetched_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (ticker, bar_timestamp)               -- Prevents duplicate bars
);
```

**Indexes:** `(ticker, bar_date)`, `(ticker, bar_date, bar_time)`, `(bar_date)`, `(ticker)`

### CLI Runner

**File:** `m1_bars_runner.py`

```bash
python m1_bars_runner.py                  # Full batch run
python m1_bars_runner.py --dry-run        # Fetch but don't save
python m1_bars_runner.py --limit 10       # Process max 10 ticker-dates
python m1_bars_runner.py --schema         # Create m1_bars_2 table
python m1_bars_runner.py --status         # Show storage coverage stats
python m1_bars_runner.py --verbose        # Detailed logging
```

### Files

| File | Purpose |
|------|---------|
| `config.py` | DB creds, Polygon API key, time window, batch size |
| `m1_bars_storage.py` | `M1BarFetcher` (API) + `M1BarsStorage` (orchestration) |
| `m1_bars_runner.py` | CLI entry point with argparse |
| `schema/m1_bars.sql` | DDL for m1_bars_2 table |

---

## Stage 2: M1 Indicator Calculation

**Location:** `processor/secondary_analysis/m1_indicator_bars_2/`

### What It Does

Reads raw M1 bars from the `m1_bars_2` table (never from Polygon API directly), calculates 22 indicators and 3 composite scores across every bar, attaches multi-timeframe market structure labels, and writes the results to `m1_indicator_bars_2`.

### The Key Design Decision: Read From DB, Not API

Stage 1 already fetched and stored the M1 bars. Stage 2 reads from that table rather than making duplicate API calls. This is important because:

- Multiple processors may need the same M1 data
- Re-running indicator calculations doesn't re-fetch bars
- The raw data is preserved even if indicator logic changes
- API quota is conserved

The **one exception** is higher-timeframe structure detection. Native M5, M15, and H4 bars are fetched from Polygon API because they require their own aggregation windows that differ from M1 data. H1 bars are read from the `h1_bars` database table when available, falling back to Polygon API if not.

### How It Knows What to Calculate

Same incremental pattern as Stage 1, with an added join:

```sql
-- Find ticker-dates that:
--   1. Exist in trades_2 (entries were detected)
--   2. Have raw bars in m1_bars_2 (Stage 1 completed)
--   3. Do NOT yet exist in m1_indicator_bars_2 (not yet calculated)

SELECT u.ticker, u.date
FROM unique_ticker_dates u                        -- from trades_2
INNER JOIN m1_bars_2 m ON (ticker, date match)    -- raw bars exist
LEFT JOIN m1_indicator_bars_2 e ON (ticker, date match)
WHERE e.ticker IS NULL                            -- not yet calculated
```

### The Calculation Pipeline

**For each ticker-date:**

```
1. Read all M1 bars from m1_bars_2 into a Pandas DataFrame
   (sorted by bar_timestamp ascending)
       |
2. Calculate all indicators on the DataFrame
   (indicators.py -> M1IndicatorCalculator.add_all_indicators())
       |
3. For each bar in the DataFrame:
   a. Fetch HTF bars for structure detection (M1/M5/M15/H1/H4)
   b. Run fractal BOS/ChoCH structure calculation per timeframe
   c. Build M1IndicatorBarResult combining indicators + structure
       |
4. Batch insert all results into m1_indicator_bars_2
   ON CONFLICT (ticker, bar_date, bar_time) DO NOTHING
       |
5. Clear caches, move to next ticker-date
```

---

## The 22 Indicators — Detailed Formulas

### Entry Qualifier Standard Indicators

These 9 indicators match the standard used by the `02_dow_ai` Entry Qualifier module. Using the same formulas everywhere ensures consistency across the system.

---

#### 1. Candle Range % (`candle_range_pct`)

**What it measures:** How big the bar is relative to price. Tells you if there's actual price movement or if the bar is just noise.

```
candle_range_pct = (high - low) / close * 100
```

**Example:** AAPL bar with H=$187.50, L=$187.00, C=$187.25
```
(187.50 - 187.00) / 187.25 * 100 = 0.267%
```

**Classification thresholds:**
- **< 0.12%** = ABSORPTION (skip — no momentum, bar is too tight)
- **0.12% - 0.15%** = LOW
- **0.15% - 0.20%** = NORMAL (has momentum)
- **>= 0.20%** = HIGH (strong signal)

---

#### 2. Volume Delta Raw (`vol_delta_raw`)

**What it measures:** Estimated buying vs. selling pressure for a single bar. Uses where the close sits within the bar's range to infer who "won" that bar.

```
bar_position = (close - low) / (high - low)     # 0.0 to 1.0
delta_multiplier = (2 * bar_position) - 1        # -1.0 to +1.0
vol_delta_raw = volume * delta_multiplier
```

**How to read it:**
- Close at bar high → position = 1.0 → multiplier = +1.0 → all volume attributed to buyers
- Close at bar low → position = 0.0 → multiplier = -1.0 → all volume attributed to sellers
- Close at midpoint → multiplier = 0.0 → neutral

**Example:** Bar with H=$100, L=$99, C=$99.80, V=50,000
```
position = (99.80 - 99) / (100 - 99) = 0.80
multiplier = (2 * 0.80) - 1 = 0.60
vol_delta_raw = 50,000 * 0.60 = +30,000 (buyers dominated)
```

**Edge case:** If high == low (doji bar), direction is inferred from open vs. close.

---

#### 3. Volume Delta Rolling (`vol_delta_roll`)

**What it measures:** The sum of `vol_delta_raw` over the last 5 bars. Smooths out single-bar noise to show the trend in buying/selling pressure.

```
vol_delta_roll = sum(vol_delta_raw) over last 5 bars
```

Requires 5 bars of data (returns null for first 4 bars).

---

#### 4. Volume ROC (`vol_roc`)

**What it measures:** How the current bar's volume compares to the average of the prior 20 bars. Tells you if volume is elevated, normal, or dried up.

```
baseline = average volume of the 20 bars before this one (shifted by 1)
vol_roc = ((current_volume - baseline) / baseline) * 100
```

**Example:** Current volume = 75,000; 20-bar avg = 50,000
```
vol_roc = ((75000 - 50000) / 50000) * 100 = +50%
```

**Interpretation:**
- **>= 30%** = Elevated (momentum confirmation for scoring)
- **>= 50%** = High (strong momentum, contributes to health score)
- **< 0** = Below average (caution)

Requires 21 bars of data (20-bar lookback + 1 shift).

---

#### 5. SMA 9 (`sma9`)

**What it measures:** Simple moving average of the last 9 close prices. Fast-moving trend indicator.

```
sma9 = average(close) over last 9 bars
```

Returns null until 9 bars of data are available.

---

#### 6. SMA 21 (`sma21`)

**What it measures:** Simple moving average of the last 21 close prices. Slow-moving trend indicator.

```
sma21 = average(close) over last 21 bars
```

Returns null until 21 bars of data are available.

---

#### 7. SMA Config (`sma_config`)

**What it measures:** The relationship between the fast and slow moving averages. One-word trend label.

```
If sma9 > sma21 → "BULL"   (fast above slow, uptrend)
If sma9 < sma21 → "BEAR"   (fast below slow, downtrend)
If sma9 == sma21 → "FLAT"  (no trend)
```

---

#### 8. SMA Spread % (`sma_spread_pct`)

**What it measures:** How far apart the two SMAs are, as a percentage of price. Wider spread = stronger trend.

```
sma_spread_pct = abs(sma9 - sma21) / close * 100
```

**Threshold:** >= 0.15% is considered a "wide spread" indicating a meaningful trend, and earns points in the composite score.

---

#### 9. Price Position (`price_position`)

**What it measures:** Where the current close sits relative to both SMA bands.

```
higher_sma = max(sma9, sma21)
lower_sma = min(sma9, sma21)

If close > higher_sma → "ABOVE"  (price leading the trend)
If close < lower_sma  → "BELOW"  (price trailing)
Otherwise             → "BTWN"   (price between the two SMAs)
```

---

### Extended Indicators

These 5 indicators go beyond the Entry Qualifier standard to provide deeper analysis.

---

#### 10. VWAP (`vwap`)

**What it measures:** Volume-Weighted Average Price, calculated cumulatively within each trading day. Represents the "fair value" price based on volume.

```
typical_price = (high + low + close) / 3
cumulative_TPV = running sum of (typical_price * volume) within the day
cumulative_volume = running sum of volume within the day
vwap = cumulative_TPV / cumulative_volume
```

Resets at the start of each bar_date. The cumulative calculation means VWAP evolves throughout the day, heavily influenced by high-volume periods.

---

#### 11. SMA Spread Signed (`sma_spread`)

**What it measures:** The raw difference between SMA9 and SMA21, preserving direction.

```
sma_spread = sma9 - sma21
```

- Positive = bullish (SMA9 above SMA21)
- Negative = bearish (SMA9 below SMA21)

Unlike `sma_spread_pct` which uses absolute value, this preserves the sign for directional analysis.

---

#### 12. SMA Momentum Ratio (`sma_momentum_ratio`)

**What it measures:** Whether the SMA spread is expanding or contracting over the last 10 bars. Tells you if the trend is accelerating or decelerating.

```
current_spread = abs(sma9 - sma21)
spread_10_bars_ago = abs(sma9 - sma21) from 10 bars back

sma_momentum_ratio = current_spread / spread_10_bars_ago
```

- **> 1.1** = Spread is WIDENING (trend accelerating)
- **< ~0.91** = Spread is NARROWING (trend decelerating)
- **In between** = STABLE

Capped at 999.0 to prevent database overflow.

---

#### 13. SMA Momentum Label (`sma_momentum_label`)

**What it measures:** Human-readable classification of the momentum ratio.

```
If ratio > 1.1    → "WIDENING"   (trend strengthening)
If ratio < 0.909  → "NARROWING"  (trend weakening)
Otherwise          → "STABLE"    (trend holding steady)
```

The 0.909 threshold is `1.0 / 1.1` — the inverse of the widening threshold, making the logic symmetric.

---

#### 14. CVD Slope (`cvd_slope`)

**What it measures:** The trend direction and rate of cumulative volume delta over a 15-bar window. Tells you if order flow is consistently favoring buyers or sellers.

```
1. Calculate bar delta for each bar (same formula as vol_delta_raw)
2. Cumulative sum to build the CVD line
3. Fit a linear regression through the last 15 CVD values
4. Normalize the slope by dividing by average volume over 15 bars
```

**Normalization is key:** Without it, a slope of 1000 means very different things for SPY (billions in volume) vs. a low-cap stock. Dividing by average volume makes the slope comparable across instruments.

- Positive slope = buyers in control
- Negative slope = sellers in control
- Near zero = balanced order flow

---

### Market Structure — Multi-Timeframe (5 Columns)

#### 15-19. Structure Labels (`m1_structure`, `m5_structure`, `m15_structure`, `h1_structure`, `h4_structure`)

**What they measure:** Market direction on each timeframe, using fractal detection and Break of Structure / Change of Character analysis.

Each column is one of: `BULL`, `BEAR`, or `NEUTRAL`.

**How fractal detection works:**

A fractal is a local extreme point. For a bar to be a fractal, it must be the highest high (bearish fractal) or lowest low (bullish fractal) compared to the 2 bars on each side (configurable via `FRACTAL_LENGTH = 5`, with `p = 2` bars per side):

```
Bearish Fractal (local high):
  bars[i-2].high < bars[i].high AND
  bars[i-1].high < bars[i].high AND
  bars[i+1].high < bars[i].high AND
  bars[i+2].high < bars[i].high

Bullish Fractal (local low):
  bars[i-2].low > bars[i].low AND
  bars[i-1].low > bars[i].low AND
  bars[i+1].low > bars[i].low AND
  bars[i+2].low > bars[i].low
```

**How BOS/ChoCH works:**

The algorithm walks through all bars tracking:
- `upper_value`: most recent bearish fractal high
- `lower_value`: most recent bullish fractal low
- `current_structure`: +1 (BULL), -1 (BEAR), or 0 (NEUTRAL)

```
When close breaks ABOVE upper_value:
  - If was BEAR → this is a ChoCH (Change of Character) — trend reversal
  - If was BULL → this is a BOS (Break of Structure) — trend continuation
  - Set structure to BULL

When close breaks BELOW lower_value:
  - If was BULL → this is a ChoCH
  - If was BEAR → this is a BOS
  - Set structure to BEAR
```

The final `current_structure` value at the end of the bar history is the label stored.

**Data sources per timeframe:**

| Timeframe | Data Source | Lookback |
|-----------|------------|----------|
| M1 | m1_bars_2 (database) | 1 day |
| M5 | Polygon API (native 5-min bars) | 3 days |
| M15 | Polygon API (native 15-min bars) | 7 days |
| H1 | h1_bars table (DB), fallback to API | 14 days |
| H4 | Polygon API (native 4-hour bars) | 30 days |

**Caching:** HTF bars are cached per (ticker, timeframe, date). Since every M1 bar in a day shares the same H4 structure history, the H4 API call happens once per ticker-date and is reused ~390 times. This reduces API calls from ~1,950 (5 timeframes * 390 bars) to ~4 per ticker-date (one per HTF, M1 uses DB data).

---

### Composite Scores (3 Columns)

#### 20. Health Score (`health_score`)

**What it measures:** Overall bar "quality" on a 0-10 scale, regardless of direction. High health = strong, decisive market activity.

Five criteria, 2 points each:

| Criterion | Check | Points |
|-----------|-------|--------|
| Volume activity | `vol_roc > 50%` | +2 |
| Trend strength | `sma_momentum_label == "WIDENING"` | +2 |
| Order flow conviction | `abs(cvd_slope) > 0.001` | +2 |
| Trend clarity | `abs(sma_spread) / close > 0.1%` | +2 |
| Institutional interest | `abs(close - vwap) / close > 0.1%` | +2 |

A health score of 8-10 means the bar has strong volume, clear trend, and institutional participation. A score of 0-3 means quiet, indecisive conditions.

---

#### 21. Long Score (`long_score`)

**What it measures:** How favorable current conditions are for a long entry, on a 0-7 scale.

**Note:** In this processor, the long score is calculated without H1 structure (which is computed separately by the calculator). The maximum score from the indicator layer alone is 5.

| Criterion | Check | Points |
|-----------|-------|--------|
| Candle momentum | `candle_range_pct >= 0.15%` | +2 |
| Elevated volume | `vol_roc >= 30%` | +1 |
| High magnitude delta | `abs(vol_delta_roll) > 100,000` | +1 |
| Wide SMA spread | `abs(sma_spread) / close * 100 >= 0.15%` | +1 |
| H1 structure NEUTRAL | (calculated separately, adds +2) | (+2) |

---

#### 22. Short Score (`short_score`)

**What it measures:** How favorable current conditions are for a short entry, on a 0-7 scale.

The short score intentionally uses **paradox indicators** — conditions that seem bullish but actually indicate exhaustion:

| Criterion | Check | Points | Why |
|-----------|-------|--------|-----|
| Candle momentum | `candle_range_pct >= 0.15%` | +2 | Need range for a move |
| Elevated volume | `vol_roc >= 30%` | +1 | Confirms activity |
| Positive delta | `vol_delta_roll > 0` | +1 | **Paradox:** exhausted buyers |
| Bullish SMA | `sma_spread > 0` | +1 | **Paradox:** catching failed rally |
| H1 structure NEUTRAL | (calculated separately, adds +2) | (+2) | |

The paradox logic: when price has been going up (positive delta, bullish SMA) but is at a rejection zone, the buyers may be exhausted. A short at this point catches the reversal.

---

## The `m1_indicator_bars_2` Table

```sql
CREATE TABLE m1_indicator_bars_2 (
    -- Primary Key (composite)
    ticker          VARCHAR(10) NOT NULL,
    bar_date        DATE NOT NULL,
    bar_time        TIME NOT NULL,
    PRIMARY KEY (ticker, bar_date, bar_time),

    -- OHLCV (carried from m1_bars_2)
    open            NUMERIC(12,4),
    high            NUMERIC(12,4),
    low             NUMERIC(12,4),
    close           NUMERIC(12,4),
    volume          BIGINT,

    -- Entry Qualifier Standard (9 columns)
    candle_range_pct    NUMERIC(10,6),
    vol_delta_raw       NUMERIC(12,2),
    vol_delta_roll      NUMERIC(12,2),
    vol_roc             NUMERIC(10,4),
    sma9                NUMERIC(12,4),
    sma21               NUMERIC(12,4),
    sma_config          VARCHAR(10),        -- BULL / BEAR / FLAT
    sma_spread_pct      NUMERIC(10,6),
    price_position      VARCHAR(10),        -- ABOVE / BTWN / BELOW

    -- Extended (5 columns)
    vwap                NUMERIC(12,4),
    sma_spread          NUMERIC(12,4),
    sma_momentum_ratio  NUMERIC(10,6),
    sma_momentum_label  VARCHAR(15),        -- WIDENING / NARROWING / STABLE
    cvd_slope           NUMERIC(10,6),

    -- Structure (5 columns)
    h4_structure        VARCHAR(10),        -- BULL / BEAR / NEUTRAL
    h1_structure        VARCHAR(10),
    m15_structure       VARCHAR(10),
    m5_structure        VARCHAR(10),
    m1_structure        VARCHAR(10),

    -- Scores (3 columns)
    health_score        INTEGER,            -- 0-10
    long_score          INTEGER,            -- 0-7
    short_score         INTEGER,            -- 0-7

    -- Metadata
    bars_in_calculation INTEGER,
    calculated_at       TIMESTAMPTZ DEFAULT NOW()
);
```

**Total columns:** 31 (3 PK + 5 OHLCV + 9 EQ standard + 5 extended + 5 structure + 3 scores + 1 metadata + calculated_at)

**Indexes:**
- `(ticker, bar_date)` — primary query pattern
- `(bar_date)` — date-level queries
- `(ticker, bar_date, m1_structure, m5_structure)` — structure queries
- `(ticker, bar_date, sma_config, price_position)` — SMA queries

---

## File Architecture

```
m1_indicator_bars_2/
│
├── config.py           Self-contained settings
│                       (DB creds, Polygon key, SMA periods, CVD window,
│                        score thresholds, HTF lookback days, batch size)
│
├── indicators.py       M1IndicatorCalculator class
│                       All 22 indicator calculations on a DataFrame
│                       Imports formulas from processor/indicators/core/
│
├── structure.py        MarketStructureCalculator + HTFBarFetcher + StructureAnalyzer
│                       Fractal detection, BOS/ChoCH, multi-TF structure
│                       Fetches M5/M15/H4 from Polygon, H1 from DB
│
├── calculator.py       M1IndicatorBarsCalculator (orchestrator)
│                       Reads M1 bars from DB, calls indicators + structure,
│                       produces M1IndicatorBarResult objects
│
├── populator.py        M1IndicatorBarsPopulator (batch processor)
│                       Finds missing ticker-dates, runs calculator,
│                       batch inserts results into m1_indicator_bars_2
│
├── runner.py           CLI entry point (argparse)
│                       --schema, --status, --dry-run, --limit, --verbose
│
└── schema/
    └── m1_indicator_bars_2.sql    DDL for the target table
```

### How the files connect:

```
runner.py
    └── populator.py
            ├── calculator.py
            │       ├── indicators.py
            │       │       └── processor/indicators/core/*.py  (centralized formulas)
            │       └── structure.py
            │               └── Polygon API (M5, M15, H4)
            │               └── h1_bars DB table (H1)
            └── m1_bars_2 DB table (raw M1 data)
```

---

## CLI Runner

**File:** `runner.py`

```bash
python runner.py                    # Full batch run
python runner.py --dry-run          # Calculate but don't save
python runner.py --limit 10         # Process max 10 ticker-dates
python runner.py --schema           # Create m1_indicator_bars_2 table
python runner.py --status           # Show current status
python runner.py --verbose          # Detailed per-bar logging
```

---

## Configuration Reference

**File:** `config.py`

| Setting | Value | Purpose |
|---------|-------|---------|
| **SMA** | | |
| `SMA_FAST_PERIOD` | 9 | Fast SMA window |
| `SMA_SLOW_PERIOD` | 21 | Slow SMA window |
| `SMA_MOMENTUM_LOOKBACK` | 10 | Bars back for momentum ratio |
| `SMA_WIDENING_THRESHOLD` | 1.1 | Ratio above this = WIDENING |
| `SMA_NARROWING_THRESHOLD` | 0.9 | Ratio below this = NARROWING |
| **Volume** | | |
| `VOLUME_ROC_BASELINE_PERIOD` | 20 | Bars for average volume baseline |
| `VOLUME_DELTA_ROLLING_PERIOD` | 5 | Rolling sum window for delta |
| **CVD** | | |
| `CVD_WINDOW` | 15 | Linear regression window for slope |
| **Structure** | | |
| `FRACTAL_LENGTH` | 5 | Bars for fractal detection (2 per side) |
| `HTF_BARS_NEEDED` | M1:100, M5:100, M15:100, H1:100, H4:50 | Minimum bars for structure calc |
| `HTF_LOOKBACK_DAYS` | M1:1, M5:3, M15:7, H1:14, H4:30 | Calendar days to fetch per TF |
| **Health** | | |
| `HEALTH_VOL_ROC_THRESHOLD` | 50.0 | Vol ROC above this = healthy |
| `HEALTH_CVD_SLOPE_THRESHOLD` | 0.0 | CVD slope sign matters |
| **Batch** | | |
| `BATCH_INSERT_SIZE` | 500 | Rows per execute_values call |

---

## Null Value Handling

Early bars in each session will have null indicators because rolling calculations need history:

| Indicator | First Non-Null Bar | Why |
|-----------|--------------------|-----|
| `vol_delta_raw` | Bar 1 | Single-bar calculation |
| `candle_range_pct` | Bar 1 | Single-bar calculation |
| `sma9` | Bar 9 | Needs 9 bars |
| `sma21` | Bar 21 | Needs 21 bars |
| `sma_config` | Bar 21 | Needs both SMAs |
| `sma_spread_pct` | Bar 21 | Needs both SMAs |
| `price_position` | Bar 21 | Needs both SMAs |
| `vol_roc` | Bar 22 | 20-bar avg + 1 shift |
| `vol_delta_roll` | Bar 5 | 5-bar rolling sum |
| `sma_momentum_ratio` | Bar 31 | SMA21 (21) + lookback (10) |
| `cvd_slope` | Bar 15 | 15-bar regression window |

The first ~30 bars of each session (roughly 16:00-16:30 of the prior day) will have partial indicator coverage. By the time pre-market begins at 04:00, all indicators are fully populated.

---

## Performance

| Metric | Typical Value |
|--------|---------------|
| Bars per ticker-date | ~360-390 |
| Indicators per bar | 27 (22 indicators + 5 structure) |
| HTF API calls per ticker | ~3-4 (M5, M15, H4; H1 from DB) |
| Time per ticker-date | ~2-5 seconds |
| 5 tickers total | ~15-40 seconds |
| DB insert batch size | 500 rows |

The bottleneck is structure detection — iterating 390 bars and querying structure for each one. The HTF caching mitigates API calls, but the fractal calculation itself runs per bar. For M1 structure, the full M1 bar history is re-analyzed at each bar position (progressively longer lookback).

---

## Example: One Bar Through the Pipeline

**AAPL, 2026-02-13, 10:30:00 ET**

**Raw bar from m1_bars_2:**
```
open=187.25, high=187.60, low=187.10, close=187.45, volume=42,000
```

**Indicator calculations:**
```
candle_range_pct = (187.60 - 187.10) / 187.45 * 100 = 0.267%   → NORMAL range
vol_delta_raw    = 42000 * ((2 * (187.45-187.10)/(187.60-187.10)) - 1)
                 = 42000 * (2 * 0.70 - 1) = 42000 * 0.40 = +16,800
vol_delta_roll   = sum of last 5 vol_delta_raw values
vol_roc          = ((42000 - 35000) / 35000) * 100 = +20%       (if avg was 35k)
sma9             = 187.38  (last 9 closes)
sma21            = 187.12  (last 21 closes)
sma_config       = "BULL"  (sma9 > sma21)
sma_spread_pct   = abs(187.38 - 187.12) / 187.45 * 100 = 0.139%
price_position   = "ABOVE" (187.45 > max(187.38, 187.12))
sma_spread       = +0.26
sma_momentum     = STABLE  (if ratio between 0.91 and 1.1)
cvd_slope        = +0.0023 (positive = buyers in control)
vwap             = 187.20  (cumulative day VWAP)
```

**Structure (at 10:30):**
```
h4_structure  = "BULL"    (H4 BOS up on morning push)
h1_structure  = "BULL"    (H1 continuation above fractal high)
m15_structure = "BULL"    (M15 aligned)
m5_structure  = "NEUTRAL" (M5 consolidating)
m1_structure  = "BULL"    (M1 making higher highs)
```

**Scores:**
```
health_score = 6   (vol_roc <50 so no vol points, but CVD, SMA, VWAP clear)
long_score   = 4   (candle range +2, vol_roc <30 so +0, delta +1, SMA spread +1)
short_score  = 3   (candle range +2, vol_roc +0, positive delta paradox +1)
```

**Stored row:** All 31 columns written to m1_indicator_bars_2 with `bars_in_calculation = 270` (indicating this was the 270th bar in the session).
