-- ============================================================================
-- EPOCH TRADING SYSTEM - Backtest Module Schema
-- v4.5 - Entry Detection + M1 Bars + M1 Indicators + M1/M5 ATR Stop
--         + Trades Consolidated + Indicator Analysis Tables
-- XIII Trading LLC
-- ============================================================================

-- ============================================================================
-- TABLE 1: trades_2
-- Entry detection results from EPCH1-4 models on S15 bars
-- ============================================================================

CREATE TABLE IF NOT EXISTS trades_2 (
    trade_id    VARCHAR PRIMARY KEY,
    date        DATE NOT NULL,
    ticker      VARCHAR NOT NULL,
    model       VARCHAR NOT NULL,       -- EPCH1, EPCH2, EPCH3, EPCH4
    zone_type   VARCHAR NOT NULL,       -- PRIMARY, SECONDARY
    direction   VARCHAR NOT NULL,       -- LONG, SHORT
    zone_high   NUMERIC,
    zone_low    NUMERIC,
    entry_price NUMERIC,
    entry_time  TIME,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_2_date ON trades_2 (date);
CREATE INDEX IF NOT EXISTS idx_trades_2_ticker ON trades_2 (ticker);
CREATE INDEX IF NOT EXISTS idx_trades_2_model ON trades_2 (model);

-- ============================================================================
-- TABLE 2: m1_bars_2
-- 1-minute bar data from Polygon API
-- Prior day 16:00 ET through trade day 16:00 ET
-- ============================================================================

CREATE TABLE IF NOT EXISTS m1_bars_2 (
    id              BIGSERIAL PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL,
    bar_date        DATE NOT NULL,              -- Trade date (all bars grouped here)
    bar_time        TIME NOT NULL,              -- Bar start time (ET)
    bar_timestamp   TIMESTAMPTZ NOT NULL,       -- Full timestamp with timezone
    open            NUMERIC(12, 4) NOT NULL,
    high            NUMERIC(12, 4) NOT NULL,
    low             NUMERIC(12, 4) NOT NULL,
    close           NUMERIC(12, 4) NOT NULL,
    volume          BIGINT NOT NULL,
    vwap            NUMERIC(12, 4),
    transactions    INTEGER,
    fetched_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT m1_bars_2_unique_bar UNIQUE (ticker, bar_timestamp)
);

CREATE INDEX IF NOT EXISTS idx_m1_bars_2_ticker_date ON m1_bars_2 (ticker, bar_date);
CREATE INDEX IF NOT EXISTS idx_m1_bars_2_ticker_date_time ON m1_bars_2 (ticker, bar_date, bar_time);
CREATE INDEX IF NOT EXISTS idx_m1_bars_2_date ON m1_bars_2 (bar_date);
CREATE INDEX IF NOT EXISTS idx_m1_bars_2_ticker ON m1_bars_2 (ticker);

-- ============================================================================
-- TABLE 3: m1_indicator_bars_2
-- Pre-computed 1-minute indicator bars
-- Reads from m1_bars_2, computes 22 indicators + composite scores
-- Data range: Prior day 16:00 ET -> Trade day 16:00 ET (matches m1_bars_2)
-- Pipeline: trades_2 -> m1_bars_2 -> m1_indicator_bars_2
-- ============================================================================

CREATE TABLE IF NOT EXISTS m1_indicator_bars_2 (
    ticker VARCHAR(10) NOT NULL,
    bar_date DATE NOT NULL,
    bar_time TIME WITHOUT TIME ZONE NOT NULL,

    -- OHLCV (from m1_bars_2)
    open NUMERIC(12, 4) NOT NULL,
    high NUMERIC(12, 4) NOT NULL,
    low NUMERIC(12, 4) NOT NULL,
    close NUMERIC(12, 4) NOT NULL,
    volume BIGINT NOT NULL,

    -- Entry Qualifier Standard Indicators
    candle_range_pct NUMERIC(10, 6),       -- (high-low)/close * 100
    vol_delta_raw NUMERIC(12, 2),          -- Single bar delta: ((2*(close-low)/(high-low))-1)*volume
    vol_delta_roll NUMERIC(12, 2),         -- 5-bar rolling sum of raw delta
    vol_roc NUMERIC(10, 4),               -- ((vol-avg20)/avg20)*100
    sma9 NUMERIC(12, 4),                  -- 9-period SMA
    sma21 NUMERIC(12, 4),                 -- 21-period SMA
    sma_config VARCHAR(10),               -- BULL, BEAR, FLAT
    sma_spread_pct NUMERIC(10, 6),        -- abs(sma9-sma21)/close*100
    price_position VARCHAR(10),           -- ABOVE, BTWN, BELOW

    -- Extended Indicators
    vwap NUMERIC(12, 4),                  -- Cumulative session VWAP
    sma_spread NUMERIC(12, 4),            -- sma9 - sma21 (signed)
    sma_momentum_ratio NUMERIC(10, 6),    -- Current abs spread / abs spread 10 bars ago
    sma_momentum_label VARCHAR(15),       -- WIDENING, NARROWING, STABLE
    cvd_slope NUMERIC(10, 6),             -- Normalized CVD slope (15-bar window)

    -- Multi-timeframe Structure (fractal BOS/ChoCH method)
    h4_structure VARCHAR(10),             -- BULL, BEAR, NEUTRAL
    h1_structure VARCHAR(10),
    m15_structure VARCHAR(10),
    m5_structure VARCHAR(10),
    m1_structure VARCHAR(10),

    -- Composite Scores
    health_score INTEGER,                 -- 0-10 direction-agnostic quality score
    long_score INTEGER,                   -- 0-7 long composite score
    short_score INTEGER,                  -- 0-7 short composite score

    -- Metadata
    bars_in_calculation INTEGER,
    calculated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT m1_indicator_bars_2_pkey PRIMARY KEY (ticker, bar_date, bar_time)
);

CREATE INDEX IF NOT EXISTS idx_m1_indicator_bars_2_ticker_date
    ON m1_indicator_bars_2 (ticker, bar_date);

CREATE INDEX IF NOT EXISTS idx_m1_indicator_bars_2_date
    ON m1_indicator_bars_2 (bar_date);

CREATE INDEX IF NOT EXISTS idx_m1_indicator_bars_2_structure
    ON m1_indicator_bars_2 (ticker, bar_date, m1_structure, m5_structure);

CREATE INDEX IF NOT EXISTS idx_m1_indicator_bars_2_sma_config
    ON m1_indicator_bars_2 (ticker, bar_date, sma_config, price_position);

-- ============================================================================
-- TABLE 4: m1_atr_stop_2
-- M1 ATR Stop Analysis - R-Multiple Target Evaluation
-- Evaluates each trade using M1 ATR(14) as stop/risk unit (1R).
-- Tracks R1-R5 target hits, stop trigger, and win/loss outcome.
-- Pipeline: trades_2 + m1_bars_2 + m1_indicator_bars_2 → m1_atr_stop_2
-- ============================================================================

CREATE TABLE IF NOT EXISTS m1_atr_stop_2 (
    -- PRIMARY KEY
    trade_id VARCHAR(50) NOT NULL,
    PRIMARY KEY (trade_id),

    -- TRADE IDENTIFICATION (denormalized from trades_2 for query convenience)
    date DATE NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    direction VARCHAR(10) NOT NULL,      -- LONG, SHORT
    model VARCHAR(10),                   -- EPCH1, EPCH2, EPCH3, EPCH4
    zone_type VARCHAR(10),               -- PRIMARY, SECONDARY

    -- ENTRY REFERENCE
    entry_time TIME NOT NULL,            -- Original entry time from trades_2
    entry_price DECIMAL(12, 4) NOT NULL,
    m1_entry_candle_adj TIME,            -- Entry time truncated to M1 candle (e.g., 09:31:15 → 09:31:00)

    -- M1 ATR STOP CALCULATION
    m1_atr_value DECIMAL(12, 6),         -- Raw M1 ATR(14) value at entry candle
    stop_price DECIMAL(12, 4),           -- entry -/+ m1_atr depending on direction
    stop_distance DECIMAL(12, 6),        -- abs(entry - stop) = 1R distance = m1_atr_value
    stop_distance_pct DECIMAL(8, 4),     -- (stop_distance / entry_price) * 100

    -- R-LEVEL TARGET PRICES
    r1_price DECIMAL(12, 4),  -- entry +/- 1R
    r2_price DECIMAL(12, 4),  -- entry +/- 2R
    r3_price DECIMAL(12, 4),  -- entry +/- 3R
    r4_price DECIMAL(12, 4),  -- entry +/- 4R
    r5_price DECIMAL(12, 4),  -- entry +/- 5R

    -- R-LEVEL HIT TRACKING (each level tracked independently)
    r1_hit BOOLEAN DEFAULT FALSE,
    r1_time TIME,
    r1_bars_from_entry INTEGER,

    r2_hit BOOLEAN DEFAULT FALSE,
    r2_time TIME,
    r2_bars_from_entry INTEGER,

    r3_hit BOOLEAN DEFAULT FALSE,
    r3_time TIME,
    r3_bars_from_entry INTEGER,

    r4_hit BOOLEAN DEFAULT FALSE,
    r4_time TIME,
    r4_bars_from_entry INTEGER,

    r5_hit BOOLEAN DEFAULT FALSE,
    r5_time TIME,
    r5_bars_from_entry INTEGER,

    -- STOP HIT TRACKING
    stop_hit BOOLEAN DEFAULT FALSE,
    stop_time TIME,                       -- Time stop was first triggered
    stop_bars_from_entry INTEGER,

    -- OUTCOME
    max_r INTEGER DEFAULT -1,             -- -1=LOSS, 1-5=highest R-level reached before stop
    result VARCHAR(10) NOT NULL,          -- WIN, LOSS

    -- SYSTEM METADATA
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- CONSTRAINTS
    FOREIGN KEY (trade_id) REFERENCES trades_2(trade_id) ON DELETE CASCADE,
    CONSTRAINT valid_result CHECK (result IN ('WIN', 'LOSS')),
    CONSTRAINT valid_max_r CHECK (max_r >= -1 AND max_r <= 5)
);

-- Primary lookups
CREATE INDEX IF NOT EXISTS idx_m1as2_trade_id ON m1_atr_stop_2(trade_id);
CREATE INDEX IF NOT EXISTS idx_m1as2_date ON m1_atr_stop_2(date DESC);
CREATE INDEX IF NOT EXISTS idx_m1as2_ticker ON m1_atr_stop_2(ticker);
CREATE INDEX IF NOT EXISTS idx_m1as2_model ON m1_atr_stop_2(model);
CREATE INDEX IF NOT EXISTS idx_m1as2_direction ON m1_atr_stop_2(direction);
CREATE INDEX IF NOT EXISTS idx_m1as2_result ON m1_atr_stop_2(result);

-- Composite indexes for analysis
CREATE INDEX IF NOT EXISTS idx_m1as2_model_result ON m1_atr_stop_2(model, result);
CREATE INDEX IF NOT EXISTS idx_m1as2_direction_result ON m1_atr_stop_2(direction, result);
CREATE INDEX IF NOT EXISTS idx_m1as2_model_direction ON m1_atr_stop_2(model, direction);
CREATE INDEX IF NOT EXISTS idx_m1as2_date_result ON m1_atr_stop_2(date, result);
CREATE INDEX IF NOT EXISTS idx_m1as2_max_r ON m1_atr_stop_2(max_r);

-- R-level hit analysis
CREATE INDEX IF NOT EXISTS idx_m1as2_r1_hit ON m1_atr_stop_2(r1_hit);
CREATE INDEX IF NOT EXISTS idx_m1as2_r2_hit ON m1_atr_stop_2(r2_hit);
CREATE INDEX IF NOT EXISTS idx_m1as2_r3_hit ON m1_atr_stop_2(r3_hit);

-- ============================================================================
-- ANALYSIS VIEWS: m1_atr_stop_2
-- ============================================================================

-- Overall summary
CREATE OR REPLACE VIEW v_m1_atr_stop_2_summary AS
SELECT
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE result = 'WIN') as wins,
    COUNT(*) FILTER (WHERE result = 'LOSS') as losses,
    ROUND(100.0 * COUNT(*) FILTER (WHERE result = 'WIN') / NULLIF(COUNT(*), 0), 2) as win_rate_pct,
    ROUND(AVG(stop_distance_pct), 2) as avg_stop_pct,
    ROUND(AVG(max_r), 2) as avg_max_r,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r1_hit) / NULLIF(COUNT(*), 0), 2) as r1_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r2_hit) / NULLIF(COUNT(*), 0), 2) as r2_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r3_hit) / NULLIF(COUNT(*), 0), 2) as r3_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r4_hit) / NULLIF(COUNT(*), 0), 2) as r4_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r5_hit) / NULLIF(COUNT(*), 0), 2) as r5_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE stop_hit) / NULLIF(COUNT(*), 0), 2) as stop_hit_pct,
    ROUND(AVG(max_r)::decimal, 3) as expectancy_r
