"""
Database module for Moneytodo - Family Expense Manager
Handles SQLite database creation, connection and CRUD operations.
"""
import re
import sqlite3
import os
import sys
import hashlib
from datetime import datetime


def _get_db_path():
    """Return the path to the SQLite database file.

    When running as a PyInstaller frozen executable, ``__file__`` resolves
    to a temporary extraction directory that changes on every launch.  In
    that case we place the database next to the actual ``.exe`` so that data
    (including the saved password hash) persists between runs.
    """
    if getattr(sys, "frozen", False):
        # Running inside a PyInstaller bundle – use the directory that
        # contains the .exe file, not the temp extraction folder.
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "moneytodo.db")


DB_PATH = _get_db_path()


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
            remind_time TEXT,
            is_done INTEGER DEFAULT 0,
            notified INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # App settings (key-value store)
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    conn.commit()
    _migrate_db(conn)
    _seed_default_categories(conn)
    _create_exercise_tables(conn)
    _create_password_tables(conn)
    _create_contact_tables(conn)
    conn.close()


def _create_exercise_tables(conn):
    """Create exercise reminder system tables."""
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS exercise_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_name TEXT NOT NULL,
            description TEXT,
            interval_minutes INTEGER DEFAULT 30,
            is_enabled INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS exercise_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            mode TEXT NOT NULL,
            interval_minutes INTEGER DEFAULT 30,
            is_active INTEGER DEFAULT 0,
            auto_stop_hours INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS exercise_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES exercise_sessions(id) ON DELETE CASCADE,
            exercise_name TEXT NOT NULL,
            exercise_time TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    conn.commit()

    # Seed default exercises if table is empty
    c.execute("SELECT COUNT(*) FROM exercise_reminders")
    if c.fetchone()[0] == 0:
        defaults = [
            ("1-Tập vai", "Shoulder exercises", 30, 1),
            ("2-Tập lưng", "Back exercises", 30, 2),
            ("3-Hít đất", "Push-ups", 30, 3),
            ("4-Hít xà", "Pull-ups", 30, 4),
            ("5-Stretching", "Flexibility", 30, 5),
            ("6-Chạy bộ tại chỗ", "Jogging in place", 30, 6),
        ]
        for name, desc, interval, sort_ord in defaults:
            c.execute(
                "INSERT INTO exercise_reminders (exercise_name, description, interval_minutes, sort_order) VALUES (?, ?, ?, ?)",
                (name, desc, interval, sort_ord),
            )
        conn.commit()


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

    # Migration: add remind_time column to reminders if missing
    c.execute("PRAGMA table_info(reminders)")
    rem_cols = [row[1] for row in c.fetchall()]
    if "remind_time" not in rem_cols:
        c.execute("ALTER TABLE reminders ADD COLUMN remind_time TEXT")
        conn.commit()

    # Migration: create settings table if missing
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()

    # Migration: add sort_order column to exercise_reminders if missing
    c.execute("PRAGMA table_info(exercise_reminders)")
    ex_cols = [row[1] for row in c.fetchall()]
    if ex_cols and "sort_order" not in ex_cols:
        c.execute("ALTER TABLE exercise_reminders ADD COLUMN sort_order INTEGER DEFAULT 0")
        conn.commit()

    # Migration: add is_active column to exercise_reminders if missing
    c.execute("PRAGMA table_info(exercise_reminders)")
    ex_cols = [row[1] for row in c.fetchall()]
    if ex_cols and "is_active" not in ex_cols:
        c.execute("ALTER TABLE exercise_reminders ADD COLUMN is_active INTEGER DEFAULT 1")
        conn.commit()

    # Migration: add detail column and make password nullable in passwords table
    c.execute("PRAGMA table_info(passwords)")
    pw_col_rows = c.fetchall()
    if pw_col_rows:
        pw_col_names = [row[1] for row in pw_col_rows]
        if "detail" not in pw_col_names:
            # Recreate the passwords table with detail column and nullable password
            c.execute("ALTER TABLE passwords RENAME TO passwords_old")
            c.execute("""
                CREATE TABLE passwords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    detail TEXT,
                    account_name TEXT NOT NULL,
                    password TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    updated_at TEXT DEFAULT (datetime('now','localtime'))
                )
            """)
            # Only copy columns that exist in the old table
            old_has_timestamps = "created_at" in pw_col_names
            if old_has_timestamps:
                c.execute("""
                    INSERT INTO passwords (id, category, detail, account_name, password, notes, created_at, updated_at)
                    SELECT id, category, NULL, account_name, password, notes, created_at, updated_at
                    FROM passwords_old
                """)
            else:
                c.execute("""
                    INSERT INTO passwords (id, category, detail, account_name, password, notes)
                    SELECT id, category, NULL, account_name, password, notes
                    FROM passwords_old
                """)
            c.execute("DROP TABLE passwords_old")
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
    c.execute("SELECT * FROM reminders ORDER BY remind_date ASC, remind_time ASC, id ASC")
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


