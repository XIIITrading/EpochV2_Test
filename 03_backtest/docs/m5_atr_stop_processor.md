# M5 ATR Stop Processor — Workflow & Calculation Overview

**Epoch Trading System v2.0 — XIII Trading LLC**
**Module:** 03_backtest / secondary_analysis / m5_atr_stop_2
**Added:** February 2026

---

## 1. Purpose

The M5 ATR Stop Processor evaluates every entry-detected trade by using the
**M5 ATR(14)** value at entry as the stop distance (1R), then walking M1 bars
forward to determine:

- Was the trade a **WIN** (R1 hit before stop) or **LOSS** (everything else)?
- What was the **max R-level** reached (1R through 5R)?
- When was the **stop triggered** (if at all)?
- How many **bars from entry** did each R-level or stop take?

One row per trade is written to the `m5_atr_stop_2` table. The `max_r` column
is designed for direct use in calculations: **-1 for losses, 1-5 for wins**.
`AVG(max_r)` across any set of trades gives net expectancy in R.

### Relationship to M1 ATR Stop

This processor is structurally identical to `m1_atr_stop_2` with one key
difference: the **stop distance comes from M5 ATR** instead of M1 ATR.

| Aspect | m1_atr_stop_2 | m5_atr_stop_2 |
|--------|--------------|--------------|
| ATR source | `atr_m1` (micro-volatility) | `atr_m5` (short-term volatility) |
| Typical stop width | $0.03 - $0.50 | $0.10 - $1.50 |
| Simulation bars | M1 bars | M1 bars (same fidelity) |
| R-level spacing | Tighter | Wider |
| Effect | More stop-outs, faster R hits | Fewer stop-outs, slower R hits |

Running both processors on the same trade population enables direct
**cross-timeframe comparison** of win rates, expectancy, and R-distributions.

---

## 2. Data Pipeline

```
┌─────────────────────────────────┐
│         trades_2                │  Entry-only detection results
│  trade_id, ticker, date,       │  (from EPCH1-4 on S15 bars)
│  direction, entry_time,        │
│  entry_price, model            │
└──────────────┬──────────────────┘
               │
               │  1. Read trade metadata
               │  2. Adjust entry_time to M1 candle
               ▼
┌─────────────────────────────────┐
│    m1_indicator_bars_2          │  Pre-computed indicators on M1 bars
│  ticker, bar_date, bar_time,   │  (22 indicators + 3 scores + 3 ATR)
│  atr_m1, atr_m5, atr_m15      │
└──────────────┬──────────────────┘
               │
               │  3. Fetch atr_m5 at adjusted entry candle
               │     (stop distance = 1R = raw M5 ATR, no multiplier)
               ▼
┌─────────────────────────────────┐
│         m1_bars_2               │  Raw M1 OHLCV bars
│  ticker, bar_date, bar_time,   │  (prior day 16:00 → trade day 16:00)
│  open, high, low, close, vol   │
└──────────────┬──────────────────┘
               │
               │  4. Walk M1 bars from entry to 15:30 ET
               │     - R-level detection (price-based)
               │     - Stop detection (close-based on M1 candle)
               ▼
┌─────────────────────────────────┐
│       m5_atr_stop_2             │  Results: 1 row per trade
│  trade_id, stop_price,         │  R-level hits, stop tracking,
│  r1-r5 prices/hits/times,      │  max_r, result (WIN/LOSS)
│  stop_time, max_r, result      │
└─────────────────────────────────┘
```

**Key design:** The M5 ATR sets the stop distance (wider), but the bar-by-bar
simulation walks **M1 bars** for maximum detection fidelity. There is no
`m5_bars_2` table — M1 resolution gives the most accurate R-level and stop
trigger detection regardless of which ATR timeframe sets the levels.

No Polygon API calls are made. All data comes from the three v2 database tables.

---

## 3. Entry Candle Adjustment

