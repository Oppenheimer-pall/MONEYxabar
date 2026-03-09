"""
💾 Database - SQLite boshqaruv moduli
"""

import os
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict


class Database:
    def __init__(self, db_path: str = None):
        from config import DB_PATH
        self.db_path = db_path or DB_PATH
        # DB papkasini yaratish (agar mavjud bo'lmasa)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True) if os.path.dirname(self.db_path) else None

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self):
        """Barcha jadvallarni yaratish"""
        with self.get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id          INTEGER PRIMARY KEY,
                    user_id     INTEGER UNIQUE NOT NULL,
                    full_name   TEXT,
                    username    TEXT,
                    created_at  TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS cards (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    card_number TEXT NOT NULL,
                    expiry      TEXT NOT NULL,
                    card_name   TEXT NOT NULL,
                    balance     REAL DEFAULT 0.0,
                    is_active   INTEGER DEFAULT 1,
                    created_at  TEXT DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    card_id     INTEGER NOT NULL,
                    card_number TEXT NOT NULL,
                    amount      REAL NOT NULL,
                    fee         REAL DEFAULT 0,
                    receiver    TEXT,
                    type        TEXT NOT NULL,
                    status      TEXT DEFAULT 'success',
                    created_at  TEXT DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (card_id) REFERENCES cards(id)
                );

                CREATE INDEX IF NOT EXISTS idx_cards_user ON cards(user_id);
                CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions(user_id);
                CREATE INDEX IF NOT EXISTS idx_tx_card ON transactions(card_id);
            """)

    # ── USERS ──────────────────────────────────────────

    def get_or_create_user(self, user_id: int, full_name: str, username: str = None):
        with self.get_conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO users (user_id, full_name, username)
                VALUES (?, ?, ?)
            """, (user_id, full_name, username))
            conn.execute("""
                UPDATE users SET full_name=?, username=? WHERE user_id=?
            """, (full_name, username, user_id))

    def get_user(self, user_id: int) -> Optional[Dict]:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id=?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    # ── CARDS ──────────────────────────────────────────

    def add_card(self, user_id: int, card_number: str, expiry: str, card_name: str) -> int:
        with self.get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO cards (user_id, card_number, expiry, card_name, balance)
                VALUES (?, ?, ?, ?, 0)
            """, (user_id, card_number, expiry, card_name))
            return cur.lastrowid

    def get_card(self, card_id: int) -> Optional[Dict]:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM cards WHERE id=? AND is_active=1", (card_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_user_cards(self, user_id: int) -> List[Dict]:
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM cards WHERE user_id=? AND is_active=1 ORDER BY id",
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def card_exists(self, user_id: int, card_number: str) -> bool:
        with self.get_conn() as conn:
            row = conn.execute("""
                SELECT id FROM cards
                WHERE user_id=? AND card_number=? AND is_active=1
            """, (user_id, card_number)).fetchone()
            return row is not None

    def delete_card(self, user_id: int, card_id: int):
        with self.get_conn() as conn:
            conn.execute("""
                UPDATE cards SET is_active=0
                WHERE id=? AND user_id=?
            """, (card_id, user_id))

    def deduct_balance(self, card_id: int, amount: float) -> float:
        """Kartadan pul yechish va yangi balansni qaytarish"""
        with self.get_conn() as conn:
            conn.execute("""
                UPDATE cards SET balance = balance - ?
                WHERE id=? AND balance >= ?
            """, (amount, card_id, amount))
            row = conn.execute(
                "SELECT balance FROM cards WHERE id=?", (card_id,)
            ).fetchone()
            return row['balance'] if row else 0

    def add_balance(self, card_id: int, amount: float) -> float:
        """Kartaga pul qo'shish"""
        with self.get_conn() as conn:
            conn.execute("""
                UPDATE cards SET balance = balance + ? WHERE id=?
            """, (amount, card_id))
            row = conn.execute(
                "SELECT balance FROM cards WHERE id=?", (card_id,)
            ).fetchone()
            return row['balance'] if row else 0

    # ── TRANSACTIONS ───────────────────────────────────

    def save_transaction(self, user_id: int, card_id: int, card_number: str,
                          amount: float, fee: float, receiver: str,
                          tx_type: str, status: str = 'success') -> int:
        with self.get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO transactions
                (user_id, card_id, card_number, amount, fee, receiver, type, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, card_id, card_number, amount, fee, receiver, tx_type, status))
            return cur.lastrowid

    def get_transaction(self, tx_id: int) -> Optional[Dict]:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM transactions WHERE id=?", (tx_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_transactions(self, user_id: int, limit: int = 10) -> List[Dict]:
        with self.get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM transactions
                WHERE user_id=?
                ORDER BY id DESC LIMIT ?
            """, (user_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def get_user_stats(self, user_id: int) -> Dict:
        with self.get_conn() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as tx_count,
                    SUM(CASE WHEN type='debit' THEN amount ELSE 0 END) as total_debit,
                    SUM(CASE WHEN type='credit' THEN amount ELSE 0 END) as total_credit
                FROM transactions
                WHERE user_id=?
                  AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
            """, (user_id,)).fetchone()
            return dict(row) if row else {}