FROM m1_atr_stop_2
WHERE stop_price IS NOT NULL;

-- Summary by model
CREATE OR REPLACE VIEW v_m1_atr_stop_2_by_model AS
SELECT
    model,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE result = 'WIN') as wins,
    COUNT(*) FILTER (WHERE result = 'LOSS') as losses,
    ROUND(100.0 * COUNT(*) FILTER (WHERE result = 'WIN') / NULLIF(COUNT(*), 0), 2) as win_rate_pct,
    ROUND(AVG(max_r), 2) as avg_max_r,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r1_hit) / NULLIF(COUNT(*), 0), 2) as r1_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r2_hit) / NULLIF(COUNT(*), 0), 2) as r2_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r3_hit) / NULLIF(COUNT(*), 0), 2) as r3_hit_pct,
    ROUND(AVG(max_r)::decimal, 3) as expectancy_r
FROM m1_atr_stop_2
WHERE stop_price IS NOT NULL
GROUP BY model
ORDER BY model;

-- Summary by direction
CREATE OR REPLACE VIEW v_m1_atr_stop_2_by_direction AS
SELECT
    direction,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE result = 'WIN') as wins,
    COUNT(*) FILTER (WHERE result = 'LOSS') as losses,
    ROUND(100.0 * COUNT(*) FILTER (WHERE result = 'WIN') / NULLIF(COUNT(*), 0), 2) as win_rate_pct,
    ROUND(AVG(max_r), 2) as avg_max_r,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r1_hit) / NULLIF(COUNT(*), 0), 2) as r1_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r2_hit) / NULLIF(COUNT(*), 0), 2) as r2_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r3_hit) / NULLIF(COUNT(*), 0), 2) as r3_hit_pct,
    ROUND(AVG(max_r)::decimal, 3) as expectancy_r
