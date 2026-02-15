-- ============================================================================
-- EPOCH TRADING SYSTEM - M1 Post-Trade Indicator Table v2
-- 25 M1 bars after entry (bar_sequence 0=entry candle, 24=25th bar after)
-- Trade outcome stamped on every row for easy aggregation
-- XIII Trading LLC
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
