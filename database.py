"""
Database module for Moneytodo - Family Expense Manager
Handles SQLite database creation, connection and CRUD operations.
"""
import sqlite3
import os
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "moneytodo.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they don't exist and seed default categories."""
    conn = get_connection()
    c = conn.cursor()

    # Categories table (parent and child)
    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
            type TEXT CHECK(type IN ('income', 'expense')),
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # Daily income/expense table
    c.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL CHECK(type IN ('income','expense')),
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            subcategory_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            amount REAL NOT NULL,
            description TEXT,
            expense_date TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # Fixed planned expenses
    c.execute("""
        CREATE TABLE IF NOT EXISTS planned_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            is_saved INTEGER DEFAULT 0,
            note TEXT,
            month TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # Todo reminders
    c.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            note TEXT,
            remind_date TEXT NOT NULL,
            is_done INTEGER DEFAULT 0,
            notified INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    conn.commit()
    _migrate_db(conn)
    _seed_default_categories(conn)
    conn.close()


def _migrate_db(conn):
    """Run schema migrations on existing databases."""
    c = conn.cursor()

    # Migration: add type column to categories if missing
    c.execute("PRAGMA table_info(categories)")
    cols = [row[1] for row in c.fetchall()]
    if "type" not in cols:
        c.execute("ALTER TABLE categories ADD COLUMN type TEXT CHECK(type IN ('income', 'expense'))")
        # Mark the old "Thu nhập" parent and its children as income
        c.execute(
            "UPDATE categories SET type='income' WHERE parent_id IS NULL AND name='Thu nhập'"
        )
        c.execute("""
            UPDATE categories SET type='income'
            WHERE parent_id IN (
                SELECT id FROM categories WHERE name='Thu nhập' AND parent_id IS NULL
            )
        """)
        # Everything else becomes expense
        c.execute("UPDATE categories SET type='expense' WHERE type IS NULL")
        # Add the new income top-level categories that didn't exist before
        for name in ("Kinh doanh", "Thưởng", "Khoản khác"):
            c.execute(
                "SELECT id FROM categories WHERE name=? AND parent_id IS NULL AND type='income'",
                (name,),
            )
            if not c.fetchone():
                c.execute(
                    "INSERT INTO categories (name, parent_id, type) VALUES (?, NULL, 'income')",
                    (name,),
                )
        conn.commit()


def _seed_default_categories(conn):
    """Insert default categories if table is empty."""
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM categories WHERE parent_id IS NULL")
    if c.fetchone()[0] > 0:
        return

    expense_parents = {
        "Ăn uống": ["Ăn sáng", "Ăn trưa", "Ăn tối", "Ăn ngoài", "Đồ uống"],
        "Giáo dục": ["Học phí", "Sách vở", "Học thêm"],
        "Xe cộ": ["Xăng dầu", "Sửa chữa", "Bảo dưỡng", "Đăng kiểm"],
        "Điện nước": ["Tiền điện", "Tiền nước", "Internet", "Điện thoại"],
        "Y tế": ["Khám bệnh", "Thuốc men", "Bảo hiểm"],
        "Giải trí": ["Du lịch", "Phim ảnh", "Thể thao"],
        "Mua sắm": ["Quần áo", "Đồ gia dụng", "Thực phẩm"],
        "Khác": [],
    }
    income_parents = {
        "Kinh doanh": [],
        "Thưởng": [],
        "Khoản khác": [],
    }

    for name in sorted(expense_parents):
        c.execute(
            "INSERT INTO categories (name, parent_id, type) VALUES (?, NULL, 'expense')",
            (name,),
        )
        parent_id = c.lastrowid
        for child in sorted(expense_parents[name]):
            c.execute(
                "INSERT INTO categories (name, parent_id, type) VALUES (?, ?, 'expense')",
                (child, parent_id),
            )

    for name in sorted(income_parents):
        c.execute(
            "INSERT INTO categories (name, parent_id, type) VALUES (?, NULL, 'income')",
            (name,),
        )
        parent_id = c.lastrowid
        for child in sorted(income_parents[name]):
            c.execute(
                "INSERT INTO categories (name, parent_id, type) VALUES (?, ?, 'income')",
                (child, parent_id),
            )

    conn.commit()


# ─── Category CRUD ────────────────────────────────────────────────────────────

def get_categories(parent_id=None, type_filter=None):
    """Return list of categories. parent_id=None → root categories.
    type_filter='income'|'expense' → filter root categories by type."""
    conn = get_connection()
    c = conn.cursor()
    if parent_id is None:
        if type_filter:
            c.execute(
                "SELECT * FROM categories WHERE parent_id IS NULL AND type=? ORDER BY name COLLATE NOCASE",
                (type_filter,),
            )
        else:
            c.execute(
                "SELECT * FROM categories WHERE parent_id IS NULL ORDER BY name COLLATE NOCASE"
            )
    else:
        c.execute(
            "SELECT * FROM categories WHERE parent_id=? ORDER BY name COLLATE NOCASE",
            (parent_id,),
        )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def add_category(name, parent_id=None, type_=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO categories (name, parent_id, type) VALUES (?, ?, ?)",
        (name, parent_id, type_),
    )
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id


def update_category(cat_id, name, type_=None):
    conn = get_connection()
    if type_ is not None:
        conn.execute(
            "UPDATE categories SET name=?, type=? WHERE id=?", (name, type_, cat_id)
        )
    else:
        conn.execute("UPDATE categories SET name=? WHERE id=?", (name, cat_id))
    conn.commit()
    conn.close()


def delete_category(cat_id):
    conn = get_connection()
    conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    conn.commit()
    conn.close()


# ─── Expense CRUD ─────────────────────────────────────────────────────────────

def get_expenses(month=None, type_filter=None):
    """
    Fetch expenses, optionally filtered by month (YYYY-MM) and/or type.
    Returns list of dicts with joined category names.
    """
    conn = get_connection()
    c = conn.cursor()
    query = """
        SELECT e.id, e.type, e.amount, e.description, e.expense_date,
               cat.name AS category_name,
               sub.name AS subcategory_name,
               e.category_id, e.subcategory_id
        FROM expenses e
        LEFT JOIN categories cat ON e.category_id = cat.id
        LEFT JOIN categories sub ON e.subcategory_id = sub.id
        WHERE 1=1
    """
    params = []
    if month:
        query += " AND strftime('%Y-%m', e.expense_date) = ?"
        params.append(month)
    if type_filter:
        query += " AND e.type = ?"
        params.append(type_filter)
    query += " ORDER BY e.expense_date DESC, e.id DESC"
    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def add_expense(type_, category_id, subcategory_id, amount, description, expense_date):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO expenses (type, category_id, subcategory_id, amount, description, expense_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (type_, category_id, subcategory_id, amount, description, expense_date),
    )
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id


def update_expense(exp_id, type_, category_id, subcategory_id, amount, description, expense_date):
    conn = get_connection()
    conn.execute(
        """UPDATE expenses SET type=?, category_id=?, subcategory_id=?,
           amount=?, description=?, expense_date=? WHERE id=?""",
        (type_, category_id, subcategory_id, amount, description, expense_date, exp_id),
    )
    conn.commit()
    conn.close()


def delete_expense(exp_id):
    conn = get_connection()
    conn.execute("DELETE FROM expenses WHERE id=?", (exp_id,))
    conn.commit()
    conn.close()


def get_monthly_summary(month):
    """Return total income and total expense for a given month (YYYY-MM)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT type, SUM(amount) as total FROM expenses
           WHERE strftime('%Y-%m', expense_date) = ?
           GROUP BY type""",
        (month,),
    )
    result = {"income": 0.0, "expense": 0.0}
    for row in c.fetchall():
        result[row["type"]] = row["total"] or 0.0
    conn.close()
    return result


def get_category_summary(month):
    """Return per-category totals for a given month."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT cat.name AS category, sub.name AS subcategory,
                  e.type, SUM(e.amount) as total
           FROM expenses e
           LEFT JOIN categories cat ON e.category_id = cat.id
           LEFT JOIN categories sub ON e.subcategory_id = sub.id
           WHERE strftime('%Y-%m', e.expense_date) = ?
           GROUP BY e.category_id, e.subcategory_id, e.type
           ORDER BY cat.name COLLATE NOCASE, sub.name COLLATE NOCASE""",
        (month,),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ─── Planned Expense CRUD ─────────────────────────────────────────────────────

def get_planned_expenses(month=None):
    conn = get_connection()
    c = conn.cursor()
    if month:
        c.execute(
            "SELECT * FROM planned_expenses WHERE month=? ORDER BY name COLLATE NOCASE",
            (month,),
        )
    else:
        c.execute("SELECT * FROM planned_expenses ORDER BY month DESC, name COLLATE NOCASE")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def add_planned_expense(name, amount, month, note=""):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO planned_expenses (name, amount, month, note) VALUES (?, ?, ?, ?)",
        (name, amount, month, note),
    )
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id


def update_planned_expense(pe_id, name, amount, note):
    conn = get_connection()
    conn.execute(
        "UPDATE planned_expenses SET name=?, amount=?, note=? WHERE id=?",
        (name, amount, note, pe_id),
    )
    conn.commit()
    conn.close()


def toggle_planned_saved(pe_id):
    conn = get_connection()
    conn.execute(
        "UPDATE planned_expenses SET is_saved = CASE WHEN is_saved=1 THEN 0 ELSE 1 END WHERE id=?",
        (pe_id,),
    )
    conn.commit()
    conn.close()


def delete_planned_expense(pe_id):
    conn = get_connection()
    conn.execute("DELETE FROM planned_expenses WHERE id=?", (pe_id,))
    conn.commit()
    conn.close()


# ─── Reminder CRUD ────────────────────────────────────────────────────────────

def get_reminders():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM reminders ORDER BY remind_date ASC, id ASC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_pending_reminders(today):
    """Return reminders due today that haven't been notified yet."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM reminders WHERE remind_date=? AND notified=0 AND is_done=0",
        (today,),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def add_reminder(title, note, remind_date):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO reminders (title, note, remind_date) VALUES (?, ?, ?)",
        (title, note, remind_date),
    )
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id


def update_reminder(rem_id, title, note, remind_date):
    conn = get_connection()
    conn.execute(
        "UPDATE reminders SET title=?, note=?, remind_date=? WHERE id=?",
        (title, note, remind_date, rem_id),
    )
    conn.commit()
    conn.close()


def mark_reminder_notified(rem_id):
    conn = get_connection()
    conn.execute("UPDATE reminders SET notified=1 WHERE id=?", (rem_id,))
    conn.commit()
    conn.close()


def toggle_reminder_done(rem_id):
    conn = get_connection()
    conn.execute(
        "UPDATE reminders SET is_done = CASE WHEN is_done=1 THEN 0 ELSE 1 END WHERE id=?",
        (rem_id,),
    )
    conn.commit()
    conn.close()


def delete_reminder(rem_id):
    conn = get_connection()
    conn.execute("DELETE FROM reminders WHERE id=?", (rem_id,))
    conn.commit()
    conn.close()
