"""Mark Gmail thread read via gog (session row)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from email_inbox.formatting import InboxRow
from email_inbox.gog import GogError, latest_message_for_inbox_row
from email_inbox.paths import session_path
from email_inbox.session import SessionRow, get_session_row, load_session


def gog_mark_read_message(mailbox: str, message_id: str) -> None:
    if not message_id:
        raise RuntimeError("missing message id for mark-read")
    result = subprocess.run(
        [
            "gog",
            "gmail",
            "mark-read",
            message_id,
            "-a",
            mailbox,
            "-y",
            "--no-input",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"mark-read failed: {err}")


def mark_read_inbox_row(row: InboxRow) -> str:
    """Mark thread read using inbox row identity (not session row number)."""
    try:
        message = latest_message_for_inbox_row(row)
    except (GogError, ValueError) as exc:
        raise RuntimeError(f"thread fetch failed for {row.mailbox}: {exc}") from exc
    if not message.message_id:
        raise RuntimeError("thread has no message id for mark-read")
    gog_mark_read_message(row.mailbox, message.message_id)
    return f"✓ Marked read — {row.subject_for_table}"


def mark_read_row(vault_root: Path, row_number: int) -> str:
    """Mark latest message in session row as read. Returns one-line status."""
    session = load_session(session_path(vault_root))
    session_row = get_session_row(session, row_number)
    return mark_read_inbox_row(_session_row_to_inbox(session_row))


def _session_row_to_inbox(row: SessionRow) -> InboxRow:
    return InboxRow(
        mailbox=row.mailbox,
        label=row.label,
        thread_id=row.thread_id,
        from_header=row.from_header,
        subject=row.subject,
        date=row.date,
        message_count=row.message_count,
        latest_message_id=row.latest_message_id,
        snippet=row.snippet,
    )
