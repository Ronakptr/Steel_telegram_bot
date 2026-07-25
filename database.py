import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager

from config import DB_PATH


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
            """
        )


# ---------- دسته‌بندی‌ها ----------

def add_category(name):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,)
        )
        return cur.lastrowid


def list_categories():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM categories ORDER BY name").fetchall()


def get_category(cat_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM categories WHERE id=?", (cat_id,)
        ).fetchone()


# ---------- محصولات ----------

def add_product(category_id, name, unit, price):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO products (category_id, name, unit, price, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (category_id, name, unit, price, datetime.now().isoformat()),
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
        q += " ORDER BY name"
        return conn.execute(q, params).fetchall()
        
def get_product_by_name(category_id, name):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM products WHERE category_id=? AND name=?", (category_id, name)
        ).fetchone()

def get_product(product_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM products WHERE id=?", (product_id,)
        ).fetchone()


def update_price(product_id, new_price):
    with get_conn() as conn:
        conn.execute(
            "UPDATE products SET price=?, updated_at=? WHERE id=?",
            (new_price, datetime.now().isoformat(), product_id),
        )


def set_product_active(product_id, active: bool):
    with get_conn() as conn:
        conn.execute(
            "UPDATE products SET is_active=? WHERE id=?",
            (1 if active else 0, product_id),
        )


def delete_product(product_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM products WHERE id=?", (product_id,))


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
