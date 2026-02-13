-- ============================================================================
-- FIFO Trade Processor - Schema Migration
-- Epoch Trading System v2.0 - XIII Trading LLC
--
-- Adds FIFO-specific columns to journal_trades table.
-- Safe to run multiple times (IF NOT EXISTS).
--
-- Usage:
--   psql -h db.xxx.supabase.co -U postgres -d postgres -f add_fifo_columns.sql
-- ============================================================================

-- FIFO trade sequence number (1, 2, 3... per symbol per session)
ALTER TABLE journal_trades
    ADD COLUMN IF NOT EXISTS trade_seq INTEGER;

-- Processing mode: 'LEGACY' for old blended trades, 'FIFO' for new
ALTER TABLE journal_trades
    ADD COLUMN IF NOT EXISTS processing_mode VARCHAR(10) DEFAULT 'LEGACY';

-- Index for sequence ordering
CREATE INDEX IF NOT EXISTS idx_journal_trades_fifo_seq
    ON journal_trades (trade_date, symbol, trade_seq);

-- Comment: trade_id format for FIFO trades includes _SEQ suffix
-- e.g., MU_021326_JRNL_0928_01
-- Legacy trades use: MU_021326_JRNL_0928 (no suffix)
