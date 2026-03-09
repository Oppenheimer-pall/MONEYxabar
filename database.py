"""
💾 Database - SQLite boshqaruv moduli
"""

import os
import sqlite3
from typing import Optional, List, Dict


def get_db_path() -> str:
    """DB yo'lini aniqlash - Railway volume yoki /tmp"""
    # Priority: ENV → /data (Railway volume) → /tmp → lokal
    env_path = os.getenv("DB_PATH", "")
    if env_path:
        folder = os.path.dirname(env_path)
        if folder:
            try:
                os.makedirs(folder, exist_ok=True)
                # Test write
                test = os.path.join(folder, ".test")
                open(test, "w").close()
                os.remove(test)
                return env_path
            except Exception:
                pass
        else:
            return env_path  # relative path like card_bot.db

    # Fallback: /tmp (har doim yozish mumkin)
    return "/tmp/card_bot.db"


class Database:
    def __init__(self):
        self.db_path = get_db_path()
        print(f"✅ Database: {self.db_path}")

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        # foreign keys disabled
        return conn

    def init(self):
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
                    
                );
            """)

    # ── USERS ──
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
            row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    # ── CARDS ──
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
                SELECT id FROM cards WHERE user_id=? AND card_number=? AND is_active=1
            """, (user_id, card_number)).fetchone()
            return row is not None

    def delete_card(self, user_id: int, card_id: int):
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE cards SET is_active=0 WHERE id=? AND user_id=?",
                (card_id, user_id)
            )

    def deduct_balance(self, card_id: int, amount: float) -> float:
        with self.get_conn() as conn:
            cur = conn.execute("""
                UPDATE cards SET balance = balance - ?
                WHERE id=? AND balance >= ?
            """, (amount, card_id, amount))
            if cur.rowcount == 0:
                raise ValueError("Mablag' yetarli emas!")
            row = conn.execute("SELECT balance FROM cards WHERE id=?", (card_id,)).fetchone()
            return row['balance']

    def add_balance(self, card_id: int, amount: float) -> float:
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE cards SET balance = balance + ? WHERE id=?",
                (amount, card_id)
            )
            row = conn.execute("SELECT balance FROM cards WHERE id=?", (card_id,)).fetchone()
            return row['balance']

    # ── TRANSACTIONS ──
    def save_transaction(self, user_id, card_id, card_number,
                         amount, fee, receiver, tx_type, status='success') -> int:
        with self.get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO transactions
                (user_id, card_id, card_number, amount, fee, receiver, type, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, card_id, card_number, amount, fee, receiver, tx_type, status))
            return cur.lastrowid

    def get_transaction(self, tx_id: int) -> Optional[Dict]:
        with self.get_conn() as conn:
            row = conn.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
            return dict(row) if row else None

    def get_transactions(self, user_id: int, limit: int = 10) -> List[Dict]:
        with self.get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM transactions WHERE user_id=?
                ORDER BY id DESC LIMIT ?
            """, (user_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def get_user_stats(self, user_id: int) -> Dict:
        with self.get_conn() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as tx_count,
                    COALESCE(SUM(CASE WHEN type='debit' THEN amount ELSE 0 END), 0) as total_debit,
                    COALESCE(SUM(CASE WHEN type='credit' THEN amount ELSE 0 END), 0) as total_credit
                FROM transactions WHERE user_id=?
                AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
            """, (user_id,)).fetchone()
            return dict(row) if row else {}
