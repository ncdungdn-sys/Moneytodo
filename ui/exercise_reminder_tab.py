"""
Exercise Reminder Tab – Dual-mode workout reminder dashboard.

Modes:
  • On-Demand : User starts/stops manually.
  • Auto      : Runs automatically 09:00 – 18:00.

Background events are received via the queue from utils.exercise_reminder
and dispatched to the UI every 2 seconds using Tkinter's after() mechanism.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

import database as db
from utils.exercise_reminder import get_event_queue, start_monitor

# ── Colour palette (matches main app) ────────────────────────────────────────
BG = "#F0F4F8"
CARD_BG = "#FFFFFF"
HEADER_BG = "#2C3E50"
ACCENT = "#3498DB"
GREEN = "#27AE60"
RED = "#E74C3C"
ORANGE = "#E67E22"
TEXT_DARK = "#2C3E50"
TEXT_LIGHT = "#ECF0F1"
TEXT_MUTED = "#7F8C8D"

FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADER = ("Segoe UI", 12, "bold")
FONT_LARGE = ("Segoe UI", 14, "bold")
FONT_SMALL = ("Segoe UI", 9)

# Poll queue every N ms
POLL_MS = 2000
# Refresh countdown every N ms
COUNTDOWN_MS = 5000


class ExerciseReminderFrame(tk.Frame):
    """Main exercise reminder tab."""

    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._session = None          # active session dict
        self._next_reminder_dt = None # datetime of next reminder
        self._event_queue = get_event_queue()
        self._build_ui()
        self.load_data()
        self._poll_queue()
        self._schedule_countdown()

    # ─────────────────────────────────────────────────────────────────────────
    # UI Construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Main scrollable layout – left column and right column
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=12, pady=8)

        # Page title
        tk.Label(outer, text="🏋️ Nhắc Nhở Tập Thể Dục",
                 bg=BG, fg=TEXT_DARK, font=FONT_LARGE).pack(anchor="w", pady=(0, 6))

        # Two-column layout
        columns = tk.Frame(outer, bg=BG)
        columns.pack(fill="both", expand=True)
        columns.columnconfigure(0, weight=2)
        columns.columnconfigure(1, weight=3)

        left = tk.Frame(columns, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        right = tk.Frame(columns, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")

        # Left column: mode + status + controls
        self._build_mode_panel(left)
        self._build_status_panel(left)
        self._build_control_panel(left)

        # Right column: config + history + stats
        self._build_config_panel(right)
        self._build_history_panel(right)
        self._build_stats_panel(right)

    # ── Mode Selection ────────────────────────────────────────────────────────

    def _build_mode_panel(self, parent):
        card = _Card(parent, "⚙️ Chọn Chế Độ")
        inner = card.inner

        self._mode_var = tk.StringVar(value="on_demand")
        modes = [("🖱️ Thủ Công (On-Demand)", "on_demand"),
                 ("🤖 Tự Động (09:00–18:00)", "auto")]
        for label, value in modes:
            ttk.Radiobutton(
                inner, text=label, variable=self._mode_var, value=value,
                command=self._on_mode_change,
            ).pack(anchor="w", pady=2)

        self._mode_desc = tk.Label(
            inner, text="Nhấn BẬT NGAY để bắt đầu phiên tập.",
            bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL, wraplength=240, justify="left",
        )
        self._mode_desc.pack(anchor="w", pady=(4, 0))

    def _on_mode_change(self):
        if self._mode_var.get() == "auto":
            self._mode_desc.config(
                text="Tự động nhắc nhở mỗi khoảng thời gian từ 09:00 đến 18:00."
            )
        else:
            self._mode_desc.config(text="Nhấn BẬT NGAY để bắt đầu phiên tập.")

    # ── Status Panel ──────────────────────────────────────────────────────────

    def _build_status_panel(self, parent):
        card = _Card(parent, "📊 Trạng Thái")
        inner = card.inner

        # Status indicator row
        status_row = tk.Frame(inner, bg=CARD_BG)
        status_row.pack(fill="x", pady=2)
        self._status_indicator = tk.Label(
            status_row, text="🔴 DỪNG", bg=CARD_BG, fg=RED, font=FONT_LARGE,
        )
        self._status_indicator.pack(side="left")

        # Details grid
        grid = tk.Frame(inner, bg=CARD_BG)
        grid.pack(fill="x", pady=(4, 0))

        def _row(label, row_idx):
            tk.Label(grid, text=label, bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL,
                     anchor="w", width=14).grid(row=row_idx, column=0, sticky="w")
            var = tk.StringVar(value="—")
            tk.Label(grid, textvariable=var, bg=CARD_BG, fg=TEXT_DARK, font=FONT,
                     anchor="w").grid(row=row_idx, column=1, sticky="w")
            return var

        self._start_time_var = _row("Bắt đầu:", 0)
        self._next_time_var = _row("Nhắc tiếp:", 1)
        self._countdown_var = _row("Đếm ngược:", 2)
        self._exercise_var = _row("Bài tập:", 3)

    # ── Control Buttons ───────────────────────────────────────────────────────

    def _build_control_panel(self, parent):
        card = _Card(parent, "🎮 Điều Khiển")
        inner = card.inner

        btn_row = tk.Frame(inner, bg=CARD_BG)
        btn_row.pack(fill="x", pady=2)

        self._btn_start = tk.Button(
            btn_row, text="🟢 BẬT NGAY",
            bg=GREEN, fg="white", font=FONT_BOLD,
            relief="flat", padx=10, pady=6, cursor="hand2",
            command=self._start_session,
        )
        self._btn_start.pack(side="left", padx=(0, 4))

        self._btn_stop = tk.Button(
            btn_row, text="⏸️ DỪNG",
            bg=RED, fg="white", font=FONT_BOLD,
            relief="flat", padx=10, pady=6, cursor="hand2",
            command=self._stop_session, state="disabled",
        )
        self._btn_stop.pack(side="left", padx=4)

        btn_row2 = tk.Frame(inner, bg=CARD_BG)
        btn_row2.pack(fill="x", pady=(4, 0))

        self._btn_skip = tk.Button(
            btn_row2, text="⏭️ Bỏ qua",
            bg=ORANGE, fg="white", font=FONT,
            relief="flat", padx=10, pady=5, cursor="hand2",
            command=self._skip_reminder, state="disabled",
        )
        self._btn_skip.pack(side="left", padx=(0, 4))

        ttk.Button(btn_row2, text="🔄 Làm Mới", command=self.load_data).pack(side="left", padx=4)

    # ── Configuration Panel ───────────────────────────────────────────────────

    def _build_config_panel(self, parent):
        card = _Card(parent, "⚙️ Cấu Hình")
        inner = card.inner

        # Interval selection
        int_row = tk.Frame(inner, bg=CARD_BG)
        int_row.pack(fill="x", pady=(0, 6))
        tk.Label(int_row, text="Chu kỳ nhắc:", bg=CARD_BG, font=FONT_BOLD).pack(side="left")

        self._interval_var = tk.IntVar(value=30)
        for label, val in [("15p", 15), ("30p", 30), ("45p", 45), ("1h", 60)]:
            ttk.Radiobutton(
                int_row, text=label, variable=self._interval_var, value=val,
            ).pack(side="left", padx=4)

        custom_row = tk.Frame(inner, bg=CARD_BG)
        custom_row.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(
            custom_row, text="Tùy chỉnh:",
            variable=self._interval_var, value=-1,
        ).pack(side="left")
        self._custom_interval_var = tk.StringVar(value="")
        ttk.Entry(custom_row, textvariable=self._custom_interval_var, width=6).pack(side="left", padx=4)
        tk.Label(custom_row, text="phút", bg=CARD_BG, font=FONT).pack(side="left")

        # Auto-stop duration
        stop_row = tk.Frame(inner, bg=CARD_BG)
        stop_row.pack(fill="x", pady=(0, 6))
        tk.Label(stop_row, text="Tự dừng sau:", bg=CARD_BG, font=FONT_BOLD).pack(side="left")

        self._auto_stop_var = tk.IntVar(value=8)
        for label, val in [("4h", 4), ("8h", 8), ("10h", 10), ("Thủ công", 0)]:
            ttk.Radiobutton(
                stop_row, text=label, variable=self._auto_stop_var, value=val,
            ).pack(side="left", padx=4)

        # Exercise list
        tk.Label(inner, text="Danh sách bài tập:", bg=CARD_BG, font=FONT_BOLD).pack(anchor="w", pady=(4, 2))

        list_frame = tk.Frame(inner, bg=CARD_BG)
        list_frame.pack(fill="both")

        self._exercise_list_frame = list_frame
        self._exercise_check_vars = {}
        self._refresh_exercise_list()

        # Buttons
        btn_row = tk.Frame(inner, bg=CARD_BG)
        btn_row.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_row, text="💾 Lưu Cấu hình", command=self._save_config).pack(side="left", padx=2)
        ttk.Button(btn_row, text="➕ Thêm Bài Tập", command=self._open_add_exercise_dialog).pack(side="left", padx=2)

    def _refresh_exercise_list(self):
        for widget in self._exercise_list_frame.winfo_children():
            widget.destroy()
        self._exercise_check_vars.clear()
        exercises = db.get_exercise_reminders()
        for ex in exercises:
            var = tk.BooleanVar(value=bool(ex.get("is_enabled", 1)))
            self._exercise_check_vars[ex["id"]] = var
            row = tk.Frame(self._exercise_list_frame, bg=CARD_BG)
            row.pack(fill="x")
            ttk.Checkbutton(row, text=ex["exercise_name"], variable=var).pack(side="left")
            if ex.get("description"):
                tk.Label(row, text=f"({ex['description']})",
                         bg=CARD_BG, fg=TEXT_MUTED, font=FONT_SMALL).pack(side="left", padx=4)
            tk.Button(
                row, text="🗑️", bg=CARD_BG, relief="flat", cursor="hand2",
                command=lambda eid=ex["id"]: self._delete_exercise(eid),
            ).pack(side="right")

    # ── History Panel ─────────────────────────────────────────────────────────

    def _build_history_panel(self, parent):
        card = _Card(parent, "📋 Lịch Sử Hôm Nay")
        inner = card.inner

        cols = ("time", "exercise", "status")
        self._history_tree = ttk.Treeview(
            inner, columns=cols, show="headings", height=6, selectmode="browse",
        )
        headings = {"time": ("Giờ", 65), "exercise": ("Bài Tập", 150), "status": ("Trạng Thái", 100)}
        for col, (text, width) in headings.items():
            self._history_tree.heading(col, text=text)
            self._history_tree.column(col, width=width, anchor="w")
        self._history_tree.tag_configure("completed", foreground=GREEN)
        self._history_tree.tag_configure("skipped", foreground=ORANGE)
        self._history_tree.tag_configure("pending", foreground=ACCENT)

        vsb = ttk.Scrollbar(inner, orient="vertical", command=self._history_tree.yview)
        self._history_tree.configure(yscrollcommand=vsb.set)
        self._history_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        inner.columnconfigure(0, weight=1)
        inner.rowconfigure(0, weight=1)

    # ── Statistics Panel ──────────────────────────────────────────────────────

    def _build_stats_panel(self, parent):
        card = _Card(parent, "📈 Thống Kê Hôm Nay")
        inner = card.inner

        grid = tk.Frame(inner, bg=CARD_BG)
        grid.pack(fill="x")

        def _stat_label(row, col, text, color=TEXT_DARK, font=FONT):
            lbl = tk.Label(grid, text=text, bg=CARD_BG, fg=color, font=font)
            lbl.grid(row=row, column=col, sticky="w", padx=4, pady=2)
            return lbl

        _stat_label(0, 0, "Tổng nhắc:", font=FONT_BOLD)
        self._stat_total = _stat_label(0, 1, "0")

        _stat_label(1, 0, "Hoàn thành:", font=FONT_BOLD)
        self._stat_completed = _stat_label(1, 1, "0", color=GREEN)

        _stat_label(2, 0, "Bỏ qua:", font=FONT_BOLD)
        self._stat_skipped = _stat_label(2, 1, "0", color=ORANGE)

        # Progress bar
        pb_row = tk.Frame(inner, bg=CARD_BG)
        pb_row.pack(fill="x", pady=(6, 0))
        tk.Label(pb_row, text="Tiến độ:", bg=CARD_BG, font=FONT_BOLD).pack(side="left")
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            pb_row, variable=self._progress_var, maximum=100, length=200,
        )
        self._progress_bar.pack(side="left", padx=6)
        self._progress_pct = tk.Label(pb_row, text="0%", bg=CARD_BG, font=FONT)
        self._progress_pct.pack(side="left")

    # ─────────────────────────────────────────────────────────────────────────
    # Data Loading
    # ─────────────────────────────────────────────────────────────────────────

    def load_data(self):
        """Refresh session state, history and stats."""
        today = datetime.now().strftime("%Y-%m-%d")
        self._session = db.get_active_session(today)
        self._update_status_panel()
        self._update_history()
        self._update_stats()
        self._refresh_exercise_list()

    def _update_status_panel(self):
        if self._session:
            self._status_indicator.config(text="🟢 ĐANG CHẠY", fg=GREEN)
            self._start_time_var.set(self._session.get("start_time", "—"))
            self._btn_start.config(state="disabled")
            self._btn_stop.config(state="normal")
            self._btn_skip.config(state="normal")
            self._compute_next_reminder()
        else:
            self._status_indicator.config(text="🔴 DỪNG", fg=RED)
            self._start_time_var.set("—")
            self._next_time_var.set("—")
            self._countdown_var.set("—")
            self._exercise_var.set("—")
            self._next_reminder_dt = None
            self._btn_start.config(state="normal")
            self._btn_stop.config(state="disabled")
            self._btn_skip.config(state="disabled")

    def _compute_next_reminder(self):
        if not self._session:
            return
        today = datetime.now().strftime("%Y-%m-%d")
        session_id = self._session["id"]
        interval = self._session.get("interval_minutes", 30)
        start_str = self._session.get("start_time", "")
        try:
            start_dt = datetime.strptime(f"{today} {start_str}", "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return

        history = db.get_exercise_history_today(session_id)
        done_count = len([h for h in history if h["status"] in ("completed", "skipped")])
        self._next_reminder_dt = start_dt + timedelta(minutes=interval * (done_count + 1))
        self._next_time_var.set(self._next_reminder_dt.strftime("%H:%M"))

        # Pick next exercise
        exercises = [e for e in db.get_exercise_reminders() if e.get("is_enabled", 1)]
        if exercises:
            next_ex = exercises[done_count % len(exercises)]
            self._exercise_var.set(next_ex["exercise_name"])

    def _update_history(self):
        for row in self._history_tree.get_children():
            self._history_tree.delete(row)
        if not self._session:
            return
        history = db.get_exercise_history_today(self._session["id"])
        status_icons = {"completed": "✅ Hoàn thành", "skipped": "⏭️ Bỏ qua", "pending": "⏳ Đang chờ"}
        for h in reversed(history):
            tag = h["status"]
            self._history_tree.insert(
                "", "end",
                iid=str(h["id"]),
                values=(h["exercise_time"], h["exercise_name"],
                        status_icons.get(h["status"], h["status"])),
                tags=(tag,),
            )

    def _update_stats(self):
        if not self._session:
            self._stat_total.config(text="0")
            self._stat_completed.config(text="0")
            self._stat_skipped.config(text="0")
            self._progress_var.set(0)
            self._progress_pct.config(text="0%")
            return

        stats = db.get_exercise_stats_today(self._session["id"])
        total = stats["total"]
        completed = stats["completed"]
        skipped = stats["skipped"]

        pct = round(completed / total * 100) if total > 0 else 0
        self._stat_total.config(text=str(total))
        self._stat_completed.config(text=f"{completed} ({pct}%)")
        self._stat_skipped.config(text=f"{skipped} ({round(skipped/total*100) if total else 0}%)")
        self._progress_var.set(pct)
        self._progress_pct.config(text=f"{pct}%")

    # ─────────────────────────────────────────────────────────────────────────
    # Session Controls
    # ─────────────────────────────────────────────────────────────────────────

    def _start_session(self):
        interval = self._get_interval()
        if interval is None:
            return
        auto_stop = self._auto_stop_var.get() or None
        mode = self._mode_var.get()
        session_id = db.start_exercise_session(
            mode=mode, interval_minutes=interval, auto_stop_hours=auto_stop
        )
        self.load_data()

    def _stop_session(self):
        if not self._session:
            return
        if messagebox.askyesno("Xác nhận", "Dừng phiên tập hiện tại?", parent=self):
            db.stop_exercise_session(self._session["id"])
            self._session = None
            self.load_data()

    def _skip_reminder(self):
        if not self._session:
            return
        now_str = datetime.now().strftime("%H:%M")
        exercises = [e for e in db.get_exercise_reminders() if e.get("is_enabled", 1)]
        history = db.get_exercise_history_today(self._session["id"])
        done_count = len([h for h in history if h["status"] in ("completed", "skipped")])

        # If there's a pending history entry, update it; otherwise create new
        pending = [h for h in history if h["status"] == "pending"]
        if pending:
            conn = db.get_connection()
            conn.execute(
                "UPDATE exercise_history SET status='skipped' WHERE id=?",
                (pending[-1]["id"],),
            )
            conn.commit()
            conn.close()
        else:
            if exercises:
                ex = exercises[done_count % len(exercises)]
                db.add_exercise_history(self._session["id"], ex["exercise_name"], now_str, "skipped")

        self.load_data()

    def _get_interval(self):
        val = self._interval_var.get()
        if val == -1:
            try:
                val = int(self._custom_interval_var.get())
                if val < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Lỗi", "Vui lòng nhập chu kỳ hợp lệ (phút).", parent=self)
                return None
        return val

    # ─────────────────────────────────────────────────────────────────────────
    # Configuration
    # ─────────────────────────────────────────────────────────────────────────

    def _save_config(self):
        # Persist exercise enabled/disabled state
        for ex_id, var in self._exercise_check_vars.items():
            conn = db.get_connection()
            conn.execute(
                "UPDATE exercise_reminders SET is_enabled=? WHERE id=?",
                (1 if var.get() else 0, ex_id),
            )
            conn.commit()
            conn.close()
        messagebox.showinfo("Thành công", "Cấu hình đã được lưu.", parent=self)
        self._refresh_exercise_list()

    def _open_add_exercise_dialog(self):
        _ExerciseDialog(self)

    def _delete_exercise(self, ex_id):
        if messagebox.askyesno("Xác nhận", "Xóa bài tập này?", parent=self):
            db.delete_exercise_reminder(ex_id)
            self._refresh_exercise_list()

    # ─────────────────────────────────────────────────────────────────────────
    # Queue polling & Countdown
    # ─────────────────────────────────────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                event = self._event_queue.get_nowait()
                self._handle_event(event)
        except Exception:
            pass
        self.after(POLL_MS, self._poll_queue)

    def _handle_event(self, event):
        etype = event.get("type")
        if etype == "reminder_due":
            self._show_reminder_popup(event)
        elif etype == "session_auto_stopped":
            self._session = None
            self.load_data()
            messagebox.showinfo(
                "Kết thúc", "Phiên tập đã tự động dừng sau thời gian cấu hình.", parent=self
            )

    def _show_reminder_popup(self, event):
        popup = tk.Toplevel(self)
        popup.title("💪 Giờ Tập Rồi!")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)

        frm = tk.Frame(popup, bg=GREEN, padx=24, pady=20)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="💪 GIỜ TẬP RỒI!", bg=GREEN, fg="white",
                 font=("Segoe UI", 14, "bold")).pack()

        tk.Frame(frm, bg="white", height=1).pack(fill="x", pady=8)

        tk.Label(frm, text=f"Bài tập: {event.get('exercise_name', '—')}",
                 bg=GREEN, fg="white", font=("Segoe UI", 12)).pack(pady=2)
        tk.Label(frm, text=f"Lần: {event.get('count', 1)} (hôm nay)",
                 bg=GREEN, fg="#D5F5E3", font=FONT).pack(pady=2)
        tk.Label(frm, text=f"Thời gian: {event.get('exercise_time', '—')}",
                 bg=GREEN, fg="#D5F5E3", font=FONT).pack(pady=2)

        tk.Frame(frm, bg="white", height=1).pack(fill="x", pady=8)

        btn_row = tk.Frame(frm, bg=GREEN)
        btn_row.pack()

        session_id = event.get("session_id")
        history_id = event.get("history_id")

        def _complete():
            if history_id:
                conn = db.get_connection()
                conn.execute(
                    "UPDATE exercise_history SET status='completed' WHERE id=?",
                    (history_id,),
                )
                conn.commit()
                conn.close()
            self.load_data()
            popup.destroy()

        def _skip():
            if history_id:
                conn = db.get_connection()
                conn.execute(
                    "UPDATE exercise_history SET status='skipped' WHERE id=?",
                    (history_id,),
                )
                conn.commit()
                conn.close()
            self.load_data()
            popup.destroy()

        tk.Button(btn_row, text="✅ Thực hiện",
                  bg="#1E8449", fg="white", font=FONT_BOLD,
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  command=_complete).pack(side="left", padx=6)
        tk.Button(btn_row, text="⏭️ Bỏ qua",
                  bg=ORANGE, fg="white", font=FONT_BOLD,
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  command=_skip).pack(side="left", padx=6)

        # Auto close after 60 seconds
        popup.after(60000, popup.destroy)

    def _schedule_countdown(self):
        self._update_countdown()
        self.after(COUNTDOWN_MS, self._schedule_countdown)

    def _update_countdown(self):
        if self._next_reminder_dt is None:
            return
        now = datetime.now()
        delta = self._next_reminder_dt - now
        total_sec = int(delta.total_seconds())
        if total_sec <= 0:
            self._countdown_var.set("Sắp tới…")
        else:
            m, s = divmod(total_sec, 60)
            h, m = divmod(m, 60)
            if h:
                self._countdown_var.set(f"{h}h {m}p")
            else:
                self._countdown_var.set(f"{m}p {s}s")


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Card widget
# ─────────────────────────────────────────────────────────────────────────────

class _Card(tk.Frame):
    """Titled white card with a header strip."""

    def __init__(self, parent, title):
        super().__init__(parent, bg=BG)
        self.pack(fill="x", pady=(0, 8))

        header = tk.Frame(self, bg=HEADER_BG, padx=10, pady=4)
        header.pack(fill="x")
        tk.Label(header, text=title, bg=HEADER_BG, fg=TEXT_LIGHT, font=FONT_BOLD).pack(anchor="w")

        self.inner = tk.Frame(self, bg=CARD_BG, padx=10, pady=8)
        self.inner.pack(fill="x")


# ─────────────────────────────────────────────────────────────────────────────
# Dialog: Add / Edit Exercise
# ─────────────────────────────────────────────────────────────────────────────

class _ExerciseDialog(tk.Toplevel):
    def __init__(self, parent_frame, item=None):
        super().__init__(parent_frame)
        self.parent_frame = parent_frame
        self.item = item
        self.title("Thêm Bài Tập" if item is None else "Sửa Bài Tập")
        self.resizable(False, False)
        self.grab_set()
        self._build()
        if item:
            self._populate(item)
        self.transient(parent_frame.winfo_toplevel())
        self.wait_window()

    def _build(self):
        frm = tk.Frame(self, bg=CARD_BG, padx=16, pady=16)
        frm.pack(fill="both", expand=True)
        pad = {"padx": 8, "pady": 5}

        tk.Label(frm, text="Tên bài tập:", bg=CARD_BG, font=FONT_BOLD).grid(row=0, column=0, sticky="w", **pad)
        self._name_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._name_var, width=28).grid(row=0, column=1, sticky="w", **pad)

        tk.Label(frm, text="Mô tả:", bg=CARD_BG, font=FONT_BOLD).grid(row=1, column=0, sticky="w", **pad)
        self._desc_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._desc_var, width=28).grid(row=1, column=1, sticky="w", **pad)

        tk.Label(frm, text="Chu kỳ (phút):", bg=CARD_BG, font=FONT_BOLD).grid(row=2, column=0, sticky="w", **pad)
        self._interval_var = tk.StringVar(value="30")
        ttk.Entry(frm, textvariable=self._interval_var, width=10).grid(row=2, column=1, sticky="w", **pad)

        btn_frm = tk.Frame(frm, bg=CARD_BG)
        btn_frm.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frm, text="💾 Lưu", command=self._save).pack(side="left", padx=6)
        ttk.Button(btn_frm, text="Hủy", command=self.destroy).pack(side="left", padx=6)

    def _populate(self, item):
        self._name_var.set(item["exercise_name"])
        self._desc_var.set(item.get("description") or "")
        self._interval_var.set(str(item.get("interval_minutes", 30)))

    def _save(self):
        name = self._name_var.get().strip()
        desc = self._desc_var.get().strip()
        try:
            interval = int(self._interval_var.get())
            if interval < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Chu kỳ phải là số nguyên dương.", parent=self)
            return
        if not name:
            messagebox.showerror("Lỗi", "Tên bài tập không được để trống.", parent=self)
            return

        if self.item:
            db.update_exercise_reminder(self.item["id"], name, desc, interval)
        else:
            db.add_exercise_reminder(name, desc, interval)

        self.parent_frame._refresh_exercise_list()
        self.destroy()
