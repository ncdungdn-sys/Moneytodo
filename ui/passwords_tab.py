"""
Password Manager Tab – Securely store and manage passwords with master password protection.

Session is locked each time the user leaves the tab and must be re-authenticated on return.
"""
import tkinter as tk
from tkinter import ttk, messagebox

import database as db
from ui.passwords_dialog import (
    AddPasswordDialog,
    EditPasswordDialog,
    MasterPasswordDialog,
    VerifyMasterPasswordDialog,
)

BG = "#F0F4F8"
CARD_BG = "#FFFFFF"
ACCENT = "#3498DB"
TEXT_DARK = "#2C3E50"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADER = ("Segoe UI", 12, "bold")


class PasswordsFrame(ttk.Frame):
    """Password Manager Tab with per-session master password authentication."""

    def __init__(self, parent):
        super().__init__(parent)
        self._authenticated = False
        self._password_session_active = False
        self._build_locked_ui()
        self._build_manager_ui()
        self._show_locked_state()

    # ── Locked state UI ───────────────────────────────────────────────────────

    def _build_locked_ui(self):
        self._locked_frame = tk.Frame(self, bg=BG)
        self._locked_frame.place(relwidth=1, relheight=1)

        center = tk.Frame(self._locked_frame, bg=BG)
        center.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(center, text="🔐", bg=BG, fg=TEXT_DARK,
                 font=("Segoe UI", 48)).pack(pady=(0, 10))
        tk.Label(center, text="🔐 Nhập Master Password để truy cập",
                 bg=BG, fg=TEXT_DARK, font=FONT_HEADER).pack()

    # ── Full manager UI ───────────────────────────────────────────────────────

    def _build_manager_ui(self):
        self._manager_frame = tk.Frame(self, bg=BG)
        self._manager_frame.place(relwidth=1, relheight=1)

        # ── Header ────────────────────────────────────────────────────────
        ctrl = tk.Frame(self._manager_frame, bg=BG)
        ctrl.pack(fill="x", padx=10, pady=(10, 0))

        tk.Label(ctrl, text="🔒 Quản Lý Mật Khẩu",
                 bg=BG, fg=TEXT_DARK, font=FONT_HEADER).pack(side="left")
        ttk.Button(ctrl, text="🔄 Refresh", command=self._refresh).pack(side="right", padx=4)

        # ── Search bar ────────────────────────────────────────────────────
        search_frame = tk.Frame(self._manager_frame, bg=BG)
        search_frame.pack(fill="x", padx=10, pady=(6, 4))

        tk.Label(search_frame, text="🔍 Tìm kiếm:",
                 bg=BG, fg=TEXT_DARK, font=FONT).pack(side="left", padx=(0, 6))
        self._search_var = tk.StringVar()
        self._search_var.trace("w", self._on_search_change)
        self._search_entry = ttk.Entry(search_frame, textvariable=self._search_var, width=30)
        self._search_entry.pack(side="left")

        # ── Treeview ──────────────────────────────────────────────────────
        tree_frame = tk.Frame(self._manager_frame, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        cols = ("category", "account_name", "password", "notes")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")

        self._tree.heading("category", text="Danh Mục")
        self._tree.heading("account_name", text="Tài Khoản")
        self._tree.heading("password", text="Mật Khẩu")
        self._tree.heading("notes", text="Ghi Chú")

        self._tree.column("category", width=120, minwidth=80)
        self._tree.column("account_name", width=200, minwidth=120)
        self._tree.column("password", width=160, minwidth=100)
        self._tree.column("notes", width=200, minwidth=100)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)

        # Double-click to edit
        self._tree.bind("<Double-1>", lambda e: self._open_edit_dialog())

        # ── Action buttons ────────────────────────────────────────────────
        action_frame = tk.Frame(self._manager_frame, bg=BG)
        action_frame.pack(fill="x", padx=10, pady=(0, 8))

        ttk.Button(action_frame, text="➕ Thêm Mật Khẩu",
                   command=self._open_add_dialog).pack(side="left", padx=4)
        ttk.Button(action_frame, text="✏️ Sửa",
                   command=self._open_edit_dialog).pack(side="left", padx=4)
        ttk.Button(action_frame, text="🗑️ Xóa",
                   command=self._delete_selected).pack(side="left", padx=4)

        # Internal map: treeview iid → db password id
        self._item_id_map = {}

    # ── State helpers ─────────────────────────────────────────────────────────

    def _show_locked_state(self):
        self._locked_frame.lift()

    def _show_manager_state(self):
        self._manager_frame.lift()
        self._refresh()

    # ── Public API called by main.py ──────────────────────────────────────────

    def request_access(self):
        """Show authentication dialogs and return True if access is granted."""
        # Already authenticated in this session
        if self._authenticated and self._password_session_active:
            return True

        # First time: set up a master password
        if not db.master_password_exists():
            dlg = MasterPasswordDialog(self.winfo_toplevel())
            if dlg.result:
                self._authenticated = True
                self._password_session_active = True
                self._show_manager_state()
                return True
            return False

        # Subsequent entries: verify master password
        dlg = VerifyMasterPasswordDialog(self.winfo_toplevel())
        if dlg.result:
            self._authenticated = True
            self._password_session_active = True
            self._show_manager_state()
            return True

        self._show_locked_state()
        return False

    def lock_session(self):
        """Lock the session when the user navigates away from this tab."""
        self._authenticated = False
        self._password_session_active = False
        self._show_locked_state()

    def load_data(self):
        """Called by main app on tab switch; authentication is handled via request_access()."""
        pass

    # ── Data operations ───────────────────────────────────────────────────────

    def _refresh(self):
        keyword = self._search_var.get().strip() if hasattr(self, "_search_var") else ""
        rows = db.search_passwords(keyword) if keyword else db.get_all_passwords()

        self._tree.delete(*self._tree.get_children())
        self._item_id_map.clear()

        for pw_id, category, account_name, password, notes in rows:
            iid = self._tree.insert(
                "", "end", values=(category, account_name, password, notes or "")
            )
            self._item_id_map[iid] = pw_id

    def _on_search_change(self, *_args):
        if self._authenticated:
            self._refresh()

    def _open_add_dialog(self):
        dlg = AddPasswordDialog(self.winfo_toplevel())
        if dlg.result:
            category, account_name, password, notes = dlg.result
            db.add_password(category, account_name, password, notes)
            self._refresh()

    def _open_edit_dialog(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn mục cần sửa!", parent=self)
            return
        iid = sel[0]
        pw_id = self._item_id_map[iid]
        data = db.get_password_by_id(pw_id)
        if data is None:
            return
        dlg = EditPasswordDialog(self.winfo_toplevel(), data)
        if dlg.result:
            category, account_name, password, notes = dlg.result
            db.update_password(pw_id, category, account_name, password, notes)
            self._refresh()

    def _delete_selected(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn mục cần xóa!", parent=self)
            return
        iid = sel[0]
        pw_id = self._item_id_map[iid]
        values = self._tree.item(iid, "values")
        account_name = values[1] if values else "?"

        if messagebox.askyesno("Xác nhận", f"Xóa mật khẩu cho '{account_name}'?", parent=self):
            db.delete_password(pw_id)
            self._refresh()
