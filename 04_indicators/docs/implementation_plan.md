# 04_indicators Module v2.0 - Implementation Plan

## Executive Summary

Complete rebuild of the `04_indicators` module from a statistical edge-testing CLI into a **three-phase indicator analysis system** with PyQt6 visualization. The system will answer three questions for every trade:

1. **Ramp-Up (Pre-Entry)**: Were indicators trending favorably in the 25 minutes before entry?
2. **Entry Snapshot**: What was the exact indicator state when the trade was taken?
3. **Post-Trade**: How did indicators behave after entry, and did they predict the outcome?

The old edge testing code will be archived. Three new Supabase tables will be populated as secondary processors in `03_backtest`. A new PyQt6 viewer (modeled on `05_system_analysis`) will provide interactive analysis.

---

## Current State

### What Exists Today in 04_indicators
- **Edge testing framework** (~2,600 lines): chi-square and Spearman tests across 7 indicators
- **PyQt6 GUI**: Launches CLI tests, displays text results in terminal widget
- **CLI runner**: `run_edge_tests.py` with markdown report export
- **Results**: 4 markdown reports in `results/` directory
- **Tables used**: `trades` (v1), `m1_indicator_bars` (v1), `entry_indicators` (v1), `stop_analysis` (v1)

### Problem
- Uses **v1 tables** (not the v2 `_2` suffix tables from `03_backtest`)
- Tests are purely statistical (p-values, effect sizes) with no visual indicator progression
- No concept of the three phases (ramp-up, entry, post-trade)
- Cannot show what a "good setup" looks like over time
- Not structured for ML consumption

### What Replaces It
- Three new database tables populated by `03_backtest` secondary processors
- PyQt6 viewer with per-indicator analysis tabs and Plotly charts
- Data structured for `10_machine_learning` consumption

---

## Architecture Overview

```
                    DATA POPULATION                              VISUALIZATION
                    (03_backtest)                                (04_indicators)

trades_2 ───────────┐
  (entry records)    │
                     ├─► m1_ramp_up_indicator_2      ─┐
m1_indicator_bars_2 ─┤   (25 bars before entry)       │
  (all indicators)   │                                 │
                     ├─► m1_trade_indicator_2          ├─► PyQt6 Indicator Viewer
                     │   (1 bar at entry)              │   - Ramp-Up Tab
m5_atr_stop_2 ───────┤                                │   - Entry Snapshot Tab
  (outcomes only:    ├─► m1_post_trade_indicator_2    ─┘   - Post-Trade Tab
   is_winner,        │   (25 bars after entry)             - Indicator Deep-Dive Tab
   pnl_r, max_r)     │                                    - Composite Setup Tab
                     │
```

**Source table roles**:
- **`trades_2`**: The authoritative source for all trade entries. Provides trade_id, ticker, date, direction, model, zone_type, entry_price, entry_time
- **`m1_indicator_bars_2`**: Provides all indicator values per M1 bar. Joined by ticker + bar_date + bar_time
- **`m5_atr_stop_2`**: Provides trade outcomes ONLY (is_winner, pnl_r/max_r). Joined by trade_id where outcome data is needed

Key design principle: **No new indicator calculations**. All values come from the existing `m1_indicator_bars_2` table. The three new tables are materialized views that slice the data by trade phase for fast querying. Trade outcomes come from `m5_atr_stop_2` via trade_id join.

---

## Step 1: Database Tables (Secondary Processors)

### 1.1 Table: `m1_ramp_up_indicator_2`

**Purpose**: 25 M1 bars ending at the candle BEFORE entry (bar_sequence 0 = oldest, 24 = most recent completed bar before entry candle)

**Source data**: JOIN `trades_2` with `m1_indicator_bars_2` (no outcome data needed for ramp-up bars)

```sql
CREATE TABLE m1_ramp_up_indicator_2 (
    -- Trade Reference
    trade_id            VARCHAR(50) NOT NULL,

    -- Bar Identification
    bar_sequence        INTEGER NOT NULL,           -- 0 (oldest) to 24 (just before entry)
    ticker              VARCHAR(10) NOT NULL,
    bar_date            DATE NOT NULL,
    bar_time            TIME NOT NULL,

    -- OHLCV
    open                NUMERIC(12, 4),
    high                NUMERIC(12, 4),
    low                 NUMERIC(12, 4),
    close               NUMERIC(12, 4),
    volume              BIGINT,

    -- Core Indicators (from m1_indicator_bars_2)
    candle_range_pct    NUMERIC(10, 6),
    vol_delta_raw       NUMERIC(12, 2),
    vol_delta_roll      NUMERIC(12, 2),
    vol_roc             NUMERIC(10, 4),
    sma9                NUMERIC(12, 4),
    sma21               NUMERIC(12, 4),
    sma_config          VARCHAR(10),                -- BULL / BEAR / FLAT
    sma_spread_pct      NUMERIC(10, 6),
    sma_momentum_label  VARCHAR(15),                -- WIDENING / NARROWING / STABLE
    price_position      VARCHAR(10),                -- ABOVE / BTWN / BELOW
    cvd_slope           NUMERIC(10, 6),

    -- Multi-Timeframe Structure
    m5_structure        VARCHAR(10),                -- BULL / BEAR / NEUTRAL
    m15_structure       VARCHAR(10),
    h1_structure        VARCHAR(10),

    -- Composite Scores
    health_score        INTEGER,                    -- 0-10
    long_score          INTEGER,                    -- 0-7
    short_score         INTEGER,                    -- 0-7

    -- Metadata
    calculated_at       TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (trade_id, bar_sequence),
    FOREIGN KEY (trade_id) REFERENCES trades_2(trade_id) ON DELETE CASCADE
);

CREATE INDEX idx_ramp_up_trade ON m1_ramp_up_indicator_2 (trade_id);
CREATE INDEX idx_ramp_up_ticker_date ON m1_ramp_up_indicator_2 (ticker, bar_date);
```

**Population Logic**:
1. For each trade in `trades_2`, INNER JOIN `m5_atr_stop_2` to confirm outcome exists
2. **Skip trades without outcomes** - ramp-up data is only useful if we know the trade result
3. Get `entry_time`, `ticker`, `date` from `trades_2`
4. Truncate `entry_time` to M1 boundary (floor to minute) = entry candle start
5. The bar BEFORE entry candle = `entry_candle_start - 1 minute` = bar_sequence 24
6. Query 25 bars from `m1_indicator_bars_2` ending at that time
7. Assign bar_sequence 0-24 (chronological order)

**Look-ahead bias protection**: The entry candle has NOT closed when the trade is entered (S15 entries happen within a minute). Bar_sequence 24 is the LAST COMPLETED M1 bar before the entry candle opens.

### 1.2 Table: `m1_trade_indicator_2`

**Purpose**: Single M1 bar that closed just before the entry candle (same as ramp_up bar_sequence 24, but denormalized for fast single-row lookups)

