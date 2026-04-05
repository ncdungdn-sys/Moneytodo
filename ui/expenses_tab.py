"""
Expenses tab - daily income/expense management.
Features: add, edit, delete, filter by month or date range, daily summary, sort, export to Excel.
"""
import calendar
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime
import database as db
from utils.excel_export import export_monthly_report, OPENPYXL_OK

# -- Colour palette (matches dashboard) --------------------------------------
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
FONT_SMALL = ("Segoe UI", 9)


def _fmt_money(val):
    try:
        return f"{int(val):,} \u20ab"
    except Exception:
        return str(val)


class ExpensesFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._expenses = []
        self._sort_col = "date"
        self._sort_reverse = True
        self._build_ui()
        self.load_data()

    # -- UI Construction ------------------------------------------------------

    def _build_ui(self):
        # -- Mode toggle row --------------------------------------------------
        mode_row = tk.Frame(self, bg=BG)
        mode_row.pack(fill="x", padx=10, pady=(10, 0))

        self.filter_mode = tk.StringVar(value="month")
        tk.Radiobutton(
            mode_row, text="\U0001f4c5 Theo Th\xe1ng", variable=self.filter_mode,
            value="month", bg=BG, font=FONT, command=self._on_mode_change,
        ).pack(side="left")
        tk.Radiobutton(
            mode_row, text="\U0001f4c6 Kho\u1ea3ng Ng\xe0y", variable=self.filter_mode,
            value="range", bg=BG, font=FONT, command=self._on_mode_change,
        ).pack(side="left", padx=(10, 0))

        ttk.Button(mode_row, text="\U0001f4ca Xu\u1ea5t Excel", command=self.export_excel).pack(side="right", padx=2)
        ttk.Button(mode_row, text="+ Th\xeam M\u1edbi", command=self.open_add_dialog).pack(side="right", padx=2)

        # -- Filter controls container ----------------------------------------
        self._filter_area = tk.Frame(self, bg=BG)
        self._filter_area.pack(fill="x", padx=10, pady=(4, 0))

        # Month filter controls (default visible)
        self.month_ctrl = tk.Frame(self._filter_area, bg=BG)
        tk.Label(self.month_ctrl, text="Th\xe1ng (YYYY-MM):", bg=BG, font=FONT).pack(side="left")
        self.month_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
        ttk.Entry(self.month_ctrl, textvariable=self.month_var, width=10).pack(side="left", padx=(4, 10))
        ttk.Button(self.month_ctrl, text="\U0001f50d L\u1ecdc", command=self.load_data).pack(side="left", padx=2)
        self.month_ctrl.pack(fill="x")

        # Date range controls (initially hidden)
        today = date.today()
        first_day = today.replace(day=1)
        self.range_ctrl = tk.Frame(self._filter_area, bg=BG)
        tk.Label(self.range_ctrl, text="T\u1eeb (YYYY-MM-DD):", bg=BG, font=FONT).pack(side="left")
        self.from_var = tk.StringVar(value=first_day.isoformat())
        ttk.Entry(self.range_ctrl, textvariable=self.from_var, width=12).pack(side="left", padx=(4, 10))
        tk.Label(self.range_ctrl, text="\u0110\u1ebfn:", bg=BG, font=FONT).pack(side="left")
        self.to_var = tk.StringVar(value=today.isoformat())
        ttk.Entry(self.range_ctrl, textvariable=self.to_var, width=12).pack(side="left", padx=(4, 10))
        ttk.Button(self.range_ctrl, text="\U0001f50d L\u1ecdc", command=self.load_data).pack(side="left", padx=2)

        # -- Summary bar -------------------------------------------------------
        self.summary_frame = tk.Frame(self, bg=BG)
        self.summary_frame.pack(fill="x", padx=10, pady=6)

        self.lbl_income = tk.Label(
            self.summary_frame, text="Thu: 0 \u20ab", bg=INCOME_COLOR,
            fg="white", font=FONT_BOLD, padx=16, pady=4,
        )
        self.lbl_income.pack(side="left", padx=(0, 4))

        self.lbl_expense = tk.Label(
            self.summary_frame, text="Chi: 0 \u20ab", bg=EXPENSE_COLOR,
            fg="white", font=FONT_BOLD, padx=16, pady=4,
        )
        self.lbl_expense.pack(side="left", padx=(0, 4))

        self.lbl_balance = tk.Label(
            self.summary_frame, text="S\u1ed1 d\u01b0: 0 \u20ab", bg=ACCENT,
            fg="white", font=FONT_BOLD, padx=16, pady=4,
        )
        self.lbl_balance.pack(side="left")

        # -- Daily Summary section ---------------------------------------------
        daily_section = tk.LabelFrame(
            self, text=" \U0001f4ca T\u1ed5ng K\u1ebft Theo Ng\xe0y ", bg=BG,
            font=FONT_BOLD, fg=TEXT_DARK,
        )
        daily_section.pack(fill="x", padx=10, pady=(0, 4))

        self.daily_canvas = tk.Canvas(daily_section, bg=BG, height=190, highlightthickness=0)
        daily_vsb = ttk.Scrollbar(daily_section, orient="vertical", command=self.daily_canvas.yview)
        self.daily_canvas.configure(yscrollcommand=daily_vsb.set)

        self.daily_inner = tk.Frame(self.daily_canvas, bg=BG)
        self._daily_window = self.daily_canvas.create_window((0, 0), window=self.daily_inner, anchor="nw")

        self.daily_inner.bind("<Configure>", self._on_daily_frame_configure)
        self.daily_canvas.bind("<Configure>", self._on_daily_canvas_configure)
        self.daily_canvas.bind("<MouseWheel>", self._on_daily_mousewheel)
        self.daily_canvas.bind("<Button-4>", self._on_daily_mousewheel)
        self.daily_canvas.bind("<Button-5>", self._on_daily_mousewheel)

        self.daily_canvas.pack(side="left", fill="both", expand=True)
        daily_vsb.pack(side="right", fill="y")

        # -- Treeview ----------------------------------------------------------
        tree_frame = tk.Frame(self, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("date", "type", "category", "subcategory", "amount", "description")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")

        headings = {
            "date": ("Ng\xe0y", 90),
            "type": ("Lo\u1ea1i", 60),
            "category": ("Danh M\u1ee5c", 130),
            "subcategory": ("Danh M\u1ee5c Con", 130),
            "amount": ("S\u1ed1 Ti\u1ec1n", 110),
            "description": ("Di\u1ec5n Gi\u1ea3i", 260),
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
        ttk.Button(btn_row, text="\u270f\ufe0f S\u1eeda", command=self.open_edit_dialog).pack(side="left", padx=2)
        ttk.Button(btn_row, text="\U0001f5d1\ufe0f X\xf3a", command=self.delete_selected).pack(side="left", padx=2)

    # -- Mode switching -------------------------------------------------------

    def _on_mode_change(self):
        mode = self.filter_mode.get()
        if mode == "month":
            self.range_ctrl.pack_forget()
            self.month_ctrl.pack(fill="x")
        else:
            self.month_ctrl.pack_forget()
            self.range_ctrl.pack(fill="x")
        self.load_data()

    # -- Daily summary canvas helpers -----------------------------------------

    def _on_daily_frame_configure(self, _event=None):
        self.daily_canvas.configure(scrollregion=self.daily_canvas.bbox("all"))

    def _on_daily_canvas_configure(self, event):
        self.daily_canvas.itemconfig(self._daily_window, width=event.width)

    def _on_daily_mousewheel(self, event):
        if event.num == 4:
            self.daily_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.daily_canvas.yview_scroll(1, "units")
        else:
            self.daily_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # -- Data loading ---------------------------------------------------------

    def load_data(self):
        mode = self.filter_mode.get()
        if mode == "month":
            month = self.month_var.get().strip()
            self._expenses = db.get_expenses(month=month if month else None)
            s = db.get_monthly_summary(month) if month else {"income": 0.0, "expense": 0.0}
            summaries = []
            if month:
                try:
                    year, m = map(int, month.split("-"))
                    last_day = calendar.monthrange(year, m)[1]
                    summaries = db.get_daily_summaries_range(
                        f"{month}-01", f"{month}-{last_day:02d}"
                    )
                except (ValueError, AttributeError):
                    summaries = []
        else:
            from_date = self.from_var.get().strip()
            to_date = self.to_var.get().strip()
            self._expenses = db.get_expenses_range(from_date, to_date) if (from_date and to_date) else []
            # Keep consistent DESC sort for the treeview
            self._expenses.sort(
                key=lambda r: (r.get("expense_date", ""), r.get("id", 0)), reverse=True
            )
            s = db.get_summary_range(from_date, to_date) if (from_date and to_date) else {"income": 0.0, "expense": 0.0}
            summaries = db.get_daily_summaries_range(from_date, to_date) if (from_date and to_date) else []

        self._refresh_summary(s)
        self._refresh_tree()
        self._refresh_daily_summaries(summaries)

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
                    exp["category_name"] or "\u2014",
                    exp["subcategory_name"] or "\u2014",
                    _fmt_money(exp["amount"]),
                    exp["description"] or "",
                ),
                tags=tag,
            )

    def _refresh_summary(self, s):
        income = s.get("income", 0)
        expense = s.get("expense", 0)
        balance = income - expense
        self.lbl_income.config(text=f"Thu: {_fmt_money(income)}")
        self.lbl_expense.config(text=f"Chi: {_fmt_money(expense)}")
        self.lbl_balance.config(text=f"S\u1ed1 d\u01b0: {_fmt_money(balance)}")

    def _refresh_daily_summaries(self, summaries):
        for widget in self.daily_inner.winfo_children():
            widget.destroy()

        if not summaries:
            tk.Label(
                self.daily_inner, text="Kh\xf4ng c\xf3 d\u1eef li\u1ec7u.",
                bg=BG, fg="#95A5A6", font=FONT,
            ).pack(padx=10, pady=10)
            return

        for summary in summaries:
            self._build_day_card(self.daily_inner, summary)

    def _build_day_card(self, parent, summary):
        date_str = summary["date"]
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            date_display = d.strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            date_display = date_str

        income = summary["income"]
        expense = summary["expense"]
        balance = income - expense
        categories = summary["categories"]

        # Card with solid border
        card = tk.Frame(parent, bg=CARD_BG, relief="solid", bd=1)
        card.pack(fill="x", padx=6, pady=3)

        # Date header bar
        header = tk.Frame(card, bg=HEADER_BG)
        header.pack(fill="x")
        tk.Label(
            header, text=f"\U0001f4c5  {date_display}",
            bg=HEADER_BG, fg=TEXT_LIGHT, font=FONT_BOLD,
            padx=8, pady=3, anchor="w",
        ).pack(side="left", fill="x", expand=True)

        # Content
        content = tk.Frame(card, bg=CARD_BG, padx=10, pady=4)
        content.pack(fill="x")

        # Income row
        tk.Label(
            content, text=f"  Thu:  {_fmt_money(income)}",
            bg=CARD_BG, fg=INCOME_COLOR, font=FONT_BOLD, anchor="w",
        ).pack(fill="x")

        # Expense total row
        tk.Label(
            content, text=f"  Chi:  {_fmt_money(expense)}",
            bg=CARD_BG, fg=EXPENSE_COLOR, font=FONT_BOLD, anchor="w",
        ).pack(fill="x")

        # Category breakdown
        for i, cat in enumerate(categories):
            prefix = "      \u2514\u2500" if i == len(categories) - 1 else "      \u251c\u2500"
            cat_name = cat["category"] or "Kh\xf4ng r\xf5"
            lbl = tk.Label(
                content,
                text=f"{prefix} {cat_name}: {_fmt_money(cat['total'])}",
                bg=CARD_BG, fg=EXPENSE_COLOR, font=FONT_SMALL, anchor="w",
            )
            lbl.pack(fill="x")
            lbl.bind("<MouseWheel>", self._on_daily_mousewheel)
            lbl.bind("<Button-4>", self._on_daily_mousewheel)
            lbl.bind("<Button-5>", self._on_daily_mousewheel)

        # Balance row
        balance_color = INCOME_COLOR if balance >= 0 else EXPENSE_COLOR
        tk.Label(
            content, text=f"  C\xf2n l\u1ea1i:  {_fmt_money(balance)}",
            bg=CARD_BG, fg=balance_color, font=FONT_BOLD, anchor="w",
        ).pack(fill="x")

        # Bind mousewheel on card containers so scrolling works everywhere
        for widget in (card, header, content):
            widget.bind("<MouseWheel>", self._on_daily_mousewheel)
            widget.bind("<Button-4>", self._on_daily_mousewheel)
            widget.bind("<Button-5>", self._on_daily_mousewheel)

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

    # -- CRUD dialogs ---------------------------------------------------------

    def open_add_dialog(self):
        _ExpenseDialog(self, title="Th\xeam Thu Chi M\u1edbi")

    def open_edit_dialog(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Th\xf4ng b\xe1o", "Vui l\xf2ng ch\u1ecdn m\u1ed9t m\u1ee5c \u0111\u1ec3 s\u1eeda.", parent=self)
            return
        exp_id = int(sel[0])
        exp = next((e for e in self._expenses if e["id"] == exp_id), None)
        if exp:
            _ExpenseDialog(self, title="S\u1eeda Thu Chi", expense=exp)

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Th\xf4ng b\xe1o", "Vui l\xf2ng ch\u1ecdn m\u1ed9t m\u1ee5c \u0111\u1ec3 x\xf3a.", parent=self)
            return
        if messagebox.askyesno("X\xe1c nh\u1eadn", "B\u1ea1n c\xf3 ch\u1eafc mu\u1ed1n x\xf3a m\u1ee5c n\xe0y?", parent=self):
            db.delete_expense(int(sel[0]))
            self.load_data()

    # -- Excel export ---------------------------------------------------------

    def export_excel(self):
        if not OPENPYXL_OK:
            messagebox.showerror("L\u1ed7i", "C\u1ea7n c\xe0i openpyxl: pip install openpyxl", parent=self)
            return
        mode = self.filter_mode.get()
        if mode != "month":
            messagebox.showinfo(
                "Th\xf4ng b\xe1o",
                "Xu\u1ea5t Excel hi\u1ec7n ch\u1ec9 h\u1ed7 tr\u1ee3 ch\u1ebf \u0111\u1ed9 Theo Th\xe1ng.\n"
                "Vui l\xf2ng chuy\u1ec3n sang ch\u1ebf \u0111\u1ed9 Theo Th\xe1ng \u0111\u1ec3 xu\u1ea5t b\xe1o c\xe1o.",
                parent=self,
            )
            return
        month = self.month_var.get().strip() or date.today().strftime("%Y-%m")
        expenses = db.get_expenses(month=month)
        summary = db.get_monthly_summary(month)
        cat_summary = db.get_category_summary(month)

        out_dir = filedialog.askdirectory(title="Ch\u1ecdn th\u01b0 m\u1ee5c l\u01b0u file Excel", parent=self)
        if not out_dir:
            return
        try:
            path = export_monthly_report(month, expenses, summary, cat_summary, out_dir)
            messagebox.showinfo("Th\xe0nh c\xf4ng", f"\u0110\xe3 xu\u1ea5t b\xe1o c\xe1o:\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("L\u1ed7i", str(e), parent=self)


# -- Add / Edit Dialog --------------------------------------------------------

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
        tk.Label(frm, text="Lo\u1ea1i:", bg=CARD_BG, font=FONT_BOLD).grid(row=0, column=0, sticky="w", **pad)
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
        tk.Label(frm, text="Danh M\u1ee5c:", bg=CARD_BG, font=FONT_BOLD).grid(row=1, column=0, sticky="w", **pad)
        self._cats = db.get_categories(type_filter="expense")
        cat_names = [c["name"] for c in self._cats]
        self.cat_var = tk.StringVar()
        self.cat_cb = ttk.Combobox(frm, textvariable=self.cat_var, values=cat_names, state="readonly", width=22)
        self.cat_cb.grid(row=1, column=1, sticky="w", **pad)
        self.cat_cb.bind("<<ComboboxSelected>>", self._on_cat_change)

        # Subcategory
        tk.Label(frm, text="Danh M\u1ee5c Con:", bg=CARD_BG, font=FONT_BOLD).grid(row=2, column=0, sticky="w", **pad)
        self.sub_var = tk.StringVar()
        self.sub_cb = ttk.Combobox(frm, textvariable=self.sub_var, width=22)
        self.sub_cb.grid(row=2, column=1, sticky="w", **pad)
        tk.Label(frm, text="(kh\xf4ng b\u1eaft bu\u1ed9c)", bg=CARD_BG, fg="#7F8C8D",
                 font=("Segoe UI", 9)).grid(row=2, column=2, sticky="w", padx=2)

        # Amount
        tk.Label(frm, text="S\u1ed1 Ti\u1ec1n (\u20ab):", bg=CARD_BG, font=FONT_BOLD).grid(row=3, column=0, sticky="w", **pad)
        self.amount_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.amount_var, width=24).grid(row=3, column=1, sticky="w", **pad)

        # Date
        tk.Label(frm, text="Ng\xe0y (YYYY-MM-DD):", bg=CARD_BG, font=FONT_BOLD).grid(row=4, column=0, sticky="w", **pad)
        self.date_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(frm, textvariable=self.date_var, width=24).grid(row=4, column=1, sticky="w", **pad)

        # Description
        tk.Label(frm, text="Di\u1ec5n Gi\u1ea3i:", bg=CARD_BG, font=FONT_BOLD).grid(row=5, column=0, sticky="nw", **pad)
        self.desc_text = tk.Text(frm, width=30, height=4, font=FONT)
        self.desc_text.grid(row=5, column=1, sticky="w", **pad)

        # Buttons
        btn_frm = tk.Frame(frm, bg=CARD_BG)
        btn_frm.grid(row=6, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frm, text="\U0001f4be L\u01b0u", command=self._save).pack(side="left", padx=6)
        ttk.Button(btn_frm, text="H\u1ee7y", command=self.destroy).pack(side="left", padx=6)

        # Category management link
        tk.Label(frm, text="Qu\u1ea3n l\xfd danh m\u1ee5c \u2192", bg=CARD_BG, fg=ACCENT,
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
            self.sub_var.set("")  # Keep blank - subcategory is optional
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
            messagebox.showerror("L\u1ed7i", "Vui l\xf2ng ch\u1ecdn danh m\u1ee5c.", parent=self)
            return
        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("L\u1ed7i", "S\u1ed1 ti\u1ec1n kh\xf4ng h\u1ee3p l\u1ec7.", parent=self)
            return
        try:
            datetime.strptime(exp_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("L\u1ed7i", "Ng\xe0y kh\xf4ng h\u1ee3p l\u1ec7 (YYYY-MM-DD).", parent=self)
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
