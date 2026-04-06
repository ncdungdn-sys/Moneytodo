"""
Background exercise reminder monitoring thread.

Checks every 60 seconds whether a reminder is due for the active session.
Uses a queue to safely communicate events back to the Tkinter main thread.
"""
import threading
import queue
import time
from datetime import datetime, timedelta

import database as db

# How often (seconds) the background thread wakes up to check
CHECK_INTERVAL = 60

# Singleton thread + queue reference
_thread = None
_stop_event = threading.Event()
_event_queue = queue.Queue()


def get_event_queue():
    """Return the queue that the UI should poll for exercise events."""
    return _event_queue


def start_monitor():
    """Start the background monitoring thread (idempotent)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_monitor_loop, daemon=True, name="ExerciseMonitor")
    _thread.start()


def stop_monitor():
    """Signal the monitoring thread to stop."""
    _stop_event.set()


def _monitor_loop():
    """Main loop: wakes every CHECK_INTERVAL seconds and fires reminders."""
    while not _stop_event.is_set():
        try:
            _check_sessions()
        except Exception as exc:
            # Log to stderr; don't crash the monitor thread
            import traceback
            traceback.print_exc()
        _stop_event.wait(CHECK_INTERVAL)


def _check_sessions():
    """Check active sessions and fire reminders when due."""
    today = datetime.now().strftime("%Y-%m-%d")
    session = db.get_active_session(today)
    if not session:
        return

    now = datetime.now()
    session_id = session["id"]
    interval_minutes = session.get("interval_minutes", 30)
    auto_stop_hours = session.get("auto_stop_hours")
    start_time_str = session.get("start_time", "")

    # Parse start time
    try:
        start_dt = datetime.strptime(f"{today} {start_time_str}", "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return

    # Check auto-stop
    if auto_stop_hours:
        stop_dt = start_dt + timedelta(hours=auto_stop_hours)
        if now >= stop_dt:
            db.stop_exercise_session(session_id)
            _event_queue.put({"type": "session_auto_stopped", "session_id": session_id})
            return

    # Auto mode: only active between 09:00 and 18:00
    if session.get("mode") == "auto":
        if now.hour < 9 or now.hour >= 18:
            return

    # Compute next reminder time
    history = db.get_exercise_history_today(session_id)
    completed_count = len([h for h in history if h["status"] in ("completed", "skipped")])
    next_reminder_dt = start_dt + timedelta(minutes=interval_minutes * (completed_count + 1))

    if now >= next_reminder_dt:
        # Pick next exercise (cycle through active exercises in sorted order)
        exercises = db.get_active_exercises()
        if not exercises:
            return
        exercise = exercises[completed_count % len(exercises)]
        exercise_time = now.strftime("%H:%M")

        # Add as pending history entry
        history_id = db.add_exercise_history(
            session_id, exercise["exercise_name"], exercise_time, "pending"
        )

        _event_queue.put({
            "type": "reminder_due",
            "session_id": session_id,
            "history_id": history_id,
            "exercise_name": exercise["exercise_name"],
            "exercise_time": exercise_time,
            "count": completed_count + 1,
        })