def add_reminder(title, note, remind_date, remind_time=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO reminders (title, note, remind_date, remind_time) VALUES (?, ?, ?, ?)",
        (title, note, remind_date, remind_time),
    )
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id


def update_reminder(rem_id, title, note, remind_date, remind_time=None):
    conn = get_connection()
    conn.execute(
        "UPDATE reminders SET title=?, note=?, remind_date=?, remind_time=?, notified=0 WHERE id=?",
        (title, note, remind_date, remind_time, rem_id),
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


# ─── Settings / Password ──────────────────────────────────────────────────────

def get_setting(key):
    """Return the value for a settings key, or None if not set."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else None


def set_setting(key, value):
    """Insert or update a settings key-value pair."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def hash_password(password):
    """Return SHA-256 hex digest of a password string."""
    return hashlib.sha256(password.encode()).hexdigest()


def check_password(password):
    """Return True if password matches the stored password hash."""
    stored = get_setting("password_hash")
    if stored is None:
        return False
    return stored == hash_password(password)


def has_password():
    """Return True if a password has been set."""
    return get_setting("password_hash") is not None


def set_password(password):
    """Store a new hashed password."""
    set_setting("password_hash", hash_password(password))


# ─── Report queries ───────────────────────────────────────────────────────────

def get_expenses_range(from_date, to_date, type_filter=None):
    """Fetch expenses between from_date and to_date (inclusive, YYYY-MM-DD)."""
    conn = get_connection()
    c = conn.cursor()
    query = """
        SELECT e.id, e.type, e.amount, e.description, e.expense_date,
               cat.name AS category_name,
               sub.name AS subcategory_name
        FROM expenses e
        LEFT JOIN categories cat ON e.category_id = cat.id
        LEFT JOIN categories sub ON e.subcategory_id = sub.id
        WHERE e.expense_date >= ? AND e.expense_date <= ?
    """
    params = [from_date, to_date]
    if type_filter:
        query += " AND e.type = ?"
        params.append(type_filter)
    query += " ORDER BY e.expense_date ASC, e.id ASC"
    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_summary_range(from_date, to_date):
    """Return total income and expense between from_date and to_date."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT type, SUM(amount) as total FROM expenses
           WHERE expense_date >= ? AND expense_date <= ?
           GROUP BY type""",
        (from_date, to_date),
    )
    result = {"income": 0.0, "expense": 0.0}
    for row in c.fetchall():
        result[row["type"]] = row["total"] or 0.0
    conn.close()
    return result


