"""
Password Manager Dialogs – master password setup/verify and password CRUD dialogs.
"""
import tkinter as tk
from tkinter import ttk, messagebox

import database as db

CARD_BG = "#FFFFFF"
TEXT_DARK = "#2C3E50"
FONT = ("Segoe UI", 10)
FONT_HEADER = ("Segoe UI", 12, "bold")

CATEGORIES = ["Email", "Bank", "Social Media", "Hệ Thống", "Khác"]


def _center_dialog(dialog, parent):
    """Center a Toplevel dialog over its parent window."""
    dialog.update_idletasks()
    pw = parent.winfo_rootx() + parent.winfo_width() // 2
    ph = parent.winfo_rooty() + parent.winfo_height() // 2
    w = dialog.winfo_width()
    h = dialog.winfo_height()
    dialog.geometry(f"+{pw - w // 2}+{ph - h // 2}")


class MasterPasswordDialog(tk.Toplevel):
    """Dialog for first-time master password setup."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("🔑 Đặt Master Password Lần Đầu")
        self.resizable(False, False)
        self.grab_set()
        self.result = False
        self._build_ui()
        _center_dialog(self, parent)
        self.wait_window()

    def _build_ui(self):
        self.configure(bg=CARD_BG)
        frame = tk.Frame(self, bg=CARD_BG, padx=30, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame, text="🔑 Đặt Master Password Lần Đầu",
            bg=CARD_BG, fg=TEXT_DARK, font=FONT_HEADER,
        ).pack(pady=(0, 20))

        tk.Label(frame, text="Master Password:", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._pw_var = tk.StringVar()
        self._pw_entry = ttk.Entry(frame, textvariable=self._pw_var, show="•", width=35)
        self._pw_entry.pack(pady=(4, 12))

        tk.Label(frame, text="Xác nhận lại:", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._confirm_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self._confirm_var, show="•", width=35).pack(pady=(4, 12))

        tk.Label(
            frame,
            text="⚠️ Hãy nhớ password này!\nNếu quên không thể khôi phục",
            bg=CARD_BG, fg="#E74C3C", font=("Segoe UI", 9),
        ).pack(pady=(0, 16))

        btn_frame = tk.Frame(frame, bg=CARD_BG)
        btn_frame.pack()
        ttk.Button(btn_frame, text="✅ OK", command=self._on_ok).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="❌ Hủy", command=self._on_cancel).pack(side="left", padx=6)

        self._pw_entry.focus_set()
        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())

    def _on_ok(self):
        pw = self._pw_var.get().strip()
        confirm = self._confirm_var.get().strip()

        if not pw:
            messagebox.showerror("Lỗi", "Vui lòng nhập master password!", parent=self)
            return
        if len(pw) < 6:
            messagebox.showerror("Lỗi", "Password phải ít nhất 6 ký tự!", parent=self)
            return
        if pw != confirm:
            messagebox.showerror("Lỗi", "Hai mật khẩu không khớp!", parent=self)
            return

        if db.set_master_password(pw):
            self.result = True
            self.destroy()
        else:
            messagebox.showerror("Lỗi", "Không thể lưu master password!", parent=self)

    def _on_cancel(self):
        self.result = False
        self.destroy()


class VerifyMasterPasswordDialog(tk.Toplevel):
    """Dialog for verifying master password on every tab entry."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("🔑 Nhập Master Password")
        self.resizable(False, False)
        self.grab_set()
        self.result = False
        self._build_ui()
        _center_dialog(self, parent)
        self.wait_window()

    def _build_ui(self):
        self.configure(bg=CARD_BG)
        frame = tk.Frame(self, bg=CARD_BG, padx=30, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame, text="🔑 Nhập Master Password",
            bg=CARD_BG, fg=TEXT_DARK, font=FONT_HEADER,
        ).pack(pady=(0, 20))

        tk.Label(frame, text="Master Password:", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._pw_var = tk.StringVar()
        self._pw_entry = ttk.Entry(frame, textvariable=self._pw_var, show="•", width=35)
        self._pw_entry.pack(pady=(4, 20))

        btn_frame = tk.Frame(frame, bg=CARD_BG)
        btn_frame.pack()
        ttk.Button(btn_frame, text="✅ Xác nhận", command=self._on_confirm).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="❌ Hủy", command=self._on_cancel).pack(side="left", padx=6)

        self._pw_entry.focus_set()
        self.bind("<Return>", lambda e: self._on_confirm())
        self.bind("<Escape>", lambda e: self._on_cancel())

    def _on_confirm(self):
        pw = self._pw_var.get()
        if db.verify_master_password(pw):
            self.result = True
            self.destroy()
        else:
            messagebox.showerror("Lỗi", "Mật khẩu không đúng!", parent=self)
            self._pw_var.set("")
            self._pw_entry.focus_set()

    def _on_cancel(self):
        self.result = False
        self.destroy()


