"""
Reminders tab – todo notes with date+time-based desktop popup notifications.
Each reminder fires a popup at the specified time on the due date.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime
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

# Check interval for reminders: every 60 seconds
REMINDER_CHECK_MS = 60_000


class RemindersFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._build_ui()
        self.load_data()
        self._schedule_check()

    def _build_ui(self):
        # ── Header + Add button ───────────────────────────────────────────
        ctrl = tk.Frame(self, bg=BG)
        ctrl.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(ctrl, text="Ghi Chú Việc Cần Làm", bg=BG, fg=TEXT_DARK, font=FONT_HEADER).pack(side="left")
        ttk.Button(ctrl, text="+ Thêm Công Việc", command=self.open_add_dialog).pack(side="right")

        # ── Filter ────────────────────────────────────────────────────────
        flt = tk.Frame(self, bg=BG)
        flt.pack(fill="x", padx=10, pady=4)
        self.show_done_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(flt, text="Hiện công việc đã hoàn thành", variable=self.show_done_var,
                        command=self._refresh_tree).pack(side="left")

        # ── Treeview ──────────────────────────────────────────────────────
        tree_frame = tk.Frame(self, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        cols = ("status", "title", "remind_date", "remind_time", "countdown", "note")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        headings = {
            "status": ("Trạng Thái", 110),
            "title": ("Công Việc", 200),
            "remind_date": ("Ngày Nhắc", 95),
            "remind_time": ("Giờ Nhắc", 70),
            "countdown": ("Còn Lại", 120),
            "note": ("Ghi Chú", 260),
        }
        for col, (text, width) in headings.items():
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")

        self.tree.tag_configure("done", foreground=DONE_COLOR)
        self.tree.tag_configure("overdue", foreground=PENDING_COLOR)
        self.tree.tag_configure("upcoming", foreground="#2980B9")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.tree.bind("<Double-1>", lambda e: self.toggle_done())

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Button(btn_row, text="✅ Đánh dấu Hoàn Thành", command=self.toggle_done).pack(side="left", padx=2)
        ttk.Button(btn_row, text="✏️ Sửa", command=self.open_edit_dialog).pack(side="left", padx=2)
        ttk.Button(btn_row, text="🗑️ Xóa", command=self.delete_selected).pack(side="left", padx=2)

    # ── Data ─────────────────────────────────────────────────────────────────

    def load_data(self):
        self._items = db.get_reminders()
        self._refresh_tree()

    def _refresh_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        now = datetime.now()
        today = date.today().isoformat()
        for item in self._items:
            if item["is_done"] and not self.show_done_var.get():
                continue

            remind_time = item.get("remind_time") or ""
            time_display = remind_time if remind_time else "—"

            if item["is_done"]:
                tag = "done"
                status = "✅ Hoàn Thành"
                countdown = "—"
            else:
                # Compute countdown
                countdown = _compute_countdown(item["remind_date"], remind_time, now)
                if item["remind_date"] < today:
                    tag = "overdue"
                    status = "⚠️ Quá Hạn"
                elif item["remind_date"] == today:
                    tag = "upcoming"
                    status = "🔔 Hôm Nay"
                else:
                    tag = "upcoming"
                    status = "⏳ Sắp Tới"

            self.tree.insert(
                "", "end",
                iid=str(item["id"]),
                values=(status, item["title"], item["remind_date"],
                        time_display, countdown, item["note"] or ""),
                tags=(tag,),
            )

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def open_add_dialog(self):
        _ReminderDialog(self, title="Thêm Công Việc")

    def open_edit_dialog(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một mục.", parent=self)
            return
        item_id = int(sel[0])
        item = next((i for i in self._items if i["id"] == item_id), None)
        if item:
            _ReminderDialog(self, title="Sửa Công Việc", item=item)

    def toggle_done(self):
        sel = self.tree.selection()
        if not sel:
            return
        db.toggle_reminder_done(int(sel[0]))
        self.load_data()

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Xác nhận", "Xóa công việc này?", parent=self):
            db.delete_reminder(int(sel[0]))
            self.load_data()

    # ── Reminder notification ─────────────────────────────────────────────────

    def _schedule_check(self):
        """Schedule periodic reminder check using Tkinter's after()."""
        self._check_reminders()
        self.after(REMINDER_CHECK_MS, self._schedule_check)

    def _check_reminders(self):
        now = datetime.now()
        today = date.today().isoformat()
        pending = db.get_pending_reminders(today)
        for rem in pending:
            remind_time = rem.get("remind_time") or ""
            if remind_time:
                # Only fire when current time has reached or passed the remind_time
                try:
                    h, m = map(int, remind_time.split(":"))
                    remind_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    if now < remind_dt:
                        continue  # Not yet time
                except (ValueError, AttributeError):
                    pass
            db.mark_reminder_notified(rem["id"])
            self._show_popup(rem)
        if pending:
            self.load_data()

    def _show_popup(self, rem):
        popup = tk.Toplevel(self)
        popup.title("🔔 Nhắc Nhở Công Việc")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)

        frm = tk.Frame(popup, bg=ACCENT, padx=20, pady=16)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="🔔 NHẮC NHỞ HÔM NAY", bg=ACCENT, fg="white",
                 font=("Segoe UI", 13, "bold")).pack()
        tk.Label(frm, text=rem["title"], bg=ACCENT, fg="white",
                 font=("Segoe UI", 11)).pack(pady=4)
        if rem.get("note"):
            tk.Label(frm, text=rem["note"], bg=ACCENT, fg="#ECF0F1",
                     font=("Segoe UI", 10), wraplength=280).pack()
        time_str = f"  lúc {rem['remind_time']}" if rem.get("remind_time") else ""
        tk.Label(frm, text=f"Ngày: {rem['remind_date']}{time_str}", bg=ACCENT, fg="#BDC3C7",
                 font=("Segoe UI", 9)).pack(pady=(4, 0))

        ttk.Button(popup, text="Đã Biết", command=popup.destroy).pack(pady=8)
        popup.after(30000, popup.destroy)  # Auto-close after 30 seconds