Trades in `trades_2` have sub-minute precision from the S15 detection engine
(e.g., `09:31:15`). M1 bars are bucketed by minute (`09:31:00`). The processor
truncates the entry time to match:

```
Original entry_time:   09:31:15
Adjusted (m1_candle):  09:31:00    ← seconds zeroed

Original entry_time:   10:05:47
Adjusted (m1_candle):  10:05:00
```

This adjusted time (`m1_entry_candle_adj`) is used to:
1. Look up `atr_m5` from `m1_indicator_bars_2` at the exact M1 candle
2. Determine the starting point for the M1 bar walk

Both the original `entry_time` and `m1_entry_candle_adj` are stored in the
output table for transparency.

---

## 4. Stop Calculation

### ATR Source

The processor reads the **pre-computed** `atr_m5` from `m1_indicator_bars_2`.
This is a 14-period Simple Moving Average of True Range on M5 bars, already
calculated and stored by the M1 Indicator Bars processor.

```
atr_m5 = SMA( TrueRange(M5_bars), 14 )
```

The M5 ATR is stored on every M1 row in `m1_indicator_bars_2` — the value
represents the M5 ATR at the time of that M1 candle. This allows lookup at
any M1 entry time, even though the underlying ATR is computed on M5 bars.

### Stop Distance (1R)

The stop distance equals the raw M5 ATR value — **no multiplier**.

```
stop_distance = m5_atr_value        (1.0x M5 ATR = 1R)
```

### Stop Price

```
LONG trade:   stop_price = entry_price - stop_distance
SHORT trade:  stop_price = entry_price + stop_distance
```

### Worked Example

```
Direction:    LONG
Entry Price:  $152.50
M5 ATR(14):   $0.85

stop_distance     = $0.85
stop_price        = $152.50 - $0.85 = $151.65
stop_distance_pct = ($0.85 / $152.50) * 100 = 0.5574%
```

Compare with the M1 ATR for the same trade:

```
M1 ATR(14):   $0.35  →  stop = $152.15  (tighter)
M5 ATR(14):   $0.85  →  stop = $151.65  (wider, ~2.4× the M1 stop)
```

The M5 stop gives the trade more room to breathe, but R-level targets are
also proportionally farther away.

---

## 5. R-Level Target Prices

Each R-level is a multiple of the stop distance (1R) from the entry price.

```
LONG:   R(n)_price = entry_price + (n × stop_distance)
SHORT:  R(n)_price = entry_price - (n × stop_distance)
```

### Full Example (LONG at $152.50, M5 ATR = $0.85)

| Level | Calculation | Target Price | Dollar Move |
|-------|-------------|-------------|-------------|
| Stop  | 152.50 - 0.85 | $151.65 | -$0.85 |
| R1    | 152.50 + (1 × 0.85) | $153.35 | +$0.85 |
| R2    | 152.50 + (2 × 0.85) | $154.20 | +$1.70 |
| R3    | 152.50 + (3 × 0.85) | $155.05 | +$2.55 |
| R4    | 152.50 + (4 × 0.85) | $155.90 | +$3.40 |
| R5    | 152.50 + (5 × 0.85) | $156.75 | +$4.25 |

### Full Example (SHORT at $152.50, M5 ATR = $0.85)

| Level | Calculation | Target Price | Dollar Move |
|-------|-------------|-------------|-------------|
| Stop  | 152.50 + 0.85 | $153.35 | +$0.85 (adverse) |
| R1    | 152.50 - (1 × 0.85) | $151.65 | -$0.85 |
| R2    | 152.50 - (2 × 0.85) | $150.80 | -$1.70 |
| R3    | 152.50 - (3 × 0.85) | $149.95 | -$2.55 |
| R4    | 152.50 - (4 × 0.85) | $149.10 | -$3.40 |
| R5    | 152.50 - (5 × 0.85) | $148.25 | -$4.25 |

### M1 vs M5 Target Comparison (same LONG trade)

