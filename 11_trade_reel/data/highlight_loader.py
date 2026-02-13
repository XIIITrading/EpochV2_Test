"""
Epoch Trading System - Highlight Loader
Queries trades_m5_r_win_2 for highlight trades.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date
from typing import List, Optional, Tuple
import logging

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_CONFIG
from models.highlight import HighlightTrade

logger = logging.getLogger(__name__)


class HighlightLoader:
    """Load highlight trades from trades_m5_r_win_2 table."""

    def __init__(self):
        self.conn = None

    def connect(self) -> bool:
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            logger.info("Connected to Supabase")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def _ensure_connected(self) -> bool:
        """Reconnect if needed. Returns True if connected."""
        if not self.conn or self.conn.closed:
            return self.connect()
        return True

    def fetch_highlights(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        min_r: int = 3,
        model: Optional[str] = None,
        direction: Optional[str] = None,
        ticker: Optional[str] = None,
        limit: int = 200
    ) -> List[HighlightTrade]:
        """
        Fetch highlight trades from trades_m5_r_win_2.

        Args:
            date_from: Start date (inclusive)
            date_to: End date (inclusive)
            min_r: Minimum max_r_achieved (default 3)
            model: Filter by model (EPCH1-4)
            direction: Filter by direction (LONG/SHORT)
            ticker: Filter by ticker
            limit: Max results

        Returns:
            List of HighlightTrade sorted by max_r DESC, date DESC
        """
        if not self._ensure_connected():
            logger.warning("Skipping fetch_highlights - no database connection")
            return []

        query = """
            SELECT * FROM trades_m5_r_win_2
            WHERE outcome = 'WIN'
              AND max_r_achieved >= %s
        """
        params: list = [min_r]

        if date_from:
            query += " AND date >= %s"
            params.append(date_from)

        if date_to:
            query += " AND date <= %s"
            params.append(date_to)

        if model:
            query += " AND model = %s"
            params.append(model.upper())

        if direction:
            query += " AND direction = %s"
            params.append(direction.upper())

        if ticker:
            query += " AND ticker = %s"
            params.append(ticker.upper())

        query += " ORDER BY max_r_achieved DESC, date DESC"
        query += f" LIMIT {limit}"

        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                return [HighlightTrade.from_db_row(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching highlights: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
            return []

    def fetch_zones_for_trade(self, ticker: str, trade_date: date) -> List[dict]:
        """
        Fetch zones for a trade's ticker and date (for chart overlays).

        Returns:
            List of dicts with zone_high, zone_low, hvn_poc, rank, score, is_filtered
        """
        if not self._ensure_connected():
            logger.warning("Skipping fetch_zones_for_trade - no database connection")
            return []

        query = """
            SELECT zone_id, ticker, date, zone_high, zone_low, hvn_poc,
                   rank, score, is_filtered
            FROM zones
            WHERE ticker = %s AND date = %s
            ORDER BY score DESC NULLS LAST
        """

        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (ticker.upper(), trade_date))
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching zones: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
            return []

    def fetch_hvn_pocs(self, ticker: str, trade_date: date) -> List[float]:
        """
        Fetch HVN POC prices from hvn_pocs table for a ticker-date pair.
        Returns up to 10 POC prices (poc_1 through poc_10), filtering out nulls.

        Args:
            ticker: Ticker symbol
            trade_date: Trade/analysis date

        Returns:
            List of POC prices (floats), ordered poc_1..poc_10
        """
        if not self._ensure_connected():
            logger.warning("Skipping fetch_hvn_pocs - no database connection")
            return []

        query = """
            SELECT poc_1, poc_2, poc_3, poc_4, poc_5,
                   poc_6, poc_7, poc_8, poc_9, poc_10
            FROM hvn_pocs
            WHERE ticker = %s AND date = %s
            LIMIT 1
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (ticker.upper(), trade_date))
                row = cur.fetchone()
                if row:
                    return [float(p) for p in row if p is not None]
                return []
        except Exception as e:
            logger.error(f"Error fetching hvn_pocs: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
            return []

    def fetch_epoch_start_date(self, ticker: str, trade_date: date) -> Optional[date]:
        """
        Fetch the epoch_start_date (anchor date) from hvn_pocs for a ticker-date pair.
        This is the start of the HVN epoch, used to build Volume by Price.

        Args:
            ticker: Ticker symbol
            trade_date: Trade/analysis date

        Returns:
            epoch_start_date or None if not found
        """
        if not self._ensure_connected():
            logger.warning("Skipping fetch_epoch_start_date - no database connection")
            return None

        query = """
            SELECT epoch_start_date FROM hvn_pocs
            WHERE ticker = %s AND date = %s
            LIMIT 1
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (ticker.upper(), trade_date))
                row = cur.fetchone()
                if row and row[0]:
                    return row[0]
                return None
        except Exception as e:
            logger.error(f"Error fetching epoch_start_date: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
            return None

    def get_available_models(self) -> List[str]:
        """Get unique models from highlight trades."""
        if not self._ensure_connected():
            logger.warning("Skipping get_available_models - no database connection")
            return ['EPCH1', 'EPCH2', 'EPCH3', 'EPCH4']

        query = """
            SELECT DISTINCT model FROM trades_m5_r_win_2
            WHERE model IS NOT NULL AND outcome = 'WIN'
            ORDER BY model
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                return [row[0] for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching models: {e}")
            return ['EPCH1', 'EPCH2', 'EPCH3', 'EPCH4']

    def get_available_tickers(self, date_from: Optional[date] = None) -> List[str]:
        """Get unique tickers that have highlight-quality trades."""
        if not self._ensure_connected():
            logger.warning("Skipping get_available_tickers - no database connection")
            return []

        query = """
            SELECT DISTINCT ticker FROM trades_m5_r_win_2
            WHERE outcome = 'WIN' AND max_r_achieved >= 3
        """
        params = []

        if date_from:
            query += " AND date >= %s"
            params.append(date_from)

        query += " ORDER BY ticker"

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, params)
                return [row[0] for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching tickers: {e}")
            return []

    def get_date_range(self) -> Tuple[Optional[date], Optional[date]]:
        """Get min/max date range from trades_m5_r_win_2."""
        if not self._ensure_connected():
            logger.warning("Skipping get_date_range - no database connection")
            return None, None

        query = "SELECT MIN(date), MAX(date) FROM trades_m5_r_win_2"

        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                row = cur.fetchone()
                if row:
                    return row[0], row[1]
                return None, None
        except Exception as e:
            logger.error(f"Error fetching date range: {e}")
            return None, None


# Singleton
_loader = None


def get_highlight_loader() -> HighlightLoader:
    """Get or create the HighlightLoader singleton."""
    global _loader
    if _loader is None:
        _loader = HighlightLoader()
        _loader.connect()
    return _loader
