"""
Income/Expense Management tab – consolidated view of:
  • Quản Lý Danh Mục  (Category Management)
  • Dự Chi Cố Định     (Planned Expenses)
  • Báo Cáo            (Reports)
All three sections are accessible via sub-tabs inside one main tab.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta, datetime
from collections import defaultdict
import database as db
from ui.expenses_tab import _PaginationBar

BG = "#F0F4F8"
CARD_BG = "#FFFFFF"
HEADER_BG = "#2C3E50"
ACCENT = "#3498DB"
INCOME_COLOR = "#27AE60"
EXPENSE_COLOR = "#E74C3C"
DONE_COLOR = "#27AE60"
PENDING_COLOR = "#E74C3C"
TEXT_DARK = "#2C3E50"
TEXT_LIGHT = "#ECF0F1"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADER = ("Segoe UI", 12, "bold")

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False


def _fmt_money(val):
    try:
        return f"{int(val):,} ₫"
    except Exception:
        return str(val)


# ─────────────────────────────────────────────────────────────────────────────
# Main consolidated frame
# ─────────────────────────────────────────────────────────────────────────────

class IncomeExpenseManagementFrame(tk.Frame):
    """Consolidated tab with sub-tabs for Categories, Planned Expenses, and Reports."""

    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._build_ui()

    def _build_ui(self):
        tk.Label(self, text="📊 Thu Chi", bg=BG, fg=TEXT_DARK,
                 font=FONT_HEADER).pack(anchor="w", padx=12, pady=(10, 4))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._categories_tab = _CategoriesSubTab(notebook)
        self._planned_tab = _PlannedSubTab(notebook)
        self._reports_tab = _ReportsSubTab(notebook)

        notebook.add(self._categories_tab, text="🗂️ Quản Lý Danh Mục")
        notebook.add(self._planned_tab, text="📋 Dự Chi Cố Định")
        notebook.add(self._reports_tab, text="📈 Báo Cáo")

        # Reload data when switching sub-tabs
        notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

    def _on_tab_change(self, event):
        nb = event.widget
        idx = nb.index(nb.select())
        frames = [self._categories_tab, self._planned_tab, self._reports_tab]
        if hasattr(frames[idx], "load_data"):
            frames[idx].load_data()

    def load_data(self):
        """Called when the main sidebar switches to this tab."""
        self._categories_tab.load_data()
        self._planned_tab.load_data()
        # Reports are loaded on demand (user clicks 🔍 Xem Báo Cáo)


# ─────────────────────────────────────────────────────────────────────────────
# Sub-tab 1: Category Management
# ─────────────────────────────────────────────────────────────────────────────

class _CategoriesSubTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        panes = tk.Frame(self, bg=BG)
        panes.pack(fill="both", expand=True, padx=10, pady=8)

        # ── Parent categories ─────────────────────────────────────────────
        left = tk.LabelFrame(panes, text="Danh Mục Chính", bg=BG, font=FONT_BOLD)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self.parent_tree = ttk.Treeview(
            left, columns=("name", "type"), show="headings", selectmode="browse", height=18
        )
        self.parent_tree.heading("name", text="Tên Danh Mục")
        self.parent_tree.heading("type", text="Loại")
        self.parent_tree.column("name", width=150)
        self.parent_tree.column("type", width=60, anchor="center")
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

        # ── Subcategories ─────────────────────────────────────────────────
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

    def load_data(self):
        self._parents = db.get_categories()
        for row in self.parent_tree.get_children():
            self.parent_tree.delete(row)
        for cat in self._parents:
            type_label = "Thu" if cat.get("type") == "income" else "Chi"
            self.parent_tree.insert("", "end", iid=str(cat["id"]), values=(cat["name"], type_label))
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

    def _add_parent(self):
        result = _ask_name_and_type(self, "Thêm Danh Mục Chính")
        if result:
            db.add_category(result["name"], type_=result["type"])
            self.load_data()

    def _edit_parent(self):
        sel = self.parent_tree.selection()
        if not sel:
            return
        cat_id = int(sel[0])
        cat = next((c for c in self._parents if c["id"] == cat_id), None)
        if cat:
            result = _ask_name_and_type(
                self, "Sửa Danh Mục",
                initial_name=cat["name"],
                initial_type=cat.get("type") or "expense",
            )
            if result:
                db.update_category(cat_id, result["name"], type_=result["type"])
                self.load_data()

    def _delete_parent(self):
        sel = self.parent_tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Xác nhận", "Xóa danh mục này sẽ xóa toàn bộ danh mục con. Tiếp tục?", parent=self):
            db.delete_category(int(sel[0]))
            self.load_data()

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


# ─────────────────────────────────────────────────────────────────────────────
# Sub-tab 2: Planned Expenses
# ─────────────────────────────────────────────────────────────────────────────

class _PlannedSubTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._items = []
        self._current_page = 1
        self._per_page = 50
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        ctrl = tk.Frame(self, bg=BG)
        ctrl.pack(fill="x", padx=10, pady=(10, 0))

        tk.Label(ctrl, text="Tháng:", bg=BG, font=FONT).pack(side="left")
        self.month_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
        ttk.Entry(ctrl, textvariable=self.month_var, width=10).pack(side="left", padx=(4, 10))
        ttk.Button(ctrl, text="🔍 Lọc", command=self.load_data).pack(side="left", padx=2)
        ttk.Button(ctrl, text="+ Thêm Dự Chi", command=self.open_add_dialog).pack(side="left", padx=2)

        self.lbl_summary = tk.Label(self, text="", bg=BG, font=FONT_BOLD, fg=TEXT_DARK)
        self.lbl_summary.pack(anchor="w", padx=10, pady=4)

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

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=10, pady=(0, 4))
        ttk.Button(btn_row, text="✅ Đánh dấu Đã Dành", command=self.toggle_saved).pack(side="left", padx=2)
        ttk.Button(btn_row, text="✏️ Sửa", command=self.open_edit_dialog).pack(side="left", padx=2)
        ttk.Button(btn_row, text="🗑️ Xóa", command=self.delete_selected).pack(side="left", padx=2)

        # -- Pagination bar ---------------------------------------------------
        self._pagination = _PaginationBar(self, on_page_change=self._on_page_change)
        self._pagination.pack(fill="x", padx=10, pady=(0, 8))

    def _on_page_change(self, page, per_page):
        self._current_page = page
        self._per_page = per_page
        self.load_data(keep_page=True)

    def load_data(self, keep_page=False):
        if not keep_page:
            self._current_page = 1

        month = self.month_var.get().strip() or None
        result = db.get_planned_expenses_paginated(
            page=self._current_page,
            per_page=self._per_page,
            month=month,
        )
        self._items = result["data"]
        self._current_page = result["page"]

        # Summary totals are computed across ALL matching rows (not just the page)
        all_items = db.get_planned_expenses(month=month)
        total = sum(i["amount"] for i in all_items)
        saved = sum(i["amount"] for i in all_items if i["is_saved"])
        self.lbl_summary.config(
            text=f"Tổng dự chi: {_fmt_money(total)}   |   Đã dành: {_fmt_money(saved)}   |   Còn lại: {_fmt_money(total - saved)}"
        )

        self._refresh_tree()
        self._pagination.update(
            page=result["page"],
            pages=result["pages"],
            total=result["total"],
            per_page=result["per_page"],
        )

    def _refresh_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for item in self._items:
            status = "✅ Đã Dành" if item["is_saved"] else "⏳ Chưa Đủ"
            tag = "saved" if item["is_saved"] else "pending"
            self.tree.insert(
                "", "end",
                iid=str(item["id"]),
                values=(status, item["name"], _fmt_money(item["amount"]), item["note"] or "", item["month"]),
                tags=(tag,),
            )

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
        self.load_data(keep_page=True)

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Xác nhận", "Xóa khoản dự chi này?", parent=self):
            db.delete_planned_expense(int(sel[0]))
            self.load_data()


# ─────────────────────────────────────────────────────────────────────────────
# Sub-tab 3: Reports
# ─────────────────────────────────────────────────────────────────────────────

class _ReportsSubTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._canvas_bar = None
        self._canvas_pie = None
        self._build_ui()

    def _build_ui(self):
        # ── Controls ──────────────────────────────────────────────────────
        ctrl = tk.Frame(self, bg=BG)
        ctrl.pack(fill="x", padx=12, pady=(10, 0))

        tk.Label(ctrl, text="Từ ngày:", bg=BG, font=FONT).pack(side="left")
        first_day = date.today().replace(day=1).isoformat()
        self.from_var = tk.StringVar(value=first_day)
        ttk.Entry(ctrl, textvariable=self.from_var, width=12).pack(side="left", padx=(4, 8))

        tk.Label(ctrl, text="Đến ngày:", bg=BG, font=FONT).pack(side="left")
        self.to_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(ctrl, textvariable=self.to_var, width=12).pack(side="left", padx=(4, 8))

        ttk.Button(ctrl, text="🔍 Xem Báo Cáo", command=self.load_data).pack(side="left", padx=4)

        # Quick-range buttons
        quick = tk.Frame(self, bg=BG)
        quick.pack(fill="x", padx=12, pady=4)
        for label, days in [("Tháng này", None), ("7 ngày qua", 7), ("30 ngày qua", 30)]:
            ttk.Button(quick, text=label,
                       command=lambda d=days: self._set_quick_range(d)).pack(side="left", padx=2)

        # ── Summary cards ─────────────────────────────────────────────────
        self.summary_frame = tk.Frame(self, bg=BG)
        self.summary_frame.pack(fill="x", padx=12, pady=6)

        self.lbl_income = tk.Label(
            self.summary_frame, text="Tổng Thu: —", bg=INCOME_COLOR,
            fg="white", font=FONT_BOLD, padx=16, pady=6)
        self.lbl_income.pack(side="left", padx=(0, 6))

        self.lbl_expense = tk.Label(
            self.summary_frame, text="Tổng Chi: —", bg=EXPENSE_COLOR,
            fg="white", font=FONT_BOLD, padx=16, pady=6)
        self.lbl_expense.pack(side="left", padx=(0, 6))

        self.lbl_balance = tk.Label(
            self.summary_frame, text="Số Dư: —", bg=ACCENT,
            fg="white", font=FONT_BOLD, padx=16, pady=6)
        self.lbl_balance.pack(side="left")

        # ── Chart area ────────────────────────────────────────────────────
        if MATPLOTLIB_OK:
            chart_frame = tk.Frame(self, bg=BG)
            chart_frame.pack(fill="both", expand=True, padx=12, pady=(0, 4))

            self._bar_frame = tk.LabelFrame(chart_frame, text="Biểu Đồ Cột (Thu vs Chi theo Ngày)",
                                            bg=BG, font=FONT_BOLD)
            self._bar_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))

            self._pie_frame = tk.LabelFrame(chart_frame, text="Biểu Đồ Tròn (Chi theo Danh Mục)",
                                            bg=BG, font=FONT_BOLD)
            self._pie_frame.pack(side="left", fill="both", expand=True)
        else:
            tk.Label(self, text="⚠️ Cần cài matplotlib để xem biểu đồ.\n\npip install matplotlib",
                     bg=BG, fg=EXPENSE_COLOR, font=FONT_BOLD,
                     justify="center").pack(expand=True)

        # ── Detail table ──────────────────────────────────────────────────
        tbl_frame = tk.LabelFrame(self, text="Chi Tiết Theo Danh Mục", bg=BG, font=FONT_BOLD)
        tbl_frame.pack(fill="x", padx=12, pady=(0, 10))

        cols = ("category", "income", "expense")
        self.detail_tree = ttk.Treeview(tbl_frame, columns=cols, show="headings",
                                        height=6, selectmode="browse")
        for col, text, width in [("category", "Danh Mục", 200),
                                  ("income", "Thu", 130),
                                  ("expense", "Chi", 130)]:
            self.detail_tree.heading(col, text=text)
            self.detail_tree.column(col, width=width, anchor="w" if col == "category" else "e")
        vsb2 = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.detail_tree.yview)
        self.detail_tree.configure(yscrollcommand=vsb2.set)
        self.detail_tree.pack(side="left", fill="x", expand=True)
        vsb2.pack(side="left", fill="y")

        # Make rows clickable for drilldown
        self.detail_tree.bind("<ButtonRelease-1>", self._on_category_click)
        self.detail_tree.bind("<Motion>", self._on_tree_motion)
        self.detail_tree.tag_configure("hover", background="#D6EAF8")
        tk.Label(tbl_frame, text="💡 Nhấp vào dòng danh mục để xem chi tiết",
                 bg=BG, fg="#7F8C8D", font=("Segoe UI", 8, "italic")).pack(
            side="bottom", anchor="w", padx=4, pady=(0, 2))

    def load_data(self):
        from_date = self.from_var.get().strip()
        to_date = self.to_var.get().strip()
        if not from_date or not to_date:
            messagebox.showerror("Lỗi", "Vui lòng nhập khoảng thời gian.", parent=self)
            return
        try:
            datetime.strptime(from_date, "%Y-%m-%d")
            datetime.strptime(to_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Lỗi", "Ngày không hợp lệ (YYYY-MM-DD).", parent=self)
            return
        if from_date > to_date:
            messagebox.showerror("Lỗi", "Ngày bắt đầu phải trước ngày kết thúc.", parent=self)
            return

        summary = db.get_summary_range(from_date, to_date)
        income = summary.get("income", 0.0)
        expense = summary.get("expense", 0.0)
        balance = income - expense
        self.lbl_income.config(text=f"Tổng Thu: {_fmt_money(income)}")
        self.lbl_expense.config(text=f"Tổng Chi: {_fmt_money(expense)}")
        self.lbl_balance.config(
            text=f"Số Dư: {_fmt_money(balance)}",
            bg=INCOME_COLOR if balance >= 0 else EXPENSE_COLOR,
        )

        if MATPLOTLIB_OK:
            self._draw_bar_chart(from_date, to_date)
            self._draw_pie_chart(from_date, to_date)

        self._refresh_detail_table(from_date, to_date)

    def _set_quick_range(self, days):
        today = date.today()
        if days is None:
            self.from_var.set(today.replace(day=1).isoformat())
        else:
            self.from_var.set((today - timedelta(days=days - 1)).isoformat())
        self.to_var.set(today.isoformat())
        self.load_data()

    def _draw_bar_chart(self, from_date, to_date):
        rows = db.get_daily_totals_range(from_date, to_date)

        day_data = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
        for r in rows:
            day_data[r["expense_date"]][r["type"]] = r["total"] or 0.0

        days = sorted(day_data.keys())
        inc_vals = [day_data[d]["income"] for d in days]
        exp_vals = [day_data[d]["expense"] for d in days]

        if self._canvas_bar:
            self._canvas_bar.get_tk_widget().destroy()

        fig = Figure(figsize=(5, 3), dpi=80, facecolor=BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor("#F7F9FC")

        if days:
            x = range(len(days))
            width = 0.35
            ax.bar([i - width / 2 for i in x], [v / 1e6 for v in inc_vals],
                   width, label="Thu", color=INCOME_COLOR, alpha=0.85)
            ax.bar([i + width / 2 for i in x], [v / 1e6 for v in exp_vals],
                   width, label="Chi", color=EXPENSE_COLOR, alpha=0.85)

            step = max(1, len(days) // 10)
            ax.set_xticks([i for i in x if i % step == 0])
            ax.set_xticklabels([days[i][5:] for i in x if i % step == 0],
                               rotation=45, fontsize=7)
            ax.set_ylabel("Triệu ₫", fontsize=8)
            ax.legend(fontsize=8)
        else:
            ax.text(0.5, 0.5, "Không có dữ liệu", ha="center", va="center",
                    transform=ax.transAxes, fontsize=10, color="gray")

        ax.tick_params(labelsize=7)
        fig.tight_layout()

        self._canvas_bar = FigureCanvasTkAgg(fig, master=self._bar_frame)
        self._canvas_bar.draw()
        self._canvas_bar.get_tk_widget().pack(fill="both", expand=True)

    def _draw_pie_chart(self, from_date, to_date):
        rows = db.get_category_totals_range(from_date, to_date, type_filter="expense")

        if self._canvas_pie:
            self._canvas_pie.get_tk_widget().destroy()

        fig = Figure(figsize=(4, 3), dpi=80, facecolor=BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(BG)

        if rows:
            labels = [r["category"] or "Khác" for r in rows]
            sizes = [r["total"] for r in rows]
            ax.pie(sizes, labels=labels, autopct="%1.0f%%",
                   startangle=90, textprops={"fontsize": 7})
            ax.axis("equal")
        else:
            ax.text(0.5, 0.5, "Không có dữ liệu", ha="center", va="center",
                    transform=ax.transAxes, fontsize=10, color="gray")

        fig.tight_layout()
        self._canvas_pie = FigureCanvasTkAgg(fig, master=self._pie_frame)
        self._canvas_pie.draw()
        self._canvas_pie.get_tk_widget().pack(fill="both", expand=True)

    def _refresh_detail_table(self, from_date, to_date):
        for row in self.detail_tree.get_children():
            self.detail_tree.delete(row)

        rows = db.get_expenses_range(from_date, to_date)
        cat_income = defaultdict(float)
        cat_expense = defaultdict(float)
        for r in rows:
            cat = r["category_name"] or "Không rõ"
            if r["type"] == "income":
                cat_income[cat] += r["amount"]
            else:
                cat_expense[cat] += r["amount"]

        all_cats = sorted(set(list(cat_income.keys()) + list(cat_expense.keys())))
        for cat in all_cats:
            inc = cat_income.get(cat, 0.0)
            exp = cat_expense.get(cat, 0.0)
            self.detail_tree.insert("", "end", values=(
                cat,
                _fmt_money(inc) if inc else "—",
                _fmt_money(exp) if exp else "—",
            ))

    def _on_tree_motion(self, event):
        """Highlight row under cursor and show pointer cursor."""
        item = self.detail_tree.identify_row(event.y)
        for row in self.detail_tree.get_children():
            self.detail_tree.item(row, tags=())
        if item:
            self.detail_tree.item(item, tags=("hover",))
            self.detail_tree.config(cursor="hand2")
        else:
            self.detail_tree.config(cursor="")

    def _on_category_click(self, event):
        """Open drilldown dialog when a category row is clicked."""
        item = self.detail_tree.identify_row(event.y)
        if not item:
            return
        values = self.detail_tree.item(item, "values")
        if not values:
            return
        category_name = values[0]
        from_date = self.from_var.get().strip()
        to_date = self.to_var.get().strip()
        if from_date and to_date:
            _DrilldownDialog(self, category_name, from_date, to_date)


# ─────────────────────────────────────────────────────────────────────────────
# Drilldown dialog – click a category row to see per-transaction detail
# ─────────────────────────────────────────────────────────────────────────────

class _DrilldownDialog(tk.Toplevel):
    """Modal dialog showing all transactions for a given category in a date range."""

    def __init__(self, parent, category_name, from_date, to_date):
        super().__init__(parent)
        self.title(f"Chi Tiết: {category_name}")
        self.resizable(True, True)
        self.grab_set()
        self.configure(bg=BG)

        self._category_name = category_name
        self._from_date = from_date
        self._to_date = to_date

        self._build(category_name, from_date, to_date)

        # Center on screen
        self.update_idletasks()
        w, h = 780, 520
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def _build(self, category_name, from_date, to_date):
        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=HEADER_BG, padx=12, pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"Chi Tiết: {category_name}",
                 bg=HEADER_BG, fg=TEXT_LIGHT, font=FONT_HEADER).pack(side="left")
        tk.Label(hdr, text=f"({from_date}  →  {to_date})",
                 bg=HEADER_BG, fg="#BDC3C7", font=FONT).pack(side="left", padx=12)

        # ── Transactions table ─────────────────────────────────────────────
        tbl_frame = tk.Frame(self, bg=BG)
        tbl_frame.pack(fill="both", expand=True, padx=12, pady=(10, 4))

        cols = ("subcategory", "type", "amount", "date", "note")
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show="headings",
                                 selectmode="none")
        col_cfg = [
            ("subcategory", "Danh Mục Con", 160, "w"),
            ("type",        "Loại",          80, "center"),
            ("amount",      "Số Tiền",       130, "e"),
            ("date",        "Ngày",           90, "center"),
            ("note",        "Ghi Chú",       240, "w"),
        ]
        for cid, text, width, anchor in col_cfg:
            self.tree.heading(cid, text=text)
            self.tree.column(cid, width=width, anchor=anchor, minwidth=50)

        vsb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tbl_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        # Tag styles
        self.tree.tag_configure("income_row", foreground=INCOME_COLOR)
        self.tree.tag_configure("expense_row", foreground=EXPENSE_COLOR)
        self.tree.tag_configure("subtotal_row", background="#EBF5FB", font=FONT_BOLD)
        self.tree.tag_configure("total_row", background="#D5E8D4", font=FONT_BOLD)

        # ── Subtotals panel ────────────────────────────────────────────────
        sub_frame = tk.LabelFrame(self, text="Tổng Hợp Theo Danh Mục Con",
                                  bg=BG, font=FONT_BOLD)
        sub_frame.pack(fill="x", padx=12, pady=(0, 4))

        self.subtotal_label = tk.Label(sub_frame, text="", bg=BG, font=FONT,
                                       justify="left", anchor="w", wraplength=740)
        self.subtotal_label.pack(fill="x", padx=8, pady=4)

        # ── Close button ──────────────────────────────────────────────────
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(btn_frame, text="✖ Đóng", command=self.destroy).pack(side="right")

        # Populate data
        self._load_data(category_name, from_date, to_date)

    def _load_data(self, category_name, from_date, to_date):
        rows = db.get_category_transactions_range(from_date, to_date, category_name)

        # Group by subcategory
        sub_groups = defaultdict(list)
        for r in rows:
            sub = r["subcategory_name"] or "(Chung)"
            sub_groups[sub].append(r)

        subtotals = {}  # sub -> (income_total, expense_total)
        grand_income = 0.0
        grand_expense = 0.0

        for sub in sorted(sub_groups.keys()):
            inc_total = 0.0
            exp_total = 0.0
            for r in sub_groups[sub]:
                tag = "income_row" if r["type"] == "income" else "expense_row"
                amt = r["amount"] or 0.0
                type_label = "Thu" if r["type"] == "income" else "Chi"
                self.tree.insert("", "end", values=(
                    sub,
                    type_label,
                    _fmt_money(amt),
                    r["expense_date"],
                    r["description"] or "",
                ), tags=(tag,))
                if r["type"] == "income":
                    inc_total += amt
                else:
                    exp_total += amt

            # Subtotal row for this subcategory
            subtotal_parts = []
            if inc_total:
                subtotal_parts.append(f"Thu: {_fmt_money(inc_total)}")
            if exp_total:
                subtotal_parts.append(f"Chi: {_fmt_money(exp_total)}")
            subtotal_str = "  |  ".join(subtotal_parts) if subtotal_parts else "—"
            self.tree.insert("", "end", values=(
                f"── Cộng {sub}",
                "",
                subtotal_str,
                "",
                "",
            ), tags=("subtotal_row",))

            subtotals[sub] = (inc_total, exp_total)
            grand_income += inc_total
            grand_expense += exp_total

        # Grand total row
        if rows:
            self.tree.insert("", "end", values=(
                "TỔNG CỘNG",
                "",
                f"Thu: {_fmt_money(grand_income)}  |  Chi: {_fmt_money(grand_expense)}",
                "",
                "",
            ), tags=("total_row",))

        # Subtotals summary text
        lines = []
        for sub in sorted(subtotals.keys()):
            inc, exp = subtotals[sub]
            if exp:
                lines.append(f"└── {sub}: Chi {_fmt_money(exp)}")
            if inc:
                lines.append(f"└── {sub}: Thu {_fmt_money(inc)}")
        if lines:
            lines.append(f"TỔNG: Chi {_fmt_money(grand_expense)}  |  Thu {_fmt_money(grand_income)}")
        self.subtotal_label.config(text="\n".join(lines) if lines else "Không có giao dịch.")



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
        self.note_text = tk.Text(frm, width=30, height=4, font=FONT)
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


# ─────────────────────────────────────────────────────────────────────────────
# Helper dialogs (shared)
# ─────────────────────────────────────────────────────────────────────────────

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


def _ask_name_and_type(parent, title, initial_name="", initial_type="expense"):
    """Input dialog for category name and type (Chi/Thu)."""
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.grab_set()
    result = {"value": None}

    frm = tk.Frame(dlg, padx=16, pady=12)
    frm.pack(fill="both", expand=True)

    tk.Label(frm, text="Tên danh mục:", anchor="w").grid(row=0, column=0, sticky="w", pady=4)
    name_var = tk.StringVar(value=initial_name)
    entry = ttk.Entry(frm, textvariable=name_var, width=26)
    entry.grid(row=0, column=1, padx=(8, 0), pady=4)
    entry.focus_set()

    tk.Label(frm, text="Loại:", anchor="w").grid(row=1, column=0, sticky="w", pady=4)
    type_var = tk.StringVar(value=initial_type)
    type_frm = tk.Frame(frm)
    type_frm.grid(row=1, column=1, sticky="w", padx=(8, 0))
    ttk.Radiobutton(type_frm, text="Chi", variable=type_var, value="expense").pack(side="left")
    ttk.Radiobutton(type_frm, text="Thu", variable=type_var, value="income").pack(side="left")

    def _ok():
        v = name_var.get().strip()
        if not v:
            messagebox.showerror("Lỗi", "Tên không được để trống.", parent=dlg)
            return
        result["value"] = {"name": v, "type": type_var.get()}
        dlg.destroy()

    btn_row = tk.Frame(dlg)
    btn_row.pack(pady=8)
    ttk.Button(btn_row, text="OK", command=_ok).pack(side="left", padx=6)
    ttk.Button(btn_row, text="Hủy", command=dlg.destroy).pack(side="left", padx=6)

    entry.bind("<Return>", lambda e: _ok())
    dlg.transient(parent)
    dlg.wait_window()
    return result["value"]