| Level | M1 ATR ($0.35) | M5 ATR ($0.85) | M5 is wider by |
|-------|---------------|---------------|----------------|
| Stop  | $152.15 | $151.65 | $0.50 |
| R1    | $152.85 | $153.35 | $0.50 |
| R3    | $153.55 | $155.05 | $1.50 |
| R5    | $154.25 | $156.75 | $2.50 |

---

## 6. M1 Bar Walk — Detection Logic

After setting up the stop and R-level prices, the processor walks every M1 bar
sequentially from the first bar after entry through 15:30 ET (EOD cutoff).

### What Gets Checked Each Bar

```
For each M1 bar (after entry, up to 15:30):
    │
    ├── 1. STOP CHECK (close-based)
    │       LONG:  bar_close <= stop_price?
    │       SHORT: bar_close >= stop_price?
    │
    └── 2. R-LEVEL CHECK (price-based)
            LONG:  bar_high >= R(n)_price?
            SHORT: bar_low  <= R(n)_price?
```

### Detection Type Differences

| What | Trigger Type | Why |
|------|-------------|-----|
| **R-level targets** | Price-based (high/low touch) | Any wick touch = target reached |
| **Stop** | Close-based (M1 bar close) | Prevents wick-only stop-outs; requires conviction |

This is a deliberate design choice. R-targets use the most generous detection
(any touch counts) while stops require the bar to actually *close* beyond the
level, filtering out wick fakeouts.

**Important:** Even though the stop distance is derived from M5 ATR, the stop
trigger is checked on every **M1 bar close**. This gives 5× more granular
detection than checking M5 bar closes.

### Same-Candle Conflict

If a single M1 bar shows **both** an R-level hit (wick touches target) **and**
a close beyond the stop level:

> **Stop takes priority. R-level hits on that bar are invalidated.**

```
Example: LONG trade, R1 = $153.35, Stop = $151.65

Bar: O=$152.50  H=$153.40  L=$151.50  C=$151.60
         │          │           │          │
         │       R1 hit!        │       Close below stop!
         │    (H >= R1)         │     (C <= stop_price)
         │                      │
         └── CONFLICT: Same bar has R1 touch AND stop close
             RESOLUTION: Stop wins → LOSS (R1 not credited)
```

---

## 7. Outcome Determination

After the bar walk completes, the result is determined:

### Result Logic

```
if R1 was hit (before stop):
    result = WIN
    max_r  = highest R-level hit before stop_time (1-5)
else:
    result = LOSS
    max_r  = -1
```

### All Possible Scenarios

| Scenario | R1 Hit | Stop Hit | Result | max_r |
|----------|--------|----------|--------|-------|
| R1 hit, then stop later | Yes | Yes | **WIN** | Highest R hit before stop |
| R1-R5 all hit, no stop | Yes | No | **WIN** | 5 |
| R1-R3 hit, no stop by 15:30 | Yes | No | **WIN** | 3 |
| Stop hit before R1 | No | Yes | **LOSS** | -1 |
| Same-candle conflict (R1 + stop) | No* | Yes | **LOSS** | -1 |
| Neither R1 nor stop by 15:30 | No | No | **LOSS** | -1 |
| No ATR data available | — | — | Skipped | — |

*R1 hit is invalidated by same-candle conflict.

**Key rule:** No R1 = LOSS, always. There is no EOD price check — if the trade
hasn't reached R1 by 15:30, it's a loss regardless of where price is.

---

## 8. The max_r Column

The `max_r` column is the core analytical output of this processor.

### Values

| max_r | Meaning |
|-------|---------|
| **-1** | LOSS — stopped out or R1 never reached |
| **1** | WIN — R1 hit, but R2 not reached before stop |
| **2** | WIN — R2 hit before stop |
| **3** | WIN — R3 hit before stop |
| **4** | WIN — R4 hit before stop |
| **5** | WIN — R5 hit before stop (maximum) |

