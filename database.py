import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from config import DB_PATH


def _clean_text(value):
    """متن ورودی را برای ذخیره و مقایسه یکدست می‌کند."""
    if value is None:
        return ""
    text = str(value).replace("ي", "ی").replace("ك", "ک")
    return " ".join(text.strip().split())


@contextmanager
def get_conn():
    db_dir = os.path.dirname(os.path.abspath(DB_PATH))
    os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                unit TEXT NOT NULL DEFAULT 'کیلوگرم',
                price INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            );

            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                username TEXT,
                phone TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                items_json TEXT NOT NULL,
                total_price INTEGER NOT NULL,
                address TEXT,
                phone TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS payment_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                telegram_file_id TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                mime_type TEXT,
                status TEXT NOT NULL DEFAULT 'pending_review',
                ai_result_json TEXT,
                amount_detected INTEGER,
                tracking_number TEXT,
                admin_id INTEGER,
                admin_note TEXT,
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);
            CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);
            CREATE INDEX IF NOT EXISTS idx_receipts_order_id ON payment_receipts(order_id);
            CREATE INDEX IF NOT EXISTS idx_receipts_file_hash ON payment_receipts(file_hash);
            """
        )


# ---------- دسته‌بندی‌ها ----------

def add_category(name):
    """دسته را ایجاد می‌کند و همیشه شناسه واقعی آن را برمی‌گرداند.

    در نسخه قبلی، INSERT OR IGNORE برای دسته تکراری ممکن بود شناسه 0 برگرداند؛
    همین مسئله باعث توقف ورود اکسل بعد از اولین محصول یک دسته می‌شد.
    """
    name = _clean_text(name)
    if not name:
        raise ValueError("نام دسته‌بندی خالی است.")

    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
        row = conn.execute(
            "SELECT id FROM categories WHERE name=? COLLATE NOCASE LIMIT 1", (name,)
        ).fetchone()
        if not row:
            raise RuntimeError("شناسه دسته‌بندی ساخته یا پیدا نشد.")
        return row["id"]


def list_categories(active_products_only=False):
    with get_conn() as conn:
        if active_products_only:
            return conn.execute(
                """
                SELECT DISTINCT c.*
                FROM categories c
                JOIN products p ON p.category_id=c.id
                WHERE p.is_active=1
                ORDER BY c.name
                """
            ).fetchall()
        return conn.execute("SELECT * FROM categories ORDER BY name").fetchall()


def get_category(cat_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM categories WHERE id=?", (cat_id,)
        ).fetchone()


# ---------- محصولات ----------

def add_product(category_id, name, unit, price, is_active=True):
    name = _clean_text(name)
    unit = _clean_text(unit)
    if not name or not unit:
        raise ValueError("نام محصول و واحد نباید خالی باشند.")

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO products (category_id, name, unit, price, is_active, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                category_id,
                name,
                unit,
                int(price),
                1 if is_active else 0,
                datetime.now().isoformat(),
            ),
        )
        return cur.lastrowid


def list_products(category_id=None, active_only=True):
    with get_conn() as conn:
        q = "SELECT * FROM products WHERE 1=1"
        params = []
        if category_id is not None:
            q += " AND category_id=?"
            params.append(category_id)
        if active_only:
            q += " AND is_active=1"
        q += " ORDER BY name, id"
        return conn.execute(q, params).fetchall()


def get_product_by_name(category_id, name):
    name = _clean_text(name)
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT * FROM products
            WHERE category_id=? AND TRIM(name)=? COLLATE NOCASE
            ORDER BY id LIMIT 1
            """,
            (category_id, name),
        ).fetchone()


def get_product(product_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM products WHERE id=?", (product_id,)
        ).fetchone()


