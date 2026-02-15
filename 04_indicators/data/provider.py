"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 04: INDICATOR ANALYSIS v2.0
Data Provider - Central data access for all analysis tabs
XIII Trading LLC
================================================================================

Provides all indicator data needed by the 5 analysis tabs.
Sources: m1_trade_indicator_2, m1_ramp_up_indicator_2, m1_post_trade_indicator_2
"""
import warnings
import psycopg2
import psycopg2.extras
import pandas as pd
from datetime import date
from typing import Optional, Dict, List, Tuple

# Silence pandas warning about psycopg2 not being a tested DBAPI2 connector
warnings.filterwarnings("ignore", message=".*pandas only supports SQLAlchemy.*")

from config import (
    DB_CONFIG, TABLE_TRADES, TABLE_M5_ATR,
    TABLE_RAMP_UP, TABLE_TRADE_IND, TABLE_POST_TRADE,
)


class DataProvider:
    """Provides all data needed by indicator analysis tabs."""

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

    def _query(self, sql: str, params=None) -> pd.DataFrame:
        if not self._conn or self._conn.closed:
            self.connect()
        try:
            return pd.read_sql_query(sql, self._conn, params=params)
        except Exception as e:
            print(f"[DataProvider] Query error: {e}")
            # Try reconnecting once
            self.connect()
            return pd.read_sql_query(sql, self._conn, params=params)

    # ------------------------------------------------------------------
    # Filter support
    # ------------------------------------------------------------------
    def get_tickers(self) -> list:
        """Get distinct tickers from trade indicator table."""
        sql = f"SELECT DISTINCT ticker FROM {TABLE_TRADE_IND} ORDER BY ticker"
        df = self._query(sql)
        return df["ticker"].tolist() if not df.empty else []

    def get_date_range(self) -> Dict:
        """Get the min/max dates available."""
        sql = f"""
            SELECT MIN(date) as min_date, MAX(date) as max_date,
                   COUNT(*) as total
            FROM {TABLE_TRADE_IND}
        """
        df = self._query(sql)
        if df.empty:
            return {"min_date": date.today(), "max_date": date.today(), "total": 0}
        return {
            "min_date": df.iloc[0]["min_date"],
            "max_date": df.iloc[0]["max_date"],
            "total": int(df.iloc[0]["total"]),
        }

    def get_pending_count(self, model: Optional[str] = None,
                          direction: Optional[str] = None,
                          date_from: Optional[date] = None,
                          date_to: Optional[date] = None) -> int:
        """Count trades in trades_2 that match filters but are NOT in indicator tables.

        This drives the amber warning in the filter panel.
        """
        sql = f"""
            SELECT COUNT(*) as pending_count
            FROM {TABLE_TRADES} t
            WHERE t.trade_id NOT IN (SELECT trade_id FROM {TABLE_TRADE_IND})
        """
        params = []

        if model:
            sql += " AND t.model = %s"
            params.append(model)
        if direction:
            sql += " AND t.direction = %s"
            params.append(direction)
        if date_from:
            sql += " AND t.date >= %s"
            params.append(date_from)
        if date_to:
            sql += " AND t.date <= %s"
            params.append(date_to)

        df = self._query(sql, params if params else None)
        return int(df.iloc[0]["pending_count"]) if not df.empty else 0

    # ------------------------------------------------------------------
    # Entry Snapshot (Tab 2) - m1_trade_indicator_2
    # ------------------------------------------------------------------
    def get_entry_data(self, model: Optional[str] = None,
                       direction: Optional[str] = None,
                       ticker: Optional[str] = None,
                       outcome: Optional[str] = None,
                       date_from: Optional[date] = None,
                       date_to: Optional[date] = None) -> pd.DataFrame:
        """Get all entry indicator snapshots with filters."""
        sql = f"SELECT * FROM {TABLE_TRADE_IND} WHERE 1=1"
        params = []

        if model:
            sql += " AND model = %s"
            params.append(model)
        if direction:
            sql += " AND direction = %s"
            params.append(direction)
        if ticker:
            sql += " AND ticker = %s"
            params.append(ticker)
        if outcome == "Winners":
            sql += " AND is_winner = true"
        elif outcome == "Losers":
            sql += " AND is_winner = false"
        if date_from:
            sql += " AND date >= %s"
            params.append(date_from)
        if date_to:
            sql += " AND date <= %s"
            params.append(date_to)

        sql += " ORDER BY date, entry_time"
        return self._query(sql, params if params else None)

    def get_trade_ids(self, model: Optional[str] = None,
                      direction: Optional[str] = None,
                      ticker: Optional[str] = None,
                      outcome: Optional[str] = None,
                      date_from: Optional[date] = None,
                      date_to: Optional[date] = None) -> List[str]:
        """Get filtered trade_ids for use in ramp-up/post-trade queries."""
        df = self.get_entry_data(model, direction, ticker, outcome, date_from, date_to)
        return df["trade_id"].tolist() if not df.empty else []

    # ------------------------------------------------------------------
    # Ramp-Up Analysis (Tab 1) - m1_ramp_up_indicator_2
    # ------------------------------------------------------------------
    def get_ramp_up_data(self, trade_ids: List[str]) -> pd.DataFrame:
        """Get ramp-up data for given trade_ids."""
        if not trade_ids:
            return pd.DataFrame()

        sql = f"""
            SELECT r.*, s.result as outcome
            FROM {TABLE_RAMP_UP} r
            JOIN {TABLE_M5_ATR} s ON r.trade_id = s.trade_id
            WHERE r.trade_id = ANY(%s)
            ORDER BY r.trade_id, r.bar_sequence
        """
        return self._query(sql, [trade_ids])

    def get_ramp_up_averages(self, trade_ids: List[str]) -> pd.DataFrame:
        """Get average indicator values per bar_sequence, split by outcome.

        Direction-sensitive indicators (vol_delta_roll, cvd_slope) are
        normalized so that positive = favorable for the trade direction.
        SHORT trades have these values sign-flipped before averaging.
        """
        if not trade_ids:
            return pd.DataFrame()

        sql = f"""
            SELECT
                r.bar_sequence,
                (s.result = 'WIN') as is_winner,
                AVG(r.candle_range_pct) as avg_candle_range,
                AVG(CASE WHEN s.direction = 'SHORT'
                    THEN -r.vol_delta_roll ELSE r.vol_delta_roll END
                ) as avg_vol_delta,
                AVG(r.vol_roc) as avg_vol_roc,
                AVG(r.sma_spread_pct) as avg_sma_spread,
                AVG(CASE WHEN s.direction = 'SHORT'
                    THEN -r.cvd_slope ELSE r.cvd_slope END
                ) as avg_cvd_slope,
                COUNT(DISTINCT r.trade_id) as trade_count
            FROM {TABLE_RAMP_UP} r
            JOIN {TABLE_M5_ATR} s ON r.trade_id = s.trade_id
            WHERE r.trade_id = ANY(%s)
            GROUP BY r.bar_sequence, (s.result = 'WIN')
            ORDER BY r.bar_sequence
        """
        return self._query(sql, [trade_ids])

    # ------------------------------------------------------------------
    # Post-Trade Analysis (Tab 3) - m1_post_trade_indicator_2
    # ------------------------------------------------------------------
    def get_post_trade_data(self, trade_ids: List[str]) -> pd.DataFrame:
        """Get post-trade data for given trade_ids."""
        if not trade_ids:
            return pd.DataFrame()

        sql = f"""
            SELECT *
            FROM {TABLE_POST_TRADE}
            WHERE trade_id = ANY(%s)
            ORDER BY trade_id, bar_sequence
        """
        return self._query(sql, [trade_ids])

    def get_post_trade_averages(self, trade_ids: List[str]) -> pd.DataFrame:
        """Get average indicator values per bar_sequence, split by outcome.

        Direction-sensitive indicators (vol_delta_roll, cvd_slope) are
        normalized so that positive = favorable for the trade direction.
        SHORT trades have these values sign-flipped before averaging.
        """
        if not trade_ids:
            return pd.DataFrame()

        sql = f"""
            SELECT
                p.bar_sequence,
                p.is_winner,
                AVG(p.candle_range_pct) as avg_candle_range,
                AVG(CASE WHEN s.direction = 'SHORT'
                    THEN -p.vol_delta_roll ELSE p.vol_delta_roll END
                ) as avg_vol_delta,
                AVG(p.vol_roc) as avg_vol_roc,
                AVG(p.sma_spread_pct) as avg_sma_spread,
                AVG(CASE WHEN s.direction = 'SHORT'
                    THEN -p.cvd_slope ELSE p.cvd_slope END
                ) as avg_cvd_slope,
                COUNT(DISTINCT p.trade_id) as trade_count
            FROM {TABLE_POST_TRADE} p
            JOIN {TABLE_M5_ATR} s ON p.trade_id = s.trade_id
            WHERE p.trade_id = ANY(%s)
            GROUP BY p.bar_sequence, p.is_winner
            ORDER BY p.bar_sequence
        """
        return self._query(sql, [trade_ids])

    # ------------------------------------------------------------------
    # Entry Win Rate by Indicator State (Tab 2 / Tab 4)
    # ------------------------------------------------------------------
    def get_win_rate_by_state(self, trade_ids: List[str],
                              indicator_col: str) -> pd.DataFrame:
        """Get win rate breakdown by indicator state at entry."""
        if not trade_ids:
            return pd.DataFrame()

        sql = f"""
            SELECT
                {indicator_col} as state,
                COUNT(*) as trades,
                SUM(CASE WHEN is_winner THEN 1 ELSE 0 END) as wins,
                ROUND(AVG(CASE WHEN is_winner THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
                ROUND(AVG(pnl_r), 2) as avg_r
            FROM {TABLE_TRADE_IND}
            WHERE trade_id = ANY(%s)
              AND {indicator_col} IS NOT NULL
            GROUP BY {indicator_col}
            ORDER BY win_rate DESC
        """
        return self._query(sql, [trade_ids])

    def get_win_rate_by_quintile(self, trade_ids: List[str],
                                 indicator_col: str) -> pd.DataFrame:
        """Get win rate by quintile for continuous indicators at entry."""
        if not trade_ids:
            return pd.DataFrame()

        sql = f"""
            WITH ranked AS (
                SELECT
                    trade_id, is_winner, pnl_r,
                    {indicator_col},
                    NTILE(5) OVER (ORDER BY {indicator_col}) as quintile
                FROM {TABLE_TRADE_IND}
                WHERE trade_id = ANY(%s)
                  AND {indicator_col} IS NOT NULL
            )
            SELECT
                quintile,
                MIN({indicator_col}) as range_min,
                MAX({indicator_col}) as range_max,
                COUNT(*) as trades,
                SUM(CASE WHEN is_winner THEN 1 ELSE 0 END) as wins,
                ROUND(AVG(CASE WHEN is_winner THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
                ROUND(AVG(pnl_r), 2) as avg_r
            FROM ranked
            GROUP BY quintile
            ORDER BY quintile
        """
        return self._query(sql, [trade_ids])

    # ------------------------------------------------------------------
    # Composite Setup Analysis (Tab 5)
    # ------------------------------------------------------------------
    def get_setup_combinations(self, trade_ids: List[str],
                                min_trades: int = 20) -> pd.DataFrame:
        """Get win rate for indicator state combinations at entry."""
        if not trade_ids:
            return pd.DataFrame()

        sql = f"""
            SELECT
                sma_config,
                h1_structure,
                m15_structure,
                CASE WHEN vol_roc >= 30 THEN 'ELEVATED' ELSE 'NORMAL' END as vol_roc_level,
                CASE
                    WHEN candle_range_pct >= 0.15 THEN 'NORMAL'
                    WHEN candle_range_pct >= 0.12 THEN 'LOW'
                    ELSE 'ABSORPTION'
                END as candle_level,
                COUNT(*) as trades,
                SUM(CASE WHEN is_winner THEN 1 ELSE 0 END) as wins,
                ROUND(AVG(CASE WHEN is_winner THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
                ROUND(AVG(pnl_r), 2) as avg_r
            FROM {TABLE_TRADE_IND}
            WHERE trade_id = ANY(%s)
            GROUP BY sma_config, h1_structure, m15_structure, vol_roc_level, candle_level
            HAVING COUNT(*) >= %s
            ORDER BY win_rate DESC
        """
        return self._query(sql, [trade_ids, min_trades])

    # ------------------------------------------------------------------
    # Deep Dive: Three-Phase Progression (Tab 4)
    # ------------------------------------------------------------------
    # Indicators where positive = bullish, negative = bearish
    # These get sign-flipped for SHORT trades so positive = "favorable"
    DIRECTIONAL_INDICATORS = {'vol_delta_roll', 'cvd_slope'}

    def get_three_phase_averages(self, trade_ids: List[str],
                                 indicator_col: str) -> pd.DataFrame:
        """Get average indicator across ramp-up + post-trade, split by outcome.

        Direction-sensitive indicators are normalized (SHORT flipped)
        so positive always means "favorable for the trade direction".

        Returns a unified DataFrame with:
        - phase: 'ramp_up' or 'post_trade'
        - bar_sequence: 0-24
        - is_winner: True/False
        - avg_value: average of the indicator
        """
        if not trade_ids:
            return pd.DataFrame()

        # Build the AVG expression — flip sign for SHORT on directional indicators
        if indicator_col in self.DIRECTIONAL_INDICATORS:
            ramp_avg = f"""AVG(CASE WHEN s.direction = 'SHORT'
                THEN -r.{indicator_col} ELSE r.{indicator_col} END)"""
            post_avg = f"""AVG(CASE WHEN s.direction = 'SHORT'
                THEN -p.{indicator_col} ELSE p.{indicator_col} END)"""
        else:
            ramp_avg = f"AVG(r.{indicator_col})"
            post_avg = f"AVG(p.{indicator_col})"

        # Ramp-up averages
        sql_ramp = f"""
            SELECT
                'ramp_up' as phase,
                r.bar_sequence,
                (s.result = 'WIN') as is_winner,
                {ramp_avg} as avg_value,
                COUNT(DISTINCT r.trade_id) as trade_count
            FROM {TABLE_RAMP_UP} r
            JOIN {TABLE_M5_ATR} s ON r.trade_id = s.trade_id
            WHERE r.trade_id = ANY(%s)
              AND r.{indicator_col} IS NOT NULL
            GROUP BY r.bar_sequence, (s.result = 'WIN')
        """

        # Post-trade averages
        sql_post = f"""
            SELECT
                'post_trade' as phase,
                p.bar_sequence,
                p.is_winner,
                {post_avg} as avg_value,
                COUNT(DISTINCT p.trade_id) as trade_count
            FROM {TABLE_POST_TRADE} p
            JOIN {TABLE_M5_ATR} s ON p.trade_id = s.trade_id
            WHERE p.trade_id = ANY(%s)
              AND p.{indicator_col} IS NOT NULL
            GROUP BY p.bar_sequence, p.is_winner
        """

        sql = f"""
            ({sql_ramp})
            UNION ALL
            ({sql_post})
            ORDER BY phase DESC, bar_sequence
        """
        return self._query(sql, [trade_ids, trade_ids])