**Source data**: JOIN `trades_2` (entry context) + `m5_atr_stop_2` (outcome) + `m1_indicator_bars_2` (indicator values)

```sql
CREATE TABLE m1_trade_indicator_2 (
    -- Trade Reference
    trade_id            VARCHAR(50) NOT NULL PRIMARY KEY,

    -- Trade Context (from trades_2)
    ticker              VARCHAR(10) NOT NULL,
    date                DATE NOT NULL,
    direction           VARCHAR(10) NOT NULL,       -- LONG / SHORT
    model               VARCHAR(10),                -- EPCH1-4
    zone_type           VARCHAR(10),                -- PRIMARY / SECONDARY
    entry_time          TIME NOT NULL,
    entry_price         NUMERIC(12, 4),

    -- Trade Outcome (from m5_atr_stop_2, joined by trade_id)
    is_winner           BOOLEAN,                    -- m5_atr_stop_2.result = 'WIN'
    pnl_r               NUMERIC(8, 2),              -- m5_atr_stop_2.max_r
    max_r_achieved      INTEGER,                    -- m5_atr_stop_2.max_r

    -- Bar Identification
    bar_date            DATE NOT NULL,
    bar_time            TIME NOT NULL,

    -- OHLCV
    open                NUMERIC(12, 4),
    high                NUMERIC(12, 4),
    low                 NUMERIC(12, 4),
    close               NUMERIC(12, 4),
    volume              BIGINT,

    -- Core Indicators
    candle_range_pct    NUMERIC(10, 6),
    vol_delta_raw       NUMERIC(12, 2),
    vol_delta_roll      NUMERIC(12, 2),
    vol_roc             NUMERIC(10, 4),
    sma9                NUMERIC(12, 4),
    sma21               NUMERIC(12, 4),
    sma_config          VARCHAR(10),
    sma_spread_pct      NUMERIC(10, 6),
    sma_momentum_label  VARCHAR(15),
    price_position      VARCHAR(10),
    cvd_slope           NUMERIC(10, 6),

    -- Multi-Timeframe Structure
    m5_structure        VARCHAR(10),
    m15_structure       VARCHAR(10),
    h1_structure        VARCHAR(10),

    -- Composite Scores
    health_score        INTEGER,
    long_score          INTEGER,
    short_score         INTEGER,

    -- Metadata
    calculated_at       TIMESTAMPTZ DEFAULT NOW(),

    FOREIGN KEY (trade_id) REFERENCES trades_2(trade_id) ON DELETE CASCADE
);

CREATE INDEX idx_trade_ind_ticker_date ON m1_trade_indicator_2 (ticker, date);
CREATE INDEX idx_trade_ind_direction ON m1_trade_indicator_2 (direction);
CREATE INDEX idx_trade_ind_model ON m1_trade_indicator_2 (model);
CREATE INDEX idx_trade_ind_winner ON m1_trade_indicator_2 (is_winner);
```

**Population Logic**:
1. For each trade in `trades_2`, INNER JOIN `m5_atr_stop_2` by trade_id to get outcome (result → is_winner, max_r → pnl_r)
2. **Skip trades without outcomes** - if no m5_atr_stop_2 row exists, the trade is NOT inserted
3. Find the M1 bar from `m1_indicator_bars_2` that closed just before entry
4. Merge entry context + outcome + indicator values into single row

**Outcome required**: Trades without a completed `m5_atr_stop_2` analysis are excluded entirely. We do not want incomplete data in the indicator analysis tables - every row must have a definitive WIN/LOSS. The `--status` flag will report how many trades are pending outcome analysis so the user knows to run the upstream processors first.

### 1.3 Table: `m1_post_trade_indicator_2`

**Purpose**: 25 M1 bars starting from the entry candle (bar_sequence 0 = entry candle, 24 = 25th bar after entry)

```sql
CREATE TABLE m1_post_trade_indicator_2 (
    -- Trade Reference
    trade_id            VARCHAR(50) NOT NULL,

    -- Bar Identification
    bar_sequence        INTEGER NOT NULL,           -- 0 (entry candle) to 24
    ticker              VARCHAR(10) NOT NULL,
    bar_date            DATE NOT NULL,
    bar_time            TIME NOT NULL,

    -- OHLCV
    open                NUMERIC(12, 4),
    high                NUMERIC(12, 4),
    low                 NUMERIC(12, 4),
    close               NUMERIC(12, 4),
    volume              BIGINT,

    -- Core Indicators (from m1_indicator_bars_2)
    candle_range_pct    NUMERIC(10, 6),
    vol_delta_raw       NUMERIC(12, 2),
    vol_delta_roll      NUMERIC(12, 2),
    vol_roc             NUMERIC(10, 4),
    sma9                NUMERIC(12, 4),
    sma21               NUMERIC(12, 4),
    sma_config          VARCHAR(10),
    sma_spread_pct      NUMERIC(10, 6),
    sma_momentum_label  VARCHAR(15),
    price_position      VARCHAR(10),
    cvd_slope           NUMERIC(10, 6),

    -- Multi-Timeframe Structure
    m5_structure        VARCHAR(10),
    m15_structure       VARCHAR(10),
    h1_structure        VARCHAR(10),

    -- Composite Scores
    health_score        INTEGER,
    long_score          INTEGER,
    short_score         INTEGER,

    -- Trade Outcome Context (from m5_atr_stop_2, joined by trade_id)
    is_winner           BOOLEAN,                    -- m5_atr_stop_2.result = 'WIN'
    pnl_r               NUMERIC(8, 2),              -- m5_atr_stop_2.max_r
    max_r_achieved      INTEGER,                    -- m5_atr_stop_2.max_r

    -- Metadata
    calculated_at       TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (trade_id, bar_sequence),
    FOREIGN KEY (trade_id) REFERENCES trades_2(trade_id) ON DELETE CASCADE
);

CREATE INDEX idx_post_trade_trade ON m1_post_trade_indicator_2 (trade_id);
CREATE INDEX idx_post_trade_ticker_date ON m1_post_trade_indicator_2 (ticker, bar_date);
CREATE INDEX idx_post_trade_winner ON m1_post_trade_indicator_2 (is_winner);
```

**Population Logic**:
1. For each trade in `trades_2`, INNER JOIN `m5_atr_stop_2` by trade_id to get outcome
2. **Skip trades without outcomes** - same rule as m1_trade_indicator_2
3. Truncate `entry_time` to M1 boundary = entry candle (bar_sequence 0)
4. Query 25 bars from `m1_indicator_bars_2` starting at entry candle
5. Stamp outcome on each row for easy aggregation (same outcome on all 25 rows per trade)

**Note on entry candle**: The entry candle IS included here (bar_sequence 0) because we are analyzing what happens AFTER the trade is entered, including how that entry candle closed.

---

## Step 2: Secondary Processor Implementation

### Location in 03_backtest

