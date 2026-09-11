"""
A dependency-free smoke test that exercises every tool's underlying logic
directly (without needing an actual MCP client / Claude Desktop). Useful to
quickly confirm "the server doesn't crash and the tools work" while
developing.

Run with:
    python tests/smoke_test.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_task_assistant.security import SlidingWindowRateLimiter  # noqa: E402
from mcp_task_assistant.storage import TaskStore, ValidationError  # noqa: E402


def check(label: str, condition: bool) -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    return condition


def main() -> bool:
    results = []

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "smoke_test.db"
        store = TaskStore(db_path)

        # add_task
        task = store.add_task(title="Write README", priority="high", due_date="2026-09-20")
        results.append(check("add_task creates a task with an id", task.id is not None))
        results.append(check("add_task stores the title correctly", task.title == "Write README"))

        # validation
        try:
            store.add_task(title="   ")
            results.append(check("add_task rejects empty title", False))
        except ValidationError:
            results.append(check("add_task rejects empty title", True))

        try:
            store.add_task(title="Bad priority", priority="urgent!!")
            results.append(check("add_task rejects invalid priority", False))
        except ValidationError:
            results.append(check("add_task rejects invalid priority", True))

        # list_tasks
        store.add_task(title="Second task", priority="low")
        pending = store.list_tasks(status="pending")
        results.append(check("list_tasks returns pending tasks", len(pending) == 2))

        # complete_task
        done = store.complete_task(task.id)
        results.append(check("complete_task marks a task done", done is not None and done.status == "done"))

        pending_after = store.list_tasks(status="pending")
        results.append(
            check("completed task no longer appears in pending list", len(pending_after) == 1)
        )

    # Rate limiter
    limiter = SlidingWindowRateLimiter(max_calls=2, window_seconds=60)
    limiter.check()
    limiter.check()
    blocked = False
    try:
        limiter.check()
    except Exception:
        blocked = True
    results.append(check("rate limiter blocks the 3rd call within the window", blocked))

    print()
    passed = all(results)
    print(f"{sum(results)}/{len(results)} checks passed.")
    print("RESULT:", "ALL PASSED" if passed else "SOME FAILED")
    return passed


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
