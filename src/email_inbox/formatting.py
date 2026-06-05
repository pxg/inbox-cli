"""Markdown table and Gmail link formatting."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

_GMAIL_BASE = "https://mail.google.com/mail/?authuser="

INDEX_TABLE_WIDTH = 3
FROM_TABLE_MAX = 14
SUBJECT_TABLE_MAX = 53
ACCOUNT_TABLE_MAX = 18
DATE_TABLE_WIDTH = 17


@dataclass(frozen=True)
class InboxRow:
    mailbox: str
    label: str
    thread_id: str
    from_header: str
    subject: str
    date: str
    message_count: int = 1
    latest_message_id: str = ""
    snippet: str = ""

    @property
    def has_cached_latest_message(self) -> bool:
        """True when list/search already has enough data to skip gog thread get."""
        return self.message_count <= 1 and bool(self.latest_message_id)

    @property
    def from_display(self) -> str:
        return display_name(self.from_header)

    @property
    def from_for_table(self) -> str:
        return truncate_table_cell(self.from_display, FROM_TABLE_MAX)

    @property
    def subject_for_table(self) -> str:
        return truncate_table_cell(self.subject, SUBJECT_TABLE_MAX)

    @property
    def account_for_table(self) -> str:
        return truncate_table_cell(self.label, ACCOUNT_TABLE_MAX)

    @property
    def gmail_url(self) -> str:
        return gmail_thread_url(self.mailbox, self.thread_id)

    @property
    def subject_markdown(self) -> str:
        title = self.subject_for_table
        return f"[{title}]({self.gmail_url})"


def display_name(from_header: str) -> str:
    text = from_header.strip()
    if "<" in text:
        text = text.split("<", 1)[0].strip().strip('"')
    if not text:
        return from_header.strip()
    return text


def gmail_thread_url(mailbox: str, thread_id: str) -> str:
    authuser = quote(mailbox, safe="")
    return f"{_GMAIL_BASE}{authuser}#all/{thread_id}"


def sanitize_table_cell(text: str) -> str:
    return text.replace("|", "·").strip()


def truncate_table_cell(text: str, max_len: int) -> str:
    """Sanitize and cap cell text for fixed-width inbox tables."""
    text = sanitize_table_cell(text)
    if max_len <= 0:
        return ""
    if len(text) <= max_len:
        return text
    if max_len == 1:
        return "…"
    return text[: max_len - 1].rstrip() + "…"


def render_markdown_table(rows: list[InboxRow]) -> str:
    if not rows:
        return "Inbox clear."

    lines = [
        f"Inbox ({len(rows)} unread)",
        "",
        "| # | From | Subject | Account | Date |",
        "|---|------|---------|---------|------|",
    ]
    for i, row in enumerate(rows, start=1):
        lines.append(
            f"| {i} | {row.from_for_table} | {row.subject_markdown} | {row.account_for_table} | {row.date} |"
        )
    return "\n".join(lines)


def render_inbox(
    rows: list[InboxRow],
    *,
    output_format: str = "auto",
) -> None:
    """Print inbox table. auto = Rich on TTY, markdown otherwise."""
    import sys

    fmt = output_format
    if fmt == "auto":
        fmt = "rich" if sys.stdout.isatty() else "markdown"

    if fmt == "rich":
        from email_inbox.terminal import render_rich_inbox

        render_rich_inbox(rows)
    elif fmt == "markdown":
        print(render_markdown_table(rows))
    else:
        raise ValueError(f"unknown output format: {output_format!r}")
