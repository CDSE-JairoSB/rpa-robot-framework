"""SQLite persistence layer and price drop detector for tracked products."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
import re
import sqlite3
from typing import Any, Dict, Generator, List, Optional


class PriceRepository:
    """Manages SQLite storage for Amazon wishlist items, price history, and drop alerts."""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(self, db_path: str = "data/prices.db") -> None:
        """Initializes the repository and provisions the schema if needed.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provides a thread-safe connection context with automatic commit/rollback."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL journal mode for high concurrency
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Creates tables and indexes if they do not exist."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    asin TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT,
                    currency TEXT DEFAULT 'MXN',
                    current_price REAL NOT NULL,
                    lowest_price REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT NOT NULL,
                    price REAL NOT NULL,
                    currency TEXT DEFAULT 'MXN',
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY (asin) REFERENCES products(asin) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_price_history_asin
                ON price_history(asin, recorded_at);
                """
            )

    @staticmethod
    def _parse_price(raw_price: Any) -> float:
        """Normalizes integer, float, or formatted string price into a float."""
        if isinstance(raw_price, (int, float)):
            return float(raw_price)

        text = str(raw_price).strip().replace("$", "").replace(" ", "")
        # Remove commas if used as thousands separator
        if "," in text and "." in text:
            text = text.replace(",", "")
        elif "," in text:
            # Handle comma as decimal separator if followed by 1 or 2 digits
            trailing = text.rsplit(",", 1)[-1]
            if len(trailing) in (1, 2):
                text = text.replace(",", ".")
            else:
                text = text.replace(",", "")

        match = re.search(r"(\d+(?:\.\d+)?)", text)
        if not match:
            raise ValueError(f"Unable to parse price from: {raw_price}")

        return round(float(match.group(1)), 2)

    def record_price(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Records product price observation, tracking lowest price and drop detection.

        Args:
            item: Product dictionary containing 'asin', 'current_price',
                  and optionally 'title', 'url', 'currency'.

        Returns:
            Dictionary containing price comparison results:
            {
                "asin": str,
                "title": str,
                "url": str,
                "currency": str,
                "is_drop": bool,
                "previous_price": Optional[float],
                "current_price": float,
                "lowest_price": float,
                "drop_percentage": float
            }
        """
        asin = str(item["asin"]).strip().upper()
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        currency = str(item.get("currency") or "MXN").strip()
        current_price = self._parse_price(item["current_price"])

        now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT title, url, currency, current_price, lowest_price FROM products WHERE asin = ?",
                (asin,),
            )
            existing = cursor.fetchone()

            if existing is None:
                previous_price = None
                lowest_price = current_price
                is_drop = False
                drop_percentage = 0.0

                conn.execute(
                    """
                    INSERT INTO products (asin, title, url, currency, current_price, lowest_price, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (asin, title, url, currency, current_price, lowest_price, now_iso, now_iso),
                )
            else:
                previous_price = float(existing["current_price"])
                existing_lowest = float(existing["lowest_price"])
                lowest_price = min(existing_lowest, current_price)

                if current_price < previous_price:
                    is_drop = True
                    drop_percentage = round(((previous_price - current_price) / previous_price) * 100, 2)
                else:
                    is_drop = False
                    drop_percentage = 0.0

                # Keep existing title/url if incoming are blank
                final_title = title if title else existing["title"]
                final_url = url if url else existing["url"]
                final_currency = currency if currency else existing["currency"]

                conn.execute(
                    """
                    UPDATE products
                    SET title = ?, url = ?, currency = ?, current_price = ?, lowest_price = ?, updated_at = ?
                    WHERE asin = ?
                    """,
                    (final_title, final_url, final_currency, current_price, lowest_price, now_iso, asin),
                )

            conn.execute(
                """
                INSERT INTO price_history (asin, price, currency, recorded_at)
                VALUES (?, ?, ?, ?)
                """,
                (asin, current_price, currency, now_iso),
            )

        return {
            "asin": asin,
            "title": title or (existing["title"] if existing else ""),
            "url": url or (existing["url"] if existing else ""),
            "currency": currency or (existing["currency"] if existing else "MXN"),
            "is_drop": is_drop,
            "previous_price": previous_price,
            "current_price": current_price,
            "lowest_price": lowest_price,
            "drop_percentage": drop_percentage,
        }

    def get_tracked_items(self) -> List[Dict[str, Any]]:
        """Retrieves all tracked products with their latest and lowest price metadata.

        Returns:
            List of product dictionaries.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT asin, title, url, currency, current_price, lowest_price, created_at, updated_at
                FROM products
                ORDER BY asin ASC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_price_history(self, asin: str) -> List[Dict[str, Any]]:
        """Retrieves chronological price history for an ASIN.

        Args:
            asin: Amazon Standard Identification Number.

        Returns:
            List of price observation dictionaries.
        """
        asin = str(asin).strip().upper()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, asin, price, currency, recorded_at
                FROM price_history
                WHERE asin = ?
                ORDER BY recorded_at ASC, id ASC
                """,
                (asin,),
            )
            return [dict(row) for row in cursor.fetchall()]
