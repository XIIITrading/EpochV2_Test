-- ============================================================================
-- EPOCH TRADING SYSTEM - trades_m5_r_win_2 Table
-- Consolidated trade outcomes (trades_2 + m5_atr_stop_2 + m1_bars_2)
-- Denormalized for 11_trade_reel highlight viewer
-- XIII Trading LLC
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

-- ============================================================================
-- INDEXES
-- ============================================================================

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
-- ANALYSIS VIEWS
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
