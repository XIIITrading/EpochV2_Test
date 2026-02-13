# M1 ATR Stop Processor — Workflow & Calculation Overview

**Epoch Trading System v2.0 — XIII Trading LLC**
**Module:** 03_backtest / secondary_analysis / m1_atr_stop_2
**Added:** February 2026

---

## 1. Purpose

The M1 ATR Stop Processor evaluates every entry-detected trade by using the
**M1 ATR(14)** value at entry as the stop distance (1R), then walking M1 bars
forward to determine:

- Was the trade a **WIN** (R1 hit before stop) or **LOSS** (everything else)?
- What was the **max R-level** reached (1R through 5R)?
- When was the **stop triggered** (if at all)?
- How many **bars from entry** did each R-level or stop take?

One row per trade is written to the `m1_atr_stop_2` table. The `max_r` column
is designed for direct use in calculations: **-1 for losses, 1-5 for wins**.
`AVG(max_r)` across any set of trades gives net expectancy in R.

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
               │  3. Fetch atr_m1 at adjusted entry candle
               │     (stop distance = 1R = raw ATR, no multiplier)
               ▼
┌─────────────────────────────────┐
│         m1_bars_2               │  Raw M1 OHLCV bars
│  ticker, bar_date, bar_time,   │  (prior day 16:00 → trade day 16:00)
│  open, high, low, close, vol   │
└──────────────┬──────────────────┘
               │
               │  4. Walk M1 bars from entry to 15:30 ET
               │     - R-level detection (price-based)
               │     - Stop detection (close-based)
               ▼
┌─────────────────────────────────┐
│       m1_atr_stop_2             │  Results: 1 row per trade
│  trade_id, stop_price,         │  R-level hits, stop tracking,
│  r1-r5 prices/hits/times,      │  max_r, result (WIN/LOSS)
│  stop_time, max_r, result      │
└─────────────────────────────────┘
```

**Key:** No Polygon API calls are made. All data comes from the three v2
database tables that were populated by earlier pipeline stages.

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
1. Look up `atr_m1` from `m1_indicator_bars_2` at the exact candle
2. Determine the starting point for the M1 bar walk

Both the original `entry_time` and `m1_entry_candle_adj` are stored in the
output table for transparency.

---

## 4. Stop Calculation

### ATR Source

The processor reads the **pre-computed** `atr_m1` from `m1_indicator_bars_2`.
This is a 14-period Simple Moving Average of True Range on M1 bars, already
calculated and stored by the M1 Indicator Bars processor.

```
atr_m1 = SMA( TrueRange(M1_bars), 14 )
```

### Stop Distance (1R)

The stop distance equals the raw ATR value — **no multiplier**.

```
stop_distance = m1_atr_value        (1.0x ATR = 1R)
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
M1 ATR(14):   $0.35

stop_distance     = $0.35
stop_price        = $152.50 - $0.35 = $152.15
stop_distance_pct = ($0.35 / $152.50) * 100 = 0.2295%
```

---

## 5. R-Level Target Prices

Each R-level is a multiple of the stop distance (1R) from the entry price.

```
LONG:   R(n)_price = entry_price + (n × stop_distance)
SHORT:  R(n)_price = entry_price - (n × stop_distance)
```

### Full Example (LONG at $152.50, ATR = $0.35)

| Level | Calculation | Target Price | Dollar Move |
|-------|-------------|-------------|-------------|
| Stop  | 152.50 - 0.35 | $152.15 | -$0.35 |
| R1    | 152.50 + (1 × 0.35) | $152.85 | +$0.35 |
| R2    | 152.50 + (2 × 0.35) | $153.20 | +$0.70 |
| R3    | 152.50 + (3 × 0.35) | $153.55 | +$1.05 |
| R4    | 152.50 + (4 × 0.35) | $153.90 | +$1.40 |
| R5    | 152.50 + (5 × 0.35) | $154.25 | +$1.75 |

### Full Example (SHORT at $152.50, ATR = $0.35)

| Level | Calculation | Target Price | Dollar Move |
|-------|-------------|-------------|-------------|
| Stop  | 152.50 + 0.35 | $152.85 | +$0.35 (adverse) |
| R1    | 152.50 - (1 × 0.35) | $152.15 | -$0.35 |
| R2    | 152.50 - (2 × 0.35) | $151.80 | -$0.70 |
| R3    | 152.50 - (3 × 0.35) | $151.45 | -$1.05 |
| R4    | 152.50 - (4 × 0.35) | $151.10 | -$1.40 |
| R5    | 152.50 - (5 × 0.35) | $150.75 | -$1.75 |

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

### Same-Candle Conflict

If a single M1 bar shows **both** an R-level hit (wick touches target) **and**
a close beyond the stop level:

> **Stop takes priority. R-level hits on that bar are invalidated.**

```
Example: LONG trade, R1 = $153.00, Stop = $152.00

Bar: O=$152.50  H=$153.10  L=$151.80  C=$151.90
         │          │           │          │
         │       R1 hit!        │       Close below stop!
         │    (H >= R1)         │     (C <= stop_price)
         │                      │
         └── CONFLICT: Same bar has R1 touch AND stop close
             RESOLUTION: Stop wins → LOSS (R1 not credited)
