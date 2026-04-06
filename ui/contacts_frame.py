"""
Contacts Tab – manage personal contacts (Danh Bạ).
Fields: name (required), age, phone, email, address, notes.
"""
import tkinter as tk
import traceback
from tkinter import ttk, messagebox

import database as db

BG = "#F0F4F8"
CARD_BG = "#FFFFFF"
ACCENT = "#3498DB"
TEXT_DARK = "#2C3E50"
TEXT_LIGHT = "#ECF0F1"
SIDEBAR_BG = "#34495E"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADER = ("Segoe UI", 12, "bold")
FONT_SMALL = ("Segoe UI", 9)


class ContactsFrame(tk.Frame):
    """Contacts management tab."""

    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._expanded = {}  # contact_id → bool (expanded detail visible)
        self._detail_frames = {}  # contact_id → detail Frame widget
        self._build_ui()
        self.load_data()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Top bar ───────────────────────────────────────────────────────
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=10, pady=(10, 0))

        tk.Label(top, text="📞 Danh Bạ", bg=BG, fg=TEXT_DARK,
                 font=FONT_HEADER).pack(side="left")
        ttk.Button(top, text="🔄 Refresh", command=self.load_data).pack(side="right", padx=4)
        ttk.Button(top, text="➕ Thêm Liên Hệ",
                   command=self._show_add_dialog).pack(side="right", padx=4)

        # ── Search bar ────────────────────────────────────────────────────
        search_row = tk.Frame(self, bg=BG)
        search_row.pack(fill="x", padx=10, pady=(8, 4))

        tk.Label(search_row, text="🔍 Tìm kiếm:", bg=BG, fg=TEXT_DARK,
                 font=FONT).pack(side="left", padx=(0, 6))
        self._search_var = tk.StringVar()
        self._search_var.trace("w", self._on_search_change)
        ttk.Entry(search_row, textvariable=self._search_var, width=35).pack(side="left")

        # ── Scrollable contact list ───────────────────────────────────────
        container = tk.Frame(self, bg=BG)
        container.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._list_frame = tk.Frame(canvas, bg=BG)
        self._list_window = canvas.create_window((0, 0), window=self._list_frame, anchor="nw")

        self._list_frame.bind("<Configure>",
                              lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(self._list_window, width=e.width))
        # Mouse wheel scrolling (bind to canvas only to avoid conflicts)
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        canvas.bind("<Enter>",
                    lambda e: canvas.bind_all("<MouseWheel>",
                                             lambda ev: canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")))
        canvas.bind("<Leave>",
                    lambda e: canvas.unbind_all("<MouseWheel>"))

        self._canvas = canvas

    # ── Data Loading ──────────────────────────────────────────────────────────

    def load_data(self):
        """Reload contact list (called on tab switch and after mutations)."""
        query = self._search_var.get().strip() if hasattr(self, "_search_var") else ""
        try:
            if query:
                contacts = db.search_contacts(query)
            else:
                contacts = db.get_all_contacts()
            print(f"[ContactsFrame] ✅ load_data: {len(contacts)} contacts loaded")
            self._render_contacts(contacts)
        except Exception as e:
            print(f"[ContactsFrame] ❌ load_data failed: {e}")
            self._render_contacts([])

    def _on_search_change(self, *_):
        self.load_data()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render_contacts(self, contacts):
        """Clear and re-draw the contact list."""
        # Preserve which contacts are expanded
        prev_expanded = set(cid for cid, val in self._expanded.items() if val)

        for widget in self._list_frame.winfo_children():
            widget.destroy()
        self._expanded.clear()
        self._detail_frames.clear()

        if not contacts:
            tk.Label(self._list_frame,
                     text="Không có liên hệ nào. Nhấn '➕ Thêm Liên Hệ' để bắt đầu.",
                     bg=BG, fg=TEXT_DARK, font=FONT).pack(pady=20)
            return

        for row in contacts:
            contact_id, name, age, phone, email, address, notes, created_at, _ = row
            self._build_contact_row(contact_id, name, age, phone, email, address, notes,
                                    expanded=(contact_id in prev_expanded))

    def _build_contact_row(self, contact_id, name, age, phone, email, address, notes, expanded=False):
        """Build a single contact card with collapsible detail section."""
        card = tk.Frame(self._list_frame, bg=CARD_BG, relief="solid", bd=1)
        card.pack(fill="x", pady=3, padx=2)

        # ── Header row (always visible) ───────────────────────────────────
        header = tk.Frame(card, bg=CARD_BG)
        header.pack(fill="x", padx=8, pady=6)

        age_str = f" ({age} tuổi)" if age else ""
        toggle_text = "▼" if not expanded else "▲"
        toggle_btn = tk.Button(
            header, text=toggle_text,
            bg=CARD_BG, fg=ACCENT, font=FONT_BOLD,
            relief="flat", cursor="hand2", padx=4,
        )
        toggle_btn.pack(side="left")

        name_label = tk.Label(header, text=f"{name}{age_str}",
                               bg=CARD_BG, fg=TEXT_DARK, font=FONT_BOLD)
        name_label.pack(side="left", padx=(4, 0))

        # ── Detail section (collapsible) ──────────────────────────────────
        detail = tk.Frame(card, bg=CARD_BG)
        if expanded:
            detail.pack(fill="x", padx=20, pady=(0, 8))

        self._populate_detail(detail, contact_id, phone, email, address, notes)

        self._expanded[contact_id] = expanded
        self._detail_frames[contact_id] = detail

        # Wire toggle
        def _toggle(btn=toggle_btn, det=detail, cid=contact_id):
            if self._expanded.get(cid, False):
                det.pack_forget()
                btn.config(text="▼")
                self._expanded[cid] = False
            else:
                det.pack(fill="x", padx=20, pady=(0, 8))
                btn.config(text="▲")
                self._expanded[cid] = True

        toggle_btn.config(command=_toggle)
        name_label.bind("<Button-1>", lambda e, t=_toggle: t())

    def _populate_detail(self, parent, contact_id, phone, email, address, notes):
        """Fill the detail frame with contact info and action buttons."""
        if phone:
            tk.Label(parent, text=f"☎️  {phone}", bg=CARD_BG, fg=TEXT_DARK,
                     font=FONT).pack(anchor="w")
        if email:
            tk.Label(parent, text=f"📧  {email}", bg=CARD_BG, fg=TEXT_DARK,
                     font=FONT).pack(anchor="w")
        if address:
            tk.Label(parent, text=f"📍  {address}", bg=CARD_BG, fg=TEXT_DARK,
                     font=FONT).pack(anchor="w")
        if notes:
            tk.Label(parent, text=f"📝  Ghi chú: {notes}", bg=CARD_BG, fg=TEXT_DARK,
                     font=FONT, wraplength=600, justify="left").pack(anchor="w")

        # Action buttons
        btn_row = tk.Frame(parent, bg=CARD_BG)
        btn_row.pack(anchor="w", pady=(6, 0))
        ttk.Button(btn_row, text="✏️ Sửa",
                   command=lambda cid=contact_id: self._show_edit_dialog(cid)).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="🗑️ Xóa",
                   command=lambda cid=contact_id: self._delete_contact(cid)).pack(side="left")

    # ── Dialogs ───────────────────────────────────────────────────────────────

    def _show_add_dialog(self):
        """Show dialog to add a new contact."""
        dlg = _ContactDialog(self.winfo_toplevel(), title="➕ Thêm Liên Hệ Mới")
        if dlg.result:
            name, age, phone, email, address, notes = dlg.result
            print(f"[_show_add_dialog] 🔍 Parameters: name={name!r}, age={age!r}, phone={phone!r}, email={email!r}, address={address!r}, notes={notes!r}")
            try:
                print("[_show_add_dialog] 🔍 Calling db.add_contact()...")
                new_id = db.add_contact(name, age, phone, email, address, notes)
                print(f"[_show_add_dialog] ✅ SUCCESS: Contact added with id={new_id}")
                self.load_data()
            except Exception as e:
                print(f"[_show_add_dialog] ❌ EXCEPTION: {type(e).__name__}: {e}")
                traceback.print_exc()
                messagebox.showerror("Lỗi", f"Lưu liên hệ thất bại:\n{e}", parent=self)

    def _show_edit_dialog(self, contact_id):
        """Show dialog to edit an existing contact."""
        data = db.get_contact_by_id(contact_id)
        if data is None:
            messagebox.showerror("Lỗi", "Không tìm thấy liên hệ", parent=self)
            return
        cid, name, age, phone, email, address, notes, *_ = data
        dlg = _ContactDialog(
            self.winfo_toplevel(),
            title="✏️ Sửa Liên Hệ",
            initial=(name, age, phone, email, address, notes),
        )
        if dlg.result:
            name, age, phone, email, address, notes = dlg.result
            print(f"[_show_edit_dialog] 🔍 Parameters: contact_id={contact_id}, name={name!r}, age={age!r}, phone={phone!r}, email={email!r}, address={address!r}, notes={notes!r}")
            try:
                print("[_show_edit_dialog] 🔍 Calling db.update_contact()...")
                db.update_contact(contact_id, name, age, phone, email, address, notes)
                print(f"[_show_edit_dialog] ✅ SUCCESS: Contact updated id={contact_id}")
                self.load_data()
            except Exception as e:
                print(f"[_show_edit_dialog] ❌ EXCEPTION: {type(e).__name__}: {e}")
                traceback.print_exc()
                messagebox.showerror("Lỗi", f"Cập nhật liên hệ thất bại:\n{e}", parent=self)

    def _delete_contact(self, contact_id):
        """Confirm and delete a contact."""
        data = db.get_contact_by_id(contact_id)
        if data is None:
            messagebox.showerror("Lỗi", "Không tìm thấy liên hệ", parent=self)
            return
        name = data[1]
        if messagebox.askyesno("Xác nhận", f"Xóa liên hệ '{name}'?", parent=self):
            try:
                print(f"[_delete_contact] 🔍 Deleting contact id={contact_id}")
                db.delete_contact(contact_id)
                print(f"[_delete_contact] ✅ SUCCESS: Contact deleted")
                self.load_data()
            except Exception as e:
                print(f"[_delete_contact] ❌ EXCEPTION: {type(e).__name__}: {e}")
                traceback.print_exc()
                messagebox.showerror("Lỗi", f"Xóa liên hệ thất bại:\n{e}", parent=self)


# ── Add / Edit Dialog ─────────────────────────────────────────────────────────

class _ContactDialog(tk.Toplevel):
    """Modal dialog for adding or editing a contact."""

    def __init__(self, parent, title="Liên Hệ", initial=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result = None

        self.configure(bg=BG)

        # Center the dialog
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = 420, 420
        self.geometry(f"{w}x{h}+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

        self._build(initial or ("", None, "", "", "", ""))

    def _build(self, initial):
        name0, age0, phone0, email0, address0, notes0 = initial

        pad = {"padx": 12, "pady": 4}

        # Name (required)
        tk.Label(self, text="Tên: *", bg=BG, fg=TEXT_DARK, font=FONT_BOLD).pack(anchor="w", **pad)
        self._name = ttk.Entry(self, width=45)
        self._name.insert(0, name0 or "")
        self._name.pack(fill="x", **pad)

        # Age
        tk.Label(self, text="Tuổi:", bg=BG, fg=TEXT_DARK, font=FONT).pack(anchor="w", **pad)
        self._age = ttk.Entry(self, width=12)
        self._age.insert(0, str(age0) if age0 else "")
        self._age.pack(anchor="w", **pad)

        # Phone
        tk.Label(self, text="Số ĐT:", bg=BG, fg=TEXT_DARK, font=FONT).pack(anchor="w", **pad)
        self._phone = ttk.Entry(self, width=45)
        self._phone.insert(0, phone0 or "")
        self._phone.pack(fill="x", **pad)

        # Email
        tk.Label(self, text="Email:", bg=BG, fg=TEXT_DARK, font=FONT).pack(anchor="w", **pad)
        self._email = ttk.Entry(self, width=45)
        self._email.insert(0, email0 or "")
        self._email.pack(fill="x", **pad)

        # Address (new field)
        tk.Label(self, text="Địa Chỉ:", bg=BG, fg=TEXT_DARK, font=FONT).pack(anchor="w", **pad)
        self._address = ttk.Entry(self, width=45)
        self._address.insert(0, address0 or "")
        self._address.pack(fill="x", **pad)

        # Notes (wider single-line entry)
        tk.Label(self, text="Ghi Chú:", bg=BG, fg=TEXT_DARK, font=FONT).pack(anchor="w", **pad)
        self._notes = ttk.Entry(self, width=45)
        self._notes.insert(0, notes0 or "")
        self._notes.pack(fill="x", **pad)

        # Buttons
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(pady=(12, 8))
        ttk.Button(btn_row, text="💾 Lưu", command=self._save).pack(side="left", padx=8)
        ttk.Button(btn_row, text="❌ Hủy", command=self.destroy).pack(side="left", padx=8)

        self._name.focus_set()
        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())

    def _save(self):
        name = self._name.get().strip()
        if not name:
            messagebox.showerror("Lỗi", "Tên liên hệ không được để trống.", parent=self)
            self._name.focus_set()
            return

        age_str = self._age.get().strip()
        age = None
        if age_str:
            try:
                age = int(age_str)
                if age <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Lỗi", "Tuổi phải là số nguyên dương.", parent=self)
                self._age.focus_set()
                return

        phone = self._phone.get().strip()
        email = self._email.get().strip()
        address = self._address.get().strip()
        notes = self._notes.get().strip()

        self.result = (name, age, phone, email, address, notes)
        self.destroy()