```
03_backtest/processor/secondary_analysis/
├── m1_ramp_up_indicator_2/
│   ├── __init__.py
│   ├── config.py
│   ├── populator.py             -- Core logic: query + insert
│   ├── runner.py                -- CLI: python runner.py [--schema] [--dry-run] [--limit N] [--status]
│   └── schema/
│       └── m1_ramp_up_indicator_2.sql
│
├── m1_trade_indicator_2/
│   ├── __init__.py
│   ├── config.py
│   ├── populator.py
│   ├── runner.py
│   └── schema/
│       └── m1_trade_indicator_2.sql
│
└── m1_post_trade_indicator_2/
    ├── __init__.py
    ├── config.py
    ├── populator.py
    ├── runner.py
    └── schema/
        └── m1_post_trade_indicator_2.sql
```

### Runner CLI Pattern (follows existing processors)

```bash
# Create tables
python runner.py --schema

# Check what needs processing (shows outcome analysis gaps)
python runner.py --status

# Dry run (no writes)
python runner.py --dry-run

# Process with limit
python runner.py --limit 10

# Full run (only processes trades that have outcomes)
python runner.py

# Verbose output
python runner.py --verbose

# Example --status output:
#   Total trades in trades_2:              5,900
#   Trades with outcomes (m5_atr_stop_2):  5,650
#   Already in m1_trade_indicator_2:       5,400
#   Ready to process:                        250
#   Pending outcome analysis:                250  ← need to run: python m5_atr_stop_2/runner.py
```

### Populator Logic (all three share the same pattern)

```
1. Connect to Supabase
2. Query trades_2 INNER JOIN m5_atr_stop_2 for all trade_ids:
   - That HAVE a completed outcome (m5_atr_stop_2 row exists)
   - That are NOT YET in the target table
3. For each eligible trade:
   a. Get entry_time, ticker, date, direction, model, zone_type from trades_2
   b. Get is_winner, pnl_r, max_r from m5_atr_stop_2
   c. Compute M1 candle boundary for entry
   d. Query m1_indicator_bars_2 for the relevant bar range
   e. Map columns to target schema
   f. Batch insert (500 rows per batch)
4. Print summary:
   - Trades processed (with outcomes)
   - Trades SKIPPED (no m5_atr_stop_2 outcome yet)
   - Trades SKIPPED (no m1_indicator_bars_2 data)
   - Rows inserted
   - Errors
```

**Key implementation detail**: These processors do NOT recalculate any indicators. They SELECT from `m1_indicator_bars_2` (which already has all 22+ indicators computed) and INSERT into the phase-specific tables. This is a data reshaping operation, not a calculation.

**Outcome required**: Trades without a completed `m5_atr_stop_2` row are SKIPPED entirely. The `--status` flag reports the breakdown:
```
Status: m1_trade_indicator_2
  Total trades in trades_2:              5,900
  Trades with outcomes (m5_atr_stop_2):  5,650
  Already populated:                     5,400
  Ready to process:                        250
  Pending outcome analysis:                250  ← Run m5_atr_stop processor first
```
This makes it clear when upstream processors need to run before indicator tables can be populated.

### Integration with run_backtest.py

Add three new CLI flags to the main backtest runner:

```bash
python run_backtest.py 2026-02-13 --m1-ramp-up --m1-trade-ind --m1-post-trade
```

These run after the existing `--m5-atr-stop` step in the pipeline (so outcomes are available):

```
Existing pipeline:
  trades_2 → m1_bars → m1_indicator_bars_2 → m1_atr_stop_2 → m5_atr_stop_2 → trades_m5_r_win_2

New additions (run after m5_atr_stop_2, before or alongside trades_m5_r_win_2):
  trades_2 + m1_indicator_bars_2 (+ m5_atr_stop_2 for outcomes) → m1_ramp_up_indicator_2
  trades_2 + m1_indicator_bars_2 + m5_atr_stop_2               → m1_trade_indicator_2
  trades_2 + m1_indicator_bars_2 + m5_atr_stop_2               → m1_post_trade_indicator_2
```

**Note**: All three processors REQUIRE `m5_atr_stop_2` outcomes to exist before populating. Even though ramp-up data is technically pre-entry, there is no value in storing it without knowing whether the trade won or lost - you can't split winners vs losers in the viewer without that data. This keeps the tables clean: every trade_id in these tables has a definitive outcome.

---

## Step 3: PyQt6 Indicator Viewer (04_indicators rebuild)

### Module Structure

```
04_indicators/
├── app.py                           -- Entry point (python 04_indicators/app.py)
├── config.py                        -- DB tables, indicator configs, UI settings
├── CLAUDE.md                        -- AI context
├── __init__.py
│
├── data/
│   ├── __init__.py
│   └── provider.py                  -- DataProvider class (Supabase queries)
│
├── ui/
│   ├── __init__.py
│   ├── main_window.py               -- MainWindow (filters + 5 tabs)
│   ├── styles.py                    -- Dark theme (import from shared)
│   └── tabs/
│       ├── __init__.py
│       ├── ramp_up_tab.py           -- Tab 1: 25-bar ramp-up analysis
│       ├── entry_snapshot_tab.py    -- Tab 2: Entry indicator state
│       ├── post_trade_tab.py        -- Tab 3: Post-trade indicator behavior
│       ├── indicator_deep_dive_tab.py -- Tab 4: Per-indicator statistical view
│       └── composite_setup_tab.py   -- Tab 5: Multi-indicator ideal setups
│
├── docs/
│   └── implementation_plan.md       -- This document
│
└── _archive/                        -- Old edge testing code preserved here
    ├── edge_testing/
    ├── scripts/
    ├── indicator_gui/
    └── results/
```

### Main Window Layout (follows 05_system_analysis pattern)

```
┌──────────────────────────────────────────────────────────────────┐
│  EPOCH INDICATOR ANALYSIS  v2.0                                  │
├────────┬─────────────────────────────────────────────────────────┤
│        │ ┌─────────┬──────────┬────────────┬────────────┬──────┐│
│ FILTER │ │ Ramp-Up │  Entry   │ Post-Trade │ Deep Dive  │Setup ││
│ PANEL  │ │         │ Snapshot │            │            │      ││
│        │ ├─────────┴──────────┴────────────┴────────────┴──────┤│
│ Model  │ │                                                     ││
│ Dir    │ │              TAB CONTENT AREA                       ││
│ Ticker │ │                                                     ││
│ Date   │ │  (Charts, tables, statistics rendered here)         ││
│ Range  │ │                                                     ││
│        │ │                                                     ││
│[Refr]  │ │                                                     ││
│ N trds │ │                                                     ││
├────────┴─┴─────────────────────────────────────────────────────┤│
│ Status: Connected | Last refresh: 14:32:01                      │
└──────────────────────────────────────────────────────────────────┘
```

### Filter Panel (Left Sidebar - 220px fixed width)