```

This prevents crediting favorable targets on the same bar where the trade was
effectively stopped out.

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
FROM m1_atr_stop_2;

-- Example: 40% win rate, avg winner = 2.5R, losses = -1R
-- AVG(max_r) = (0.40 * 2.5) + (0.60 * -1) = 1.0 - 0.6 = 0.40R per trade

-- Total R earned
SELECT SUM(max_r) as total_r FROM m1_atr_stop_2;

-- Cumulative R curve by date
SELECT date, SUM(max_r) OVER (ORDER BY date) as cumulative_r
FROM m1_atr_stop_2;
```

If 0 were used for losses, you'd need separate win/loss aggregations with
conditional formulas. With -1, a single `AVG(max_r)` is all you need.

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

09:36  R1 hit     → r1_hit=TRUE, r1_time=09:36
09:38  R2 hit     → r2_hit=TRUE, r2_time=09:38
09:41  STOP HIT   → stop_hit=TRUE, stop_time=09:41
                   → R3, R4, R5 cannot be credited (stop already triggered)
                   → max_r = 2 (highest R hit before stop)
                   → result = WIN (R1 was hit before stop)
```

If no stop is triggered by 15:30 and R-levels were hit:

```
09:36  R1 hit
09:40  R2 hit
09:55  R3 hit
15:30  EOD cutoff → stop_hit=FALSE, stop_time=NULL
                  → max_r = 3, result = WIN
```

---

## 10. Deduplication

The processor uses a `NOT EXISTS` query to find trades not yet processed:

```sql
SELECT t.*
FROM trades_2 t
WHERE t.entry_time IS NOT NULL
  AND t.entry_price IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM m1_atr_stop_2 r
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
| `atr_m1` not found at entry candle | No ATR row in m1_indicator_bars_2 |
| `atr_m1 <= 0` | Invalid ATR (would produce zero stop distance) |
| No M1 bars for that ticker/date | No data to walk |

Skipped trades are counted separately in the execution summary and do not
produce a row in `m1_atr_stop_2`.

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

### Table: `m1_atr_stop_2`

```
Column Groups:
  Trade ID          (1 col)   trade_id (PK, FK → trades_2)
  Trade Metadata    (5 cols)  date, ticker, direction, model, zone_type
  Entry Reference   (3 cols)  entry_time, entry_price, m1_entry_candle_adj
  ATR/Stop          (4 cols)  m1_atr_value, stop_price, stop_distance, stop_distance_pct
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
| `v_m1_atr_stop_2_summary` | Overall win rate, R-hit rates, expectancy_r |
| `v_m1_atr_stop_2_by_model` | Breakdown by EPCH1/2/3/4 |
| `v_m1_atr_stop_2_by_direction` | Breakdown by LONG/SHORT |
| `v_m1_atr_stop_2_r_distribution` | Trade count at each max_r level (-1 through 5) |

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
M1 ATR Stop Calculator v1.0.0
============================================================

Start Time: 2026-02-13 08:30:37
Mode: DRY-RUN
Limit: 10 trades

[1/4] Connecting to Supabase...
  Connected successfully

[2/4] Querying trades needing calculation...
  Found 10 trades to process

[3/4] Processing trades...
  [1/10] AMD_021226_EPCH4_0930       LONG   LOSS  maxR=-1 hits=- stop@09:31:00
  [2/10] AMD_021226_EPCH4_0932       LONG   WIN   maxR=3 hits=R1R2R3 stop@09:41:00
  [3/10] AMD_021226_EPCH3_0945       SHORT  WIN   maxR=5 hits=R1R2R3R4R5 no_stop

[4/4] Writing results to database...
  [DRY-RUN] Would insert 10 records

============================================================
EXECUTION SUMMARY
============================================================
  Trades Processed:  10
  Trades Skipped:    0
  Records Created:   0
  Execution Time:    0.8s

============================================================
COMPLETED SUCCESSFULLY
============================================================
```

---

## 15. File Structure

```
m1_atr_stop_2/
├── __init__.py        Module exports (M1AtrStopCalculator, config constants)
├── config.py          Self-contained config (DB creds, EOD cutoff, R-levels, table names)
├── calculator.py      Core processor (entry adjustment, bar walk, R/stop detection, batch)
├── runner.py          CLI entry point (--dry-run, --limit, --schema, --info, --verbose)
└── schema/
    └── m1_atr_stop_2.sql   Full DDL + indexes + comments + 4 analysis views
```

---

## 16. Example Queries

```sql
-- Overall summary (uses the pre-built view)
SELECT * FROM v_m1_atr_stop_2_summary;

-- Win rate by entry model
SELECT * FROM v_m1_atr_stop_2_by_model;

-- R-level distribution (how many trades at each max_r)
SELECT * FROM v_m1_atr_stop_2_r_distribution;

-- Trades that reached R3 or higher
SELECT trade_id, ticker, date, model, direction,
       entry_price, stop_price, max_r,
       r1_time, r2_time, r3_time, result
FROM m1_atr_stop_2
WHERE max_r >= 3
ORDER BY date DESC;

-- Net expectancy by model
SELECT model,
       COUNT(*) as trades,
       ROUND(AVG(max_r)::decimal, 3) as expectancy_r
FROM m1_atr_stop_2
GROUP BY model
ORDER BY expectancy_r DESC;

-- Cumulative R curve
SELECT date,
       SUM(max_r) OVER (ORDER BY date, entry_time) as cumulative_r
FROM m1_atr_stop_2
ORDER BY date, entry_time;

-- Average time to R1 for winners
SELECT model,
       ROUND(AVG(r1_bars_from_entry), 1) as avg_bars_to_r1
FROM m1_atr_stop_2
WHERE result = 'WIN'
GROUP BY model;
```