class AddPasswordDialog(tk.Toplevel):
    """Dialog for adding a new password entry."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("➕ Thêm Mật Khẩu Mới")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._build_ui()
        _center_dialog(self, parent)
        self.wait_window()

    def _build_ui(self):
        self.configure(bg=CARD_BG)
        frame = tk.Frame(self, bg=CARD_BG, padx=30, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame, text="➕ Thêm Mật Khẩu Mới",
            bg=CARD_BG, fg=TEXT_DARK, font=FONT_HEADER,
        ).pack(pady=(0, 20))

        tk.Label(frame, text="Danh Mục:", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._cat_var = tk.StringVar(value=CATEGORIES[0])
        ttk.Combobox(
            frame, textvariable=self._cat_var, values=CATEGORIES, state="readonly", width=33,
        ).pack(pady=(4, 12), anchor="w")

        tk.Label(frame, text="Chi Tiết:", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._detail_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self._detail_var, width=35).pack(pady=(4, 4))
        tk.Label(frame, text="(vd: Gmail, Vietcombank, Facebook...)", bg=CARD_BG, fg="#95A5A6", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))

        tk.Label(frame, text="Tên Tài Khoản:", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._acc_var = tk.StringVar()
        self._acc_entry = ttk.Entry(frame, textvariable=self._acc_var, width=35)
        self._acc_entry.pack(pady=(4, 12))

        tk.Label(frame, text="Mật Khẩu:", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._pw_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self._pw_var, width=35).pack(pady=(4, 4))
        tk.Label(frame, text="(tuỳ chọn)", bg=CARD_BG, fg="#95A5A6", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))

        tk.Label(frame, text="Ghi Chú:", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._notes_text = tk.Text(frame, width=35, height=4, font=FONT, relief="solid", borderwidth=1)
        self._notes_text.pack(pady=(4, 4))
        tk.Label(frame, text="(tuỳ chọn)", bg=CARD_BG, fg="#95A5A6", font=("Segoe UI", 9)).pack(anchor="w")

        btn_frame = tk.Frame(frame, bg=CARD_BG)
        btn_frame.pack(pady=(16, 0))
        ttk.Button(btn_frame, text="💾 Lưu", command=self._on_save).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="❌ Hủy", command=self._on_cancel).pack(side="left", padx=6)

        self._acc_entry.focus_set()
        self.bind("<Escape>", lambda e: self._on_cancel())

    def _on_save(self):
        category = self._cat_var.get().strip()
        detail = self._detail_var.get().strip()
        account_name = self._acc_var.get().strip()
        password = self._pw_var.get().strip()
        notes = self._notes_text.get("1.0", "end-1c").strip()

        if not account_name:
            messagebox.showerror("Lỗi", "Vui lòng nhập tên tài khoản!", parent=self)
            return

        self.result = (category, detail, account_name, password, notes)
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


class EditPasswordDialog(tk.Toplevel):
    """Dialog for editing an existing password entry."""

    def __init__(self, parent, password_data):
        super().__init__(parent)
        self.title("✏️ Chỉnh Sửa Mật Khẩu")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._data = password_data
        self._build_ui()
        _center_dialog(self, parent)
        self.wait_window()

    def _build_ui(self):
        self.configure(bg=CARD_BG)

        # password_data = (id, category, detail, account_name, password, notes)
        _, category, detail, account_name, password, notes = self._data

        frame = tk.Frame(self, bg=CARD_BG, padx=30, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame, text="✏️ Chỉnh Sửa Mật Khẩu",
            bg=CARD_BG, fg=TEXT_DARK, font=FONT_HEADER,
        ).pack(pady=(0, 20))

        tk.Label(frame, text="Danh Mục:", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._cat_var = tk.StringVar(value=category)
        ttk.Combobox(
            frame, textvariable=self._cat_var, values=CATEGORIES, state="readonly", width=33,
        ).pack(pady=(4, 12), anchor="w")

        tk.Label(frame, text="Chi Tiết:", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._detail_var = tk.StringVar(value=detail or "")
        ttk.Entry(frame, textvariable=self._detail_var, width=35).pack(pady=(4, 4))
        tk.Label(frame, text="(vd: Gmail, Vietcombank, Facebook...)", bg=CARD_BG, fg="#95A5A6", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))

        tk.Label(frame, text="Tên Tài Khoản:", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._acc_var = tk.StringVar(value=account_name)
        ttk.Entry(frame, textvariable=self._acc_var, width=35).pack(pady=(4, 12))

        tk.Label(frame, text="Mật Khẩu:", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._pw_var = tk.StringVar(value=password or "")
        ttk.Entry(frame, textvariable=self._pw_var, width=35).pack(pady=(4, 4))
        tk.Label(frame, text="(tuỳ chọn)", bg=CARD_BG, fg="#95A5A6", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))

        tk.Label(frame, text="Ghi Chú:", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._notes_text = tk.Text(frame, width=35, height=4, font=FONT, relief="solid", borderwidth=1)
        self._notes_text.pack(pady=(4, 4))
        if notes:
            self._notes_text.insert("1.0", notes)
        tk.Label(frame, text="(tuỳ chọn)", bg=CARD_BG, fg="#95A5A6", font=("Segoe UI", 9)).pack(anchor="w")

        btn_frame = tk.Frame(frame, bg=CARD_BG)
        btn_frame.pack(pady=(16, 0))
        ttk.Button(btn_frame, text="💾 Lưu", command=self._on_save).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="❌ Hủy", command=self._on_cancel).pack(side="left", padx=6)

        self.bind("<Escape>", lambda e: self._on_cancel())

    def _on_save(self):
        category = self._cat_var.get().strip()
        detail = self._detail_var.get().strip()
        account_name = self._acc_var.get().strip()
        password = self._pw_var.get().strip()
        notes = self._notes_text.get("1.0", "end-1c").strip()

        if not account_name:
            messagebox.showerror("Lỗi", "Vui lòng nhập tên tài khoản!", parent=self)
            return

        self.result = (category, detail, account_name, password, notes)
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()