FROM m1_atr_stop_2
WHERE stop_price IS NOT NULL
GROUP BY direction
ORDER BY direction;

-- R-level distribution
CREATE OR REPLACE VIEW v_m1_atr_stop_2_r_distribution AS
SELECT
    max_r,
    COUNT(*) as trade_count,
    ROUND(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0), 2) as pct_of_total,
    COUNT(*) FILTER (WHERE result = 'WIN') as wins,
    COUNT(*) FILTER (WHERE result = 'LOSS') as losses
FROM m1_atr_stop_2
WHERE stop_price IS NOT NULL
GROUP BY max_r
ORDER BY max_r;

-- ============================================================================
-- TABLE 5: m5_atr_stop_2
-- M5 ATR Stop Analysis - R-Multiple Target Evaluation
-- Evaluates each trade using M5 ATR(14) as stop/risk unit (1R).
-- Wider stop than M1 ATR — useful for cross-timeframe comparison.
-- Simulation walks M1 bars from m1_bars_2 for detection fidelity.
-- Pipeline: trades_2 + m1_bars_2 + m1_indicator_bars_2 → m5_atr_stop_2
-- ============================================================================

CREATE TABLE IF NOT EXISTS m5_atr_stop_2 (
    -- PRIMARY KEY
    trade_id VARCHAR(50) NOT NULL,
    PRIMARY KEY (trade_id),

    -- TRADE IDENTIFICATION (denormalized from trades_2 for query convenience)
    date DATE NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    direction VARCHAR(10) NOT NULL,      -- LONG, SHORT
    model VARCHAR(10),                   -- EPCH1, EPCH2, EPCH3, EPCH4
    zone_type VARCHAR(10),               -- PRIMARY, SECONDARY

    -- ENTRY REFERENCE
    entry_time TIME NOT NULL,            -- Original entry time from trades_2
    entry_price DECIMAL(12, 4) NOT NULL,
    m1_entry_candle_adj TIME,            -- Entry time truncated to M1 candle (e.g., 09:31:15 → 09:31:00)

    -- M5 ATR STOP CALCULATION
    m5_atr_value DECIMAL(12, 6),         -- Raw M5 ATR(14) value at entry candle
    stop_price DECIMAL(12, 4),           -- entry -/+ m5_atr depending on direction
    stop_distance DECIMAL(12, 6),        -- abs(entry - stop) = 1R distance = m5_atr_value
    stop_distance_pct DECIMAL(8, 4),     -- (stop_distance / entry_price) * 100

    -- R-LEVEL TARGET PRICES
    r1_price DECIMAL(12, 4),  -- entry +/- 1R
    r2_price DECIMAL(12, 4),  -- entry +/- 2R
    r3_price DECIMAL(12, 4),  -- entry +/- 3R
    r4_price DECIMAL(12, 4),  -- entry +/- 4R
    r5_price DECIMAL(12, 4),  -- entry +/- 5R

    -- R-LEVEL HIT TRACKING (each level tracked independently)
    r1_hit BOOLEAN DEFAULT FALSE,
    r1_time TIME,
    r1_bars_from_entry INTEGER,

    r2_hit BOOLEAN DEFAULT FALSE,
    r2_time TIME,
    r2_bars_from_entry INTEGER,

    r3_hit BOOLEAN DEFAULT FALSE,
    r3_time TIME,
    r3_bars_from_entry INTEGER,

    r4_hit BOOLEAN DEFAULT FALSE,
    r4_time TIME,
    r4_bars_from_entry INTEGER,

    r5_hit BOOLEAN DEFAULT FALSE,
    r5_time TIME,
    r5_bars_from_entry INTEGER,

    -- STOP HIT TRACKING
    stop_hit BOOLEAN DEFAULT FALSE,
    stop_time TIME,                       -- Time stop was first triggered
    stop_bars_from_entry INTEGER,

    -- OUTCOME
    max_r INTEGER DEFAULT -1,             -- -1=LOSS, 1-5=highest R-level reached before stop
    result VARCHAR(10) NOT NULL,          -- WIN, LOSS

    -- SYSTEM METADATA
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- CONSTRAINTS
    FOREIGN KEY (trade_id) REFERENCES trades_2(trade_id) ON DELETE CASCADE,
    CONSTRAINT valid_result CHECK (result IN ('WIN', 'LOSS')),
    CONSTRAINT valid_max_r CHECK (max_r >= -1 AND max_r <= 5)
);