def get_daily_totals_range(from_date, to_date):
    """Return per-day income/expense totals between from_date and to_date."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT expense_date, type, SUM(amount) as total
           FROM expenses
           WHERE expense_date >= ? AND expense_date <= ?
           GROUP BY expense_date, type
           ORDER BY expense_date ASC""",
        (from_date, to_date),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_category_totals_range(from_date, to_date, type_filter="expense"):
    """Return per-category totals (expense by default) between from_date and to_date."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT cat.name AS category, SUM(e.amount) as total
           FROM expenses e
           LEFT JOIN categories cat ON e.category_id = cat.id
           WHERE e.expense_date >= ? AND e.expense_date <= ? AND e.type = ?
           GROUP BY e.category_id
           ORDER BY total DESC""",
        (from_date, to_date, type_filter),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_daily_summary(expense_date):
    """Get income, expense, and category breakdown for a specific date.

    Returns a dict:
        {
            'date': '2026-04-05',
            'income': 500000.0,
            'expense': 125187.0,
            'categories': [{'category': 'Ăn uống', 'total': 87000.0}, ...]
        }
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT type, SUM(amount) as total FROM expenses WHERE expense_date=? GROUP BY type",
        (expense_date,),
    )
    result = {"date": expense_date, "income": 0.0, "expense": 0.0, "categories": []}
    for row in c.fetchall():
        result[row["type"]] = row["total"] or 0.0
    c.execute(
        """SELECT cat.name AS category, SUM(e.amount) as total
           FROM expenses e
           LEFT JOIN categories cat ON e.category_id = cat.id
           WHERE e.expense_date = ? AND e.type = 'expense'
           GROUP BY e.category_id
           ORDER BY total DESC""",
        (expense_date,),
    )
    result["categories"] = [dict(r) for r in c.fetchall()]
    conn.close()
    return result


def get_daily_summaries_range(from_date, to_date):
    """Get daily summaries for all dates in a range, ordered by date DESC.

    Returns a list of dicts, each as returned by get_daily_summary().
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT DISTINCT expense_date FROM expenses
           WHERE expense_date >= ? AND expense_date <= ?
           ORDER BY expense_date DESC""",
        (from_date, to_date),
    )
    dates = [row["expense_date"] for row in c.fetchall()]
    conn.close()
    return [get_daily_summary(d) for d in dates]


# ─── Exercise Reminder CRUD ───────────────────────────────────────────────────

def _extract_leading_number(text):
    """Extract leading integer from a string; returns float('inf') if none."""
    match = re.match(r'^(\d+)', text)
    return int(match.group(1)) if match else float('inf')


def get_exercise_reminders():
    """Get all exercise reminders ordered by id (insertion order)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM exercise_reminders ORDER BY id ASC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_exercises_sorted():
    """Get all exercises sorted by numeric prefix first, then alphabetically."""
    rows = get_exercise_reminders()
    rows.sort(key=lambda x: (_extract_leading_number(x['exercise_name']), x['exercise_name']))
    return rows


def add_exercise_reminder(name, description, interval_minutes=30, sort_order=None):
    """Add new exercise reminder."""
    conn = get_connection()
    c = conn.cursor()
    if sort_order is None:
        c.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM exercise_reminders")
        sort_order = c.fetchone()[0]
    c.execute(
        "INSERT INTO exercise_reminders (exercise_name, description, interval_minutes, sort_order) VALUES (?, ?, ?, ?)",
        (name, description, interval_minutes, sort_order),
    )
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id


def update_exercise_reminder(rem_id, name, description, interval_minutes, sort_order=None):
    """Update exercise reminder."""
    conn = get_connection()
    if sort_order is not None:
        conn.execute(
            "UPDATE exercise_reminders SET exercise_name=?, description=?, interval_minutes=?, sort_order=? WHERE id=?",
            (name, description, interval_minutes, sort_order, rem_id),
        )
    else:
        conn.execute(
            "UPDATE exercise_reminders SET exercise_name=?, description=?, interval_minutes=? WHERE id=?",
            (name, description, interval_minutes, rem_id),
        )
    conn.commit()
    conn.close()


def toggle_exercise_reminder_enabled(rem_id):
    """Toggle is_enabled for an exercise reminder."""
    conn = get_connection()
    conn.execute(
        "UPDATE exercise_reminders SET is_enabled = CASE WHEN is_enabled=1 THEN 0 ELSE 1 END WHERE id=?",
        (rem_id,),
    )
    conn.commit()
    conn.close()


def delete_exercise_reminder(rem_id):
    """Delete exercise reminder."""
    conn = get_connection()
    conn.execute("DELETE FROM exercise_reminders WHERE id=?", (rem_id,))
    conn.commit()
    conn.close()


def start_exercise_session(mode="on_demand", interval_minutes=30, auto_stop_hours=None):
    """Start new exercise session. Returns session_id."""
    conn = get_connection()
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    start_time = datetime.now().strftime("%H:%M:%S")
    c.execute(
        """INSERT INTO exercise_sessions
           (session_date, start_time, mode, interval_minutes, is_active, auto_stop_hours)
           VALUES (?, ?, ?, ?, 1, ?)""",
        (today, start_time, mode, interval_minutes, auto_stop_hours),
    )
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id