- **Model**: EPCH1 / EPCH2 / EPCH3 / EPCH4 / All Models
- **Direction**: LONG / SHORT / All Directions
- **Ticker**: Populated from database (+ "All Tickers")
- **Date From / To**: QDateEdit with calendar popup
- **Outcome**: Winners / Losers / All (new filter)
- **Refresh Button**: Triggers data reload
- **Trade Count**: Display count matching filters
- **Pending Analysis Warning**: If trades exist in `trades_2` for the selected filters that are NOT in the indicator tables (missing outcomes), show amber warning: `"⚠ 47 trades pending outcome analysis - run m5_atr_stop processor"`. This tells you data is incomplete and you need to run upstream processors before the analysis is comprehensive

### Data Loading (Background Thread)

```python
class DataLoadThread(QThread):
    """Loads all tab data in background to keep UI responsive."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        provider = DataProvider()
        data = {
            'trades': provider.get_trades(filters),
            'ramp_up': provider.get_ramp_up_data(filters),
            'entry': provider.get_entry_data(filters),
            'post_trade': provider.get_post_trade_data(filters),
        }
        self.finished.emit(data)
```

---

## Step 4: Tab Specifications

### Tab 1: Ramp-Up Analysis

**Purpose**: Show how indicators evolve in the 25 minutes before entry, comparing winners vs losers.

**Sections**:

1. **Ramp-Up Heatmap** (primary visual)
   - X-axis: bar_sequence 0-24 (25 bars)
   - Y-axis: Each indicator (candle_range_pct, vol_delta_roll, vol_roc, sma_spread_pct, cvd_slope)
   - Color: Green (favorable) / Red (unfavorable) / Gray (neutral)
   - Two heatmaps side-by-side: WINNERS vs LOSERS
   - Shows the average value at each bar_sequence position

2. **Ramp-Up Line Charts** (one per indicator)
   - X-axis: bar_sequence 0-24
   - Y-axis: indicator value
   - Two lines: Winner average (green) vs Loser average (red)
   - Shaded region: +/- 1 standard deviation
   - Goal: See if winners have a distinguishable ramp-up pattern

3. **Structure Alignment Timeline**
   - For M5, M15, H1 structure across the 25 bars
   - Show bar chart of % BULL / % BEAR / % NEUTRAL at each position
   - Separate for winners vs losers

4. **Summary Statistics Table**
   - For each indicator: Winner avg (bars 20-24), Loser avg (bars 20-24), Delta, Significance
   - Highlights statistically significant differences

### Tab 2: Entry Snapshot

**Purpose**: Show indicator state at the exact moment of entry (the completed M1 bar before entry candle).

**Sections**:

1. **Indicator Cards** (summary row)
   - One card per indicator showing: Value, Win Rate at that level, Trade Count
   - Color-coded by favorability

2. **Win Rate by Indicator State** (bar charts)
   - For each categorical indicator (sma_config, price_position, structures):
     - Bar chart: state (BULL/BEAR/etc.) vs win rate
     - Includes trade count per state
   - For each continuous indicator (candle_range_pct, vol_roc, etc.):
     - Quintile analysis: divide into 5 groups, show win rate per quintile

3. **Indicator Correlation Matrix**
   - Heatmap showing how indicators relate to each other at entry
   - Helps identify redundant vs independent indicators

4. **Best vs Worst Entry Profiles**
   - Top 10% of trades by pnl_r: what did their entry indicators look like?
   - Bottom 10%: what did their entry indicators look like?
   - Side-by-side comparison table

### Tab 3: Post-Trade Analysis

**Purpose**: Show what happens to indicators after entry, and whether indicator behavior predicts trade outcome.

**Sections**:

1. **Post-Entry Indicator Evolution** (line charts)
   - Same format as ramp-up but for bars 0-24 after entry
   - Winner vs Loser lines
   - Key question: Do indicators diverge immediately after entry?

2. **Early Warning Signals**
   - At which bar_sequence do indicators first show divergence?
   - Table: Indicator, Divergence Bar, Direction of Divergence, Effect Size
   - Goal: Can we detect losing trades early enough to exit?

3. **Indicator Stability**
   - Did indicators that were favorable at entry STAY favorable?
   - % of time indicator maintained entry state through bars 0-5, 0-10, 0-15, 0-24
   - Winners vs losers comparison

4. **Post-Entry Structure Shifts**
   - Timeline of M5/M15/H1 structure changes after entry
   - Did structure break down during losing trades?

### Tab 4: Indicator Deep Dive (Per-Indicator)

**Purpose**: Focus on one indicator at a time with comprehensive analysis across all three phases.

**Controls**:
- Indicator selector dropdown (7 indicators)
- All filters from main panel still apply

**Sections** (for the selected indicator):

1. **Three-Phase Progression Chart**
   - Single chart showing ramp-up (bars -24 to -1) → entry (bar 0) → post-trade (bars 1 to 24)
   - Winner line vs Loser line
   - Vertical marker at entry point
   - 50 total bars in one view

2. **Optimal State Analysis**
   - What value/state of this indicator has the highest win rate?
   - For categorical: win rate per state with sample size
   - For continuous: optimal range analysis (find the sweet spot)

3. **Ramp-Up Trend Analysis**
   - Is the indicator IMPROVING or DEGRADING in the ramp-up?
   - Calculate slope of indicator over bars 15-24 (last 10 bars)
   - Compare: positive slope win rate vs negative slope win rate
   - Key insight: Is the DIRECTION of change more predictive than the absolute value?

4. **Breakdown by Model/Direction**
   - Table: Model x Direction grid showing this indicator's predictive power
   - Example: candle_range_pct might matter more for EPCH2 (rejection) than EPCH1 (continuation)

### Tab 5: Composite Setup Analysis

**Purpose**: Show how indicators work together to identify the ideal entry setup.

**Sections**:

1. **Setup Combinations Table**
   - Test pairs and triples of indicator conditions
   - Example: "SMA BULL + H1 BULL + Vol ROC Elevated" → win rate, trade count
   - Rank by win rate (min 20 trades per combination)
   - Top 10 and Bottom 10 combinations highlighted

2. **Ideal Setup Profile**
   - Based on top combinations, define the "ideal" entry state
   - Show how often the ideal setup occurs
   - Win rate when ideal vs not ideal

3. **Setup Score Card**
   - Assign points for each favorable indicator condition at entry
   - Create a composite "setup score" (similar to health_score but trade-validated)
   - Show win rate by score tier (0-2: Weak, 3-4: Moderate, 5-7: Strong)
   - Plotly bar chart of score distribution with win rate overlay

4. **ML Feature Importance Preview**
   - Basic feature importance ranking (information gain or similar)
   - Shows which indicators the ML system should focus on
   - Formatted for export to `10_machine_learning`

---

## Step 5: Data Provider API

### DataProvider Class Methods

