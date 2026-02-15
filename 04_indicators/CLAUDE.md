# 04_indicators - Indicator Analysis v2.0

## Module Overview

PyQt6-based three-phase indicator analysis tool that examines how 7 trading indicators behave before, at, and after trade entry. Uses pre-computed M1 indicator bar data joined with trade outcomes to identify actionable patterns. Built for future consumption by `10_machine_learning`.

## Architecture

```
04_indicators/
├── app.py                          # PyQt6 entry point
├── config.py                       # DB config, table names, indicator registry
├── CLAUDE.md                       # AI context (this file)
├── data/
│   ├── __init__.py
│   └── provider.py                 # DataProvider - all SQL queries via psycopg2
├── ui/
│   ├── __init__.py
│   ├── styles.py                   # Re-exports from 00_shared/ui/styles.py
│   ├── main_window.py              # MainWindow with filter panel + 5 tabs
│   └── tabs/
│       ├── __init__.py
│       ├── ramp_up_tab.py          # Tab 1: Pre-entry indicator behavior (25 bars)
│       ├── entry_snapshot_tab.py   # Tab 2: Entry-bar indicator state
│       ├── post_trade_tab.py       # Tab 3: Post-entry indicator evolution (25 bars)
│       ├── indicator_deep_dive_tab.py  # Tab 4: Single-indicator deep analysis
│       └── composite_setup_tab.py  # Tab 5: Multi-indicator setup scoring
├── docs/
│   └── implementation_plan.md      # Full design document (1200+ lines)
└── _archive/                       # V1 edge testing code (preserved)
```

## Entry Point

```bash
python 04_indicators/app.py
```

## Three-Phase Analysis Model

The module examines indicators across three time phases relative to trade entry:

```
Phase 1: RAMP-UP          Phase 2: ENTRY       Phase 3: POST-TRADE
(25 bars before entry)     (1 bar snapshot)     (25 bars after entry)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
bar_seq 0 ────── 24    │   prior M1 bar    │   bar_seq 0 ────── 24
                        │                    │   (0 = entry candle)
```

**Look-ahead bias protection**: Entry candle is NOT included in ramp-up data. The "entry snapshot" uses the M1 bar that COMPLETED before entry (floor to minute - 1 minute).

## Data Sources (Supabase Tables)

### Input Tables (populated by 03_backtest processors)

| Table | Rows Per Trade | Purpose | Primary Key |
|-------|---------------|---------|-------------|
| `m1_trade_indicator_2` | 1 | Entry snapshot with trade context + outcome | (trade_id) |
| `m1_ramp_up_indicator_2` | 25 | Pre-entry indicator evolution | (trade_id, bar_sequence) |
| `m1_post_trade_indicator_2` | 25 | Post-entry indicator evolution | (trade_id, bar_sequence) |

### Source Tables (upstream)

| Table | Purpose |
|-------|---------|
| `trades_2` | Trade records (entry time, model, direction, zone type) |
| `m5_atr_stop_2` | Trade outcomes (result='WIN'/'LOSS', max_r, pnl_r) |
| `m1_indicator_bars_2` | M1 bar snapshots with 35 indicator columns |

### Outcome Handling

**Critical**: All three processors use INNER JOIN with `m5_atr_stop_2`. Trades without outcomes are **never inserted** - they are skipped entirely. The viewer shows an amber warning when trades exist in `trades_2` but are missing from `m1_trade_indicator_2`.

## Indicators Analyzed

### Continuous (5)
| Column | Label | Key Thresholds |
|--------|-------|---------------|
| `candle_range_pct` | Candle Range % | <0.12% = ABSORPTION (skip), >=0.15% = NORMAL |
| `vol_delta_roll` | Volume Delta (5-bar) | Sign alignment with direction |
| `vol_roc` | Volume ROC | >=30% = ELEVATED activity |
| `sma_spread_pct` | SMA Spread % | >=0.15% = WIDE (trending) |
| `cvd_slope` | CVD Slope | >0.1 bullish, <-0.1 bearish |

