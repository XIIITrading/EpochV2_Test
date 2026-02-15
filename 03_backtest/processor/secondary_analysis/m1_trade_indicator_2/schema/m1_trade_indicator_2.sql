-- ============================================================================
-- EPOCH TRADING SYSTEM - M1 Trade Indicator Table v2
-- Single M1 bar snapshot at entry (last completed bar before entry candle)
-- Denormalized with trade context + outcome for fast indicator analysis
-- XIII Trading LLC
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
