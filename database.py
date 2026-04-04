import sqlite3
from datetime import datetime
from typing import List, Dict
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")


class Database:
    def __init__(self):
        self._create_tables()

    def _connect(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    text TEXT NOT NULL,
                    done INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    datetime TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)

    # --- Goals ---

    def add_goal(self, goal_type: str, text: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO goals (type, text) VALUES (?, ?)", (goal_type, text)
            )
            return cur.lastrowid

    def get_goals(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM goals ORDER BY done, type, id"
            ).fetchall()
            return [dict(row) for row in rows]

    def mark_goal_done(self, goal_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE goals SET done = 1 WHERE id = ? AND done = 0", (goal_id,)
            )
            return cur.rowcount > 0

    def delete_goal(self, goal_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
            return cur.rowcount > 0

    # --- Appointments ---

    def add_appointment(self, dt: datetime, title: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO appointments (datetime, title) VALUES (?, ?)",
                (dt.isoformat(), title),
            )
            return cur.lastrowid

    def get_upcoming_appointments(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM appointments WHERE datetime >= ? ORDER BY datetime",
                (datetime.now().isoformat(),),
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_appointment(self, appt_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM appointments WHERE id = ?", (appt_id,))
            return cur.rowcount > 0