### Why -1 (Not 0)

Using -1 for losses enables direct arithmetic on the column:

```sql
-- Net expectancy in R per trade (single column!)
SELECT ROUND(AVG(max_r)::decimal, 3) as expectancy_r
FROM m5_atr_stop_2;

-- Example: 50% win rate, avg winner = 2.0R, losses = -1R
-- AVG(max_r) = (0.50 * 2.0) + (0.50 * -1) = 1.0 - 0.5 = 0.50R per trade

-- Total R earned
SELECT SUM(max_r) as total_r FROM m5_atr_stop_2;

-- Cumulative R curve by date
SELECT date, SUM(max_r) OVER (ORDER BY date, entry_time) as cumulative_r
FROM m5_atr_stop_2;
```

---

## 9. Stop Time & R-Level Time Tracking

For every R-level and the stop, the processor records:

| Column | What It Stores |
|--------|---------------|
| `r{n}_hit` | Boolean — did price reach this R-level? |
| `r{n}_time` | TIME — when was it first reached? |
| `r{n}_bars_from_entry` | INTEGER — how many M1 bars from entry? |
| `stop_hit` | Boolean — was the stop triggered? |
| `stop_time` | TIME — when was the stop triggered? |
| `stop_bars_from_entry` | INTEGER — how many M1 bars from entry? |

### How stop_time Works With max_r

R-levels are only credited if they were hit **before** `stop_time`:

```
Timeline example (LONG, entry at 09:35):

09:38  R1 hit     → r1_hit=TRUE, r1_time=09:38
09:45  R2 hit     → r2_hit=TRUE, r2_time=09:45
10:02  STOP HIT   → stop_hit=TRUE, stop_time=10:02
                   → R3, R4, R5 cannot be credited (stop already triggered)
                   → max_r = 2 (highest R hit before stop)
                   → result = WIN (R1 was hit before stop)
```

Note: With the wider M5 ATR stop, stops tend to trigger later than with M1 ATR
(more room before the stop level is breached), giving R-levels more time to
be reached.

---

## 10. Deduplication

The processor uses a `NOT EXISTS` query to find trades not yet processed:

```sql
SELECT t.*
FROM trades_2 t
WHERE t.entry_time IS NOT NULL
  AND t.entry_price IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM m5_atr_stop_2 r
      WHERE r.trade_id = t.trade_id
  )
```

The INSERT uses `ON CONFLICT (trade_id) DO UPDATE SET` (upsert), so re-running
the processor on already-processed trades will overwrite with fresh calculations
rather than failing.

---

## 11. Skip Conditions

A trade is **skipped** (not written to output) if any of these are true:

| Condition | Why |
|-----------|-----|
| `entry_time` is NULL | Cannot determine starting point |
| `entry_price` is NULL | Cannot calculate stop/targets |
| `atr_m5` not found at entry candle | No M5 ATR row in m1_indicator_bars_2 |
| `atr_m5 <= 0` | Invalid ATR (would produce zero stop distance) |
| No M1 bars for that ticker/date | No data to walk |

Note: `atr_m5` may be NULL for early-session entries if insufficient M5 bar
warmup data exists (14 M5 bars needed = ~70 minutes of data). This is expected
and will result in more skips than the M1 ATR processor for early entries.

---

## 12. Performance Optimizations

### M1 Bar Caching

M1 bars are cached by `{ticker}_{date}` during batch processing. If multiple
trades share the same ticker and date (common — a single ticker can generate
many EPCH entries in one day), the bars are fetched from the database once and
reused.

```
Trade 1: AMD 2026-02-12 09:30 → fetch M1 bars from DB, cache
Trade 2: AMD 2026-02-12 09:32 → reuse cached bars
Trade 3: AMD 2026-02-12 09:45 → reuse cached bars
Trade 4: AAPL 2026-02-12 09:35 → fetch M1 bars from DB, cache (new key)
```