```python
class DataProvider:
    """Central data access for the indicator viewer."""

    # Connection
    def connect(self) -> bool
    def disconnect(self)

    # Filter queries
    def get_trades(self, model, direction, ticker, date_from, date_to, outcome) -> pd.DataFrame
    def get_tickers(self) -> List[str]
    def get_date_range(self) -> Tuple[date, date]

    # Phase data
    def get_ramp_up_data(self, trade_ids: List[str]) -> pd.DataFrame
    def get_entry_data(self, trade_ids: List[str]) -> pd.DataFrame
    def get_post_trade_data(self, trade_ids: List[str]) -> pd.DataFrame

    # Aggregated views
    def get_ramp_up_averages(self, trade_ids, group_by='is_winner') -> pd.DataFrame
    def get_entry_win_rates(self, trade_ids, indicator_col) -> pd.DataFrame
    def get_post_trade_averages(self, trade_ids, group_by='is_winner') -> pd.DataFrame

    # Composite analysis
    def get_setup_combinations(self, trade_ids, indicators, min_trades=20) -> pd.DataFrame
```

### Key Queries

**Ramp-up averages (winners vs losers)**:
```sql
-- All trades in m1_ramp_up_indicator_2 are guaranteed to have outcomes
-- (processor only populates trades with m5_atr_stop_2 results)
SELECT
    r.bar_sequence,
    s.result = 'WIN' as is_winner,
    AVG(r.candle_range_pct) as avg_candle_range,
    AVG(r.vol_delta_roll) as avg_vol_delta,
    AVG(r.vol_roc) as avg_vol_roc,
    AVG(r.sma_spread_pct) as avg_sma_spread,
    AVG(r.cvd_slope) as avg_cvd_slope,
    COUNT(*) as trade_count
FROM m1_ramp_up_indicator_2 r
JOIN m5_atr_stop_2 s ON r.trade_id = s.trade_id
WHERE r.trade_id = ANY(%(trade_ids)s)
GROUP BY r.bar_sequence, s.result
ORDER BY r.bar_sequence
```

**Pending analysis check (for filter panel warning)**:
```sql
-- Count trades in trades_2 that match filters but are NOT in indicator tables
SELECT COUNT(*) as pending_count
FROM trades_2 t
WHERE t.date BETWEEN %(date_from)s AND %(date_to)s
  AND t.trade_id NOT IN (SELECT trade_id FROM m1_trade_indicator_2)
```

**Entry win rate by indicator state**:
```sql
SELECT
    sma_config,
    COUNT(*) as trades,
    SUM(CASE WHEN is_winner THEN 1 ELSE 0 END) as wins,
    ROUND(AVG(CASE WHEN is_winner THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
    ROUND(AVG(pnl_r), 2) as avg_r
FROM m1_trade_indicator_2
WHERE trade_id = ANY(%(trade_ids)s)
GROUP BY sma_config
ORDER BY win_rate DESC
```

---

## Step 6: Implementation Sequence

### Phase A: Database & Processors (do first)

| Step | Task | Dependencies | Notes |
|------|------|-------------|-------|
| A1 | Create SQL schema files for all 3 tables | None | Run against Supabase |
| A2 | Build `m1_trade_indicator_2` processor | A1 | Simplest (1 row per trade) |
| A3 | Build `m1_ramp_up_indicator_2` processor | A1 | 25 rows per trade |
| A4 | Build `m1_post_trade_indicator_2` processor | A1 | 25 rows per trade |
| A5 | Add flags to `run_backtest.py` | A2-A4 | Integration into pipeline |
| A6 | Run full population against existing data | A5 | Backfill all historical trades |

### Phase B: PyQt6 Viewer (do after data exists)

| Step | Task | Dependencies | Notes |
|------|------|-------------|-------|
| B1 | Archive old 04_indicators code | None | Move to `_archive/` |
| B2 | Create module skeleton (app.py, config.py, data/provider.py) | A6 | Follow 05_system_analysis pattern |
| B3 | Build main_window.py with filter panel | B2 | Left sidebar + tab container |
| B4 | Build Entry Snapshot tab | B2, B3 | Simplest tab (single row data) |
| B5 | Build Ramp-Up Analysis tab | B2, B3 | Line charts + heatmap |
| B6 | Build Post-Trade Analysis tab | B2, B3 | Similar to ramp-up |
| B7 | Build Indicator Deep Dive tab | B4, B5, B6 | Combines all three phases |
| B8 | Build Composite Setup tab | B4 | Combination analysis |

### Phase C: Polish & ML Integration

| Step | Task | Dependencies | Notes |
|------|------|-------------|-------|
| C1 | Update CLAUDE.md and README.md | B8 | |
| C2 | Update main launcher.py | B8 | Add 04_indicators entry |
| C3 | Export format for 10_machine_learning | B8 | CSV/JSON feature export |

---

## Key Technical Decisions

### 1. No New Indicator Calculations
All indicator values already exist in `m1_indicator_bars_2`. The three new tables are materialized slices keyed by trade phase. This means:
- No risk of calculation drift between modules
- Fast population (SELECT + INSERT, no compute)
- Single source of truth for indicator values

### 2. Bar Timing Precision
- Entries happen on S15 bars (sub-minute precision, e.g., 09:35:15)
- M1 bar at 09:35:00 is the "entry candle" (opens at :35, closes at :36)
- The PRIOR completed bar is 09:34:00 (opened at :34, closed at :35)
- `entry_candle_start = floor(entry_time to minute)`
- `prior_bar_time = entry_candle_start - 1 minute`

### 3. Why Denormalize Trade Context
The `m1_trade_indicator_2` table includes direction, model (from `trades_2`) and is_winner, pnl_r (from `m5_atr_stop_2`) even though these exist in their source tables. This avoids JOINs in the most common query pattern (filter by outcome + show indicators) and follows the existing pattern from `trades_m5_r_win_2` which also denormalizes. The authoritative trade record is always `trades_2`.

### 4. Chart Rendering
Following `05_system_analysis`: Plotly figures → PNG export via kaleido → QPixmap display in QLabel. This gives professional chart quality with zero interactivity overhead.

### 5. Indicator Column Selection
Only the 7 indicators from the live entry qualifier are included (not all 22+ from `m1_indicator_bars_2`). This keeps the tables focused and the UI manageable:
- candle_range_pct
- vol_delta_raw + vol_delta_roll
- vol_roc
- sma9, sma21, sma_config, sma_spread_pct, sma_momentum_label, price_position
- cvd_slope
- m5_structure, m15_structure, h1_structure
- health_score, long_score, short_score

---

## How to Read Each Indicator (Trader's Reference)

This section defines exactly what each number means, what "good" looks like across all three phases, and how the PyQt viewer will present it. These definitions drive every visualization, threshold, and color choice in the tool.

### The Core Problem This Solves

When you're sitting in the market watching the entry qualifier scroll, you see 7 rows of data across 25 columns. You need to process this in real-time and decide: **trade or no trade**. The difficulty is that:

