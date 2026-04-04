import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS life_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    horizon INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    achieved INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            # Migration: add due_date to goals if not present
            try:
                conn.execute("ALTER TABLE goals ADD COLUMN due_date TEXT")
            except sqlite3.OperationalError:
                pass  # column already exists

    # --- Goals ---

    def add_goal(self, goal_type: str, text: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO goals (type, text) VALUES (?, ?)", (goal_type, text)
            )
            return cur.lastrowid

    def set_goal_due_date(self, goal_id: int, due_date: Optional[str]) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE goals SET due_date = ? WHERE id = ?", (due_date, goal_id)
            )
            return cur.rowcount > 0

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

    SHORT_TERM_GOALS_SEED = [
        ("short", "Sell 20 shirts/month consistently — RYSY milestone"),
    ]

    def seed_short_term_goals(self) -> None:
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM goals WHERE type = 'short'").fetchone()[0]
            if count == 0:
                conn.executemany(
                    "INSERT INTO goals (type, text) VALUES (?, ?)",
                    self.SHORT_TERM_GOALS_SEED,
                )

    # --- Life Goals ---

    LIFE_GOALS_SEED = [
        (5, "Ecom business making €50k revenue/month with 25% profit margin"),
        (5, "Living in a house in center of Poznań — room for each kid, room for us with bathroom & jacuzzi, working space, big garage, small workshop"),
        (5, "Still have free time — work on average 4h/day"),
        (5, "Be healthy and fit, BJJ black belt and still actively training"),
        (5, "Make one big travel a year to a different continent (2-3 weeks)"),
        (5, "Speaking fluent Polish (C2)"),
        (10, "Having sold one business, or growing it further — owning a famous brand through Europe"),
        (10, "Being a frequently asked speaker for business conferences, strong personal brand with solid following"),
        (10, "Still being healthy and fit, working out 6 times/week"),
        (10, "Owning a luxury apartment in Świnoujście"),
        (10, "Driving Dakar rally with my own team"),
        (15, "Owning a business which is a market leader throughout Europe — owning, less managing"),
        (15, "Having written a book about branding, marketing, or anything related"),
        (15, "Having children knowledgeable about business, with means to study further or abroad"),
        (15, "Healthy and fit, working out 6 times/week"),
        (15, "Living in a luxury apartment in the center of Poznań or any other interesting city"),
    ]

    def seed_life_goals(self) -> None:
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM life_goals").fetchone()[0]
            if count == 0:
                conn.executemany(
                    "INSERT INTO life_goals (horizon, text) VALUES (?, ?)",
                    self.LIFE_GOALS_SEED,
                )

    def add_life_goal(self, horizon: int, text: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO life_goals (horizon, text) VALUES (?, ?)", (horizon, text)
            )
            return cur.lastrowid

    def get_life_goals(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM life_goals ORDER BY horizon, achieved, id"
            ).fetchall()
            return [dict(row) for row in rows]

    def mark_life_goal_achieved(self, goal_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE life_goals SET achieved = 1 WHERE id = ? AND achieved = 0", (goal_id,)
            )
            return cur.rowcount > 0

    def delete_life_goal(self, goal_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM life_goals WHERE id = ?", (goal_id,))
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