def stop_exercise_session(session_id):
    """Stop exercise session."""
    conn = get_connection()
    end_time = datetime.now().strftime("%H:%M:%S")
    conn.execute(
        "UPDATE exercise_sessions SET is_active=0, end_time=? WHERE id=?",
        (end_time, session_id),
    )
    conn.commit()
    conn.close()


def get_active_session(today_date):
    """Get active session for today."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM exercise_sessions WHERE session_date=? AND is_active=1 ORDER BY id DESC LIMIT 1",
        (today_date,),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def add_exercise_history(session_id, exercise_name, exercise_time, status):
    """Log exercise activity. status: 'completed'|'skipped'|'pending'."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO exercise_history (session_id, exercise_name, exercise_time, status) VALUES (?, ?, ?, ?)",
        (session_id, exercise_name, exercise_time, status),
    )
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id


def get_exercise_history_today(session_id):
    """Get today's exercise history for a session."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM exercise_history WHERE session_id=? ORDER BY id ASC",
        (session_id,),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_exercise_stats_today(session_id):
    """Get stats: total_reminders, completed, skipped."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT status, COUNT(*) as cnt FROM exercise_history
           WHERE session_id=? GROUP BY status""",
        (session_id,),
    )
    stats = {"total": 0, "completed": 0, "skipped": 0, "pending": 0}
    for row in c.fetchall():
        stats[row["status"]] = row["cnt"]
    stats["total"] = stats["completed"] + stats["skipped"] + stats["pending"]
    conn.close()
    return stats


def toggle_exercise_active(exercise_id):
    """Toggle is_active status for an exercise (1→0 or 0→1). Returns new state."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT is_active FROM exercise_reminders WHERE id=?", (exercise_id,))
    row = c.fetchone()
    if row is None:
        conn.close()
        return None
    new_state = 0 if row["is_active"] else 1
    conn.execute("UPDATE exercise_reminders SET is_active=? WHERE id=?", (new_state, exercise_id))
    conn.commit()
    conn.close()
    return new_state


def set_exercise_active(exercise_id, state):
    """Set is_active for a single exercise. state: 1 (active) or 0 (inactive)."""
    conn = get_connection()
    conn.execute(
        "UPDATE exercise_reminders SET is_active=? WHERE id=?",
        (1 if state else 0, exercise_id),
    )
    conn.commit()
    conn.close()


def set_all_exercises_active(state):
    """Set is_active for all exercises. state: 1 (active) or 0 (inactive)."""
    conn = get_connection()
    conn.execute("UPDATE exercise_reminders SET is_active=?", (1 if state else 0,))
    conn.commit()
    conn.close()


def get_active_exercises():
    """Get only exercises where is_active = 1, sorted."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM exercise_reminders WHERE is_active=1 ORDER BY id ASC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    rows.sort(key=lambda x: (_extract_leading_number(x['exercise_name']), x['exercise_name']))
    return rows


def get_all_exercises_with_status():
    """Get all exercises with is_active status, sorted."""
    return get_exercises_sorted()


def count_active_exercises():
    """Return (active_count, total_count) for exercise_reminders."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM exercise_reminders WHERE is_active=1")
    active = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM exercise_reminders")
    total = c.fetchone()[0]
    conn.close()
    return active, total


# ── Password Manager ──────────────────────────────────────────────────────────

def _create_password_tables(conn):
    """Create password manager tables."""
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS master_password (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS passwords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            detail TEXT,
            account_name TEXT NOT NULL,
            password TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    conn.commit()


def _derive_master_password_hash(password, salt_hex):
    """Derive a secure hash from the master password using PBKDF2-HMAC-SHA256.

    Uses 260,000 iterations (OWASP 2023 recommendation) with a per-user salt
    so that the hash is resistant to brute-force and rainbow-table attacks.
    Returns the hex-encoded derived key.
    """
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        260_000,
        dklen=32,
    )
    return dk.hex()


def set_master_password(password):
    """Set the master password (first time only). Returns True on success."""
    try:
        salt = os.urandom(32).hex()
        pw_hash = _derive_master_password_hash(password, salt)
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO master_password (id, password_hash, password_salt) VALUES (1, ?, ?)",
            (pw_hash, salt),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def verify_master_password(password):
    """Verify the master password against the stored hash. Returns True if correct."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT password_hash, password_salt FROM master_password WHERE id = 1")
    row = c.fetchone()
    conn.close()
    if row is None:
        return False
    candidate = _derive_master_password_hash(password, row["password_salt"])
    return candidate == row["password_hash"]


def master_password_exists():
    """Return True if a master password has already been set."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM master_password WHERE id = 1")
    count = c.fetchone()[0]
    conn.close()
    return count > 0