- A single indicator value at one moment means little on its own
- The *trajectory* over 25 bars matters more than any single reading
- What's "good" for a LONG EPCH1 continuation is different from a SHORT EPCH2 rejection
- After entry, you need to know quickly if the trade is working or dying

The PyQt viewer will take your entire trade history and show you: **"When this indicator looked like THIS before entry, you won X% of the time."** That's the gap between raw data and actionable knowledge.

---

### Indicator 1: Candle Range % (`candle_range_pct`)

**What it measures**: How large the M1 candle body+wicks are relative to price. `(high - low) / close * 100`

**What you see in the entry qualifier**: `0.18%` (white text) or dimmed column if < 0.12%

**Thresholds**:
| Value | Label | Color | What It Means |
|-------|-------|-------|---------------|
| < 0.12% | ABSORPTION | Red / Dimmed | Price is compressed. No movement. **Skip this bar entirely** - there is no edge opportunity when price isn't moving |
| 0.12% - 0.15% | LOW | Gray | Candles are forming but small. Caution - momentum hasn't arrived yet |
| >= 0.15% | NORMAL | Green | Healthy candle size. Price is moving enough for your entry to have room to work |
| >= 0.20% | HIGH | Green | Strong expansion. Can signal momentum but also exhaustion |

**How to read the ramp-up (25 bars before entry)**:
- **Ideal pattern**: Bars transitioning from LOW/ABSORPTION → NORMAL. You want to see candle range *expanding* into the entry. This means volatility is arriving and price is starting to move
- **Warning pattern**: NORMAL → LOW → ABSORPTION. Range is compressing INTO the entry = momentum dying
- **What the viewer will show**: Average candle range at each bar_sequence position, winner vs loser. The key question: *Were winners preceded by expanding ranges?*

**How to read at entry (snapshot)**:
- The bar that just closed before entry should be >= 0.15%. If the last completed bar is in absorption, the entry qualifier was firing on a candle that may have been a false start

**How to read post-trade (25 bars after entry)**:
- Winners: Candle range should STAY >= 0.15% for the first 5-10 bars. If ranges immediately compress after entry, the move may be stalling
- Losers: Often show immediate range compression - the move that triggered the entry was a one-bar event, not sustained momentum

**Per-model nuance**:
- **EPCH1/3 (Continuation)**: Needs sustained range. The zone traversal should be followed by continued movement
- **EPCH2/4 (Rejection)**: A single high-range bar at the rejection point is expected, but watch for follow-through range staying healthy

---

### Indicator 2: Volume Delta (`vol_delta_roll`)

**What it measures**: Whether buyers or sellers dominated the last 5 M1 bars. Calculated per-bar as: `((2 * (close - low) / (high - low)) - 1) * volume`, then summed over a 5-bar rolling window.

**What you see in the entry qualifier**: `+2.5M` (green) or `-800K` (red)

**How bar position works**:
- Close at the HIGH of the bar → multiplier = +1.0 → all volume attributed to buyers
- Close at the LOW → multiplier = -1.0 → all volume attributed to sellers
- Close at the midpoint → multiplier = 0 → neutral
- The rolling 5-bar sum smooths out single-bar noise

**How to read for LONG trades**:
| Value | Color | What It Means |
|-------|-------|---------------|
| Strong positive (+) | Green | Buyers dominating. Aligned with your LONG direction. Good |
| Weak positive | Green | Slight buying bias. Not strong confirmation |
| Negative (-) | Red | Sellers dominating even though you're going long. Caution |

**How to read for SHORT trades** (paradox logic):
| Value | Color | What It Means |
|-------|-------|---------------|
| Strong positive (+) | Green | Buyers are EXHAUSTING themselves. For rejections (EPCH2/4), this is actually favorable - buyers pushed into the zone and got rejected |
| Negative (-) | Red | Sellers already in control. Aligned, but the easy money may already be priced in |

**Ramp-up ideal (LONG continuation)**:
- Vol delta transitioning from neutral/negative → consistently positive in last 10 bars
- Shows buying pressure building into the entry

**Ramp-up ideal (SHORT rejection)**:
- Vol delta strongly POSITIVE in bars 10-20, then weakening/flipping in bars 21-24
- Shows buyers pushed hard, failed, and are now exhausted

**Post-trade**:
- Winners (LONG): Vol delta stays positive for bars 0-10 after entry
- Losers (LONG): Vol delta flips negative within first 5 bars - sellers took over immediately

**Display format in viewer**: Abbreviated with sign: `+2.5M`, `-800K`, `+45K`. Magnitude matters - bigger absolute numbers = stronger conviction.

---

### Indicator 3: Volume Rate of Change (`vol_roc`)

**What it measures**: How current bar volume compares to the average of the prior 20 bars. `((current_volume - avg_20_bar_volume) / avg_20_bar_volume) * 100`

**What you see in the entry qualifier**: `+45%` (green if >= 30%) or `-12%` (red if < 0%)

**Thresholds**:
| Value | Label | Color | What It Means |
|-------|-------|-------|---------------|
| >= 50% | HIGH | Green | Volume is 1.5x the 20-bar average. Strong institutional interest or news flow |
| >= 30% | ELEVATED | Green | Volume is 1.3x average. Meaningful above-normal activity. This is the confirmation threshold |
| 0% to 30% | NORMAL | Yellow | Volume is average. No unusual activity. Not a disqualifier but no confirmation either |
| < 0% | DECLINING | Red | Volume is BELOW average. Less interest than normal. Weak signal - the move happening on light volume is less trustworthy |

**Why 30% is the magic number**: Your system uses 30% as the "elevated" threshold because historically, entries with vol_roc >= 30% have shown meaningfully higher win rates. Below 30%, volume is within normal variance.

**Ramp-up ideal**:
- Bars 0-15: Can be normal or declining (quiet before the move)
- Bars 16-24: Vol ROC should ramp from NORMAL → ELEVATED (30%+)
- **Best pattern**: A clear volume surge building into entry. Bars 20-24 all showing green (>=30%)
- **Warning**: Vol ROC already elevated at bar 0-5 and declining by bar 20-24 = the volume surge happened too early, momentum fading

**At entry**:
- Ideal: >= 30% (confirmation that the entry is happening on real volume)
- Acceptable: 0-30% (not a dealbreaker if other indicators are aligned)
- Bad: < 0% (entering on below-average volume = low conviction move)

**Post-trade**:
- Winners: Vol ROC stays elevated (>=30%) for 3-5 bars after entry, then can normalize
- Losers: Vol ROC often spikes on the entry bar then immediately collapses to normal/declining

---

### Indicator 4: SMA Configuration (`sma_config`, `sma_spread_pct`, `sma_momentum_label`)

**What it measures**: Three related sub-indicators from the 9-period and 21-period Simple Moving Averages:

