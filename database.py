# ═══════════════════════════════════════════════════════
#  Telegram View Booster Bot - Database Layer (SQLite)
# ═══════════════════════════════════════════════════════

import sqlite3
import time
from contextlib import contextmanager
from config import DATABASE_FILE


def init_database():
    """Create all required tables if they don't exist."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                balance REAL DEFAULT 0.0,
                ref_by TEXT DEFAULT 'none',
                referred INTEGER DEFAULT 0,
                welcome_bonus INTEGER DEFAULT 0,
                total_refs INTEGER DEFAULT 0,
                total_orders INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0.0,
                is_banned INTEGER DEFAULT 0,
                created_at REAL DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deposits (
                deposit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                method TEXT NOT NULL,
                package_id INTEGER NOT NULL,
                views INTEGER NOT NULL,
                amount_bdt REAL DEFAULT 0,
                amount_usd REAL DEFAULT 0,
                trx_id TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                admin_note TEXT DEFAULT '',
                created_at REAL DEFAULT 0,
                resolved_at REAL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                smm_order_id TEXT DEFAULT '',
                link TEXT NOT NULL,
                views INTEGER NOT NULL,
                status TEXT DEFAULT 'processing',
                created_at REAL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        conn.commit()


@contextmanager
def get_connection():
    """Thread-safe database connection context manager."""
    conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ── User Operations ───────────────────────────────────

def user_exists(user_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (str(user_id),)
        ).fetchone()
        return row is not None


def create_user(user_id: str, username: str = "", first_name: str = "",
                ref_by: str = "none") -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO users
            (user_id, username, first_name, ref_by, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (str(user_id), username, first_name, ref_by, time.time()))
        conn.commit()


def get_user(user_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (str(user_id),)
        ).fetchone()
        return dict(row) if row else None


def update_user_info(user_id: str, username: str, first_name: str) -> None:
    with get_connection() as conn:
        conn.execute("""
            UPDATE users SET username = ?, first_name = ?
            WHERE user_id = ?
        """, (username, first_name, str(user_id)))
        conn.commit()


def add_balance(user_id: str, amount: float) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, str(user_id))
        )
        conn.commit()


def cut_balance(user_id: str, amount: float) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ?",
            (amount, str(user_id))
        )
        conn.commit()


def set_welcome_bonus_claimed(user_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET welcome_bonus = 1 WHERE user_id = ?",
            (str(user_id),)
        )
        conn.commit()


def set_referred_status(user_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET referred = 1 WHERE user_id = ?",
            (str(user_id),)
        )
        conn.commit()


def increment_ref_count(referrer_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET total_refs = total_refs + 1 WHERE user_id = ?",
            (str(referrer_id),)
        )
        conn.commit()


def increment_order_count(user_id: str, amount: float) -> None:
    with get_connection() as conn:
        conn.execute("""
            UPDATE users
            SET total_orders = total_orders + 1, total_spent = total_spent + ?
            WHERE user_id = ?
        """, (amount, str(user_id)))
        conn.commit()


def get_all_user_ids() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT user_id FROM users").fetchall()
        return [row["user_id"] for row in rows]


def get_user_count() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
        return row["cnt"]


def ban_user(user_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET is_banned = 1 WHERE user_id = ?",
            (str(user_id),)
        )
        conn.commit()


def unban_user(user_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET is_banned = 0 WHERE user_id = ?",
            (str(user_id),)
        )
        conn.commit()


def is_banned(user_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT is_banned FROM users WHERE user_id = ?",
            (str(user_id),)
        ).fetchone()
        return bool(row["is_banned"]) if row else False


# ── Deposit Operations ────────────────────────────────

def create_deposit(user_id: str, method: str, package_id: int,
                   views: int, amount_bdt: float, amount_usd: float,
                   trx_id: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO deposits
            (user_id, method, package_id, views, amount_bdt, amount_usd,
             trx_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (str(user_id), method, package_id, views,
              amount_bdt, amount_usd, trx_id, time.time()))
        conn.commit()
        return cursor.lastrowid


def get_deposit(deposit_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM deposits WHERE deposit_id = ?", (deposit_id,)
        ).fetchone()
        return dict(row) if row else None


def approve_deposit(deposit_id: int, admin_note: str = "") -> dict | None:
    deposit = get_deposit(deposit_id)
    if not deposit or deposit["status"] != "pending":
        return None
    with get_connection() as conn:
        conn.execute("""
            UPDATE deposits
            SET status = 'approved', admin_note = ?, resolved_at = ?
            WHERE deposit_id = ?
        """, (admin_note, time.time(), deposit_id))
        conn.commit()
    add_balance(deposit["user_id"], deposit["views"])
    return deposit


def reject_deposit(deposit_id: int, admin_note: str = "") -> dict | None:
    deposit = get_deposit(deposit_id)
    if not deposit or deposit["status"] != "pending":
        return None
    with get_connection() as conn:
        conn.execute("""
            UPDATE deposits
            SET status = 'rejected', admin_note = ?, resolved_at = ?
            WHERE deposit_id = ?
        """, (admin_note, time.time(), deposit_id))
        conn.commit()
    return deposit


def get_pending_deposits() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM deposits WHERE status = 'pending' ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_user_deposits(user_id: str, limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM deposits WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (str(user_id), limit)
        ).fetchall()
        return [dict(row) for row in rows]


def get_total_deposits_stats() -> dict:
    with get_connection() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                SUM(CASE WHEN status = 'approved' THEN amount_bdt ELSE 0 END) as total_bdt,
                SUM(CASE WHEN status = 'approved' THEN amount_usd ELSE 0 END) as total_usd
            FROM deposits
        """).fetchone()
        return dict(row)


# ── Order Operations ──────────────────────────────────

def create_order(user_id: str, smm_order_id: str, link: str,
                 views: int) -> int:
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO orders (user_id, smm_order_id, link, views, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (str(user_id), smm_order_id, link, views, time.time()))
        conn.commit()
        return cursor.lastrowid


def get_total_orders_stats() -> dict:
    with get_connection() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(views) as total_views
            FROM orders
        """).fetchone()
        return dict(row)