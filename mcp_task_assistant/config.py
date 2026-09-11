"""
Centralized configuration loading for the MCP Task Assistant server.

Secret management approach (assignment requirement):
    All settings and secrets are loaded from a local ``.env`` file via the
    ``python-dotenv`` package - never hardcoded in source, and never assumed
    to already be present as OS-level/system environment variables. ``.env``
    is listed in .gitignore so real secrets are never committed.

Path handling:
    All filesystem paths use ``pathlib.Path`` (per assignment requirement -
    ``os.path`` is not used anywhere in this project).
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# The project root is the parent of this package directory.
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
ENV_PATH: Path = PROJECT_ROOT / ".env"

# Populates os.environ for this process from .env (if present). override=False
# means we never clobber a real env var, but .env is our single source of
# truth for this project's own settings.
load_dotenv(dotenv_path=ENV_PATH, override=False)


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Settings:
    """Typed, read-only view over the environment loaded from .env."""

    # --- Storage ---
    database_path: Path = PROJECT_ROOT / os.getenv("DATABASE_PATH", "tasks.db")

    # --- Email / SMTP authentication (optional - see email_tool.py) ---
    smtp_email_address: str | None = os.getenv("SMTP_EMAIL_ADDRESS") or None
    smtp_app_password: str | None = os.getenv("SMTP_APP_PASSWORD") or None
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = _get_int("SMTP_PORT", 587)

    # --- Best Practice #2: Rate limiting on the email tool ---
    email_rate_limit_max_calls: int = _get_int("EMAIL_RATE_LIMIT_MAX", 3)
    email_rate_limit_window_seconds: int = _get_int(
        "EMAIL_RATE_LIMIT_WINDOW_SECONDS", 60
    )

    @property
    def email_auth_configured(self) -> bool:
        """True if real SMTP credentials are present in .env."""
        return bool(self.smtp_email_address and self.smtp_app_password)


settings = Settings()
