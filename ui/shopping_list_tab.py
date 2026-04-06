"""
Shopping List Tab – Manage a simple shopping list with item names, notes,
and a bought/not-bought checkbox toggle.
"""
import tkinter as tk
from tkinter import ttk, messagebox

import database as db

BG = "#F0F4F8"
CARD_BG = "#FFFFFF"
ACCENT = "#3498DB"
BOUGHT_COLOR = "#95A5A6"
PENDING_COLOR = "#2C3E50"
TEXT_DARK = "#2C3E50"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADER = ("Segoe UI", 12, "bold")


class ShoppingListFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._items = []
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        # ── Header + Add button ───────────────────────────────────────────
        ctrl = tk.Frame(self, bg=BG)
        ctrl.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(ctrl, text="🛒 Danh Sách Mua Sắm", bg=BG, fg=TEXT_DARK,
                 font=FONT_HEADER).pack(side="left")
        ttk.Button(ctrl, text="➕ Thêm Mua Sắm",
                   command=self.open_add_dialog).pack(side="right")

        # ── Filter ────────────────────────────────────────────────────────
        flt = tk.Frame(self, bg=BG)
        flt.pack(fill="x", padx=10, pady=4)
        self._filter_var = tk.StringVar(value="all")
        for text, value in [("Tất Cả", "all"), ("Chưa Mua", "pending"), ("Đã Mua", "bought")]:
            ttk.Radiobutton(flt, text=text, variable=self._filter_var, value=value,
                            command=self._refresh_tree).pack(side="left", padx=(0, 12))

        # ── Treeview ──────────────────────────────────────────────────────
        tree_frame = tk.Frame(self, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        cols = ("bought", "item_name", "notes")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                 selectmode="browse")
        headings = {
            "bought":    ("☑️ Đã Mua", 90),
            "item_name": ("📦 Tên Sản Phẩm", 220),
            "notes":     ("📝 Ghi Chú", 360),
        }
        for col, (text, width) in headings.items():
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")

        self.tree.tag_configure("bought", foreground=BOUGHT_COLOR)
        self.tree.tag_configure("pending", foreground=PENDING_COLOR)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        # Double-click toggles bought status
        self.tree.bind("<Double-1>", lambda e: self.toggle_bought())

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Button(btn_row, text="☑️ Đánh Dấu Đã Mua",
                   command=self.toggle_bought).pack(side="left", padx=2)
        ttk.Button(btn_row, text="✏️ Sửa",
                   command=self.open_edit_dialog).pack(side="left", padx=2)
        ttk.Button(btn_row, text="🗑️ Xóa",
                   command=self.delete_selected).pack(side="left", padx=2)

    # ── Data ─────────────────────────────────────────────────────────────────

    def load_data(self):
        self._items = db.get_all_shopping_items()
        self._refresh_tree()

    def _refresh_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        filter_val = self._filter_var.get()
        for item in self._items:
            if filter_val == "pending" and item["is_bought"]:
                continue
            if filter_val == "bought" and not item["is_bought"]:
                continue

            bought_label = "✅ Đã Mua" if item["is_bought"] else "⬜ Chưa Mua"
            tag = "bought" if item["is_bought"] else "pending"
            notes_display = (item["notes"] or "")[:80]

            self.tree.insert(
                "", "end",
                iid=str(item["id"]),
                values=(bought_label, item["item_name"], notes_display),
                tags=(tag,),
            )

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def open_add_dialog(self):
        _ShoppingItemDialog(self, title="Thêm Sản Phẩm")

    def open_edit_dialog(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một mục.", parent=self)
            return
        item_id = int(sel[0])
        item = next((i for i in self._items if i["id"] == item_id), None)
        if item:
            _ShoppingItemDialog(self, title="Sửa Sản Phẩm", item=item)

    def toggle_bought(self):
        sel = self.tree.selection()
        if not sel:
            return
        db.toggle_shopping_item_bought(int(sel[0]))
        self.load_data()

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Xác nhận", "Xóa sản phẩm này?", parent=self):
            db.delete_shopping_item(int(sel[0]))
            self.load_data()


class _ShoppingItemDialog(tk.Toplevel):
    def __init__(self, parent_frame, title, item=None):
        super().__init__(parent_frame)
        self.parent_frame = parent_frame
        self.item = item
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self._build()
        if item:
            self._populate(item)
        self.transient(parent_frame.winfo_toplevel())
        self.wait_window()

    def _build(self):
        pad = {"padx": 10, "pady": 6}
        frm = tk.Frame(self, bg=CARD_BG, padx=16, pady=16)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="Tên Sản Phẩm *:", bg=CARD_BG,
                 font=FONT_BOLD).grid(row=0, column=0, sticky="w", **pad)
        self._name_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._name_var, width=34).grid(
            row=0, column=1, sticky="w", **pad)

        tk.Label(frm, text="Ghi Chú:", bg=CARD_BG,
                 font=FONT_BOLD).grid(row=1, column=0, sticky="nw", **pad)
        self._notes_text = tk.Text(frm, width=34, height=4, font=FONT)
        self._notes_text.grid(row=1, column=1, sticky="w", **pad)

        if self.item is not None:
            tk.Label(frm, text="Đã Mua:", bg=CARD_BG,
                     font=FONT_BOLD).grid(row=2, column=0, sticky="w", **pad)
            self._bought_var = tk.BooleanVar(value=bool(self.item.get("is_bought")))
            ttk.Checkbutton(frm, variable=self._bought_var).grid(
                row=2, column=1, sticky="w", **pad)
        else:
            self._bought_var = tk.BooleanVar(value=False)

        btn_frm = tk.Frame(frm, bg=CARD_BG)
        btn_frm.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frm, text="💾 Lưu", command=self._save).pack(side="left", padx=6)
        ttk.Button(btn_frm, text="❌ Hủy", command=self.destroy).pack(side="left", padx=6)

    def _populate(self, item):
        self._name_var.set(item["item_name"])
        if item.get("notes"):
            self._notes_text.insert("1.0", item["notes"])

    def _save(self):
        item_name = self._name_var.get().strip()
        notes = self._notes_text.get("1.0", "end").strip()
        is_bought = self._bought_var.get()

        if not item_name:
            messagebox.showerror("Lỗi", "Tên sản phẩm không được để trống.", parent=self)
            return

        if self.item:
            db.update_shopping_item(self.item["id"], item_name, notes, is_bought)
        else:
            db.add_shopping_item(item_name, notes)

        self.parent_frame.load_data()
        self.destroy()
