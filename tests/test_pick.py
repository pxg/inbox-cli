import json
from pathlib import Path
from unittest.mock import patch

from email_inbox.formatting import InboxRow
from email_inbox.pick import pick_and_write, pick_inbox_row


def test_pick_writes_file(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    gmail = vault / "Projects" / "Cursor Gmail"
    gmail.mkdir(parents=True)
    (vault / "Projects" / "Acme" / "emails").mkdir(parents=True)

    session = {
        "rows": [
            {
                "n": 1,
                "mailbox": "alice@example.com",
                "thread_id": "tid1",
                "from_header": "Bob Client <bob@client.example.com>",
                "subject": "acme - docs",
                "date": "2026-06-03 10:12",
                "label": "example.com",
            }
        ]
    }
    (gmail / ".inbox-session.json").write_text(json.dumps(session))

    thread_json = {
        "thread": {
            "id": "tid1",
            "messages": [
                {
                    "id": "mid1",
                    "snippet": "Some feedback",
                    "body": "Some feedback with full detail.",
                    "headers": {
                        "from": "Bob Client <bob@client.example.com>",
                        "to": "Alice User <alice@example.com>",
                        "subject": "acme - docs",
                    },
                }
            ],
        }
    }

    with patch("email_inbox.gog.gmail_thread_get", return_value=thread_json) as thread_get:
        path = pick_and_write(vault, 1)

    thread_get.assert_called_once_with("alice@example.com", "tid1", full=True)
    assert path.exists()
    text = path.read_text()
    assert "type: email-reply" in text
    assert "> Some feedback with full detail." in text
    assert path.parent.name == "emails"
    assert "Acme" in str(path)


def test_pick_reuses_existing_reply(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    acme_emails = vault / "Projects" / "Acme" / "emails"
    acme_emails.mkdir(parents=True)
    (vault / "Projects" / "Cursor Gmail").mkdir(parents=True)

    existing = acme_emails / "reply-note-03-06-2026.md"
    existing.write_text(
        "---\n"
        "type: email-reply\n"
        "status: editing\n"
        "mailbox: alice@example.com\n"
        "send_from: alice@example.com\n"
        "project: Acme\n"
        'thread_id: "tid1"\n'
        'reply_to_message_id: "mid1"\n'
        "---\n"
        "\nDraft body\n"
    )

    session = {
        "rows": [
            {
                "n": 1,
                "mailbox": "alice@example.com",
                "thread_id": "tid1",
                "from_header": "Bob Client <bob@client.example.com>",
                "subject": "acme - docs",
                "date": "2026-06-03 10:12",
                "label": "example.com",
            }
        ]
    }
    (vault / "Projects" / "Cursor Gmail" / ".inbox-session.json").write_text(
        json.dumps(session)
    )

    thread_json = {
        "thread": {
            "id": "tid1",
            "messages": [
                {
                    "id": "mid1",
                    "snippet": "Some feedback",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Bob Client <bob@client.example.com>"},
                            {"name": "Subject", "value": "acme - docs"},
                        ]
                    },
                }
            ],
        }
    }

    with patch("email_inbox.gog.gmail_thread_get") as thread_get:
        path = pick_and_write(vault, 1)

    thread_get.assert_not_called()
    assert path == existing.resolve()
    assert path.read_text() == existing.read_text()


def test_pick_reuses_reply_in_other_project_folder(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    acme_emails = vault / "Projects" / "Acme" / "emails"
    acme_emails.mkdir(parents=True)
    (vault / "Projects" / "Cursor Gmail").mkdir(parents=True)

    existing = acme_emails / "Steve — Demo (tid1abcd).md"
    existing.write_text(
        "---\n"
        "type: email-reply\n"
        "mailbox: alice@example.com\n"
        'thread_id: "tid1"\n'
        "---\n"
        "\nDraft\n"
    )

    row = InboxRow(
        mailbox="alice@example.com",
        label="co.uk",
        thread_id="tid1",
        from_header="Steve <s@x.com>",
        subject="Demo",
        date="2026-06-03 10:12",
        message_count=1,
        latest_message_id="tid1",
    )

    with patch("email_inbox.gog.gmail_thread_get") as thread_get:
        path = pick_inbox_row(vault, row, project="Other")

    thread_get.assert_not_called()
    assert path == existing.resolve()
