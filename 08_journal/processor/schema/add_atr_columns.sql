-- =============================================================================
-- Add M1 ATR Stop + M5 ATR Stop columns to journal_trades
-- Epoch Trading System v3 - XIII Trading LLC
--
-- Run manually in Supabase SQL Editor.
-- Both ATR models computed at save time by FIFO processor.
-- M1 ATR = tight stop (1-minute ATR), M5 ATR = wider stop (5-minute ATR)
-- =============================================================================

-- M1 ATR Stop columns
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_atr_value DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_stop_price DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_stop_distance DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_r1_price DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_r2_price DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_r3_price DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_r4_price DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_r5_price DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_r1_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_r2_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_r3_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_r4_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_r5_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_r1_time TIME;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_r2_time TIME;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_r3_time TIME;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_r4_time TIME;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_r5_time TIME;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_stop_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_stop_hit_time TIME;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_max_r INTEGER DEFAULT 0;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m1_pnl_r DECIMAL;

-- M5 ATR Stop columns (same structure, wider stop)
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_atr_value DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_stop_price DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_stop_distance DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_r1_price DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_r2_price DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_r3_price DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_r4_price DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_r5_price DECIMAL;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_r1_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_r2_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_r3_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_r4_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_r5_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_r1_time TIME;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_r2_time TIME;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_r3_time TIME;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_r4_time TIME;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_r5_time TIME;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_stop_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_stop_hit_time TIME;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_max_r INTEGER DEFAULT 0;
ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS m5_pnl_r DECIMAL;
