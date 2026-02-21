"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 05: SYSTEM ANALYSIS
Data Provider - Core database access for question modules
XIII Trading LLC
================================================================================

Provides the shared database connection and base query infrastructure.
Individual question modules use provider._query() for their own SQL.
"""
import json
import psycopg2
import pandas as pd
from datetime import date, datetime
from typing import Optional, Dict

from config import DB_CONFIG, TABLE_TRADES

# Export table for question results
TABLE_EXPORT = "sa_question_results"


class DataProvider:
    """Core data access layer for system analysis questions."""

    def __init__(self):
        self._conn = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def connect(self) -> bool:
        try:
            self._conn = psycopg2.connect(**DB_CONFIG)
            return True
        except Exception as e:
            print(f"[DataProvider] Connection failed: {e}")
            return False

    def close(self):
        if self._conn and not self._conn.closed:
            self._conn.close()

    def query(self, sql: str, params=None) -> pd.DataFrame:
        """Execute a SQL query and return a DataFrame.

        Auto-reconnects on connection failure. Available to question modules
        for custom queries.
        """
        if not self._conn or self._conn.closed:
            self.connect()
        try:
            return pd.read_sql_query(sql, self._conn, params=params)
        except Exception as e:
            print(f"[DataProvider] Query error: {e}")
            self.connect()
            return pd.read_sql_query(sql, self._conn, params=params)

    # ------------------------------------------------------------------
    # Common queries used across questions
    # ------------------------------------------------------------------
    def get_trades(self, date_from: Optional[date] = None,
                   date_to: Optional[date] = None) -> pd.DataFrame:
        """Get all trades with optional date filtering."""
        sql = f"SELECT * FROM {TABLE_TRADES} WHERE 1=1"
        params = []

        if date_from:
            sql += " AND date >= %s"
            params.append(date_from)
        if date_to:
            sql += " AND date <= %s"
            params.append(date_to)

        sql += " ORDER BY date, entry_time"
        return self.query(sql, params if params else None)

    def get_date_range(self) -> Dict:
        """Get the min/max dates available in trades."""
        sql = f"SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(*) as total FROM {TABLE_TRADES}"
        df = self.query(sql)
        if df.empty:
            return {"min_date": date.today(), "max_date": date.today(), "total": 0}
        return {
            "min_date": df.iloc[0]["min_date"],
            "max_date": df.iloc[0]["max_date"],
            "total": int(df.iloc[0]["total"]),
        }

    def get_tickers(self) -> list:
        """Get distinct tickers."""
        sql = f"SELECT DISTINCT ticker FROM {TABLE_TRADES} ORDER BY ticker"
        df = self.query(sql)
        return df["ticker"].tolist() if not df.empty else []

    # ------------------------------------------------------------------
    # Export pipeline — write question results to Supabase
    # ------------------------------------------------------------------
    def ensure_export_table(self):
        """Create sa_question_results table if it doesn't exist.

        Also runs an ALTER TABLE migration to add batch_id for existing
        tables that were created before batch export support.
        """
        sql_create = f"""
            CREATE TABLE IF NOT EXISTS {TABLE_EXPORT} (
                id              SERIAL PRIMARY KEY,
                question_id     TEXT NOT NULL,
                question_text   TEXT NOT NULL,
                time_period     TEXT NOT NULL,
                result_json     JSONB NOT NULL,
                metadata_json   JSONB,
                batch_id        UUID,
                computed_at     TIMESTAMPTZ DEFAULT NOW()
            );
        """
        sql_migrate = f"""
            ALTER TABLE {TABLE_EXPORT}
            ADD COLUMN IF NOT EXISTS batch_id UUID;
        """
        if not self._conn or self._conn.closed:
            self.connect()
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql_create)
                cur.execute(sql_migrate)
            self._conn.commit()
        except Exception as e:
            print(f"[DataProvider] Failed to create export table: {e}")
            self._conn.rollback()

    def export_question_result(self, question_id: str, question_text: str,
                                time_period: str, result: dict,
                                metadata: Optional[dict] = None,
                                batch_id: Optional[str] = None) -> bool:
        """Write a question's computed result to sa_question_results.

        Args:
            batch_id: Optional UUID string. When exporting all questions at
                      once, every row shares the same batch_id so the full
                      snapshot can be queried as a group. Single-question
                      exports pass None (stored as NULL).

        Returns True on success, False on failure.
        """
        sql = f"""
            INSERT INTO {TABLE_EXPORT}
                (question_id, question_text, time_period, result_json,
                 metadata_json, batch_id, computed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        if not self._conn or self._conn.closed:
            self.connect()
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, (
                    question_id,
                    question_text,
                    time_period,
                    json.dumps(result, default=str),
                    json.dumps(metadata, default=str) if metadata else None,
                    batch_id,
                    datetime.now(),
                ))
            self._conn.commit()
            return True
        except Exception as e:
            print(f"[DataProvider] Export failed: {e}")
            self._conn.rollback()
            return False
