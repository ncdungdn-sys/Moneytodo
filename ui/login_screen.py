"""
Login screen – free-text password authentication.
On first launch: prompt user to create a password.
On subsequent launches: prompt user to enter their password.
"""
import tkinter as tk
from tkinter import messagebox
import database as db

BG = "#2C3E50"
CARD_BG = "#34495E"
ACCENT = "#3498DB"
TEXT_LIGHT = "#ECF0F1"
TEXT_DIM = "#95A5A6"
ERROR_COLOR = "#E74C3C"
FONT = ("Segoe UI", 11)
FONT_BOLD = ("Segoe UI", 11, "bold")
FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_SMALL = ("Segoe UI", 9)


class LoginScreen(tk.Toplevel):
    """
    Blocking login window shown before the main app.
    Sets self.success = True when the user authenticates or creates a password.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.success = False

        self.title("🔐 Moneytodo – Đăng Nhập")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Centre on screen
        self.update_idletasks()
        w, h = 360, 460
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._setup_mode = not db.has_password()
        self._build_ui()

        self.grab_set()
        self.transient(parent)
        self.wait_window()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=30, pady=30)

        # App logo
        tk.Label(outer, text="💰", bg=BG, font=("Segoe UI", 48)).pack(pady=(10, 4))
        tk.Label(outer, text="Moneytodo", bg=BG, fg=TEXT_LIGHT, font=FONT_TITLE).pack()
        tk.Label(outer, text="Quản Lý Chi Tiêu Gia Đình", bg=BG, fg=TEXT_DIM,
                 font=FONT_SMALL).pack(pady=(0, 24))

        if self._setup_mode:
            self._build_setup(outer)
        else:
            self._build_login(outer)

    def _build_login(self, outer):
        tk.Label(outer, text="Nhập mật khẩu", bg=BG, fg=TEXT_LIGHT,
                 font=FONT_BOLD).pack()

        self._pw_var = tk.StringVar()
        self._pw_entry = tk.Entry(
            outer, textvariable=self._pw_var, show="●",
            font=("Segoe UI", 14), width=20,
            justify="center", bd=0, relief="flat",
            bg=CARD_BG, fg=TEXT_LIGHT, insertbackground=TEXT_LIGHT,
        )
        self._pw_entry.pack(pady=16, ipady=10)
        self._pw_entry.bind("<Return>", lambda _: self._do_login())
        self._pw_entry.focus_set()

        self._error_lbl = tk.Label(outer, text="", bg=BG, fg=ERROR_COLOR, font=FONT_SMALL)
        self._error_lbl.pack()

        btn = tk.Button(
            outer, text="Đăng Nhập", command=self._do_login,
            bg=ACCENT, fg="white", font=FONT_BOLD,
            relief="flat", cursor="hand2", padx=24, pady=10,
        )
        btn.pack(pady=16, fill="x")

    def _build_setup(self, outer):
        tk.Label(outer, text="Tạo mật khẩu mới", bg=BG, fg=TEXT_LIGHT,
                 font=FONT_BOLD).pack()
        tk.Label(outer, text="(Chỉ nhập lần đầu tiên)", bg=BG, fg=TEXT_DIM,
                 font=FONT_SMALL).pack(pady=(0, 8))

        self._pw_var = tk.StringVar()
        self._pw_entry = tk.Entry(
            outer, textvariable=self._pw_var, show="●",
            font=("Segoe UI", 14), width=20,
            justify="center", bd=0, relief="flat",
            bg=CARD_BG, fg=TEXT_LIGHT, insertbackground=TEXT_LIGHT,
        )
        self._pw_entry.pack(pady=10, ipady=10)
        self._pw_entry.focus_set()

        tk.Label(outer, text="Xác nhận mật khẩu", bg=BG, fg=TEXT_LIGHT, font=FONT).pack()
        self._confirm_var = tk.StringVar()
        self._confirm_entry = tk.Entry(
            outer, textvariable=self._confirm_var, show="●",
            font=("Segoe UI", 14), width=20,
            justify="center", bd=0, relief="flat",
            bg=CARD_BG, fg=TEXT_LIGHT, insertbackground=TEXT_LIGHT,
        )
        self._confirm_entry.pack(pady=10, ipady=10)
        self._confirm_entry.bind("<Return>", lambda _: self._do_setup())

        self._error_lbl = tk.Label(outer, text="", bg=BG, fg=ERROR_COLOR, font=FONT_SMALL)
        self._error_lbl.pack()

        btn = tk.Button(
            outer, text="Tạo Mật Khẩu", command=self._do_setup,
            bg=ACCENT, fg="white", font=FONT_BOLD,
            relief="flat", cursor="hand2", padx=24, pady=10,
        )
        btn.pack(pady=12, fill="x")

    # ── Actions ────────────────────────────────────────────────────────────────

    def _do_login(self):
        pw = self._pw_var.get()
        if not pw:
            self._error_lbl.config(text="Vui lòng nhập mật khẩu.")
            return
        if db.check_password(pw):
            self.success = True
            self.destroy()
        else:
            self._error_lbl.config(text="Mật khẩu không đúng. Thử lại.")
            self._pw_var.set("")
            self._pw_entry.focus_set()

    def _do_setup(self):
        pw = self._pw_var.get()
        confirm = self._confirm_var.get()
        if not pw:
            self._error_lbl.config(text="Mật khẩu không được để trống.")
            return
        if pw != confirm:
            self._error_lbl.config(text="Hai mật khẩu không khớp.")
            self._confirm_var.set("")
            self._confirm_entry.focus_set()
            return
        db.set_password(pw)
        self.success = True
        self.destroy()

    def _on_close(self):
        """Closing without authenticating exits the application."""
        self.parent.destroy()