### No API Calls

All three data sources are database tables. The processor makes zero Polygon
API calls. The only external I/O is PostgreSQL queries to Supabase.

---

## 13. Database Schema

### Table: `m5_atr_stop_2`

```
Column Groups:
  Trade ID          (1 col)   trade_id (PK, FK → trades_2)
  Trade Metadata    (5 cols)  date, ticker, direction, model, zone_type
  Entry Reference   (3 cols)  entry_time, entry_price, m1_entry_candle_adj
  ATR/Stop          (4 cols)  m5_atr_value, stop_price, stop_distance, stop_distance_pct
  R-Level Prices    (5 cols)  r1_price through r5_price
  R-Level Tracking (15 cols)  r{1-5}_hit, r{1-5}_time, r{1-5}_bars_from_entry
  Stop Tracking     (3 cols)  stop_hit, stop_time, stop_bars_from_entry
  Outcome           (2 cols)  max_r, result
  Metadata          (2 cols)  calculated_at, updated_at
```

### Constraints

```sql
CONSTRAINT valid_result CHECK (result IN ('WIN', 'LOSS'))
CONSTRAINT valid_max_r  CHECK (max_r >= -1 AND max_r <= 5)
FOREIGN KEY (trade_id) REFERENCES trades_2(trade_id) ON DELETE CASCADE
```

### Analysis Views

| View | Purpose |
|------|---------|
| `v_m5_atr_stop_2_summary` | Overall win rate, R-hit rates, expectancy_r |
| `v_m5_atr_stop_2_by_model` | Breakdown by EPCH1/2/3/4 |
| `v_m5_atr_stop_2_by_direction` | Breakdown by LONG/SHORT |
| `v_m5_atr_stop_2_r_distribution` | Trade count at each max_r level (-1 through 5) |

---

## 14. CLI Usage

```bash
# Full batch run (process all unprocessed trades)
python runner.py

# Test without writing to database
python runner.py --dry-run

# Process limited number of trades
python runner.py --limit 50

# Verbose output
python runner.py --verbose

# Create database table (first-time setup)
python runner.py --schema

# Show processor configuration
python runner.py --info
```

### Output Example

```
============================================================
EPOCH TRADING SYSTEM
M5 ATR Stop Calculator v1.0.0
============================================================

Start Time: 2026-02-13 09:41:53
Mode: DRY-RUN
Limit: 10 trades

[1/4] Connecting to Supabase...
  Connected successfully

[2/4] Querying trades needing calculation...
  Found 10 trades to process

[3/4] Processing trades...
  [1/10] AMD_021226_EPCH4_0930       LONG   LOSS  maxR=-1 hits=- stop@09:31:00
  [2/10] AMD_021226_EPCH4_0932       LONG   WIN   maxR=5 hits=R1R2R3R4R5 no_stop
  [3/10] AMD_021226_EPCH4_0939       LONG   WIN   maxR=1 hits=R1 stop@09:41:00
  [4/10] AMD_021226_EPCH3_0945       SHORT  WIN   maxR=5 hits=R1R2R3R4R5 no_stop

[4/4] Writing results to database...
  [DRY-RUN] Would insert 10 records

============================================================
EXECUTION SUMMARY
============================================================
  Trades Processed:  10
  Trades Skipped:    0
  Records Created:   0
  Execution Time:    0.9s

============================================================
COMPLETED SUCCESSFULLY
============================================================
```

---

## 15. File Structure

```
m5_atr_stop_2/
├── __init__.py        Module exports (M5AtrStopCalculator, config constants)
├── config.py          Self-contained config (DB creds, EOD cutoff, R-levels, table names)
├── calculator.py      Core processor (entry adjustment, bar walk, R/stop detection, batch)
├── runner.py          CLI entry point (--dry-run, --limit, --schema, --info, --verbose)
└── schema/
    └── m5_atr_stop_2.sql   Full DDL + indexes + comments + 4 analysis views
```

