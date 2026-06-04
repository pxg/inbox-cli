from email_inbox.formatting import InboxRow
from email_inbox.terminal import _dashed_underline_ansi, render_rich_inbox_as_text


def _row() -> InboxRow:
    return InboxRow(
        mailbox="alice@example.com",
        label="example.com",
        thread_id="abc123",
        from_header="Bob Client <bob@client.example.com>",
        subject="acme - documentation feedback",
        date="2026-06-03 10:12",
    )


def test_rich_table_contains_columns() -> None:
    text = render_rich_inbox_as_text([_row()], width=100)
    assert "Inbox (1 unread)" in text
    assert "From" in text
    assert "Subject" in text
    assert "example.com" in text
    assert "acme" in text


def test_rich_table_has_grid_lines() -> None:
    text = render_rich_inbox_as_text([_row(), _row()], width=100)
    assert "┌" in text
    assert "┼" in text
    assert "│" in text


def test_dashed_underline_ansi_sequence() -> None:
    from email_inbox.theme import SUBJECT_UNDERLINE

    start, _end = _dashed_underline_ansi(SUBJECT_UNDERLINE)
    assert "4:5" in start
    assert "58;2::103:232:249" in start


def test_rich_table_subject_preserves_emoji() -> None:
    row = InboxRow(
        mailbox="alice@example.com",
        label="example.com",
        thread_id="abc123",
        from_header="Bob Client <bob@client.example.com>",
        subject="Verify 📧 account",
        date="2026-06-03 10:12",
    )
    text = render_rich_inbox_as_text([row], width=100)
    assert "📧" in text
    assert "Verify" in text
