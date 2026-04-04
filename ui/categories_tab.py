"""
Categories management tab.
Allows users to view, add, edit, and delete income/expense categories and subcategories.
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


class CategoriesFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(top, text="Quản Lý Danh Mục", bg=BG, fg=TEXT_DARK, font=FONT_HEADER).pack(side="left")

        # Two panes: parents left, children right
        panes = tk.Frame(self, bg=BG)
        panes.pack(fill="both", expand=True, padx=10, pady=8)

        # ── Parent categories ──────────────────────────────────────────────
        left = tk.LabelFrame(panes, text="Danh Mục Chính", bg=BG, font=FONT_BOLD)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self.parent_tree = ttk.Treeview(left, columns=("name",), show="headings", selectmode="browse", height=18)
        self.parent_tree.heading("name", text="Tên Danh Mục")
        self.parent_tree.column("name", width=180)
        vsb = ttk.Scrollbar(left, orient="vertical", command=self.parent_tree.yview)
        self.parent_tree.configure(yscrollcommand=vsb.set)
        self.parent_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.parent_tree.bind("<<TreeviewSelect>>", self._on_parent_select)

        btn_p = tk.Frame(left, bg=BG)
        btn_p.pack(fill="x")
        ttk.Button(btn_p, text="+ Thêm", command=self._add_parent).pack(side="left", padx=2, pady=4)
        ttk.Button(btn_p, text="✏️ Sửa", command=self._edit_parent).pack(side="left", padx=2)
        ttk.Button(btn_p, text="🗑️ Xóa", command=self._delete_parent).pack(side="left", padx=2)

        # ── Subcategories ──────────────────────────────────────────────────
        right = tk.LabelFrame(panes, text="Danh Mục Con", bg=BG, font=FONT_BOLD)
        right.pack(side="left", fill="both", expand=True)

        self.child_tree = ttk.Treeview(right, columns=("name",), show="headings", selectmode="browse", height=18)
        self.child_tree.heading("name", text="Tên Danh Mục Con")
        self.child_tree.column("name", width=180)
        vsb2 = ttk.Scrollbar(right, orient="vertical", command=self.child_tree.yview)
        self.child_tree.configure(yscrollcommand=vsb2.set)
        self.child_tree.pack(side="left", fill="both", expand=True)
        vsb2.pack(side="right", fill="y")

        btn_c = tk.Frame(right, bg=BG)
        btn_c.pack(fill="x")
        ttk.Button(btn_c, text="+ Thêm Con", command=self._add_child).pack(side="left", padx=2, pady=4)
        ttk.Button(btn_c, text="✏️ Sửa", command=self._edit_child).pack(side="left", padx=2)
        ttk.Button(btn_c, text="🗑️ Xóa", command=self._delete_child).pack(side="left", padx=2)

    # ── Load ─────────────────────────────────────────────────────────────────

    def load_data(self):
        self._parents = db.get_categories()
        for row in self.parent_tree.get_children():
            self.parent_tree.delete(row)
        for cat in self._parents:
            self.parent_tree.insert("", "end", iid=str(cat["id"]), values=(cat["name"],))
        # Clear children
        for row in self.child_tree.get_children():
            self.child_tree.delete(row)

    def _on_parent_select(self, _event=None):
        sel = self.parent_tree.selection()
        for row in self.child_tree.get_children():
            self.child_tree.delete(row)
        if not sel:
            return
        parent_id = int(sel[0])
        self._children = db.get_categories(parent_id=parent_id)
        for cat in self._children:
            self.child_tree.insert("", "end", iid=str(cat["id"]), values=(cat["name"],))

    # ── Parent CRUD ───────────────────────────────────────────────────────────

    def _add_parent(self):
        name = _ask_name(self, "Thêm Danh Mục Chính", "Tên danh mục:")
        if name:
            db.add_category(name)
            self.load_data()

    def _edit_parent(self):
        sel = self.parent_tree.selection()
        if not sel:
            return
        cat_id = int(sel[0])
        cat = next((c for c in self._parents if c["id"] == cat_id), None)
        if cat:
            name = _ask_name(self, "Sửa Danh Mục", "Tên mới:", initial=cat["name"])
            if name:
                db.update_category(cat_id, name)
                self.load_data()

    def _delete_parent(self):
        sel = self.parent_tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Xác nhận", "Xóa danh mục này sẽ xóa toàn bộ danh mục con. Tiếp tục?", parent=self):
            db.delete_category(int(sel[0]))
            self.load_data()

    # ── Child CRUD ────────────────────────────────────────────────────────────

    def _add_child(self):
        sel = self.parent_tree.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn danh mục chính trước.", parent=self)
            return
        name = _ask_name(self, "Thêm Danh Mục Con", "Tên danh mục con:")
        if name:
            db.add_category(name, parent_id=int(sel[0]))
            self._on_parent_select()

    def _edit_child(self):
        sel = self.child_tree.selection()
        if not sel:
            return
        cat_id = int(sel[0])
        children = getattr(self, "_children", [])
        cat = next((c for c in children if c["id"] == cat_id), None)
        if cat:
            name = _ask_name(self, "Sửa Danh Mục Con", "Tên mới:", initial=cat["name"])
            if name:
                db.update_category(cat_id, name)
                self._on_parent_select()

    def _delete_child(self):
        sel = self.child_tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Xác nhận", "Xóa danh mục con này?", parent=self):
            db.delete_category(int(sel[0]))
            self._on_parent_select()


def _ask_name(parent, title, label, initial=""):
    """Simple single-field input dialog."""
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.grab_set()
    result = {"value": None}

    tk.Label(dlg, text=label, padx=12, pady=8).pack()
    var = tk.StringVar(value=initial)
    entry = ttk.Entry(dlg, textvariable=var, width=28)
    entry.pack(padx=12, pady=4)
    entry.focus_set()

    def _ok():
        v = var.get().strip()
        if not v:
            messagebox.showerror("Lỗi", "Tên không được để trống.", parent=dlg)
            return
        result["value"] = v
        dlg.destroy()

    btn_row = tk.Frame(dlg)
    btn_row.pack(pady=8)
    ttk.Button(btn_row, text="OK", command=_ok).pack(side="left", padx=6)
    ttk.Button(btn_row, text="Hủy", command=dlg.destroy).pack(side="left", padx=6)

    entry.bind("<Return>", lambda e: _ok())
    dlg.transient(parent)
    dlg.wait_window()
    return result["value"]
