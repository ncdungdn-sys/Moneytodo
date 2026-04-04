"""
Login screen – 6-digit PIN authentication.
On first launch: prompt user to create a PIN.
On subsequent launches: prompt user to enter PIN.
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
    Sets self.success = True when the user authenticates or creates a PIN.
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
        w, h = 360, 480
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
        tk.Label(outer, text="Nhập mật khẩu 6 chữ số", bg=BG, fg=TEXT_LIGHT,
                 font=FONT_BOLD).pack()

        self._pin_var = tk.StringVar()
        self._pin_entry = tk.Entry(
            outer, textvariable=self._pin_var, show="●",
            font=("Segoe UI", 22, "bold"), width=10,
            justify="center", bd=0, relief="flat",
            bg=CARD_BG, fg=TEXT_LIGHT, insertbackground=TEXT_LIGHT,
        )
        self._pin_entry.pack(pady=16, ipady=10)
        self._pin_entry.bind("<Return>", lambda _: self._do_login())
        self._pin_entry.focus_set()

        self._error_lbl = tk.Label(outer, text="", bg=BG, fg=ERROR_COLOR, font=FONT_SMALL)
        self._error_lbl.pack()

        btn = tk.Button(
            outer, text="Đăng Nhập", command=self._do_login,
            bg=ACCENT, fg="white", font=FONT_BOLD,
            relief="flat", cursor="hand2", padx=24, pady=10,
        )
        btn.pack(pady=16, fill="x")

        # PIN dots display
        self._build_pin_dots(outer)
        self._pin_var.trace_add("write", self._on_pin_change)

    def _build_setup(self, outer):
        tk.Label(outer, text="Tạo mật khẩu 6 chữ số", bg=BG, fg=TEXT_LIGHT,
                 font=FONT_BOLD).pack()
        tk.Label(outer, text="(Chỉ nhập lần đầu tiên)", bg=BG, fg=TEXT_DIM,
                 font=FONT_SMALL).pack(pady=(0, 8))

        self._pin_var = tk.StringVar()
        self._pin_entry = tk.Entry(
            outer, textvariable=self._pin_var, show="●",
            font=("Segoe UI", 22, "bold"), width=10,
            justify="center", bd=0, relief="flat",
            bg=CARD_BG, fg=TEXT_LIGHT, insertbackground=TEXT_LIGHT,
        )
        self._pin_entry.pack(pady=10, ipady=10)
        self._pin_entry.focus_set()

        tk.Label(outer, text="Xác nhận mật khẩu", bg=BG, fg=TEXT_LIGHT, font=FONT).pack()
        self._confirm_var = tk.StringVar()
        self._confirm_entry = tk.Entry(
            outer, textvariable=self._confirm_var, show="●",
            font=("Segoe UI", 22, "bold"), width=10,
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

        # PIN dots display (for first entry)
        self._build_pin_dots(outer)
        self._pin_var.trace_add("write", self._on_pin_change)

    def _build_pin_dots(self, parent):
        """Row of 6 circles that fill as user types."""
        dot_frame = tk.Frame(parent, bg=BG)
        dot_frame.pack(pady=(4, 0))
        self._dot_labels = []
        for _ in range(6):
            lbl = tk.Label(dot_frame, text="○", bg=BG, fg=TEXT_DIM,
                           font=("Segoe UI", 18))
            lbl.pack(side="left", padx=4)
            self._dot_labels.append(lbl)

    def _on_pin_change(self, *_):
        pin = self._pin_var.get()
        # Enforce max 6 digits
        if len(pin) > 6:
            self._pin_var.set(pin[:6])
            return
        for i, lbl in enumerate(self._dot_labels):
            if i < len(pin):
                lbl.config(text="●", fg=ACCENT)
            else:
                lbl.config(text="○", fg=TEXT_DIM)
        # Auto-submit when 6 digits entered
        if len(pin) == 6:
            if self._setup_mode:
                self._confirm_entry.focus_set()
            else:
                self.after(120, self._do_login)

    # ── Actions ────────────────────────────────────────────────────────────────

    def _do_login(self):
        pin = self._pin_var.get().strip()
        if len(pin) != 6 or not pin.isdigit():
            self._error_lbl.config(text="Mật khẩu phải là 6 chữ số.")
            self._pin_var.set("")
            return
        if db.check_password(pin):
            self.success = True
            self.destroy()
        else:
            self._error_lbl.config(text="Mật khẩu không đúng. Thử lại.")
            self._pin_var.set("")
            self._pin_entry.focus_set()

    def _do_setup(self):
        pin = self._pin_var.get().strip()
        confirm = self._confirm_var.get().strip()
        if len(pin) != 6 or not pin.isdigit():
            self._error_lbl.config(text="Mật khẩu phải là 6 chữ số.")
            return
        if pin != confirm:
            self._error_lbl.config(text="Hai mật khẩu không khớp.")
            self._confirm_var.set("")
            self._confirm_entry.focus_set()
            return
        db.set_password(pin)
        self.success = True
        self.destroy()

    def _on_close(self):
        """Closing without authenticating exits the application."""
        self.parent.destroy()
