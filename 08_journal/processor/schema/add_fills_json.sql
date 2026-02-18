-- Add fills_json column for position-based trade processing
-- Stores ALL fills (entries + adds + exits) as JSONB array
-- Format: [{"side":"SS","type":"ENTRY","price":407.68,"qty":3,"time":"09:40:54","position_after":3}, ...]

ALTER TABLE journal_trades ADD COLUMN IF NOT EXISTS fills_json JSONB;