-- Primary lookups
CREATE INDEX IF NOT EXISTS idx_m5as2_trade_id ON m5_atr_stop_2(trade_id);
CREATE INDEX IF NOT EXISTS idx_m5as2_date ON m5_atr_stop_2(date DESC);
CREATE INDEX IF NOT EXISTS idx_m5as2_ticker ON m5_atr_stop_2(ticker);
CREATE INDEX IF NOT EXISTS idx_m5as2_model ON m5_atr_stop_2(model);
CREATE INDEX IF NOT EXISTS idx_m5as2_direction ON m5_atr_stop_2(direction);
CREATE INDEX IF NOT EXISTS idx_m5as2_result ON m5_atr_stop_2(result);

-- Composite indexes for analysis
CREATE INDEX IF NOT EXISTS idx_m5as2_model_result ON m5_atr_stop_2(model, result);
CREATE INDEX IF NOT EXISTS idx_m5as2_direction_result ON m5_atr_stop_2(direction, result);
CREATE INDEX IF NOT EXISTS idx_m5as2_model_direction ON m5_atr_stop_2(model, direction);
CREATE INDEX IF NOT EXISTS idx_m5as2_date_result ON m5_atr_stop_2(date, result);
CREATE INDEX IF NOT EXISTS idx_m5as2_max_r ON m5_atr_stop_2(max_r);

