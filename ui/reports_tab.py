"""
Reports tab – financial reports with date-range selector and charts.
Requires matplotlib (pip install matplotlib).
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta
import database as db

BG = "#F0F4F8"
CARD_BG = "#FFFFFF"
HEADER_BG = "#2C3E50"
ACCENT = "#3498DB"
INCOME_COLOR = "#27AE60"
EXPENSE_COLOR = "#E74C3C"
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
    import matplotlib.pyplot as plt
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False


def _fmt_money(val):
    try:
        return f"{int(val):,} ₫"
    except Exception:
        return str(val)


class ReportsFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._canvas_bar = None
        self._canvas_pie = None
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Controls ─────────────────────────────────────────────────────
        ctrl = tk.Frame(self, bg=BG)
        ctrl.pack(fill="x", padx=12, pady=(10, 0))

        tk.Label(ctrl, text="📊 Báo Cáo Thu Chi", bg=BG, fg=TEXT_DARK,
                 font=FONT_HEADER).pack(side="left", padx=(0, 20))

        tk.Label(ctrl, text="Từ ngày:", bg=BG, font=FONT).pack(side="left")
        # Default: first day of current month
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

        # ── Chart area (left: bar, right: pie) ────────────────────────────
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
                                        height=6, selectmode="none")
        for col, text, width in [("category", "Danh Mục", 200),
                                  ("income", "Thu", 130),
                                  ("expense", "Chi", 130)]:
            self.detail_tree.heading(col, text=text)
            self.detail_tree.column(col, width=width, anchor="w" if col == "category" else "e")
        vsb2 = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.detail_tree.yview)
        self.detail_tree.configure(yscrollcommand=vsb2.set)
        self.detail_tree.pack(side="left", fill="x", expand=True)
        vsb2.pack(side="left", fill="y")

    # ── Data loading ──────────────────────────────────────────────────────────

    def load_data(self):
        from_date = self.from_var.get().strip()
        to_date = self.to_var.get().strip()
        if not from_date or not to_date:
            messagebox.showerror("Lỗi", "Vui lòng nhập khoảng thời gian.", parent=self)
            return
        try:
            from datetime import datetime
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
            # Current month
            self.from_var.set(today.replace(day=1).isoformat())
        else:
            self.from_var.set((today - timedelta(days=days - 1)).isoformat())
        self.to_var.set(today.isoformat())
        self.load_data()

    # ── Charts ────────────────────────────────────────────────────────────────

    def _draw_bar_chart(self, from_date, to_date):
        rows = db.get_daily_totals_range(from_date, to_date)

        # Build day → {income, expense}
        from collections import defaultdict
        day_data = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
        for r in rows:
            day_data[r["expense_date"]][r["type"]] = r["total"] or 0.0

        days = sorted(day_data.keys())
        inc_vals = [day_data[d]["income"] for d in days]
        exp_vals = [day_data[d]["expense"] for d in days]

        # Clear previous chart
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

            # Show at most 10 day labels to avoid crowding
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

    # ── Detail table ──────────────────────────────────────────────────────────

    def _refresh_detail_table(self, from_date, to_date):
        for row in self.detail_tree.get_children():
            self.detail_tree.delete(row)

        rows = db.get_expenses_range(from_date, to_date)
        from collections import defaultdict
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
