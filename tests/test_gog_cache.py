from pathlib import Path
from unittest.mock import patch

from email_inbox.formatting import InboxRow
from email_inbox.gog import (
    inbox_row_message_fields_from_search,
    latest_message_for_inbox_row,
    parse_latest_message,
    thread_message_from_inbox_row,
)
from email_inbox.pick import pick_inbox_row


def test_search_cache_single_message() -> None:
    mc, mid, snippet = inbox_row_message_fields_from_search(
        {
            "id": "tid1",
            "messageCount": 1,
            "from": "A <a@x.com>",
            "subject": "Hi",
            "snippet": "Hello &amp; world",
        }
    )
    assert mc == 1
    assert mid == "tid1"
    assert snippet == "Hello & world"


def test_search_cache_multi_message_skips_id() -> None:
    mc, mid, _ = inbox_row_message_fields_from_search(
        {"id": "tid1", "messageCount": 3},
    )
    assert mc == 3
    assert mid == ""


def test_parse_latest_message_reads_plain_text_payload() -> None:
    import base64

    plain = "Hi Alice,\n\nFull plain text body."
    encoded = base64.urlsafe_b64encode(plain.encode()).decode().rstrip("=")
    thread_json = {
        "thread": {
            "messages": [
                {
                    "id": "mid1",
                    "snippet": "Short",
                    "payload": {
                        "mimeType": "text/plain",
                        "body": {"data": encoded},
                        "headers": [
                            {"name": "From", "value": "A <a@x.com>"},
                            {"name": "Subject", "value": "Hi"},
                        ],
                    },
                }
            ]
        }
    }
    msg = parse_latest_message(thread_json)
    assert msg.body == plain
    assert "\n\n" in msg.body


def test_parse_latest_message_reads_sanitized_body() -> None:
    thread_json = {
        "thread": {
            "messages": [
                {
                    "id": "mid1",
                    "snippet": "Short",
                    "body": "Full plain text body.",
                    "headers": {
                        "from": "A <a@x.com>",
                        "to": "B <b@x.com>",
                        "subject": "Hi",
                        "date": "Wed, 3 Jun 2026 10:00:00 +0000",
                    },
                }
            ]
        }
    }
    msg = parse_latest_message(thread_json)
    assert msg.body == "Full plain text body."
    assert msg.from_header == "A <a@x.com>"


def test_latest_message_uses_cache_without_thread_get() -> None:
    row = InboxRow(
        mailbox="a@gmail.com",
        label="a",
        thread_id="tid1",
        from_header="A <a@x.com>",
        subject="Hi",
        date="2026-06-04 10:00",
        message_count=1,
        latest_message_id="tid1",
        snippet="Body",
    )
    with patch("email_inbox.gog.gmail_thread_get") as thread_get:
        msg = latest_message_for_inbox_row(row)
    thread_get.assert_not_called()
    assert msg.message_id == "tid1"
    assert msg.snippet == "Body"


def test_pick_new_reply_fetches_full_body(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "Projects" / "Acme" / "emails").mkdir(parents=True)
    (vault / "Projects" / "Cursor Gmail").mkdir(parents=True)

    row = InboxRow(
        mailbox="alice@example.com",
        label="co.uk",
        thread_id="tid1",
        from_header="Bob Client <bob@client.example.com>",
        subject="acme - docs",
        date="2026-06-03 10:12",
        message_count=1,
        latest_message_id="tid1",
        snippet="Some feedback",
    )
    thread_json = {
        "thread": {
            "messages": [
                {
                    "id": "tid1",
                    "snippet": "Some feedback",
                    "body": "Full message body for the reply note.",
                    "headers": {
                        "from": "Bob Client <bob@client.example.com>",
                        "subject": "acme - docs",
                    },
                }
            ]
        }
    }

    with patch("email_inbox.gog.gmail_thread_get", return_value=thread_json) as thread_get:
        path = pick_inbox_row(vault, row)

    thread_get.assert_called_once_with("alice@example.com", "tid1", full=True)
    assert path.exists()
    text = path.read_text()
    assert 'reply_to_message_id: "tid1"' in text
    assert "> Full message body for the reply note." in text