1. **SMA Config** (`sma_config`): Which SMA is on top?
   - `BULL` = SMA9 > SMA21 (fast above slow = uptrend)
   - `BEAR` = SMA9 < SMA21 (fast below slow = downtrend)
   - `FLAT` = Essentially equal (no trend)

2. **SMA Spread %** (`sma_spread_pct`): How far apart are the SMAs? `abs(sma9 - sma21) / close * 100`
   - >= 0.15% = WIDE spread (strong trend)
   - < 0.15% = NARROW spread (weak/transitioning trend)

3. **SMA Momentum** (`sma_momentum_label`): Is the spread getting wider or narrower?
   - `WIDENING` = Spread is increasing (trend strengthening)
   - `NARROWING` = Spread is decreasing (trend weakening / potential reversal)
   - `STABLE` = Spread unchanged

**What you see in the entry qualifier**: `B0.15` (green, BULL config with 0.15% spread) or `S0.08` (red, BEAR config with 0.08% spread)

**How to read for LONG trades**:
| Config | Spread | Momentum | Signal |
|--------|--------|----------|--------|
| BULL | WIDE (>=0.15%) | WIDENING | **Strongest LONG** - trend is strong and accelerating |
| BULL | WIDE | STABLE | Good - strong trend holding |
| BULL | NARROW (<0.15%) | WIDENING | Promising - trend starting to assert itself |
| BULL | NARROW | NARROWING | Caution - uptrend losing steam |
| BEAR | Any | Any | Opposed to LONG direction. Can still work for reversals (EPCH2) but adds risk |
| FLAT | Any | Any | No trend established. Neutral |

**How to read for SHORT trades**:
- Mirror the above: BEAR config = aligned, BULL config = opposed
- For EPCH2/4 (rejections): BULL config on a SHORT can paradoxically be good - it means buyers were strong but the rejection at the zone signals exhaustion

**Ramp-up ideal (LONG continuation EPCH1/3)**:
- SMA config should be BULL for majority of the 25 bars
- Spread should be WIDENING in last 10 bars (trend building)
- Price position: ABOVE both SMAs

**Ramp-up warning signs**:
- Config flipping between BULL and BEAR (choppy)
- Spread narrowing into entry (trend dying)
- Price moving from ABOVE to BETWEEN the SMAs (losing trend support)

**At entry**: The SMA config should match your trade direction. BULL for LONG, BEAR for SHORT. Exceptions exist for rejection trades where the paradox applies.

**Post-trade**:
- Winners: SMA config stays aligned and spread stays wide or widens
- Losers: SMA spread narrows and config may flip (the trend you entered with reverses)

---

### Indicator 5: CVD Slope (`cvd_slope`)

**What it measures**: The direction and strength of Cumulative Volume Delta over a 15-bar window. CVD tracks the running total of volume delta (buyers - sellers). The slope is the linear regression trend of this cumulative total, normalized by average volume.

**Interpretation**:
| Value | What It Means |
|-------|---------------|
| Positive (> 0.1) | Buying pressure is ACCUMULATING over time. Each bar adds more buying than selling |
| Near zero (-0.1 to 0.1) | Balanced flow. No dominant buyer or seller trend |
| Negative (< -0.1) | Selling pressure is ACCUMULATING. Each bar adds more selling |

**Think of it this way**: Vol delta tells you who won the LAST 5 bars. CVD slope tells you who is winning the WAR over 15 bars.

**How to read for LONG trades**:
- Positive CVD slope = buyers accumulating = ALIGNED
- Negative CVD slope = sellers accumulating = OPPOSED
- Rising from negative toward zero = sellers losing grip (potential reversal setup)

**Ramp-up ideal (LONG)**:
- CVD slope transitioning from near-zero to positive in the last 10-15 bars
- Shows sustained buying accumulation building into the entry

**Post-trade**:
- Winners: CVD slope stays positive or increases (buyers maintain control)
- Losers: CVD slope flips negative shortly after entry (sellers took over the flow)

---

### Indicator 6: Market Structure (M5, M15, H1)

**What it measures**: Whether each timeframe is making higher-highs/higher-lows (BULL), lower-highs/lower-lows (BEAR), or mixed (NEUTRAL). Uses a 5-bar fractal swing analysis (2 bars per side).

**What you see**: `▲` (green), `▼` (red), or `─` (gray/cyan)

**The Three Timeframes and What They Tell You**:

| Timeframe | Lookback | Role | Changes How Often |
|-----------|----------|------|-------------------|
| **M5 Structure** | ~4 hours of M5 bars | Local/execution trend | Can change every 5 minutes. Responsive |
| **M15 Structure** | ~7.5 hours of M15 bars | Intermediate trend | Changes every 15-45 minutes. More stable |
| **H1 Structure** | ~25 hours of H1 bars | Macro trend context | Changes every 1-4 hours. Very stable. **H1 NEUTRAL is the strongest edge (+36pp win rate lift)** |

**The H1 NEUTRAL Edge**: This is your single biggest statistical edge. When H1 structure is NEUTRAL (not clearly BULL or BEAR), win rates jump dramatically. Why? Because NEUTRAL means price is in a range on the hourly - your zone-based entries work best when the hourly isn't forcing a strong directional bias that overrides the zone reaction.

**Structure Alignment for LONG trades**:
| H1 | M15 | M5 | Signal |
|----|-----|----|--------|
| NEUTRAL | Any | Any | **Best** - H1 not opposing your trade |
| BULL | BULL | BULL | Strong alignment - all timeframes agree on uptrend |
| BULL | BULL | BEAR | M5 pulling back within larger uptrend - potential continuation entry |
| BEAR | Any | Any | H1 opposing your LONG - higher risk. Needs strong zone reaction |

**How this works in the ramp-up**:
- H1 structure: Will typically NOT change during a 25-minute ramp-up. Show it as a header/context label, not in the bar-by-bar heatmap
- M15 structure: May change once or twice. Watch for M15 aligning with trade direction
- M5 structure: Most dynamic. In a good ramp-up, you'll see M5 structure shift to align with your direction (e.g., M5 goes from BEAR → NEUTRAL → BULL before a LONG entry)

**Post-trade**:
- **Critical**: If M5 structure flips AGAINST your direction within 5 bars of entry, the trade is likely failing
- Winners: M5 maintains or strengthens in your direction
- Losers: M5 flips against you AND M15 starts turning

---

### How the PyQt Viewer Will Present These

Each tab will display indicators using the **same color logic and format** as the live entry qualifier. This creates visual consistency - what you learn in the viewer directly transfers to reading the live tool.

**Color mapping (universal across the system)**:
| Color | Hex | Meaning |
|-------|-----|---------|
| Green | `#26a69a` | Favorable / Bullish / Elevated / Aligned |
| Red | `#ef5350` | Unfavorable / Bearish / Declining / Opposed |
| Yellow/Amber | `#ffc107` | Neutral / Moderate / Normal range |
| Gray | `#888888` | Neutral structure / Insufficient data |
| Cyan | `#00BCD4` | H1 NEUTRAL (special - this is the strongest signal) |
| Dimmed | `#4a4a4a` on `#1a1a1a` | Absorption zone (skip) |

