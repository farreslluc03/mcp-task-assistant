"""
SQLite-backed storage for tasks.

Best Practice #1 - Input Sanitization
--------------------------------------
Every query in this module uses parameterized placeholders (``?``) instead
of string formatting / f-strings. The Python ``sqlite3`` driver sends the
SQL text and the bound values to the database separately, so a value can
never be interpreted as SQL syntax no matter what characters it contains.
In addition, free-choice fields (``priority``, ``status``) are validated
against a fixed whitelist before they ever reach a query, and free-text
fields have length limits enforced in Python first.

See ``demo/exploit_sql_injection.py`` for a live demonstration of an
injection attempt against this code, plus a side-by-side comparison with a
deliberately vulnerable (f-string) version of the same query.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterator, Optional

VALID_PRIORITIES = ("low", "medium", "high")
VALID_STATUSES = ("pending", "done")

MAX_TITLE_LENGTH = 200


class ValidationError(ValueError):
    """Raised when caller-supplied input fails validation, before it ever
    reaches a SQL query or any other sensitive sink."""


@dataclass
class Task:
    id: int
    title: str
    priority: str
    status: str
    due_date: Optional[str]
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


class TaskStore:
    """A tiny SQLite-backed repository for Task rows."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    priority TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'pending',
                    due_date TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    # ---- validation helpers ----------------------------------------------
    @staticmethod
    def _validate_title(title: str) -> str:
        title = (title or "").strip()
        if not title:
            raise ValidationError("Task title cannot be empty.")
        if len(title) > MAX_TITLE_LENGTH:
            raise ValidationError(
                f"Task title must be {MAX_TITLE_LENGTH} characters or fewer."
            )
        return title

    @staticmethod
    def _validate_priority(priority: str) -> str:
        priority = (priority or "medium").strip().lower()
        if priority not in VALID_PRIORITIES:
            raise ValidationError(
                f"priority must be one of {VALID_PRIORITIES}, got {priority!r}."
            )
        return priority

    @staticmethod
    def _validate_status(status: str) -> str:
        status = (status or "pending").strip().lower()
        if status not in (*VALID_STATUSES, "all"):
            raise ValidationError(
                f"status must be one of {VALID_STATUSES} or 'all', got {status!r}."
            )
        return status

    # ---- public API --------------------------------------------------------
    def add_task(
        self, title: str, priority: str = "medium", due_date: str = ""
    ) -> Task:
        title = self._validate_title(title)
        priority = self._validate_priority(priority)
        due_date = (due_date or "").strip() or None

        # SAFE: values are bound parameters, never string-interpolated into
        # the SQL text.
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (title, priority, due_date) VALUES (?, ?, ?)",
                (title, priority, due_date),
            )
            task_id = cursor.lastrowid

        task = self.get_task(task_id)  # type: ignore[arg-type]
        assert task is not None
        return task

    def get_task(self, task_id: int) -> Optional[Task]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return self._row_to_task(row) if row else None

    def list_tasks(
        self, status: str = "pending", priority: Optional[str] = None
    ) -> list[Task]:
        status = self._validate_status(status)
        if priority is not None:
            priority = self._validate_priority(priority)

        query = "SELECT * FROM tasks WHERE 1=1"
        params: list[str] = []
        if status != "all":
            query += " AND status = ?"
            params.append(status)
        if priority is not None:
            query += " AND priority = ?"
            params.append(priority)
        query += " ORDER BY due_date IS NULL, due_date ASC, id ASC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_task(r) for r in rows]

    def complete_task(self, task_id: int) -> Optional[Task]:
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET status = 'done' WHERE id = ?", (task_id,)
            )
        return self.get_task(task_id)

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            title=row["title"],
            priority=row["priority"],
            status=row["status"],
            due_date=row["due_date"],
            created_at=row["created_at"],
        )
