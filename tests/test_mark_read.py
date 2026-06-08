from pathlib import Path
from unittest.mock import patch

import pytest

from email_inbox.formatting import InboxRow
from email_inbox.mark_read import mark_read_inbox_row, mark_read_row


def test_mark_read_row(tmp_path: Path) -> None:
    session_dir = tmp_path / "Projects" / "Inbox-CLI"
    session_dir.mkdir(parents=True)
    (session_dir / ".inbox-session.json").write_text(
        """{
  "rows": [{
    "n": 1,
    "mailbox": "alice@example.com",
    "thread_id": "tid1",
    "from": "Bob Client",
    "subject": "Hi",
    "date": "2026-06-04"
  }]
}"""
    )
    thread = {
        "thread": {
            "messages": [
                {
                    "id": "msg123",
                    "snippet": "Hi",
                    "payload": {"headers": [{"name": "From", "value": "p@x.com"}]},
                }
            ]
        }
    }
    with (
        patch("email_inbox.gog.gmail_thread_get", return_value=thread),
        patch("email_inbox.mark_read.gog_mark_read_message") as mark,
    ):
        msg = mark_read_row(tmp_path, 1)
    mark.assert_called_once_with("alice@example.com", "msg123")
    assert "Marked read" in msg


def test_mark_read_inbox_row_uses_cache() -> None:
    row = InboxRow(
        mailbox="alice@example.com",
        label="co.uk",
        thread_id="tid1",
        from_header="Bob Client <bob@client.example.com>",
        subject="Hi",
        date="2026-06-03 10:12",
        message_count=1,
        latest_message_id="mid1",
    )
    with patch("email_inbox.gog.gmail_thread_get") as thread_get:
        with patch("email_inbox.mark_read.gog_mark_read_message") as mark:
            mark_read_inbox_row(row)
    thread_get.assert_not_called()
    mark.assert_called_once_with("alice@example.com", "mid1")


def test_mark_read_inbox_row() -> None:
    row = InboxRow(
        mailbox="alice@example.com",
        label="example.com",
        thread_id="tid1",
        from_header="Bob Client",
        subject="Hi",
        date="2026-06-04",
    )
    thread = {
        "thread": {
            "messages": [
                {
                    "id": "msg999",
                    "snippet": "Hi",
                    "payload": {"headers": []},
                }
            ]
        }
    }
    with (
        patch("email_inbox.gog.gmail_thread_get", return_value=thread),
        patch("email_inbox.mark_read.gog_mark_read_message") as mark,
    ):
        msg = mark_read_inbox_row(row)
    mark.assert_called_once_with("alice@example.com", "msg999")
    assert "Hi" in msg
