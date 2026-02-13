-- ============================================================================
-- Epoch Trading System - Table: m1_atr_stop_2
-- M1 ATR Stop Analysis - R-Multiple Target Evaluation
-- XIII Trading LLC
--
-- PURPOSE:
--   Evaluates each trade using M1 ATR (14-period, 1x) as the stop/risk unit.
--   Tracks whether price reached 1R through 5R targets before being stopped out.
--   Uses M1 candle fidelity for target detection (high/low touch) and close-based
--   stop trigger (M1 close beyond stop level).
--
-- WIN/LOSS LOGIC:
--   WIN:  R1 target hit before stop (price high/low touches R1+)
--   LOSS: Stop hit before R1 (M1 close beyond stop level)
--   LOSS: Neither R1 nor stop by 15:30 (no R1 = LOSS always)
--
--   Same-candle conflict: If an M1 candle shows both R-level hit AND close
--   beyond stop, the stop takes priority (LOSS).
--
-- DATA SOURCES (v2 tables):
--   - Trade metadata: trades_2 table
--   - M1 bars: m1_bars_2 table (for bar-by-bar simulation)
--   - M1 ATR: m1_indicator_bars_2 table (pre-computed atr_m1 at entry candle)
--
-- Version: 1.0.0
-- ============================================================================

CREATE TABLE IF NOT EXISTS m1_atr_stop_2 (
    -- =========================================================================
    -- PRIMARY KEY
    -- =========================================================================
    trade_id VARCHAR(50) NOT NULL,

    PRIMARY KEY (trade_id),

    -- =========================================================================
    -- TRADE IDENTIFICATION (denormalized from trades_2 for query convenience)
    -- =========================================================================
    date DATE NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    direction VARCHAR(10) NOT NULL,      -- LONG, SHORT
    model VARCHAR(10),                   -- EPCH1, EPCH2, EPCH3, EPCH4
    zone_type VARCHAR(10),               -- PRIMARY, SECONDARY

    -- =========================================================================
    -- ENTRY REFERENCE
    -- =========================================================================
    entry_time TIME NOT NULL,            -- Original entry time from trades_2
    entry_price DECIMAL(12, 4) NOT NULL,
    m1_entry_candle_adj TIME,            -- Entry time truncated to M1 candle (e.g., 09:31:15 → 09:31:00)

    -- =========================================================================
    -- M1 ATR STOP CALCULATION
    -- =========================================================================
    m1_atr_value DECIMAL(12, 6),         -- Raw M1 ATR(14) value at entry candle
    stop_price DECIMAL(12, 4),           -- entry -/+ m1_atr depending on direction
    stop_distance DECIMAL(12, 6),        -- abs(entry - stop) = 1R distance = m1_atr_value
    stop_distance_pct DECIMAL(8, 4),     -- (stop_distance / entry_price) * 100

    -- =========================================================================
    -- R-LEVEL TARGET PRICES
    -- =========================================================================
    r1_price DECIMAL(12, 4),  -- entry +/- 1R
    r2_price DECIMAL(12, 4),  -- entry +/- 2R
    r3_price DECIMAL(12, 4),  -- entry +/- 3R
    r4_price DECIMAL(12, 4),  -- entry +/- 4R
    r5_price DECIMAL(12, 4),  -- entry +/- 5R

    -- =========================================================================
    -- R-LEVEL HIT TRACKING (each level tracked independently)
    -- =========================================================================
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

    -- =========================================================================
    -- STOP HIT TRACKING
    -- =========================================================================
    stop_hit BOOLEAN DEFAULT FALSE,
    stop_time TIME,                       -- Time stop was first triggered
    stop_bars_from_entry INTEGER,

    -- =========================================================================
    -- OUTCOME
    -- =========================================================================
    max_r INTEGER DEFAULT -1,             -- -1=LOSS, 1-5=highest R-level reached before stop
    result VARCHAR(10) NOT NULL,          -- WIN, LOSS

    -- =========================================================================
    -- SYSTEM METADATA
    -- =========================================================================
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- =========================================================================
    -- CONSTRAINTS
    -- =========================================================================
    FOREIGN KEY (trade_id) REFERENCES trades_2(trade_id) ON DELETE CASCADE,

    CONSTRAINT valid_result CHECK (result IN ('WIN', 'LOSS')),
    CONSTRAINT valid_max_r CHECK (max_r >= -1 AND max_r <= 5)
);

