-- ============================================================================
-- EPOCH TRADING SYSTEM - M1 Indicator Bars v2 Table
-- XIII Trading LLC
-- ============================================================================
-- Reads raw M1 bars from m1_bars_2, computes 22 indicators + 3 ATR + composite scores.
-- Data range: Prior day 16:00 ET -> Trade day 16:00 ET (matches m1_bars_2)
-- Source: Entry qualifier standard indicators + extended analysis indicators
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
    vol_delta_norm NUMERIC(10, 6),        -- vol_delta_roll / avg_volume (5-bar), cross-ticker comparable
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

    -- ATR (Average True Range, 14-period)
    atr_m1 NUMERIC(12, 6),               -- 14-period ATR on M1 bars
    atr_m5 NUMERIC(12, 6),               -- 14-period ATR on M5 bars
    atr_m15 NUMERIC(12, 6),              -- 14-period ATR on M15 bars

    -- Metadata
    bars_in_calculation INTEGER,
    calculated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT m1_indicator_bars_2_pkey PRIMARY KEY (ticker, bar_date, bar_time)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_m1_indicator_bars_2_ticker_date
    ON m1_indicator_bars_2 (ticker, bar_date);

CREATE INDEX IF NOT EXISTS idx_m1_indicator_bars_2_date
    ON m1_indicator_bars_2 (bar_date);

CREATE INDEX IF NOT EXISTS idx_m1_indicator_bars_2_structure
    ON m1_indicator_bars_2 (ticker, bar_date, m1_structure, m5_structure);

CREATE INDEX IF NOT EXISTS idx_m1_indicator_bars_2_sma_config
    ON m1_indicator_bars_2 (ticker, bar_date, sma_config, price_position);

COMMENT ON TABLE m1_indicator_bars_2 IS
    'Pre-computed 1-minute indicator bars (v2). Reads from m1_bars_2, calculates entry qualifier standard + extended indicators.';
