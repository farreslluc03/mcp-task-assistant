"""
Email sending, with optional real SMTP authentication.

Authentication handling (assignment requirement):
    Credentials come only from ``Settings`` (config.py), which loads them
    from a local ``.env`` file. They are never hardcoded and never included
    in any exception message returned to the MCP client - see the
    "Error Disclosure" note below.

Dry-run fallback:
    If SMTP_EMAIL_ADDRESS / SMTP_APP_PASSWORD are not set, this tool writes
    the email to a local ``.eml`` file under ``drafts/`` instead of sending
    it, so the whole tool - and the demo - works without requiring a real
    mailbox to be configured first.
"""
from __future__ import annotations

import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage

from .config import settings, PROJECT_ROOT

DRAFTS_DIR = PROJECT_ROOT / "drafts"


class EmailSendError(Exception):
    """Raised when an email could not be sent.

    Error Disclosure note: messages here are deliberately generic. They
    never include the SMTP password, the raw SMTP server response, or a
    stack trace - only enough information for the user to fix their .env.
    """


def _build_message(to_email: str, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_email_address or "task-assistant@localhost"
    msg["To"] = to_email
    msg.set_content(body)
    return msg


def send_or_draft_email(to_email: str, subject: str, body: str) -> dict:
    """Send a real email if SMTP credentials are configured in .env;
    otherwise save a local .eml draft. Returns a dict describing what
    happened, suitable for returning straight from an MCP tool."""
    msg = _build_message(to_email, subject, body)

    if not settings.email_auth_configured:
        DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        draft_path = DRAFTS_DIR / f"draft_{timestamp}.eml"
        draft_path.write_bytes(bytes(msg))
        return {
            "mode": "dry_run",
            "message": (
                "No SMTP credentials found in .env, so this email was saved "
                "as a local draft instead of being sent."
            ),
            "draft_path": str(draft_path),
        }

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls(context=context)
            server.login(settings.smtp_email_address, settings.smtp_app_password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise EmailSendError(
            "Email authentication failed. Check SMTP_EMAIL_ADDRESS and "
            "SMTP_APP_PASSWORD in your .env file."
        ) from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailSendError(
            "Could not send the email due to a mail server or network error."
        ) from exc

    return {"mode": "sent", "message": f"Email sent to {to_email}."}
