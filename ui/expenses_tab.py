"""
Expenses tab – daily income/expense management.
Features: add, edit, delete, filter by month, sort, export to Excel.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime
import database as db
from utils.excel_export import export_monthly_report, OPENPYXL_OK

# ── Colour palette (matches dashboard) ──────────────────────────────────────
BG = "#F0F4F8"
HEADER_BG = "#2C3E50"
CARD_BG = "#FFFFFF"
ACCENT = "#3498DB"
INCOME_COLOR = "#27AE60"
EXPENSE_COLOR = "#E74C3C"
TEXT_DARK = "#2C3E50"
TEXT_LIGHT = "#ECF0F1"
BTN_HOVER = "#2980B9"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADER = ("Segoe UI", 12, "bold")


def _fmt_money(val):
    try:
        return f"{int(val):,} ₫"
    except Exception:
        return str(val)


class ExpensesFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._build_ui()
        self.load_data()

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Top controls bar ─────────────────────────────────────────────
        ctrl = tk.Frame(self, bg=BG)
        ctrl.pack(fill="x", padx=10, pady=(10, 0))

        tk.Label(ctrl, text="Tháng:", bg=BG, font=FONT).pack(side="left")
        self.month_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
        self.month_entry = ttk.Entry(ctrl, textvariable=self.month_var, width=10)
        self.month_entry.pack(side="left", padx=(4, 10))

        ttk.Button(ctrl, text="🔍 Lọc", command=self.load_data).pack(side="left", padx=2)
        ttk.Button(ctrl, text="+ Thêm Mới", command=self.open_add_dialog).pack(side="left", padx=2)
        ttk.Button(ctrl, text="📊 Xuất Excel", command=self.export_excel).pack(side="left", padx=2)

        # ── Summary bar ──────────────────────────────────────────────────
        self.summary_frame = tk.Frame(self, bg=BG)
        self.summary_frame.pack(fill="x", padx=10, pady=6)

        self.lbl_income = tk.Label(
            self.summary_frame, text="Thu: 0 ₫", bg=INCOME_COLOR,
            fg="white", font=FONT_BOLD, padx=16, pady=4
        )
        self.lbl_income.pack(side="left", padx=(0, 4))

        self.lbl_expense = tk.Label(
            self.summary_frame, text="Chi: 0 ₫", bg=EXPENSE_COLOR,
            fg="white", font=FONT_BOLD, padx=16, pady=4
        )
        self.lbl_expense.pack(side="left", padx=(0, 4))

        self.lbl_balance = tk.Label(
            self.summary_frame, text="Số dư: 0 ₫", bg=ACCENT,
            fg="white", font=FONT_BOLD, padx=16, pady=4
        )
        self.lbl_balance.pack(side="left")

        # ── Treeview ─────────────────────────────────────────────────────
        tree_frame = tk.Frame(self, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("date", "type", "category", "subcategory", "amount", "description")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")

        headings = {
            "date": ("Ngày", 90),
            "type": ("Loại", 60),
            "category": ("Danh Mục", 130),
            "subcategory": ("Danh Mục Con", 130),
            "amount": ("Số Tiền", 110),
            "description": ("Diễn Giải", 260),
        }
        for col, (text, width) in headings.items():
            self.tree.heading(col, text=text, command=lambda c=col: self._sort_tree(c))
            self.tree.column(col, width=width, anchor="w" if col not in ("amount",) else "e")

        # Tag colours
        self.tree.tag_configure("income", foreground=INCOME_COLOR)
        self.tree.tag_configure("expense", foreground=EXPENSE_COLOR)
        self.tree.tag_configure("odd", background="#F7F9FC")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        # Double-click to edit
        self.tree.bind("<Double-1>", lambda e: self.open_edit_dialog())

        # Action buttons
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Button(btn_row, text="✏️ Sửa", command=self.open_edit_dialog).pack(side="left", padx=2)
        ttk.Button(btn_row, text="🗑️ Xóa", command=self.delete_selected).pack(side="left", padx=2)

        # Sort state
        self._sort_col = "date"
        self._sort_reverse = True

    # ── Data loading ─────────────────────────────────────────────────────────

    def load_data(self):
        month = self.month_var.get().strip()
        self._expenses = db.get_expenses(month=month if month else None)
        self._refresh_tree()
        self._refresh_summary(month)

    def _refresh_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, exp in enumerate(self._expenses):
            tag = exp["type"]
            if i % 2 == 1:
                tag = (tag, "odd")
            self.tree.insert(
                "", "end",
                iid=str(exp["id"]),
                values=(
                    exp["expense_date"],
                    "Thu" if exp["type"] == "income" else "Chi",
                    exp["category_name"] or "—",
                    exp["subcategory_name"] or "—",
                    _fmt_money(exp["amount"]),
                    exp["description"] or "",
                ),
                tags=tag,
            )

    def _refresh_summary(self, month):
        s = db.get_monthly_summary(month)
        income = s.get("income", 0)
        expense = s.get("expense", 0)
        balance = income - expense
        self.lbl_income.config(text=f"Thu: {_fmt_money(income)}")
        self.lbl_expense.config(text=f"Chi: {_fmt_money(expense)}")
        self.lbl_balance.config(text=f"Số dư: {_fmt_money(balance)}")

    def _sort_tree(self, col):
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False

        col_map = {
            "date": "expense_date",
            "type": "type",
            "category": "category_name",
            "subcategory": "subcategory_name",
            "amount": "amount",
            "description": "description",
        }
        key = col_map.get(col, col)
        self._expenses.sort(
            key=lambda r: (r.get(key) or "").lower() if isinstance(r.get(key), str) else (r.get(key) or 0),
            reverse=self._sort_reverse,
        )
        self._refresh_tree()

    # ── CRUD dialogs ──────────────────────────────────────────────────────────

    def open_add_dialog(self):
        _ExpenseDialog(self, title="Thêm Thu Chi Mới")

    def open_edit_dialog(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một mục để sửa.", parent=self)
            return
        exp_id = int(sel[0])
        exp = next((e for e in self._expenses if e["id"] == exp_id), None)
        if exp:
            _ExpenseDialog(self, title="Sửa Thu Chi", expense=exp)

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một mục để xóa.", parent=self)
            return
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa mục này?", parent=self):
            db.delete_expense(int(sel[0]))
            self.load_data()

    # ── Excel export ──────────────────────────────────────────────────────────

    def export_excel(self):
        if not OPENPYXL_OK:
            messagebox.showerror("Lỗi", "Cần cài openpyxl: pip install openpyxl", parent=self)
            return
        month = self.month_var.get().strip() or date.today().strftime("%Y-%m")
        expenses = db.get_expenses(month=month)
        summary = db.get_monthly_summary(month)
        cat_summary = db.get_category_summary(month)

        out_dir = filedialog.askdirectory(title="Chọn thư mục lưu file Excel", parent=self)
        if not out_dir:
            return
        try:
            path = export_monthly_report(month, expenses, summary, cat_summary, out_dir)
            messagebox.showinfo("Thành công", f"Đã xuất báo cáo:\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("Lỗi", str(e), parent=self)


# ── Add / Edit Dialog ─────────────────────────────────────────────────────────

class _ExpenseDialog(tk.Toplevel):
    def __init__(self, parent_frame, title, expense=None):
        super().__init__(parent_frame)
        self.parent_frame = parent_frame
        self.expense = expense
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self._build()
        if expense:
            self._populate(expense)
        self.transient(parent_frame.winfo_toplevel())
        self.wait_window()

    def _build(self):
        pad = {"padx": 10, "pady": 6}
        frm = tk.Frame(self, bg=CARD_BG, padx=16, pady=16)
        frm.pack(fill="both", expand=True)

        # Type
        tk.Label(frm, text="Loại:", bg=CARD_BG, font=FONT_BOLD).grid(row=0, column=0, sticky="w", **pad)
        self.type_var = tk.StringVar(value="expense")
        type_frame = tk.Frame(frm, bg=CARD_BG)
        type_frame.grid(row=0, column=1, sticky="w", **pad)
        tk.Radiobutton(
            type_frame, text="Chi", variable=self.type_var, value="expense",
            bg=CARD_BG, command=self._on_type_change,
        ).pack(side="left")
        tk.Radiobutton(
            type_frame, text="Thu", variable=self.type_var, value="income",
            bg=CARD_BG, command=self._on_type_change,
        ).pack(side="left")

        # Category
        tk.Label(frm, text="Danh Mục:", bg=CARD_BG, font=FONT_BOLD).grid(row=1, column=0, sticky="w", **pad)
        self._cats = db.get_categories(type_filter="expense")
        cat_names = [c["name"] for c in self._cats]
        self.cat_var = tk.StringVar()
        self.cat_cb = ttk.Combobox(frm, textvariable=self.cat_var, values=cat_names, state="readonly", width=22)
        self.cat_cb.grid(row=1, column=1, sticky="w", **pad)
        self.cat_cb.bind("<<ComboboxSelected>>", self._on_cat_change)

        # Subcategory
        tk.Label(frm, text="Danh Mục Con:", bg=CARD_BG, font=FONT_BOLD).grid(row=2, column=0, sticky="w", **pad)
        self.sub_var = tk.StringVar()
        self.sub_cb = ttk.Combobox(frm, textvariable=self.sub_var, width=22)
        self.sub_cb.grid(row=2, column=1, sticky="w", **pad)
        tk.Label(frm, text="(không bắt buộc)", bg=CARD_BG, fg="#7F8C8D",
                 font=("Segoe UI", 9)).grid(row=2, column=2, sticky="w", padx=2)

        # Amount
        tk.Label(frm, text="Số Tiền (₫):", bg=CARD_BG, font=FONT_BOLD).grid(row=3, column=0, sticky="w", **pad)
        self.amount_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.amount_var, width=24).grid(row=3, column=1, sticky="w", **pad)

        # Date
        tk.Label(frm, text="Ngày (YYYY-MM-DD):", bg=CARD_BG, font=FONT_BOLD).grid(row=4, column=0, sticky="w", **pad)
        self.date_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(frm, textvariable=self.date_var, width=24).grid(row=4, column=1, sticky="w", **pad)

        # Description
        tk.Label(frm, text="Diễn Giải:", bg=CARD_BG, font=FONT_BOLD).grid(row=5, column=0, sticky="nw", **pad)
        self.desc_text = tk.Text(frm, width=30, height=4, font=FONT)
        self.desc_text.grid(row=5, column=1, sticky="w", **pad)

        # Buttons
        btn_frm = tk.Frame(frm, bg=CARD_BG)
        btn_frm.grid(row=6, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frm, text="💾 Lưu", command=self._save).pack(side="left", padx=6)
        ttk.Button(btn_frm, text="Hủy", command=self.destroy).pack(side="left", padx=6)

        # Category management link
        tk.Label(frm, text="Quản lý danh mục →", bg=CARD_BG, fg=ACCENT,
                 cursor="hand2", font=FONT).grid(row=7, column=1, sticky="e")

    def _on_type_change(self):
        """Reload category list when income/expense type is toggled."""
        self._cats = db.get_categories(type_filter=self.type_var.get())
        cat_names = [c["name"] for c in self._cats]
        self.cat_cb["values"] = cat_names
        self.cat_var.set("")
        self.sub_cb["values"] = []
        self.sub_var.set("")
        self._subs = []

    def _on_cat_change(self, _event=None):
        cat_name = self.cat_var.get()
        cat = next((c for c in self._cats if c["name"] == cat_name), None)
        if cat:
            subs = db.get_categories(parent_id=cat["id"])
            sub_names = [s["name"] for s in subs]
            self.sub_cb["values"] = sub_names
            self.sub_var.set("")  # Keep blank – subcategory is optional
            self._subs = subs
        else:
            self.sub_cb["values"] = []
            self._subs = []

    def _populate(self, exp):
        self.type_var.set(exp["type"])
        # Reload categories for the correct type
        self._cats = db.get_categories(type_filter=exp["type"])
        self.cat_cb["values"] = [c["name"] for c in self._cats]
        # Set category
        cat_name = exp.get("category_name") or ""
        self.cat_var.set(cat_name)
        self._on_cat_change()
        sub_name = exp.get("subcategory_name") or ""
        self.sub_var.set(sub_name)
        self.amount_var.set(str(int(exp["amount"])))
        self.date_var.set(exp["expense_date"])
        if exp.get("description"):
            self.desc_text.insert("1.0", exp["description"])

    def _save(self):
        type_ = self.type_var.get()
        cat_name = self.cat_var.get()
        sub_name = self.sub_var.get()
        amount_str = self.amount_var.get().strip().replace(",", "")
        exp_date = self.date_var.get().strip()
        description = self.desc_text.get("1.0", "end").strip()

        # Validation
        if not cat_name:
            messagebox.showerror("Lỗi", "Vui lòng chọn danh mục.", parent=self)
            return
        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Số tiền không hợp lệ.", parent=self)
            return
        try:
            datetime.strptime(exp_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Lỗi", "Ngày không hợp lệ (YYYY-MM-DD).", parent=self)
            return

        cat = next((c for c in self._cats if c["name"] == cat_name), None)
        cat_id = cat["id"] if cat else None
        subs = getattr(self, "_subs", [])
        sub = next((s for s in subs if s["name"] == sub_name), None)
        sub_id = sub["id"] if sub else None

        if self.expense:
            db.update_expense(self.expense["id"], type_, cat_id, sub_id, amount, description, exp_date)
        else:
            db.add_expense(type_, cat_id, sub_id, amount, description, exp_date)

        self.parent_frame.load_data()
        self.destroy()