### Categorical (6)
| Column | Label | States |
|--------|-------|--------|
| `sma_config` | SMA Configuration | BULL, BEAR, CROSS_UP, CROSS_DOWN |
| `sma_momentum_label` | SMA Momentum | EXPANDING, NARROWING, FLAT |
| `price_position` | Price Position | ABOVE_BOTH, BETWEEN, BELOW_BOTH |
| `m5_structure` | M5 Structure | BULL, BEAR, NEUTRAL |
| `m15_structure` | M15 Structure | BULL, BEAR, NEUTRAL |
| `h1_structure` | H1 Structure | BULL, BEAR, NEUTRAL |

## Tab Specifications

### Tab 1: Ramp-Up Analysis
- **Purpose**: How do indicators behave in the 25 minutes leading up to entry?
- **Charts**: 5 multi-panel line charts (winners vs losers for each continuous indicator)
- **Features**: Shaded "ramp-up zone" (last 10 bars), summary statistics for bars 15-24
- **Key insight**: Do winning trades show different indicator patterns before entry?

### Tab 2: Entry Snapshot
- **Purpose**: What does the indicator state look like at the moment of entry?
- **Charts**: Summary cards (Total Trades, Win Rate, Avg R) + categorical win rate bars (2x3) + continuous quintile win rate bars (2x3)
- **Features**: 50% reference line on all charts, green/red coloring by win rate
- **Key insight**: Which indicator states at entry predict winners?

### Tab 3: Post-Trade Analysis
- **Purpose**: How do indicators evolve in the 25 minutes after entry?
- **Charts**: 5 multi-panel line charts (winners vs losers), entry marker at bar 0
- **Features**: Early divergence analysis (first 5 bars comparison)
- **Key insight**: Can early indicator behavior predict trade outcome?

### Tab 4: Indicator Deep Dive
- **Purpose**: Deep analysis of a single selected indicator across all three phases
- **Charts**: Three-phase progression chart (bars -24 to +24), win rate by quintile/state, model x direction breakdown table
- **Features**: Dropdown selector for all 11 indicators
- **Key insight**: Full lifecycle view of any single indicator

### Tab 5: Composite Setup Analysis
- **Purpose**: How do indicators work together to create ideal setups?
- **Charts**: Setup score (0-7) distribution with win rate overlay (dual y-axis)
- **Table**: Top 10 and Bottom 10 indicator combinations by win rate
- **Setup score components** (each +1 point):
  1. candle_range_pct >= 0.15%
  2. vol_roc >= 30%
  3. sma_spread_pct >= 0.15%
  4. SMA config aligned with direction (BULL+LONG or BEAR+SHORT)
  5. M5 structure aligned with direction
  6. H1 structure == NEUTRAL (strongest edge: +36pp)
  7. CVD slope aligned with direction (>0.1 for LONG, <-0.1 for SHORT)

## DataProvider API (data/provider.py)

Key methods:
```python
provider.connect()                          # Open psycopg2 connection
provider.get_tickers() -> List[str]         # Distinct tickers from trades_2
provider.get_date_range() -> Tuple          # Min/max dates
provider.get_pending_count() -> int         # Trades missing from indicator tables
provider.get_entry_data(filters) -> DataFrame   # Filtered m1_trade_indicator_2
provider.get_trade_ids(filters) -> List[str]    # Trade IDs matching filters
provider.get_ramp_up_averages(trade_ids)        # Avg by bar_sequence + outcome
provider.get_post_trade_averages(trade_ids)     # Avg by bar_sequence + outcome
provider.get_win_rate_by_state(trade_ids, col)  # Categorical indicator analysis
provider.get_win_rate_by_quintile(trade_ids, col)   # Continuous NTILE(5) analysis
provider.get_setup_combinations(trade_ids, min_trades)  # Multi-indicator combos
provider.get_three_phase_averages(trade_ids, col)   # UNION ALL ramp+post
```

## UI Architecture