def _compute_countdown(remind_date, remind_time, now):
    """Return a human-readable countdown string."""
    try:
        if remind_time:
            h, m = map(int, remind_time.split(":"))
            target = datetime.strptime(remind_date, "%Y-%m-%d").replace(hour=h, minute=m)
        else:
            target = datetime.strptime(remind_date, "%Y-%m-%d").replace(hour=0, minute=0)

        delta = target - now
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            return "Đã qua"
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        if days > 0:
            return f"{days} ngày {hours} giờ"
        elif hours > 0:
            return f"{hours} giờ {minutes} phút"
        else:
            return f"{minutes} phút"
    except Exception:
        return "—"


class _ReminderDialog(tk.Toplevel):
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

        tk.Label(frm, text="Tiêu Đề:", bg=CARD_BG, font=FONT_BOLD).grid(row=0, column=0, sticky="w", **pad)
        self.title_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.title_var, width=32).grid(row=0, column=1, sticky="w", **pad)

        tk.Label(frm, text="Ngày Nhắc (YYYY-MM-DD):", bg=CARD_BG, font=FONT_BOLD).grid(row=1, column=0, sticky="w", **pad)
        self.date_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(frm, textvariable=self.date_var, width=32).grid(row=1, column=1, sticky="w", **pad)

        tk.Label(frm, text="Giờ Nhắc (HH:MM):", bg=CARD_BG, font=FONT_BOLD).grid(row=2, column=0, sticky="w", **pad)
        time_frame = tk.Frame(frm, bg=CARD_BG)
        time_frame.grid(row=2, column=1, sticky="w", **pad)
        self.time_var = tk.StringVar()
        PRESET_TIMES = ["", "07:00", "08:00", "09:00", "10:00", "11:00",
                        "12:00", "13:00", "14:00", "15:00", "16:00",
                        "17:00", "18:00", "19:00", "20:00", "21:00"]
        self.time_cb = ttk.Combobox(time_frame, textvariable=self.time_var,
                                    values=PRESET_TIMES, width=10)
        self.time_cb.pack(side="left")
        tk.Label(time_frame, text="(để trống = cả ngày)", bg=CARD_BG,
                 fg="#7F8C8D", font=("Segoe UI", 9)).pack(side="left", padx=6)

        tk.Label(frm, text="Ghi Chú:", bg=CARD_BG, font=FONT_BOLD).grid(row=3, column=0, sticky="nw", **pad)
        self.note_text = tk.Text(frm, width=34, height=4, font=FONT)
        self.note_text.grid(row=3, column=1, sticky="w", **pad)

        btn_frm = tk.Frame(frm, bg=CARD_BG)
        btn_frm.grid(row=4, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frm, text="💾 Lưu", command=self._save).pack(side="left", padx=6)
        ttk.Button(btn_frm, text="Hủy", command=self.destroy).pack(side="left", padx=6)

    def _populate(self, item):
        self.title_var.set(item["title"])
        self.date_var.set(item["remind_date"])
        self.time_var.set(item.get("remind_time") or "")
        if item.get("note"):
            self.note_text.insert("1.0", item["note"])

    def _save(self):
        title = self.title_var.get().strip()
        remind_date = self.date_var.get().strip()
        remind_time = self.time_var.get().strip() or None
        note = self.note_text.get("1.0", "end").strip()

        if not title:
            messagebox.showerror("Lỗi", "Tiêu đề không được để trống.", parent=self)
            return
        try:
            datetime.strptime(remind_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Lỗi", "Ngày không hợp lệ (YYYY-MM-DD).", parent=self)
            return
        if remind_time:
            try:
                datetime.strptime(remind_time, "%H:%M")
            except ValueError:
                messagebox.showerror("Lỗi", "Giờ không hợp lệ (HH:MM), ví dụ: 08:00", parent=self)
                return

        if self.item:
            db.update_reminder(self.item["id"], title, note, remind_date, remind_time)
        else:
            db.add_reminder(title, note, remind_date, remind_time)

        self.parent_frame.load_data()
        self.destroy()