-- R-level hit analysis
CREATE INDEX IF NOT EXISTS idx_m5as2_r1_hit ON m5_atr_stop_2(r1_hit);
CREATE INDEX IF NOT EXISTS idx_m5as2_r2_hit ON m5_atr_stop_2(r2_hit);
CREATE INDEX IF NOT EXISTS idx_m5as2_r3_hit ON m5_atr_stop_2(r3_hit);

-- ============================================================================
-- ANALYSIS VIEWS: m5_atr_stop_2
-- ============================================================================

-- Overall summary
CREATE OR REPLACE VIEW v_m5_atr_stop_2_summary AS
SELECT
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE result = 'WIN') as wins,
    COUNT(*) FILTER (WHERE result = 'LOSS') as losses,
    ROUND(100.0 * COUNT(*) FILTER (WHERE result = 'WIN') / NULLIF(COUNT(*), 0), 2) as win_rate_pct,
    ROUND(AVG(stop_distance_pct), 2) as avg_stop_pct,
    ROUND(AVG(max_r), 2) as avg_max_r,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r1_hit) / NULLIF(COUNT(*), 0), 2) as r1_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r2_hit) / NULLIF(COUNT(*), 0), 2) as r2_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r3_hit) / NULLIF(COUNT(*), 0), 2) as r3_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r4_hit) / NULLIF(COUNT(*), 0), 2) as r4_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r5_hit) / NULLIF(COUNT(*), 0), 2) as r5_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE stop_hit) / NULLIF(COUNT(*), 0), 2) as stop_hit_pct,
    ROUND(AVG(max_r)::decimal, 3) as expectancy_r
FROM m5_atr_stop_2
WHERE stop_price IS NOT NULL;