**Per-indicator display format**:
| Indicator | Format | Example |
|-----------|--------|---------|
| Candle Range % | `X.XX%` | `0.18%` |
| Vol Delta (rolling) | `+X.XM` / `+XK` / `+X` | `+2.5M` |
| Vol ROC | `+X%` | `+45%` |
| SMA Config | `B` or `S` + spread % | `B0.15` |
| SMA Momentum | `WIDENING` / `NARROWING` / `STABLE` | `WIDENING` |
| CVD Slope | `+X.XX` / `-X.XX` | `+0.35` |
| Structure | `▲` / `▼` / `─` | `▲` |

---

### Calculations the Viewer Will Perform on Each Indicator

For every indicator across the filtered trade set, the viewer computes these metrics. No complex statistics - straightforward numbers a trader can internalize.

#### 1. Win Rate by State (Categorical Indicators)

For `sma_config`, `sma_momentum_label`, `price_position`, `m5_structure`, `m15_structure`, `h1_structure`:

```
For each state (e.g., BULL / BEAR / NEUTRAL):
  Total trades where indicator = this state
  Winners where indicator = this state
  Win Rate = winners / total * 100
  Avg R = average pnl_r for this state
```

Display: Bar chart with state on X-axis, win rate on Y-axis, trade count inside each bar.

#### 2. Win Rate by Quintile (Continuous Indicators)

For `candle_range_pct`, `vol_delta_roll`, `vol_roc`, `sma_spread_pct`, `cvd_slope`:

```
Sort all entry values
Split into 5 equal groups (quintiles: Q1=lowest 20%, Q5=highest 20%)
For each quintile:
  Win Rate = winners / total * 100
  Avg R = average pnl_r
  Range: min-max values in this quintile
```

Display: Bar chart with quintile label + range on X-axis, win rate on Y-axis.

**What this answers**: "Is higher candle_range_pct better? Or is there a sweet spot?" The quintile view shows you non-linear relationships.

#### 3. Ramp-Up Slope (Direction of Change)

For each continuous indicator, computed over bars 15-24 (last 10 bars of ramp-up):

```
slope = linear_regression_slope(values at bars 15-24)
Classify as: IMPROVING (slope > 0 toward favorable) / DEGRADING / FLAT
Win Rate when IMPROVING vs DEGRADING
```

**What this answers**: "Is it better when vol_roc is high at entry, or when vol_roc is RISING into entry?" Sometimes the direction of change matters more than the absolute level.

#### 4. Post-Trade Divergence Bar

For each continuous indicator:

```
At each bar 0-24 after entry:
  Winner avg value at this bar
  Loser avg value at this bar
  Delta = winner_avg - loser_avg

Divergence Bar = first bar where |delta| exceeds threshold consistently for 3+ bars
```

**What this answers**: "How quickly can I tell if the trade is working? At bar 3, does vol_delta already look different for winners vs losers?"

#### 5. Indicator Stability (Categorical Post-Trade)

For structure and SMA config:

```
entry_state = indicator value at bar 0
For each subsequent bar:
  maintained = 1 if state == entry_state, else 0

Stability rate at bar 5 = % of trades where state held through bar 5
Stability rate at bar 10, 15, 24
```

**What this answers**: "When I enter with M5 BULL, how often does it STAY BULL through the first 5 bars?"

---

### Cross-Indicator Reading: The Ideal Setup

The Composite Setup tab (Tab 5) will test combinations, but here is the conceptual framework for how indicators work together:

**For a LONG continuation (EPCH1/3) - the ideal ramp-up tells a story**:

```
Minutes -25 to -15:  Quiet. Normal ranges, normal volume. SMA BULL but narrow spread.
                     Structure: H1 NEUTRAL (your edge), M15 BULL, M5 could be anything.

Minutes -15 to -10:  Candle ranges start expanding (0.12% → 0.15%+).
                     Vol ROC moves from normal to elevated (30%+).
                     Vol Delta turns positive. Buyers showing up.

Minutes -10 to -5:   Full expansion. Ranges > 0.15%, Vol ROC > 30%.
                     SMA spread WIDENING. CVD slope turning positive.
                     M5 structure shifts to BULL (if it wasn't already).

Minutes -5 to -1:    Sustained. The indicators that turned green are STAYING green.
                     Vol delta consistently positive. Range sustained.
                     SMA BULL with spread >= 0.15%.

Entry bar:           Price traverses or rejects the zone.
                     All 7 indicators are aligned.
```

**For a SHORT rejection (EPCH2/4) - the paradox setup**:

```
Minutes -25 to -15:  Buyers have been in control. Vol Delta positive, SMA BULL.
                     This looks like a strong uptrend on the surface.

Minutes -15 to -10:  Volume surges (Vol ROC 50%+). Buyers pushing hard into the zone.
                     Candle ranges large. CVD slope strongly positive.

Minutes -10 to -5:   First signs of exhaustion. Vol Delta starts weakening.
                     Candle ranges may still be large but wicks appearing.
                     CVD slope flattening (buyers losing momentum).

Minutes -5 to -1:    The rejection. Vol Delta weakens or flips. Range still active.
                     M5 structure may flip from BULL to NEUTRAL.
                     SMA spread starts NARROWING (trend losing steam).

Entry bar:           Price rejects OFF the zone. Wick enters zone, close outside.
                     The paradox: The preceding bullish indicators = exhausted buyers = your SHORT edge.
```

The viewer's setup analysis will quantify these narrative patterns into measurable conditions and win rates.

---

## Questions to Resolve Before Implementation

1. **Composite Setup tab calculations**: What specific indicator combinations should we test first? Should we start with pairs only, or jump to triples?

2. **Deep Dive tab - three-phase chart**: Should this show individual trade progression (select a single trade) or always aggregate (average across filtered trades)?

3. **Structure indicators in ramp-up**: H1 structure typically doesn't change within a 25-minute window. Should we still include it in the ramp-up heatmap, or only show it once in a header panel?

4. **ML export format**: What format does `10_machine_learning` expect? Flat CSV with one row per trade? Or the three-phase structure preserved?

5. **Score thresholds for composite setup**: Should the "ideal setup" be auto-calculated from data, or manually defined based on your trading experience?

---

## Success Criteria

- [ ] Three new Supabase tables created and indexed
- [ ] All historical trades backfilled (all trades in trades_2 that have m1_indicator_bars_2 data)
- [ ] PyQt6 viewer launches and displays data in < 3 seconds
- [ ] Winner vs Loser patterns are visually distinguishable in ramp-up charts
- [ ] At least 3 indicator conditions identified with > 5pp win rate lift
- [ ] Data structure documented and ready for 10_machine_learning consumption
- [ ] Old edge testing code archived (not deleted)