def update_product(product_id, category_id, name, unit, price):
    name = _clean_text(name)
    unit = _clean_text(unit)
    if not name or not unit:
        raise ValueError("نام محصول و واحد نباید خالی باشند.")

    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE products
            SET category_id=?, name=?, unit=?, price=?, updated_at=?
            WHERE id=?
            """,
            (
                int(category_id),
                name,
                unit,
                int(price),
                datetime.now().isoformat(),
                int(product_id),
            ),
        )
        return cur.rowcount > 0


def update_price(product_id, new_price):
    with get_conn() as conn:
        conn.execute(
            "UPDATE products SET price=?, updated_at=? WHERE id=?",
            (int(new_price), datetime.now().isoformat(), product_id),
        )


def set_product_active(product_id, active: bool):
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE products SET is_active=?, updated_at=? WHERE id=?",
            (1 if active else 0, datetime.now().isoformat(), product_id),
        )
        return cur.rowcount > 0


def delete_product(product_id):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM products WHERE id=?", (product_id,))
        return cur.rowcount > 0


def upsert_product(category_name, product_name, unit, price, is_active=None):
    """محصول اکسل را در یک تراکنش اضافه یا به‌روزرسانی می‌کند."""
    category_name = _clean_text(category_name)
    product_name = _clean_text(product_name)
    unit = _clean_text(unit)
    if not category_name or not product_name or not unit:
        raise ValueError("دسته‌بندی، نام محصول و واحد الزامی هستند.")

    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)", (category_name,)
        )
        category = conn.execute(
            "SELECT id FROM categories WHERE name=? COLLATE NOCASE LIMIT 1",
            (category_name,),
        ).fetchone()
        if not category:
            raise RuntimeError("دسته‌بندی پیدا نشد.")
        category_id = category["id"]

        existing = conn.execute(
            """
            SELECT id FROM products
            WHERE category_id=? AND TRIM(name)=? COLLATE NOCASE
            ORDER BY id LIMIT 1
            """,
            (category_id, product_name),
        ).fetchone()
        now = datetime.now().isoformat()

        if existing:
            if is_active is None:
                conn.execute(
                    """
                    UPDATE products
                    SET name=?, unit=?, price=?, updated_at=?
                    WHERE id=?
                    """,
                    (product_name, unit, int(price), now, existing["id"]),
                )
            else:
                conn.execute(
                    """
                    UPDATE products
                    SET name=?, unit=?, price=?, is_active=?, updated_at=?
                    WHERE id=?
                    """,
                    (
                        product_name,
                        unit,
                        int(price),
                        1 if is_active else 0,
                        now,
                        existing["id"],
                    ),
                )
            return "updated", existing["id"]

        cur = conn.execute(
            """
            INSERT INTO products
            (category_id, name, unit, price, is_active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                category_id,
                product_name,
                unit,
                int(price),
                1 if is_active is not False else 0,
                now,
            ),
        )
        return "added", cur.lastrowid


# ---------- کاربران ----------

def upsert_user(user_id, full_name, username, phone=None):
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT user_id FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
        if existing:
            if phone:
                conn.execute(
                    "UPDATE users SET full_name=?, username=?, phone=? WHERE user_id=?",
                    (full_name, username, phone, user_id),
                )
            else:
                conn.execute(
                    "UPDATE users SET full_name=?, username=? WHERE user_id=?",
                    (full_name, username, user_id),
                )
        else:
            conn.execute(
                "INSERT INTO users (user_id, full_name, username, phone, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, full_name, username, phone, datetime.now().isoformat()),
            )


def get_user(user_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE user_id=?", (user_id,)
        ).fetchone()


# ---------- سفارش‌ها ----------

def create_order(user_id, items, total_price, address, phone):
    """items: لیستی از دیکشنری {product_id, name, unit, price, qty}"""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO orders (user_id, items_json, total_price, address, phone, "
            "status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
            (
                user_id,
                json.dumps(items, ensure_ascii=False),
                total_price,
                address,
                phone,
                datetime.now().isoformat(),
                datetime.now().isoformat(),
            ),
        )
        return cur.lastrowid


def get_order(order_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()


def list_user_orders(user_id, limit=20):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()


def list_all_orders(status=None, limit=50):
    with get_conn() as conn:
        if status:
            return conn.execute(
                "SELECT * FROM orders WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


def update_order_status(order_id, status):
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET status=?, updated_at=? WHERE id=?",
            (status, datetime.now().isoformat(), order_id),
        )


# ---------- فیش‌های واریزی ----------

def list_unpaid_user_orders(user_id, limit=20):
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT o.* FROM orders o
            WHERE o.user_id=?
              AND o.status != 'cancelled'
              AND NOT EXISTS (
                  SELECT 1 FROM payment_receipts r
                  WHERE r.order_id=o.id AND r.status='approved'
              )
            ORDER BY o.id DESC LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()


def create_payment_receipt(order_id, user_id, telegram_file_id, file_hash, mime_type, ai_result):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO payment_receipts
            (order_id, user_id, telegram_file_id, file_hash, mime_type, status,
             ai_result_json, amount_detected, tracking_number, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending_review', ?, ?, ?, ?)""",
            (
                order_id,
                user_id,
                telegram_file_id,
                file_hash,
                mime_type,
                json.dumps(ai_result, ensure_ascii=False),
                ai_result.get("amount"),
                ai_result.get("tracking_number"),
                datetime.now().isoformat(),
            ),
        )
        return cur.lastrowid


def get_payment_receipt(receipt_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM payment_receipts WHERE id=?", (receipt_id,)
        ).fetchone()


def find_receipt_by_hash(file_hash):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM payment_receipts WHERE file_hash=? ORDER BY id DESC LIMIT 1",
            (file_hash,),
        ).fetchone()


def update_receipt_status(receipt_id, status, admin_id=None, admin_note=None):
    with get_conn() as conn:
        conn.execute(
            """UPDATE payment_receipts SET status=?, admin_id=?, admin_note=?, reviewed_at=?
               WHERE id=?""",
            (status, admin_id, admin_note, datetime.now().isoformat(), receipt_id),
        )


def get_latest_order_receipt(order_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM payment_receipts WHERE order_id=? ORDER BY id DESC LIMIT 1",
            (order_id,),
        ).fetchone()
