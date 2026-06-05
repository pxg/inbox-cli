from email_inbox.formatting import (
    FROM_TABLE_MAX,
    SUBJECT_TABLE_MAX,
    InboxRow,
    display_name,
    gmail_thread_url,
    render_markdown_table,
    sanitize_table_cell,
    truncate_table_cell,
)


def test_display_name() -> None:
    assert display_name('Home Office <noreply@event.eventbrite.com>') == "Home Office"


def test_gmail_url_encodes_at() -> None:
    url = gmail_thread_url("alice@gmail.com", "abc123")
    assert "alice%40gmail.com" in url
    assert url.endswith("#all/abc123")


def test_sanitize_pipe() -> None:
    assert sanitize_table_cell("a|b") == "a·b"


def test_render_empty() -> None:
    assert render_markdown_table([]) == "Inbox clear."


def test_truncate_table_cell() -> None:
    assert truncate_table_cell("short", 10) == "short"
    assert truncate_table_cell("a" * 60, SUBJECT_TABLE_MAX) == ("a" * (SUBJECT_TABLE_MAX - 1) + "…")
    assert truncate_table_cell("pipe|here", 8) == "pipe·he…"


def test_inbox_row_table_cells_are_capped() -> None:
    row = InboxRow(
        mailbox="alice@example.com",
        label="example.com",
        thread_id="t1",
        from_header="Very Long Sender Name <a@b.com>",
        subject="S" * 80,
        date="2026-06-03",
    )
    assert len(row.from_for_table) <= FROM_TABLE_MAX
    assert len(row.subject_for_table) <= SUBJECT_TABLE_MAX
    assert row.subject_for_table.endswith("…")
