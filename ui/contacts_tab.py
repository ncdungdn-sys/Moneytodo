"""
Contacts Tab – Manage personal contacts with name, address, email, phone and notes.
"""
import tkinter as tk
from tkinter import ttk, messagebox

import database as db

BG = "#F0F4F8"
CARD_BG = "#FFFFFF"
ACCENT = "#3498DB"
TEXT_DARK = "#2C3E50"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADER = ("Segoe UI", 12, "bold")


def _center_dialog(dialog, parent):
    """Center a Toplevel dialog over its parent window."""
    dialog.update_idletasks()
    pw = parent.winfo_rootx() + parent.winfo_width() // 2
    ph = parent.winfo_rooty() + parent.winfo_height() // 2
    w = dialog.winfo_width()
    h = dialog.winfo_height()
    dialog.geometry(f"+{pw - w // 2}+{ph - h // 2}")


class ContactDialog(tk.Toplevel):
    """Dialog for adding or editing a contact."""

    def __init__(self, parent, contact_data=None):
        super().__init__(parent)
        self.title("➕ Thêm Danh Bạ" if contact_data is None else "✏️ Chỉnh Sửa Danh Bạ")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._data = contact_data
        self._build_ui()
        _center_dialog(self, parent)
        self.wait_window()

    def _build_ui(self):
        self.configure(bg=CARD_BG)
        frame = tk.Frame(self, bg=CARD_BG, padx=30, pady=20)
        frame.pack(fill="both", expand=True)

        title = "➕ Thêm Danh Bạ" if self._data is None else "✏️ Chỉnh Sửa Danh Bạ"
        tk.Label(frame, text=title, bg=CARD_BG, fg=TEXT_DARK, font=FONT_HEADER).pack(pady=(0, 16))

        # Pre-fill values when editing
        # contact_data tuple indices: 0=id, 1=name, 2=age(unused), 3=phone, 4=email, 5=address, 6=notes
        name_val = ""
        address_val = ""
        email_val = ""
        phone_val = ""
        notes_val = ""
        if self._data is not None:
            name_val    = self._data[1] or ""
            phone_val   = self._data[3] or ""
            email_val   = self._data[4] or ""
            address_val = self._data[5] or ""
            notes_val   = self._data[6] or ""

        # Tên (required)
        tk.Label(frame, text="Tên *", bg=CARD_BG, fg=TEXT_DARK, font=FONT_BOLD).pack(anchor="w")
        self._name_var = tk.StringVar(value=name_val)
        self._name_entry = ttk.Entry(frame, textvariable=self._name_var, width=38)
        self._name_entry.pack(pady=(4, 12), fill="x")

        # Địa Chỉ (optional)
        tk.Label(frame, text="Địa Chỉ", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._address_var = tk.StringVar(value=address_val)
        ttk.Entry(frame, textvariable=self._address_var, width=38).pack(pady=(4, 12), fill="x")

        # Email (optional)
        tk.Label(frame, text="Email", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._email_var = tk.StringVar(value=email_val)
        ttk.Entry(frame, textvariable=self._email_var, width=38).pack(pady=(4, 12), fill="x")

        # SĐT (optional)
        tk.Label(frame, text="SĐT (Số Điện Thoại)", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._phone_var = tk.StringVar(value=phone_val)
        ttk.Entry(frame, textvariable=self._phone_var, width=38).pack(pady=(4, 12), fill="x")

        # Ghi Chú (optional, multi-line)
        tk.Label(frame, text="Ghi Chú", bg=CARD_BG, fg=TEXT_DARK, font=FONT).pack(anchor="w")
        self._notes_text = tk.Text(frame, width=38, height=4, font=FONT, relief="solid", borderwidth=1)
        self._notes_text.pack(pady=(4, 4), fill="x")
        if notes_val:
            self._notes_text.insert("1.0", notes_val)
        tk.Label(frame, text="(tuỳ chọn)", bg=CARD_BG, fg="#95A5A6", font=("Segoe UI", 9)).pack(anchor="w")

        # Buttons
        btn_frame = tk.Frame(frame, bg=CARD_BG)
        btn_frame.pack(pady=(16, 0))
        ttk.Button(btn_frame, text="💾 Lưu", command=self._on_save).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="❌ Hủy", command=self._on_cancel).pack(side="left", padx=6)

        self._name_entry.focus_set()
        self.bind("<Escape>", lambda e: self._on_cancel())

    def _on_save(self):
        name = self._name_var.get().strip()
        address = self._address_var.get().strip()
        email = self._email_var.get().strip()
        phone = self._phone_var.get().strip()
        notes = self._notes_text.get("1.0", "end-1c").strip()

        if not name:
            messagebox.showerror("Lỗi", "Vui lòng nhập tên liên hệ!", parent=self)
            self._name_entry.focus_set()
            return

        self.result = (name, address, email, phone, notes)
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


class ContactsFrame(ttk.Frame):
    """Contacts Tab – simple phonebook management."""

    def __init__(self, parent):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────
        ctrl = tk.Frame(self, bg=BG)
        ctrl.pack(fill="x", padx=10, pady=(10, 0))

        tk.Label(ctrl, text="📞 Danh Bạ",
                 bg=BG, fg=TEXT_DARK, font=FONT_HEADER).pack(side="left")
        ttk.Button(ctrl, text="🔄 Refresh", command=self._refresh).pack(side="right", padx=4)

        # ── Search bar ────────────────────────────────────────────────────
        search_frame = tk.Frame(self, bg=BG)
        search_frame.pack(fill="x", padx=10, pady=(6, 4))

        tk.Label(search_frame, text="🔍 Tìm kiếm:",
                 bg=BG, fg=TEXT_DARK, font=FONT).pack(side="left", padx=(0, 6))
        self._search_var = tk.StringVar()
        self._search_var.trace("w", self._on_search_change)
        self._search_entry = ttk.Entry(search_frame, textvariable=self._search_var, width=30)
        self._search_entry.pack(side="left")

        # ── Treeview ──────────────────────────────────────────────────────
        tree_frame = tk.Frame(self, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        cols = ("name", "address", "email", "phone", "notes")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")

        self._tree.heading("name",    text="Tên")
        self._tree.heading("address", text="Địa Chỉ")
        self._tree.heading("email",   text="Email")
        self._tree.heading("phone",   text="SĐT")
        self._tree.heading("notes",   text="Ghi Chú")

        self._tree.column("name",    width=160, minwidth=100)
        self._tree.column("address", width=180, minwidth=100)
        self._tree.column("email",   width=160, minwidth=100)
        self._tree.column("phone",   width=120, minwidth=80)
        self._tree.column("notes",   width=200, minwidth=80)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)

        # Double-click to edit
        self._tree.bind("<Double-1>", lambda e: self._open_edit_dialog())

        # ── Action buttons ────────────────────────────────────────────────
        action_frame = tk.Frame(self, bg=BG)
        action_frame.pack(fill="x", padx=10, pady=(0, 8))

        ttk.Button(action_frame, text="➕ Thêm Danh Bạ",
                   command=self._open_add_dialog).pack(side="left", padx=4)
        ttk.Button(action_frame, text="✏️ Sửa",
                   command=self._open_edit_dialog).pack(side="left", padx=4)
        ttk.Button(action_frame, text="🗑️ Xóa",
                   command=self._delete_selected).pack(side="left", padx=4)

        # Internal map: treeview iid → db contact id
        self._item_id_map = {}

    # ── Data operations ───────────────────────────────────────────────────────

    def load_data(self):
        """Called by main app on tab switch."""
        self._refresh()

    def _refresh(self):
        keyword = self._search_var.get().strip() if hasattr(self, "_search_var") else ""
        rows = db.search_contacts(keyword) if keyword else db.get_all_contacts()

        self._tree.delete(*self._tree.get_children())
        self._item_id_map.clear()

        # row tuple indices: 0=id, 1=name, 2=age(unused), 3=phone, 4=email, 5=address, 6=notes
        for row in rows:
            contact_id = row[0]
            name    = row[1] or ""
            phone   = row[3] or ""
            email   = row[4] or ""
            address = row[5] or ""
            notes   = row[6] or ""
            iid = self._tree.insert(
                "", "end",
                values=(name, address or "", email or "", phone or "", notes or ""),
            )
            self._item_id_map[iid] = contact_id

    def _on_search_change(self, *_args):
        self._refresh()

    def _open_add_dialog(self):
        dlg = ContactDialog(self.winfo_toplevel())
        if dlg.result:
            name, address, email, phone, notes = dlg.result
            db.add_contact(name=name, address=address, email=email, phone=phone, notes=notes)
            self._refresh()

    def _open_edit_dialog(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn liên hệ cần sửa!", parent=self)
            return
        iid = sel[0]
        contact_id = self._item_id_map[iid]
        data = db.get_contact_by_id(contact_id)
        if data is None:
            return
        dlg = ContactDialog(self.winfo_toplevel(), contact_data=data)
        if dlg.result:
            name, address, email, phone, notes = dlg.result
            db.update_contact(contact_id, name=name, address=address, email=email, phone=phone, notes=notes)
            self._refresh()

    def _delete_selected(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn liên hệ cần xóa!", parent=self)
            return
        iid = sel[0]
        contact_id = self._item_id_map[iid]
        values = self._tree.item(iid, "values")
        name = values[0] if values else "?"

        if messagebox.askyesno("Xác nhận", f"Xóa liên hệ '{name}'?", parent=self):
            db.delete_contact(contact_id)
            self._refresh()