def add_password(category, detail, account_name, password, notes=""):
    """Add a new password entry. Returns the new row id."""
    conn = get_connection()
    try:
        _create_password_tables(conn)
        c = conn.cursor()
        c.execute(
            "INSERT INTO passwords (category, detail, account_name, password, notes) VALUES (?, ?, ?, ?, ?)",
            (category, detail or "", account_name, password or "", notes),
        )
        conn.commit()
        new_id = c.lastrowid
        print(f"[add_password] ✅ Saved: id={new_id}, account={account_name!r}")
        return new_id
    except Exception as e:
        print(f"[add_password] ❌ Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def update_password(password_id, category, detail, account_name, password, notes=""):
    """Update an existing password entry."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """UPDATE passwords
           SET category=?, detail=?, account_name=?, password=?, notes=?,
               updated_at=datetime('now','localtime')
           WHERE id=?""",
        (category, detail or "", account_name, password or "", notes, password_id),
    )
    conn.commit()
    conn.close()


def delete_password(password_id):
    """Delete a password entry."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM passwords WHERE id=?", (password_id,))
    conn.commit()
    conn.close()


def get_all_passwords():
    """Return all passwords sorted by category then account_name.

    Returns a list of tuples: (id, category, detail, account_name, password, notes).
    """
    conn = get_connection()
    try:
        _create_password_tables(conn)
        c = conn.cursor()
        c.execute(
            "SELECT id, category, detail, account_name, password, notes FROM passwords ORDER BY category, account_name"
        )
        rows = [(r["id"], r["category"], r["detail"], r["account_name"], r["password"], r["notes"]) for r in c.fetchall()]
        print(f"[get_all_passwords] ✅ Loaded {len(rows)} passwords")
        return rows
    except Exception as e:
        print(f"[get_all_passwords] ❌ Error: {e}")
        return []
    finally:
        conn.close()


def search_passwords(keyword):
    """Search passwords by account_name, detail or category (case-insensitive).

    Returns a list of tuples: (id, category, detail, account_name, password, notes).
    """
    conn = get_connection()
    c = conn.cursor()
    pattern = f"%{keyword}%"
    c.execute(
        """SELECT id, category, detail, account_name, password, notes FROM passwords
           WHERE account_name LIKE ? OR category LIKE ? OR detail LIKE ?
           ORDER BY category, account_name""",
        (pattern, pattern, pattern),
    )
    rows = [(r["id"], r["category"], r["detail"], r["account_name"], r["password"], r["notes"]) for r in c.fetchall()]
    conn.close()
    return rows