-- Summary by model
CREATE OR REPLACE VIEW v_m5_atr_stop_2_by_model AS
SELECT
    model,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE result = 'WIN') as wins,
    COUNT(*) FILTER (WHERE result = 'LOSS') as losses,
    ROUND(100.0 * COUNT(*) FILTER (WHERE result = 'WIN') / NULLIF(COUNT(*), 0), 2) as win_rate_pct,
    ROUND(AVG(max_r), 2) as avg_max_r,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r1_hit) / NULLIF(COUNT(*), 0), 2) as r1_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r2_hit) / NULLIF(COUNT(*), 0), 2) as r2_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r3_hit) / NULLIF(COUNT(*), 0), 2) as r3_hit_pct,
    ROUND(AVG(max_r)::decimal, 3) as expectancy_r
FROM m5_atr_stop_2
WHERE stop_price IS NOT NULL
GROUP BY model
ORDER BY model;

-- Summary by direction
CREATE OR REPLACE VIEW v_m5_atr_stop_2_by_direction AS
SELECT
    direction,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE result = 'WIN') as wins,
    COUNT(*) FILTER (WHERE result = 'LOSS') as losses,
    ROUND(100.0 * COUNT(*) FILTER (WHERE result = 'WIN') / NULLIF(COUNT(*), 0), 2) as win_rate_pct,
    ROUND(AVG(max_r), 2) as avg_max_r,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r1_hit) / NULLIF(COUNT(*), 0), 2) as r1_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r2_hit) / NULLIF(COUNT(*), 0), 2) as r2_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r3_hit) / NULLIF(COUNT(*), 0), 2) as r3_hit_pct,
    ROUND(AVG(max_r)::decimal, 3) as expectancy_r
FROM m5_atr_stop_2
WHERE stop_price IS NOT NULL
GROUP BY direction
ORDER BY direction;

-- R-level distribution
CREATE OR REPLACE VIEW v_m5_atr_stop_2_r_distribution AS
SELECT
    max_r,
    COUNT(*) as trade_count,
    ROUND(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0), 2) as pct_of_total,
    COUNT(*) FILTER (WHERE result = 'WIN') as wins,
    COUNT(*) FILTER (WHERE result = 'LOSS') as losses
FROM m5_atr_stop_2
WHERE stop_price IS NOT NULL
GROUP BY max_r
ORDER BY max_r;

-- ============================================================================
-- TABLE 6: trades_m5_r_win_2
-- Consolidated Trade Outcomes (Denormalized)
-- Joins trades_2 + m5_atr_stop_2 + m1_bars_2 into a single flat table
-- with derived fields for 11_trade_reel highlight viewer.
-- Pipeline: trades_2 + m5_atr_stop_2 + m1_bars_2 → trades_m5_r_win_2
-- ============================================================================

