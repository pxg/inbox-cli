"""Pick session row and write vault reply file."""

from __future__ import annotations

import sys
from pathlib import Path

from email_inbox.formatting import InboxRow, display_name
from email_inbox.gog import GogError, latest_message_for_reply
from email_inbox.paths import session_path
from email_inbox.reply import (
    build_reply_document,
    choose_reply_path,
    find_existing_reply,
    write_reply_file,
)
from email_inbox.routing import list_project_options, resolve_project
from email_inbox.session import SessionRow, get_session_row, load_session


def pick_and_write(
    vault_root: Path,
    row_number: int,
    *,
    project: str | None = None,
) -> Path:
    session = load_session(session_path(vault_root))
    row = get_session_row(session, row_number)
    return pick_inbox_row(vault_root, _session_row_to_inbox(row), project=project)


def pick_inbox_row(
    vault_root: Path,
    row: InboxRow,
    *,
    project: str | None = None,
) -> Path:
    """Create or reopen reply for this inbox row (by mailbox + thread_id)."""
    session_row = SessionRow(
        n=0,
        mailbox=row.mailbox,
        thread_id=row.thread_id,
        from_header=row.from_header,
        subject=row.subject,
        date=row.date,
        label=row.label,
    )

    resolved, ambiguous = resolve_project(
        vault_root,
        from_header=row.from_header,
        subject=row.subject,
        explicit=project,
    )

    if ambiguous:
        _print_project_choices(ambiguous, vault_root)
        raise AmbiguousProjectError(ambiguous)

    existing = find_existing_reply(
        vault_root,
        mailbox=row.mailbox,
        thread_id=row.thread_id,
        project=resolved,
    )
    if existing is not None:
        try:
            rel = existing.relative_to(vault_root)
        except ValueError:
            rel = existing
        print(f"↩ Existing reply: {rel}", file=sys.stderr)
        return existing.resolve()

    try:
        message = latest_message_for_reply(row)
    except (GogError, ValueError) as exc:
        raise RuntimeError(f"thread fetch failed for {row.mailbox}: {exc}") from exc
    out_path = choose_reply_path(
        vault_root,
        project=resolved,
        from_header=message.from_header or row.from_header,
        subject=message.subject or row.subject,
        thread_id=row.thread_id,
    )
    doc = build_reply_document(
        mailbox=row.mailbox,
        project=resolved,
        thread_id=row.thread_id,
        message=message,
        session_row=session_row,
    )
    return write_reply_file(out_path, doc)


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


class AmbiguousProjectError(Exception):
    def __init__(self, candidates: list[str]) -> None:
        self.candidates = candidates
        super().__init__(f"ambiguous project: {', '.join(candidates)}")


def _print_project_choices(candidates: list[str], vault_root: Path) -> None:
    options = list_project_options(vault_root)
    print("Ambiguous project — pass --project NAME:", file=sys.stderr)
    for oid, label in options:
        if oid == "0":
            print(f"  {oid}  {label}", file=sys.stderr)
            continue
        if oid in candidates:
            print(f"  {oid}  {label}", file=sys.stderr)
    for name in candidates:
        if name not in {o[0] for o in options}:
            print(f"      --project {name}", file=sys.stderr)


def format_success(vault_root: Path, path: Path) -> str:
    try:
        rel = path.relative_to(vault_root)
    except ValueError:
        rel = path
    return f"✓ {rel}"
