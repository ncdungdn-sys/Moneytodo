"""
Reminders tab – todo notes with date+time-based desktop popup notifications.
Each reminder fires a popup at the specified time on the due date.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime

import database as db
from utils.lunar_calendar import gregorian_to_lunar_day

BG = "#F0F4F8"
CARD_BG = "#FFFFFF"
ACCENT = "#3498DB"
DONE_COLOR = "#27AE60"
PENDING_COLOR = "#E74C3C"
TEXT_DARK = "#2C3E50"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADER = ("Segoe UI", 12, "bold")

REMINDER_CHECK_MS = 60_000


def _parse_note_metadata(note_raw):
    """Parse reminder metadata stored in note text.

    Format used:
        __KIND__:reminder
        __RECUR__:yearly
        __LUNAR__:8/15
        __LAST__:2026-10-13
        actual note text
    """
    if not note_raw:
        return {
            "kind": "reminder",
            "recurrence": "none",
            "lunar_month": None,
            "lunar_day": None,
            "last_notified": None,
            "note": "",
        }

    kind = "reminder"
    recurrence = "none"
    lunar_month = None
    lunar_day = None
    last_notified = None
    note_lines = []

    lines = str(note_raw).splitlines()
    for idx, line in enumerate(lines):
        if idx == 0 and line.startswith("__KIND__:"):
            kind = line.split(":", 1)[1].strip() or "reminder"
            continue
        if line.startswith("__RECUR__:"):
            recurrence = line.split(":", 1)[1].strip() or "none"
            continue
        if line.startswith("__LUNAR__:"):
            payload = line.split(":", 1)[1].strip()
            if "/" in payload:
                try:
                    lunar_month, lunar_day = payload.split("/", 1)
                    lunar_month = int(lunar_month)
                    lunar_day = int(lunar_day)
                except ValueError:
                    pass
            continue
        if line.startswith("__LAST__:"):
            last_notified = line.split(":", 1)[1].strip() or None
            continue
        note_lines.append(line)

    # Compatibility with older records that used __KIND__ only but no recurrence metadata.
    if note_lines and note_lines[0].startswith("__KIND__:"):
        kind = note_lines[0].split(":", 1)[1].strip() or kind

    return {
        "kind": kind,
        "recurrence": recurrence,
        "lunar_month": lunar_month,
        "lunar_day": lunar_day,
        "last_notified": last_notified,
        "note": "\n".join(note_lines).strip(),
    }


def _compose_note_metadata(kind, recurrence, lunar_month, lunar_day, last_notified, note_text):
    lines = [f"__KIND__:{kind}", f"__RECUR__:{recurrence or 'none'}"]
    if lunar_month is not None and lunar_day is not None:
        lines.append(f"__LUNAR__:{int(lunar_month)}/{int(lunar_day)}")
    if last_notified:
        lines.append(f"__LAST__:{last_notified}")
    if note_text:
        lines.append(note_text)
    return "\n".join(lines)


def _is_recurring_due(item, today_date):
    meta = _parse_note_metadata(item.get("note"))
    recurrence = meta["recurrence"]
    last_notified = meta["last_notified"]
    if recurrence == "yearly":
        try:
            target = datetime.strptime(item["remind_date"], "%Y-%m-%d").date()
            if target.month == today_date.month and target.day == today_date.day:
                return last_notified != today_date.isoformat()
        except Exception:
            return False
        return False

    if recurrence == "lunar_yearly":
        try:
            lunar = gregorian_to_lunar_day(today_date)
            if meta["lunar_month"] is not None and meta["lunar_day"] is not None:
                same = lunar[1] == meta["lunar_month"] and lunar[2] == meta["lunar_day"]
                return same and last_notified != today_date.isoformat()
        except Exception:
            return False
        return False

    if recurrence == "none":
        return item.get("remind_date") == today_date.isoformat() and last_notified != today_date.isoformat()

    return False


def _compute_countdown(remind_date, remind_time, now):
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
        if hours > 0:
            return f"{hours} giờ {minutes} phút"
        return f"{minutes} phút"
    except Exception:
        return "—"


class RemindersFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._build_ui()
        self.load_data()
        self._schedule_check()

    def _build_ui(self):
        ctrl = tk.Frame(self, bg=BG)
        ctrl.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(ctrl, text="Ghi Chú Việc Cần Làm", bg=BG, fg=TEXT_DARK, font=FONT_HEADER).pack(side="left")
        ttk.Button(ctrl, text="+ Thêm Công Việc", command=self.open_add_dialog).pack(side="right")

        flt = tk.Frame(self, bg=BG)
        flt.pack(fill="x", padx=10, pady=4)
        self.show_done_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(flt, text="Hiện công việc đã hoàn thành", variable=self.show_done_var,
                        command=self._refresh_all_tabs).pack(side="left")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        self.frame_all = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.frame_all, text="Tổng thể")

        self.frame_today = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.frame_today, text="Hôm Nay")

        self.frame_notifications = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.frame_notifications, text="Thông Báo")

        cols = ("status", "title", "remind_date", "remind_time", "countdown", "note")
        headings = {
            "status": ("Trạng Thái", 110),
            "title": ("Công Việc", 200),
            "remind_date": ("Ngày Nhắc", 95),
            "remind_time": ("Giờ Nhắc", 70),
            "countdown": ("Còn Lại", 120),
            "note": ("Ghi Chú", 260),
        }

        def _make_tree(parent):
            tree_frame = tk.Frame(parent, bg=BG)
            tree_frame.pack(fill="both", expand=True)
            tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
            for col, (text, width) in headings.items():
                tree.heading(col, text=text)
                tree.column(col, width=width, anchor="w")
            tree.tag_configure("done", foreground=DONE_COLOR)
            tree.tag_configure("overdue", foreground=PENDING_COLOR)
            tree.tag_configure("upcoming", foreground="#2980B9")
            vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)
            tree.grid(row=0, column=0, sticky="nsew")
            vsb.grid(row=0, column=1, sticky="ns")
            tree_frame.columnconfigure(0, weight=1)
            tree_frame.rowconfigure(0, weight=1)
            tree.bind("<Double-1>", lambda e: self.toggle_done())
            return tree

        self.tree_all = _make_tree(self.frame_all)
        self.tree_today = _make_tree(self.frame_today)
        self.tree_notifications = _make_tree(self.frame_notifications)

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=10, pady=(6, 8))
        ttk.Button(btn_row, text="✅ Đánh dấu Hoàn Thành", command=self.toggle_done).pack(side="left", padx=2)
        ttk.Button(btn_row, text="✏️ Sửa", command=self.open_edit_dialog).pack(side="left", padx=2)
        ttk.Button(btn_row, text="🗑️ Xóa", command=self.delete_selected).pack(side="left", padx=2)
        ttk.Button(btn_row, text="📖 Đã Đọc (Thông Báo)", command=self.mark_selected_notified).pack(side="left", padx=12)

    def load_data(self):
        self._items = db.get_reminders()
        self._refresh_all_tabs()

    def _refresh_all_tabs(self):
        self._refresh_all()
        self._refresh_today()
        self._refresh_notifications()

    def _refresh_all(self):
        tree = self.tree_all
        for row in tree.get_children():
            tree.delete(row)
        today = date.today()
        for item in self._items:
            if item["is_done"] and not self.show_done_var.get():
                continue
            meta = _parse_note_metadata(item.get("note"))
            kind = meta["kind"]
            note_text = meta["note"]
            remind_time = item.get("remind_time") or ""
            time_display = remind_time if remind_time else "—"

            if item["is_done"]:
                tag = "done"
                status = "✅ Hoàn Thành"
                countdown = "—"
            else:
                if kind == "note":
                    tag = "upcoming"
                    status = "📝 Ghi chú"
                    countdown = "—"
                elif kind == "today":
                    tag = "upcoming"
                    status = "🔔 Hôm Nay"
                    countdown = _compute_countdown(item["remind_date"], remind_time, datetime.now())
                else:
                    countdown = _compute_countdown(item["remind_date"], remind_time, datetime.now())
                    if meta["recurrence"] in {"yearly", "lunar_yearly"}:
                        tag = "upcoming"
                        status = "🔁 Hằng năm"
                    elif item["remind_date"] < today.isoformat():
                        tag = "overdue"
                        status = "⚠️ Quá Hạn"
                    elif item["remind_date"] == today.isoformat():
                        tag = "upcoming"
                        status = "🔔 Hôm Nay"
                    else:
                        tag = "upcoming"
                        status = "⏳ Sắp Tới"

            tree.insert(
                "", "end",
                iid=str(item["id"]),
                values=(status, item["title"], item["remind_date"], time_display, countdown, note_text or ""),
                tags=(tag,),
            )

    def _refresh_today(self):
        tree = self.tree_today
        for row in tree.get_children():
            tree.delete(row)
        today = date.today()
        for item in self._items:
            if item["is_done"] and not self.show_done_var.get():
                continue
            meta = _parse_note_metadata(item.get("note"))
            kind = meta["kind"]
            remind_time = item.get("remind_time") or ""
            if kind == "note":
                show = True
            elif meta["recurrence"] in {"yearly", "lunar_yearly"}:
                show = _is_recurring_due(item, today)
            else:
                show = item["remind_date"] == today.isoformat()

            if show:
                if item["is_done"]:
                    tag = "done"
                    status = "✅ Hoàn Thành"
                    countdown = "—"
                else:
                    if kind == "note":
                        tag = "upcoming"
                        status = "📝 Ghi chú"
                        countdown = "—"
                    else:
                        tag = "upcoming"
                        status = "🔔 Hôm Nay"
                        countdown = _compute_countdown(item["remind_date"], remind_time, datetime.now())
                time_display = remind_time if remind_time else "—"
                tree.insert(
                    "", "end",
                    iid=str(item["id"]),
                    values=(status, item["title"], item["remind_date"], time_display, countdown, meta["note"] or ""),
                    tags=(tag,),
                )

    def _refresh_notifications(self):
        tree = self.tree_notifications
        for row in tree.get_children():
            tree.delete(row)
        today = date.today()
        for item in self._items:
            if item["is_done"]:
                continue
            meta = _parse_note_metadata(item.get("note"))
            if meta["kind"] != "reminder":
                continue
            if not _is_recurring_due(item, today) and item["remind_date"] != today.isoformat():
                continue
            if item.get("notified") == 1 and meta["recurrence"] == "none":
                continue
            if meta["recurrence"] in {"yearly", "lunar_yearly"} and meta["last_notified"] == today.isoformat():
                continue

            remind_time = item.get("remind_time") or ""
            if remind_time:
                try:
                    h, m = map(int, remind_time.split(":"))
                    remind_dt = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
                    if datetime.now() < remind_dt:
                        continue
                except Exception:
                    pass

            tree.insert(
                "", "end",
                iid=str(item["id"]),
                values=("🔔 Hôm Nay", item["title"], item["remind_date"], remind_time if remind_time else "—",
                        _compute_countdown(item["remind_date"], remind_time, datetime.now()), meta["note"] or ""),
                tags=("upcoming",),
            )

    def open_add_dialog(self):
        _ReminderDialog(self, title="Thêm Công Việc")

    def open_edit_dialog(self):
        sel = self._get_current_tree().selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một mục.", parent=self)
            return
        item_id = int(sel[0])
        item = next((i for i in self._items if i["id"] == item_id), None)
        if item:
            _ReminderDialog(self, title="Sửa Công Việc", item=item)

    def toggle_done(self):
        sel = self._get_current_tree().selection()
        if not sel:
            return
        db.toggle_reminder_done(int(sel[0]))
        self.load_data()

    def delete_selected(self):
        sel = self._get_current_tree().selection()
        if not sel:
            return
        if messagebox.askyesno("Xác nhận", "Xóa công việc này?", parent=self):
            db.delete_reminder(int(sel[0]))
            self.load_data()

    def mark_selected_notified(self):
        sel = self.tree_notifications.selection()
        if not sel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một mục trong Thông Báo.", parent=self)
            return
        item_id = int(sel[0])
        item = next((i for i in self._items if i["id"] == item_id), None)
        if not item:
            return
        self._mark_item_read(item)
        self.load_data()

    def _mark_item_read(self, item):
        today = date.today().isoformat()
        meta = _parse_note_metadata(item.get("note"))
        if meta["recurrence"] in {"yearly", "lunar_yearly"}:
            new_note = _compose_note_metadata(
                meta["kind"], meta["recurrence"], meta["lunar_month"], meta["lunar_day"], today, meta["note"],
            )
            db.update_reminder(item["id"], item["title"], new_note, item["remind_date"], item.get("remind_time"))
            return
        db.mark_reminder_notified(item["id"])

    def _get_current_tree(self):
        cur = self.notebook.index(self.notebook.select())
        if cur == 0:
            return self.tree_all
        if cur == 1:
            return self.tree_today
        return self.tree_notifications

    def _schedule_check(self):
        self._check_reminders()
        self.after(REMINDER_CHECK_MS, self._schedule_check)

    def _check_reminders(self):
        today = date.today()
        for item in self._items:
            if item["is_done"]:
                continue
            meta = _parse_note_metadata(item.get("note"))
            if meta["kind"] != "reminder":
                continue
            if not _is_recurring_due(item, today) and item["remind_date"] != today.isoformat():
                continue
            if item.get("notified") == 1 and meta["recurrence"] == "none":
                continue
            if meta["recurrence"] in {"yearly", "lunar_yearly"} and meta["last_notified"] == today.isoformat():
                continue

            remind_time = item.get("remind_time") or ""
            if remind_time:
                try:
                    h, m = map(int, remind_time.split(":"))
                    now = datetime.now()
                    remind_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    if now < remind_dt:
                        continue
                except Exception:
                    pass

            if meta["recurrence"] in {"yearly", "lunar_yearly"}:
                self._mark_item_read(item)
            else:
                db.mark_reminder_notified(item["id"])
            self._show_popup(item)

        if self._items:
            self.load_data()

    def _show_popup(self, rem):
        popup = tk.Toplevel(self)
        popup.title("🔔 Nhắc Nhở Công Việc")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)

        frm = tk.Frame(popup, bg=ACCENT, padx=20, pady=16)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="🔔 NHẮC NHỞ HÔM NAY", bg=ACCENT, fg="white", font=("Segoe UI", 13, "bold")).pack()
        tk.Label(frm, text=rem["title"], bg=ACCENT, fg="white", font=("Segoe UI", 11)).pack(pady=4)
        meta = _parse_note_metadata(rem.get("note"))
        if meta["note"]:
            tk.Label(frm, text=meta["note"], bg=ACCENT, fg="#ECF0F1", font=("Segoe UI", 10), wraplength=280).pack()
        time_str = f"  lúc {rem['remind_time']}" if rem.get("remind_time") else ""
        tk.Label(frm, text=f"Ngày: {rem['remind_date']}{time_str}", bg=ACCENT, fg="#BDC3C7", font=("Segoe UI", 9)).pack(pady=(4, 0))

        ttk.Button(popup, text="Đã Biết", command=popup.destroy).pack(pady=8)
        popup.after(30000, popup.destroy)


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
        self.time_cb = ttk.Combobox(time_frame, textvariable=self.time_var, values=PRESET_TIMES, width=10)
        self.time_cb.pack(side="left")
        tk.Label(time_frame, text="(để trống = cả ngày)", bg=CARD_BG, fg="#7F8C8D", font=("Segoe UI", 9)).pack(side="left", padx=6)

        tk.Label(frm, text="Loại:", bg=CARD_BG, font=FONT_BOLD).grid(row=3, column=0, sticky="w", **pad)
        self.kind_var = tk.StringVar(value="reminder")
        self.kind_cb = ttk.Combobox(frm, textvariable=self.kind_var, values=["Nhắc nhở", "Ghi chú", "Hôm nay"], width=20)
        self.kind_cb.grid(row=3, column=1, sticky="w", **pad)

        tk.Label(frm, text="Lặp lại:", bg=CARD_BG, font=FONT_BOLD).grid(row=4, column=0, sticky="w", **pad)
        self.recurrence_var = tk.StringVar(value="Không lặp")
        self.recurrence_cb = ttk.Combobox(frm, textvariable=self.recurrence_var,
                                          values=["Không lặp", "Hằng năm (dương lịch)", "Hằng năm (âm lịch)"], width=24)
        self.recurrence_cb.grid(row=4, column=1, sticky="w", **pad)

        tk.Label(frm, text="Âm lịch (tháng/ngày):", bg=CARD_BG, font=FONT_BOLD).grid(row=5, column=0, sticky="w", **pad)
        lunar_frame = tk.Frame(frm, bg=CARD_BG)
        lunar_frame.grid(row=5, column=1, sticky="w", **pad)
        self.lunar_month_var = tk.StringVar(value="")
        self.lunar_day_var = tk.StringVar(value="")
        ttk.Entry(lunar_frame, textvariable=self.lunar_month_var, width=5).pack(side="left")
        tk.Label(lunar_frame, text="/", bg=CARD_BG).pack(side="left", padx=4)
        ttk.Entry(lunar_frame, textvariable=self.lunar_day_var, width=5).pack(side="left")
        tk.Label(lunar_frame, text="(chỉ dùng khi chọn âm lịch)", bg=CARD_BG, fg="#7F8C8D", font=("Segoe UI", 9)).pack(side="left", padx=6)

        tk.Label(frm, text="Ghi Chú:", bg=CARD_BG, font=FONT_BOLD).grid(row=6, column=0, sticky="nw", **pad)
        self.note_text = tk.Text(frm, width=34, height=4, font=FONT)
        self.note_text.grid(row=6, column=1, sticky="w", **pad)

        btn_frm = tk.Frame(frm, bg=CARD_BG)
        btn_frm.grid(row=7, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frm, text="💾 Lưu", command=self._save).pack(side="left", padx=6)
        ttk.Button(btn_frm, text="Hủy", command=self.destroy).pack(side="left", padx=6)

    def _populate(self, item):
        self.title_var.set(item["title"])
        self.date_var.set(item["remind_date"])
        self.time_var.set(item.get("remind_time") or "")

        meta = _parse_note_metadata(item.get("note"))
        kind_map = {"reminder": "Nhắc nhở", "note": "Ghi chú", "today": "Hôm nay"}
        self.kind_var.set(kind_map.get(meta["kind"], "Nhắc nhở"))

        recur_map = {
            "none": "Không lặp",
            "yearly": "Hằng năm (dương lịch)",
            "lunar_yearly": "Hằng năm (âm lịch)",
        }
        self.recurrence_var.set(recur_map.get(meta["recurrence"], "Không lặp"))
        if meta["lunar_month"] is not None:
            self.lunar_month_var.set(str(meta["lunar_month"]))
        if meta["lunar_day"] is not None:
            self.lunar_day_var.set(str(meta["lunar_day"]))
        if meta["note"]:
            self.note_text.insert("1.0", meta["note"])

    def _save(self):
        title = self.title_var.get().strip()
        remind_date = self.date_var.get().strip()
        remind_time = self.time_var.get().strip() or None
        note = self.note_text.get("1.0", "end").strip()

        kind_map = {"Nhắc nhở": "reminder", "Ghi chú": "note", "Hôm nay": "today"}
        recur_map = {
            "Không lặp": "none",
            "Hằng năm (dương lịch)": "yearly",
            "Hằng năm (âm lịch)": "lunar_yearly",
        }

        kind = kind_map.get(self.kind_var.get(), "reminder")
        recurrence = recur_map.get(self.recurrence_var.get(), "none")

        lunar_month = None
        lunar_day = None
        if recurrence == "lunar_yearly":
            try:
                lunar_month = int(self.lunar_month_var.get().strip())
                lunar_day = int(self.lunar_day_var.get().strip())
            except ValueError:
                messagebox.showerror("Lỗi", "Vui lòng nhập tháng/ngày âm lịch hợp lệ.", parent=self)
                return

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

        # Store recurrence metadata in note for compatibility without DB migration
        note_with_meta = _compose_note_metadata(kind, recurrence, lunar_month, lunar_day, None, note)

        if self.item:
            db.update_reminder(self.item["id"], title, note_with_meta, remind_date, remind_time)
        else:
            db.add_reminder(title, note_with_meta, remind_date, remind_time)

        self.parent_frame.load_data()
        self.destroy()
