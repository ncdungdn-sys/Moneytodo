"""
Moneytodo – Family Expense Manager
Main application entry point with Tkinter dashboard.

Run:
    python main.py
"""
import tkinter as tk
from tkinter import ttk
from datetime import date
import sys
import os

# Ensure the project root is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db
from ui.expenses_tab import ExpensesFrame
from ui.categories_tab import CategoriesFrame
from ui.planned_tab import PlannedExpensesFrame
from ui.reminders_tab import RemindersFrame
from ui.reports_tab import ReportsFrame
from ui.exercise_reminder_tab import ExerciseReminderFrame
from ui.login_screen import LoginScreen
from ui.passwords_tab import PasswordsFrame
from utils.exercise_reminder import start_monitor

# ── Colour palette ───────────────────────────────────────────────────────────
BG = "#F0F4F8"
HEADER_BG = "#2C3E50"
SIDEBAR_BG = "#34495E"
CARD_BG = "#FFFFFF"
ACCENT = "#3498DB"
INCOME_COLOR = "#27AE60"
EXPENSE_COLOR = "#E74C3C"
TEXT_DARK = "#2C3E50"
TEXT_LIGHT = "#ECF0F1"
SIDEBAR_HOVER = "#2C3E50"
SELECTED_TAB = "#3498DB"

FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADER = ("Segoe UI", 14, "bold")
FONT_TITLE = ("Segoe UI", 18, "bold")


class MoneytodoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("💰 Moneytodo – Quản Lý Chi Tiêu Gia Đình")
        self.geometry("1100x700")
        self.minsize(900, 580)
        self.configure(bg=BG)

        # Apply ttk styles
        self._apply_styles()

        # Init database first (needed for login)
        db.init_db()

        # Show login screen – exits app if user closes without authenticating
        login = LoginScreen(self)
        if not login.success:
            self.destroy()
            return

        # Start exercise reminder background monitor
        start_monitor()

        # Build layout
        self._build_header()
        self._build_main()

        # Start on Expenses tab
        self._show_tab("expenses")

    # ── Styles ───────────────────────────────────────────────────────────────

    def _apply_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TNotebook", background=BG)
        style.configure("TNotebook.Tab", font=FONT_BOLD, padding=[12, 6])

        style.configure("TButton", font=FONT, padding=6)
        style.configure("Accent.TButton", font=FONT_BOLD, foreground="white", background=ACCENT)

        style.configure("Treeview", font=FONT, rowheight=26, background=CARD_BG, fieldbackground=CARD_BG)
        style.configure("Treeview.Heading", font=FONT_BOLD, background=HEADER_BG, foreground=TEXT_LIGHT)
        style.map("Treeview", background=[("selected", ACCENT)])

        style.configure("TEntry", font=FONT)
        style.configure("TCombobox", font=FONT)

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        header = tk.Frame(self, bg=HEADER_BG, height=62)
        header.pack(fill="x")
        header.pack_propagate(False)

        # App icon + title
        tk.Label(
            header, text="💰 Moneytodo",
            bg=HEADER_BG, fg=TEXT_LIGHT, font=FONT_TITLE
        ).pack(side="left", padx=20, pady=10)

        # Date display
        today_str = date.today().strftime("%d/%m/%Y")
        tk.Label(
            header, text=f"📅 {today_str}",
            bg=HEADER_BG, fg=TEXT_LIGHT, font=FONT
        ).pack(side="right", padx=20)

    # ── Main area (sidebar + content) ─────────────────────────────────────────

    def _build_main(self):
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True)

        # ── Sidebar ───────────────────────────────────────────────────────
        sidebar = tk.Frame(main, bg=SIDEBAR_BG, width=190)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="MENU", bg=SIDEBAR_BG, fg="#95A5A6",
                 font=("Segoe UI", 9, "bold")).pack(pady=(16, 4), padx=16, anchor="w")

        nav_items = [
            ("expenses",  "💸 Thu Chi Hàng Ngày"),
            ("categories","🗂️ Quản Lý Danh Mục"),
            ("planned",   "📋 Dự Chi Cố Định"),
            ("reminders", "🔔 Ghi Chú & Nhắc Nhở"),
            ("reports",   "📊 Báo Cáo"),
            ("exercise",  "🏋️ Tập Thể Dục"),
            ("passwords", "🔒 Quản Lý Mật Khẩu"),
        ]
        self._nav_buttons = {}
        for tab_id, label in nav_items:
            btn = tk.Button(
                sidebar, text=label, anchor="w",
                bg=SIDEBAR_BG, fg=TEXT_LIGHT,
                font=FONT, relief="flat",
                padx=16, pady=10,
                cursor="hand2",
                activebackground=SELECTED_TAB, activeforeground="white",
                command=lambda t=tab_id: self._show_tab(t),
            )
            btn.pack(fill="x")
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=SIDEBAR_HOVER) if b.cget("bg") != SELECTED_TAB else None)
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=SIDEBAR_BG) if b.cget("bg") != SELECTED_TAB else None)
            self._nav_buttons[tab_id] = btn

        # ── Content area ──────────────────────────────────────────────────
        self._content = tk.Frame(main, bg=BG)
        self._content.pack(side="left", fill="both", expand=True)

        # Build all tab frames (lazy-hidden)
        self._frames = {
            "expenses":   ExpensesFrame(self._content),
            "categories": CategoriesFrame(self._content),
            "planned":    PlannedExpensesFrame(self._content),
            "reminders":  RemindersFrame(self._content),
            "reports":    ReportsFrame(self._content),
            "exercise":   ExerciseReminderFrame(self._content),
            "passwords":  PasswordsFrame(self._content),
        }
        for frame in self._frames.values():
            frame.place(relwidth=1, relheight=1)

    # ── Tab switching ─────────────────────────────────────────────────────────

    def _show_tab(self, tab_id):
        prev_tab = getattr(self, "_active_tab", None)

        # Lock the password manager session when the user leaves that tab
        if prev_tab == "passwords" and tab_id != "passwords":
            self._frames["passwords"].lock_session()

        # For the passwords tab, authentication must succeed before switching
        if tab_id == "passwords":
            if not self._frames["passwords"].request_access():
                # Authentication cancelled or failed – stay on current tab
                return

        self._active_tab = tab_id
        for tid, frame in self._frames.items():
            if tid == tab_id:
                frame.lift()
            else:
                frame.lower()
        for tid, btn in self._nav_buttons.items():
            if tid == tab_id:
                btn.config(bg=SELECTED_TAB, fg="white")
            else:
                btn.config(bg=SIDEBAR_BG, fg=TEXT_LIGHT)

        # Refresh the shown tab
        if hasattr(self._frames[tab_id], "load_data"):
            self._frames[tab_id].load_data()


def main():
    app = MoneytodoApp()
    app.mainloop()


if __name__ == "__main__":
    main()
