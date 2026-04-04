"""
Planned expenses tab – fixed monthly planned expenses with checkbox tracking.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
import database as db

BG = "#F0F4F8"
CARD_BG = "#FFFFFF"
ACCENT = "#3498DB"
DONE_COLOR = "#27AE60"
PENDING_COLOR = "#E74C3C"
TEXT_DARK = "#2C3E50"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADER = ("Segoe UI", 12, "bold")


def _fmt_money(val):
    try:
        return f"{int(val):,} ₫"
    except Exception:
        return str(val)


class PlannedExpensesFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        # ── Controls ──────────────────────────────────────────────────────
        ctrl = tk.Frame(self, bg=BG)
        ctrl.pack(fill="x", padx=10, pady=(10, 0))

        tk.Label(ctrl, text="Tháng:", bg=BG, font=FONT).pack(side="left")
        self.month_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
        ttk.Entry(ctrl, textvariable=self.month_var, width=10).pack(side="left", padx=(4, 10))
        ttk.Button(ctrl, text="🔍 Lọc", command=self.load_data).pack(side="left", padx=2)
        ttk.Button(ctrl, text="+ Thêm Dự Chi", command=self.open_add_dialog).pack(side="left", padx=2)

        # ── Summary ───────────────────────────────────────────────────────
        self.lbl_summary = tk.Label(self, text="", bg=BG, font=FONT_BOLD, fg=TEXT_DARK)
        self.lbl_summary.pack(anchor="w", padx=10, pady=4)

        # ── Treeview ──────────────────────────────────────────────────────
        tree_frame = tk.Frame(self, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        cols = ("status", "name", "amount", "note", "month")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        headings = {
            "status": ("Trạng Thái", 100),
            "name": ("Khoản Chi", 200),
            "amount": ("Số Tiền", 120),
            "note": ("Ghi Chú", 240),
            "month": ("Tháng", 90),
        }
        for col, (text, width) in headings.items():
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w" if col != "amount" else "e")

        self.tree.tag_configure("saved", foreground=DONE_COLOR, font=FONT_BOLD)
        self.tree.tag_configure("pending", foreground=PENDING_COLOR)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.tree.bind("<Double-1>", lambda e: self.toggle_saved())

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Button(btn_row, text="✅ Đánh dấu Đã Dành", command=self.toggle_saved).pack(side="left", padx=2)
        ttk.Button(btn_row, text="✏️ Sửa", command=self.open_edit_dialog).pack(side="left", padx=2)
        ttk.Button(btn_row, text="🗑️ Xóa", command=self.delete_selected).pack(side="left", padx=2)

    # ── Data ─────────────────────────────────────────────────────────────────

    def load_data(self):
        month = self.month_var.get().strip()
        self._items = db.get_planned_expenses(month=month if month else None)
        self._refresh_tree()

    def _refresh_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        total = sum(i["amount"] for i in self._items)
        saved = sum(i["amount"] for i in self._items if i["is_saved"])
        self.lbl_summary.config(
            text=f"Tổng dự chi: {_fmt_money(total)}   |   Đã dành: {_fmt_money(saved)}   |   Còn lại: {_fmt_money(total - saved)}"
        )
        for item in self._items:
            status = "✅ Đã Dành" if item["is_saved"] else "⏳ Chưa Đủ"
            tag = "saved" if item["is_saved"] else "pending"
            self.tree.insert(
                "", "end",
                iid=str(item["id"]),
                values=(status, item["name"], _fmt_money(item["amount"]), item["note"] or "", item["month"]),
                tags=(tag,),
            )

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def open_add_dialog(self):
        _PlannedDialog(self, title="Thêm Dự Chi")

    def open_edit_dialog(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một mục.", parent=self)
            return
        item_id = int(sel[0])
        item = next((i for i in self._items if i["id"] == item_id), None)
        if item:
            _PlannedDialog(self, title="Sửa Dự Chi", item=item)

    def toggle_saved(self):
        sel = self.tree.selection()
        if not sel:
            return
        db.toggle_planned_saved(int(sel[0]))
        self.load_data()

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Xác nhận", "Xóa khoản dự chi này?", parent=self):
            db.delete_planned_expense(int(sel[0]))
            self.load_data()


class _PlannedDialog(tk.Toplevel):
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

        tk.Label(frm, text="Tên Khoản Chi:", bg=CARD_BG, font=FONT_BOLD).grid(row=0, column=0, sticky="w", **pad)
        self.name_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.name_var, width=28).grid(row=0, column=1, sticky="w", **pad)

        tk.Label(frm, text="Số Tiền (₫):", bg=CARD_BG, font=FONT_BOLD).grid(row=1, column=0, sticky="w", **pad)
        self.amount_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.amount_var, width=28).grid(row=1, column=1, sticky="w", **pad)

        tk.Label(frm, text="Tháng (YYYY-MM):", bg=CARD_BG, font=FONT_BOLD).grid(row=2, column=0, sticky="w", **pad)
        self.month_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
        ttk.Entry(frm, textvariable=self.month_var, width=28).grid(row=2, column=1, sticky="w", **pad)

        tk.Label(frm, text="Ghi Chú:", bg=CARD_BG, font=FONT_BOLD).grid(row=3, column=0, sticky="nw", **pad)
        self.note_text = tk.Text(frm, width=30, height=3, font=FONT)
        self.note_text.grid(row=3, column=1, sticky="w", **pad)

        btn_frm = tk.Frame(frm, bg=CARD_BG)
        btn_frm.grid(row=4, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frm, text="💾 Lưu", command=self._save).pack(side="left", padx=6)
        ttk.Button(btn_frm, text="Hủy", command=self.destroy).pack(side="left", padx=6)

    def _populate(self, item):
        self.name_var.set(item["name"])
        self.amount_var.set(str(int(item["amount"])))
        self.month_var.set(item["month"])
        if item.get("note"):
            self.note_text.insert("1.0", item["note"])

    def _save(self):
        name = self.name_var.get().strip()
        amount_str = self.amount_var.get().strip().replace(",", "")
        month = self.month_var.get().strip()
        note = self.note_text.get("1.0", "end").strip()

        if not name:
            messagebox.showerror("Lỗi", "Tên khoản chi không được để trống.", parent=self)
            return
        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Số tiền không hợp lệ.", parent=self)
            return
        if not month:
            messagebox.showerror("Lỗi", "Vui lòng nhập tháng.", parent=self)
            return

        if self.item:
            db.update_planned_expense(self.item["id"], name, amount, note)
        else:
            db.add_planned_expense(name, amount, month, note)

        self.parent_frame.load_data()
        self.destroy()
