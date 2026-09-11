"""
MCP Task Assistant Server
==========================

A local Model Context Protocol (MCP) server for personal task tracking,
built for ENMGT 5405 - Applied AI, Assignment 4.

Domain: Personal Productivity (task tracking + email summaries)

Exposes, over stdio:
    Tools:
        - add_task
        - list_tasks
        - complete_task
        - send_task_summary_email
    Prompt:
        - weekly_summary_prompt

Run directly for a quick manual smoke test (see tests/smoke_test.py for an
automated version):
    python -m mcp_task_assistant.server

Claude Desktop launches this same command for you as a subprocess - see
README.md for the exact configuration.

Citation:
    The overall server shape here - creating a ``FastMCP`` instance, using
    the ``@mcp.tool()`` / ``@mcp.prompt()`` decorators, and calling
    ``mcp.run()`` in ``if __name__ == "__main__"`` - follows the Quickstart
    example in the official MCP Python SDK README:
    https://github.com/modelcontextprotocol/python-sdk
    All tool/prompt bodies, storage, security, and email logic below are
    original code written for this assignment.
"""
from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from .config import settings
from .email_tool import EmailSendError, send_or_draft_email
from .security import RateLimitExceededError, SlidingWindowRateLimiter
from .storage import TaskStore, ValidationError

mcp = FastMCP("task-assistant")

_store = TaskStore(settings.database_path)
_email_rate_limiter = SlidingWindowRateLimiter(
    max_calls=settings.email_rate_limit_max_calls,
    window_seconds=settings.email_rate_limit_window_seconds,
)


@mcp.tool()
def add_task(title: str, priority: str = "medium", due_date: str = "") -> dict:
    """Create a new task.

    Args:
        title: What the task is (required, max 200 characters).
        priority: One of "low", "medium", "high". Defaults to "medium".
        due_date: Optional due date as free-form text (e.g. "2026-09-20").
    """
    try:
        task = _store.add_task(title=title, priority=priority, due_date=due_date)
    except ValidationError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "task": task.to_dict()}


@mcp.tool()
def list_tasks(status: str = "pending", priority: Optional[str] = None) -> dict:
    """List tasks, optionally filtered by status and/or priority.

    Args:
        status: One of "pending", "done", or "all". Defaults to "pending".
        priority: Optional filter - one of "low", "medium", "high".
    """
    try:
        tasks = _store.list_tasks(status=status, priority=priority)
    except ValidationError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "count": len(tasks), "tasks": [t.to_dict() for t in tasks]}


@mcp.tool()
def complete_task(task_id: int) -> dict:
    """Mark a task as done, given its numeric id (see list_tasks for ids)."""
    task = _store.complete_task(task_id)
    if task is None:
        return {"ok": False, "error": f"No task found with id {task_id}."}
    return {"ok": True, "task": task.to_dict()}


@mcp.tool()
def send_task_summary_email(recipient_email: str, subject: str, body: str) -> dict:
    """Send (or draft, if no SMTP credentials are configured) an email -
    typically a task summary - to the given recipient.

    This tool is rate-limited (see security.py) to protect against runaway
    or abusive use.

    Args:
        recipient_email: Destination email address.
        subject: Email subject line.
        body: Plain-text email body.
    """
    try:
        _email_rate_limiter.check()
    except RateLimitExceededError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        result = send_or_draft_email(recipient_email, subject, body)
    except EmailSendError as exc:
        return {"ok": False, "error": str(exc)}

    return {"ok": True, **result}


@mcp.prompt()
def weekly_summary_prompt(recipient_name: str = "yourself") -> str:
    """Prompt template: draft and send a weekly task summary email.

    This is the MCP *prompt* required by the assignment - a reusable
    instruction template that tells the calling LLM how to combine the
    tools above into a small workflow, rather than doing the work itself.
    """
    return (
        f"You are preparing a weekly task summary email for {recipient_name}. "
        "1) Call the list_tasks tool with status='pending' to see what is "
        "outstanding, and again with status='done' to see what was "
        "completed. "
        "2) Write a short, friendly email summarizing both lists. "
        "3) Call send_task_summary_email with that subject and body to "
        "deliver it. "
        "4) If send_task_summary_email reports mode='dry_run', tell the "
        "user their draft was saved locally instead of sent, and why "
        "(no SMTP credentials configured in .env)."
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