---

## 16. Example Queries

```sql
-- Overall summary (uses the pre-built view)
SELECT * FROM v_m5_atr_stop_2_summary;

-- Win rate by entry model
SELECT * FROM v_m5_atr_stop_2_by_model;

-- R-level distribution (how many trades at each max_r)
SELECT * FROM v_m5_atr_stop_2_r_distribution;

-- Trades that reached R3 or higher
SELECT trade_id, ticker, date, model, direction,
       entry_price, stop_price, max_r,
       r1_time, r2_time, r3_time, result
FROM m5_atr_stop_2
WHERE max_r >= 3
ORDER BY date DESC;

-- Net expectancy by model
SELECT model,
       COUNT(*) as trades,
       ROUND(AVG(max_r)::decimal, 3) as expectancy_r
FROM m5_atr_stop_2
GROUP BY model
ORDER BY expectancy_r DESC;

-- Cumulative R curve
SELECT date,
       SUM(max_r) OVER (ORDER BY date, entry_time) as cumulative_r
FROM m5_atr_stop_2
ORDER BY date, entry_time;

-- Average time to R1 for winners (in M1 bars)
SELECT model,
       ROUND(AVG(r1_bars_from_entry), 1) as avg_bars_to_r1
FROM m5_atr_stop_2
WHERE result = 'WIN'
GROUP BY model;
```

---

## 17. Cross-Timeframe Comparison Queries

The primary value of running both M1 and M5 ATR stop processors is comparing
outcomes for the **same trade** under different volatility-based stop widths.

```sql
-- Side-by-side comparison: same trades, different ATR stops
SELECT
    m1.trade_id,
    m1.ticker,
    m1.date,
    m1.direction,
    m1.model,
    m1.stop_distance_pct as m1_stop_pct,
    m5.stop_distance_pct as m5_stop_pct,
    m1.result as m1_result,
    m5.result as m5_result,
    m1.max_r as m1_max_r,
    m5.max_r as m5_max_r
FROM m1_atr_stop_2 m1
JOIN m5_atr_stop_2 m5 ON m1.trade_id = m5.trade_id
ORDER BY m1.date DESC, m1.ticker;

-- Trades where M1 and M5 disagree (one wins, other loses)
SELECT
    m1.trade_id, m1.ticker, m1.date, m1.direction, m1.model,
    m1.result as m1_result, m5.result as m5_result,
    m1.max_r as m1_max_r, m5.max_r as m5_max_r,
    m1.stop_distance_pct as m1_stop_pct,
    m5.stop_distance_pct as m5_stop_pct
FROM m1_atr_stop_2 m1
JOIN m5_atr_stop_2 m5 ON m1.trade_id = m5.trade_id
WHERE m1.result != m5.result
ORDER BY m1.date DESC;

-- Expectancy comparison by model
SELECT
    m1.model,
    COUNT(*) as trades,
    ROUND(AVG(m1.max_r)::decimal, 3) as m1_expectancy_r,
    ROUND(AVG(m5.max_r)::decimal, 3) as m5_expectancy_r,
    ROUND(AVG(m5.max_r)::decimal - AVG(m1.max_r)::decimal, 3) as m5_vs_m1_diff
FROM m1_atr_stop_2 m1
JOIN m5_atr_stop_2 m5 ON m1.trade_id = m5.trade_id
GROUP BY m1.model
ORDER BY m1.model;

-- Win rate comparison by direction
SELECT
    m1.direction,
    COUNT(*) as trades,
    ROUND(100.0 * COUNT(*) FILTER (WHERE m1.result = 'WIN') / COUNT(*), 2) as m1_win_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE m5.result = 'WIN') / COUNT(*), 2) as m5_win_pct
FROM m1_atr_stop_2 m1
JOIN m5_atr_stop_2 m5 ON m1.trade_id = m5.trade_id
GROUP BY m1.direction;
```