def get_password_by_id(password_id):
    """Return a single password entry as a tuple (id, category, detail, account_name, password, notes)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, category, detail, account_name, password, notes FROM passwords WHERE id=?",
        (password_id,),
    )
    row = c.fetchone()
    conn.close()
    if row is None:
        return None
    return (row["id"], row["category"], row["detail"], row["account_name"], row["password"], row["notes"])


# ─── Contacts ─────────────────────────────────────────────────────────────────

def _create_contact_tables(conn):
    """Create contacts table."""
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            phone TEXT,
            email TEXT,
            address TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()

    # Migration: add address column if missing (for existing databases)
    c.execute("PRAGMA table_info(contacts)")
    cols = [row[1] for row in c.fetchall()]
    if cols and "address" not in cols:
        c.execute("ALTER TABLE contacts ADD COLUMN address TEXT")
        conn.commit()


def add_contact(name, age=None, phone="", email="", address="", notes=""):
    """Add a new contact. name is required. Returns the new contact id."""
    name = name.strip()
    if not name:
        raise ValueError("Tên liên hệ không được để trống.")
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """INSERT INTO contacts (name, age, phone, email, address, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, age if age else None, phone or "", email or "", address or "", notes or ""),
        )
        conn.commit()
        new_id = c.lastrowid
        print(f"[add_contact] ✅ Saved: id={new_id}, name={name!r}")
        return new_id
    except Exception as e:
        print(f"[add_contact] ❌ Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def update_contact(contact_id, name, age=None, phone="", email="", address="", notes=""):
    """Update an existing contact. name is required."""
    name = name.strip()
    if not name:
        raise ValueError("Tên liên hệ không được để trống.")
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """UPDATE contacts
               SET name=?, age=?, phone=?, email=?, address=?, notes=?,
                   updated_at=datetime('now','localtime')
               WHERE id=?""",
            (name, age if age else None, phone or "", email or "", address or "", notes or "", contact_id),
        )
        conn.commit()
        print(f"[update_contact] ✅ Updated: id={contact_id}, name={name!r}")
        return True
    except Exception as e:
        print(f"[update_contact] ❌ Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_contact(contact_id):
    """Delete a contact by id."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
    conn.commit()
    conn.close()


def get_all_contacts():
    """Return all contacts sorted by name.

    Returns a list of tuples: (id, name, age, phone, email, address, notes, created_at, updated_at).
    """
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT id, name, age, phone, email, address, notes, created_at, updated_at FROM contacts ORDER BY name COLLATE NOCASE"
        )
        rows = [
            (r["id"], r["name"], r["age"], r["phone"], r["email"], r["address"], r["notes"], r["created_at"], r["updated_at"])
            for r in c.fetchall()
        ]
        print(f"[get_all_contacts] ✅ Loaded {len(rows)} contacts")
        return rows
    except Exception as e:
        print(f"[get_all_contacts] ❌ Error: {e}")
        return []
    finally:
        conn.close()


def search_contacts(query):
    """Search contacts by name, phone, email, address, or notes (case-insensitive).

    Returns a list of tuples: (id, name, age, phone, email, address, notes, created_at, updated_at).
    """
    conn = get_connection()
    c = conn.cursor()
    pattern = f"%{query}%"
    c.execute(
        """SELECT id, name, age, phone, email, address, notes, created_at, updated_at
           FROM contacts
           WHERE name LIKE ? OR phone LIKE ? OR email LIKE ? OR address LIKE ? OR notes LIKE ?
           ORDER BY name COLLATE NOCASE""",
        (pattern, pattern, pattern, pattern, pattern),
    )
    rows = [
        (r["id"], r["name"], r["age"], r["phone"], r["email"], r["address"], r["notes"], r["created_at"], r["updated_at"])
        for r in c.fetchall()
    ]
    conn.close()
    return rows


def get_contact_by_id(contact_id):
    """Return a single contact as a tuple (id, name, age, phone, email, address, notes, created_at, updated_at)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, name, age, phone, email, address, notes, created_at, updated_at FROM contacts WHERE id=?",
        (contact_id,),
    )
    row = c.fetchone()
    conn.close()
    if row is None:
        return None
    return (row["id"], row["name"], row["age"], row["phone"], row["email"], row["address"], row["notes"], row["created_at"], row["updated_at"])


# ─── Debug / Verification Helpers ────────────────────────────────────────────

def verify_contacts_table():
    """Verify the contacts table exists and return its column names."""
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("PRAGMA table_info(contacts)")
        cols = [row[1] for row in c.fetchall()]
        print(f"[verify_contacts_table] Columns: {cols}")
        return cols
    except Exception as e:
        print(f"[verify_contacts_table] ❌ Error: {e}")
        return []
    finally:
        conn.close()


def verify_passwords_table():
    """Verify the passwords table exists and return its column names."""
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("PRAGMA table_info(passwords)")
        cols = [row[1] for row in c.fetchall()]
        print(f"[verify_passwords_table] Columns: {cols}")
        return cols
    except Exception as e:
        print(f"[verify_passwords_table] ❌ Error: {e}")
        return []
    finally:
        conn.close()


def log_database_state():
    """Log row counts for contacts and passwords tables. Returns dict with counts."""
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM contacts")
        row = c.fetchone()
        contact_count = row[0] if row else 0
        c.execute("SELECT COUNT(*) FROM passwords")
        row = c.fetchone()
        pw_count = row[0] if row else 0
        print(f"[log_database_state] contacts={contact_count}, passwords={pw_count}")
        return {"contacts": contact_count, "passwords": pw_count}
    except Exception as e:
        print(f"[log_database_state] ❌ Error: {e}")
        return {"contacts": 0, "passwords": 0}
    finally:
        conn.close()