- **Layout**: QSplitter with fixed filter panel (220px) + QTabWidget
- **Data loading**: QThread (DataLoadThread) for non-blocking DB queries
- **Chart rendering**: Plotly -> PNG via kaleido -> QPixmap -> QLabel
- **Filter panel**: Model, Direction, Ticker, Outcome (Winners/Losers/All), Date range
- **Warning system**: Amber label when trades are pending outcome analysis

## Filter Panel Options

| Filter | Type | Values |
|--------|------|--------|
| Model | QComboBox | All, EPCH1, EPCH2, EPCH3, EPCH4 |
| Direction | QComboBox | All, LONG, SHORT |
| Ticker | QComboBox | All, + dynamic from DB |
| Outcome | QComboBox | All, Winners, Losers |
| Date From | QDateEdit | Min date from DB |
| Date To | QDateEdit | Max date from DB |

## Bar Timing Logic

Entry at S15 (15-second bars) maps to M1 bars:
```
Entry time:  09:35:15
Floor to M1: 09:35:00  (entry candle start)
Prior bar:   09:34:00  (last completed M1 bar = entry snapshot)

Ramp-up:     25 bars ending at 09:34:00 (bar_sequence 0-24)
Post-trade:  25 bars starting at 09:35:00 (bar_sequence 0-24, 0 = entry candle)
```

## Key Indicator Findings (from V1 Testing)

### Validated Edges (Strongest First)
| Indicator | Finding | Effect |
|-----------|---------|--------|
| H1 Structure | NEUTRAL beats BULL/BEAR | +36pp win rate |
| Candle Range | <0.12% = absorption zone | 33% WR (universal skip) |
| Volume Delta | MISALIGNED beats ALIGNED | +5-21pp (paradoxical) |
| CVD Slope | Against-slope trades win | Exhaustion captures |
| SMA Spread | Direction matters for SHORT | +25pp |

### Universal Skip Filter
- **Absorption Zone**: candle_range_pct < 0.12% = 33% WR -> skip ALL trades

## Processor Population (03_backtest)

The three indicator tables are populated by secondary processors in `03_backtest`:

```bash
# Create tables
python 03_backtest/processor/secondary_analysis/m1_trade_indicator_2/runner.py --schema
python 03_backtest/processor/secondary_analysis/m1_ramp_up_indicator_2/runner.py --schema
python 03_backtest/processor/secondary_analysis/m1_post_trade_indicator_2/runner.py --schema

# Check status
python 03_backtest/processor/secondary_analysis/m1_trade_indicator_2/runner.py --status

# Populate (via run_backtest.py)
python 03_backtest/scripts/run_backtest.py --m1-trade-ind
python 03_backtest/scripts/run_backtest.py --m1-ramp-up
python 03_backtest/scripts/run_backtest.py --m1-post-trade
```

## Configuration (config.py)

```python
TABLE_TRADES = "trades_2"
TABLE_M5_ATR = "m5_atr_stop_2"
TABLE_RAMP_UP = "m1_ramp_up_indicator_2"
TABLE_TRADE_IND = "m1_trade_indicator_2"
TABLE_POST_TRADE = "m1_post_trade_indicator_2"
TABLE_INDICATORS = "m1_indicator_bars_2"

THRESHOLDS = {
    'candle_range_pct': {'good': 0.15, 'low': 0.12},
    'vol_roc': {'elevated': 30.0, 'normal': 0.0},
    'sma_spread_pct': {'wide': 0.15},
}

RAMP_UP_BARS = 25
POST_TRADE_BARS = 25
```

## Dependencies

- PyQt6 (GUI framework)
- psycopg2 (PostgreSQL via Supabase)
- pandas (data manipulation)
- plotly + kaleido (chart generation -> PNG)
- numpy (numerical operations)

## Development Notes

- Follows `05_system_analysis` hybrid pattern: Plotly charts -> PNG -> QPixmap display
- No new indicator calculations - all values come from `m1_indicator_bars_2`
- DataProvider uses psycopg2 directly (not SQLAlchemy)
- V1 edge testing code preserved in `_archive/` directory
- All processors use ON CONFLICT upsert for idempotent re-runs
- Setup score (0-7) designed for future ML feature engineering