-- ============================================================================
-- INDEXES
-- ============================================================================
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
-- COMMENTS
-- ============================================================================
COMMENT ON TABLE m1_atr_stop_2 IS 'M1 ATR stop analysis: evaluates trades using M1 ATR(14) stop with R-multiple targets (1R-5R). 1 row per trade.';
COMMENT ON COLUMN m1_atr_stop_2.m1_atr_value IS 'Raw 14-period ATR on M1 bars at entry candle time';
COMMENT ON COLUMN m1_atr_stop_2.m1_entry_candle_adj IS 'Entry time truncated to containing M1 candle (seconds zeroed)';
COMMENT ON COLUMN m1_atr_stop_2.stop_price IS 'M1 ATR stop price: entry -/+ m1_atr_value depending on direction';
COMMENT ON COLUMN m1_atr_stop_2.stop_distance IS 'Dollar distance from entry to stop = 1R unit = m1_atr_value';
COMMENT ON COLUMN m1_atr_stop_2.r1_hit IS 'Did price reach 1R target before stop?';
COMMENT ON COLUMN m1_atr_stop_2.r1_time IS 'Time when R1 was first reached';
COMMENT ON COLUMN m1_atr_stop_2.r1_bars_from_entry IS 'M1 bars from entry to R1 hit';
COMMENT ON COLUMN m1_atr_stop_2.max_r IS 'R-multiple result: -1 = LOSS (stopped out), 1-5 = highest R-level hit before stop. AVG(max_r) = net expectancy in R.';
COMMENT ON COLUMN m1_atr_stop_2.result IS 'WIN if R1 hit before stop, LOSS otherwise';
COMMENT ON COLUMN m1_atr_stop_2.stop_time IS 'Time when stop was first triggered (M1 close beyond stop level)';

-- ============================================================================
-- ANALYSIS VIEWS
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
    -- R-level hit rates
    ROUND(100.0 * COUNT(*) FILTER (WHERE r1_hit) / NULLIF(COUNT(*), 0), 2) as r1_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r2_hit) / NULLIF(COUNT(*), 0), 2) as r2_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r3_hit) / NULLIF(COUNT(*), 0), 2) as r3_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r4_hit) / NULLIF(COUNT(*), 0), 2) as r4_hit_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r5_hit) / NULLIF(COUNT(*), 0), 2) as r5_hit_pct,
    -- Stop hit rate
    ROUND(100.0 * COUNT(*) FILTER (WHERE stop_hit) / NULLIF(COUNT(*), 0), 2) as stop_hit_pct,
    -- Expectancy: AVG(max_r) directly gives net R per trade
    -- (losses = -1R, wins = 1R to 5R)
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
-- EXAMPLE QUERIES
-- ============================================================================
/*

-- 1. Overall summary
SELECT * FROM v_m1_atr_stop_2_summary;

-- 2. Win rate by model
SELECT * FROM v_m1_atr_stop_2_by_model;

-- 3. R-level distribution
SELECT * FROM v_m1_atr_stop_2_r_distribution;

-- 4. Trades that reached R3+
SELECT
    trade_id, ticker, date, model, direction,
    entry_price, stop_price, max_r,
    r1_time, r2_time, r3_time, result
FROM m1_atr_stop_2
WHERE max_r >= 3
ORDER BY date DESC;

-- 5. All trades with entry candle details
SELECT
    trade_id, ticker, date, direction, model,
    entry_time, m1_entry_candle_adj, entry_price,
    m1_atr_value, stop_price, stop_distance_pct,
    r1_hit, r1_time, stop_hit, stop_time, max_r, result
FROM m1_atr_stop_2
ORDER BY date DESC, ticker;

*/