CREATE TABLE IF NOT EXISTS trades_m5_r_win_2 (
    -- Trade identification (from trades_2)
    trade_id                VARCHAR(50) PRIMARY KEY,
    date                    DATE NOT NULL,
    ticker                  VARCHAR(10) NOT NULL,
    direction               VARCHAR(10) NOT NULL,          -- LONG, SHORT
    model                   VARCHAR(10),                    -- EPCH1, EPCH2, EPCH3, EPCH4
    zone_type               VARCHAR(10),                    -- PRIMARY, SECONDARY

    -- Zone boundaries (from trades_2)
    zone_high               DECIMAL(12, 4),
    zone_low                DECIMAL(12, 4),

    -- Entry (from trades_2 / m5_atr_stop_2)
    entry_price             DECIMAL(12, 4) NOT NULL,
    entry_time              TIME NOT NULL,

    -- M5 ATR stop calculation (from m5_atr_stop_2)
    m5_atr_value            DECIMAL(12, 6),                 -- M5 ATR(14) at entry
    stop_price              DECIMAL(12, 4),                 -- Entry -/+ M5 ATR
    stop_distance           DECIMAL(12, 6),                 -- abs(entry - stop) = 1R
    stop_distance_pct       DECIMAL(8, 4),                  -- (stop_distance / entry) * 100

    -- R-level target prices (from m5_atr_stop_2)
    r1_price                DECIMAL(12, 4),
    r2_price                DECIMAL(12, 4),
    r3_price                DECIMAL(12, 4),
    r4_price                DECIMAL(12, 4),
    r5_price                DECIMAL(12, 4),

    -- R-level hit tracking (from m5_atr_stop_2)
    r1_hit                  BOOLEAN DEFAULT FALSE,
    r1_time                 TIME,
    r1_bars_from_entry      INTEGER,

    r2_hit                  BOOLEAN DEFAULT FALSE,
    r2_time                 TIME,
    r2_bars_from_entry      INTEGER,

    r3_hit                  BOOLEAN DEFAULT FALSE,
    r3_time                 TIME,
    r3_bars_from_entry      INTEGER,

    r4_hit                  BOOLEAN DEFAULT FALSE,
    r4_time                 TIME,
    r4_bars_from_entry      INTEGER,

    r5_hit                  BOOLEAN DEFAULT FALSE,
    r5_time                 TIME,
    r5_bars_from_entry      INTEGER,

    -- Stop hit tracking (from m5_atr_stop_2, renamed)
    stop_hit                BOOLEAN DEFAULT FALSE,
    stop_hit_time           TIME,                           -- renamed from stop_time
    stop_hit_bars_from_entry INTEGER,                       -- renamed from stop_bars_from_entry

    -- Outcome (renamed/derived from m5_atr_stop_2)
    max_r_achieved          INTEGER DEFAULT -1,             -- renamed from max_r (-1=LOSS, 1-5=WIN)
    outcome                 VARCHAR(10) NOT NULL,           -- renamed from result (WIN/LOSS)
    exit_reason             VARCHAR(20) NOT NULL,           -- derived: STOP_HIT, R5_HIT, EOD
    is_winner               BOOLEAN NOT NULL,               -- derived: outcome = 'WIN'
    pnl_r                   DECIMAL(8, 2),                  -- derived: same as max_r_achieved
    outcome_method          VARCHAR(20) NOT NULL DEFAULT 'M5_ATR',  -- constant: M5_ATR

    -- EOD price (from m1_bars_2 last bar)
    eod_price               DECIMAL(12, 4),

    -- Convenience flags (derived)
    reached_2r              BOOLEAN DEFAULT FALSE,          -- derived: r2_hit
    reached_3r              BOOLEAN DEFAULT FALSE,          -- derived: r3_hit
    minutes_to_r1           INTEGER,                        -- derived: r1_time - entry_time

    -- Timestamps
    calculated_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- Primary lookups
CREATE INDEX IF NOT EXISTS idx_tmrw2_date ON trades_m5_r_win_2 (date);
CREATE INDEX IF NOT EXISTS idx_tmrw2_ticker ON trades_m5_r_win_2 (ticker);
CREATE INDEX IF NOT EXISTS idx_tmrw2_outcome ON trades_m5_r_win_2 (outcome);
CREATE INDEX IF NOT EXISTS idx_tmrw2_max_r ON trades_m5_r_win_2 (max_r_achieved);
CREATE INDEX IF NOT EXISTS idx_tmrw2_date_outcome ON trades_m5_r_win_2 (date, outcome);
CREATE INDEX IF NOT EXISTS idx_tmrw2_model ON trades_m5_r_win_2 (model);
CREATE INDEX IF NOT EXISTS idx_tmrw2_direction ON trades_m5_r_win_2 (direction);
CREATE INDEX IF NOT EXISTS idx_tmrw2_winner_r ON trades_m5_r_win_2 (outcome, max_r_achieved DESC);

-- Composite index for trade_reel highlight query pattern:
-- WHERE outcome = 'WIN' AND max_r_achieved >= N ORDER BY max_r_achieved DESC, date DESC
CREATE INDEX IF NOT EXISTS idx_tmrw2_highlights
    ON trades_m5_r_win_2 (outcome, max_r_achieved DESC, date DESC)
    WHERE outcome = 'WIN';

-- ============================================================================
-- ANALYSIS VIEWS: trades_m5_r_win_2
-- ============================================================================

-- Summary by model
CREATE OR REPLACE VIEW v_trades_m5_r_win_2_by_model AS
SELECT
    model,
    COUNT(*) as total_trades,
    SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
    ROUND(100.0 * SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as win_rate,
    ROUND(AVG(max_r_achieved)::decimal, 3) as expectancy_r,
    ROUND(AVG(CASE WHEN outcome = 'WIN' THEN max_r_achieved END)::decimal, 2) as avg_win_r,
    ROUND(AVG(minutes_to_r1)::decimal, 1) as avg_minutes_to_r1
FROM trades_m5_r_win_2
GROUP BY model
ORDER BY model;

-- Summary by direction
CREATE OR REPLACE VIEW v_trades_m5_r_win_2_by_direction AS
SELECT
    direction,
    COUNT(*) as total_trades,
    SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
    ROUND(100.0 * SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as win_rate,
    ROUND(AVG(max_r_achieved)::decimal, 3) as expectancy_r
FROM trades_m5_r_win_2
GROUP BY direction
ORDER BY direction;

-- Daily summary
CREATE OR REPLACE VIEW v_trades_m5_r_win_2_daily AS
SELECT
    date,
    COUNT(*) as total_trades,
    SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
    ROUND(100.0 * SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as win_rate,
    ROUND(AVG(max_r_achieved)::decimal, 3) as expectancy_r,
    MAX(max_r_achieved) as best_r,
    SUM(CASE WHEN reached_3r THEN 1 ELSE 0 END) as highlights_3r_plus
FROM trades_m5_r_win_2
GROUP BY date
ORDER BY date DESC;

-- Highlights view (for trade_reel quick query)
CREATE OR REPLACE VIEW v_trades_m5_r_win_2_highlights AS
SELECT *
FROM trades_m5_r_win_2
WHERE outcome = 'WIN' AND max_r_achieved >= 3
ORDER BY max_r_achieved DESC, date DESC;

-- ============================================================================
-- TABLE 7: m1_trade_indicator_2
-- Single M1 bar snapshot at entry (last completed bar before entry candle)
-- Denormalized with trade context + outcome for fast indicator analysis
-- Pipeline: trades_2 + m5_atr_stop_2 + m1_indicator_bars_2 → m1_trade_indicator_2
-- ============================================================================

CREATE TABLE IF NOT EXISTS m1_trade_indicator_2 (
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

    -- Trade Outcome (from m5_atr_stop_2)
    is_winner           BOOLEAN NOT NULL,
    pnl_r               NUMERIC(8, 2),
    max_r_achieved      INTEGER,

    -- Bar Identification (M1 bar that closed just before entry candle)
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

    -- Metadata
    calculated_at       TIMESTAMPTZ DEFAULT NOW(),

    FOREIGN KEY (trade_id) REFERENCES trades_2(trade_id) ON DELETE CASCADE
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_trade_ind_ticker_date ON m1_trade_indicator_2 (ticker, date);
CREATE INDEX IF NOT EXISTS idx_trade_ind_direction ON m1_trade_indicator_2 (direction);
CREATE INDEX IF NOT EXISTS idx_trade_ind_model ON m1_trade_indicator_2 (model);
CREATE INDEX IF NOT EXISTS idx_trade_ind_winner ON m1_trade_indicator_2 (is_winner);
CREATE INDEX IF NOT EXISTS idx_trade_ind_date ON m1_trade_indicator_2 (date);

-- ============================================================================
-- TABLE 8: m1_ramp_up_indicator_2
-- 25 M1 bars before entry (bar_sequence 0=oldest, 24=just before entry candle)
-- Pipeline: trades_2 + m5_atr_stop_2 + m1_indicator_bars_2 → m1_ramp_up_indicator_2
-- ============================================================================

CREATE TABLE IF NOT EXISTS m1_ramp_up_indicator_2 (
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

    PRIMARY KEY (trade_id, bar_sequence),
    FOREIGN KEY (trade_id) REFERENCES trades_2(trade_id) ON DELETE CASCADE
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_ramp_up_trade ON m1_ramp_up_indicator_2 (trade_id);
CREATE INDEX IF NOT EXISTS idx_ramp_up_ticker_date ON m1_ramp_up_indicator_2 (ticker, bar_date);

-- ============================================================================
-- TABLE 9: m1_post_trade_indicator_2
-- 25 M1 bars after entry (bar_sequence 0=entry candle, 24=25th bar after)
-- Trade outcome stamped on every row for easy aggregation
-- Pipeline: trades_2 + m5_atr_stop_2 + m1_indicator_bars_2 → m1_post_trade_indicator_2
-- ============================================================================

CREATE TABLE IF NOT EXISTS m1_post_trade_indicator_2 (
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

    -- Trade Outcome Context (from m5_atr_stop_2, stamped on every row)
    is_winner           BOOLEAN,
    pnl_r               NUMERIC(8, 2),
    max_r_achieved      INTEGER,

    -- Metadata
    calculated_at       TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (trade_id, bar_sequence),
    FOREIGN KEY (trade_id) REFERENCES trades_2(trade_id) ON DELETE CASCADE
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_post_trade_trade ON m1_post_trade_indicator_2 (trade_id);
CREATE INDEX IF NOT EXISTS idx_post_trade_ticker_date ON m1_post_trade_indicator_2 (ticker, bar_date);
CREATE INDEX IF NOT EXISTS idx_post_trade_winner ON m1_post_trade_indicator_2 (is_winner);
