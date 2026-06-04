from pathlib import Path
from unittest.mock import patch

import pytest

from email_inbox.send import AlreadySentError, is_reply_sent, load_reply, push_draft, push_send


def _reply_file(tmp_path: Path) -> Path:
    path = tmp_path / "reply.md"
    path.write_text(
        """---
type: email-reply
status: editing
mailbox: alice@example.com
send_from: alice@example.com
to: friend@example.com
subject: "Re: Hello"
reply_to_message_id: "abc123"
---
Hi Friend,

Thanks for your note.

---

From Friend (friend@example.com), 3 Jun 2026:

> old text
"""
    )
    return path


def test_load_reply_strips_original(tmp_path: Path) -> None:
    meta, body = load_reply(_reply_file(tmp_path))
    assert meta.to == "friend@example.com"
    assert "Thanks" in body
    assert "old text" not in body
    assert "From Friend" not in body


def test_load_reply_strips_legacy_original_heading(tmp_path: Path) -> None:
    path = tmp_path / "legacy-reply.md"
    path.write_text(
        """---
type: email-reply
status: editing
mailbox: alice@example.com
send_from: alice@example.com
to: friend@example.com
subject: "Re: Hello"
reply_to_message_id: "abc123"
---
Hi Friend,

## Original

> old text
"""
    )
    _, body = load_reply(path)
    assert body == "Hi Friend,"


def test_push_draft(tmp_path: Path) -> None:
    path = _reply_file(tmp_path)
    with (
        patch("email_inbox.send._gog_drafts_create", return_value="draft99"),
        patch("email_inbox.send._mark_read"),
    ):
        msg = push_draft(path)
    assert "Gmail draft" in msg
    text = path.read_text()
    assert "gmail_draft" in text


def test_push_draft_does_not_set_sent_at(tmp_path: Path) -> None:
    path = _reply_file(tmp_path)
    with (
        patch("email_inbox.send._gog_drafts_create", return_value="draft99"),
        patch("email_inbox.send._mark_read"),
    ):
        push_draft(path)
    text = path.read_text()
    front = text.split("---")[1]
    assert "sent_at: 2026" not in front


def test_is_reply_sent(tmp_path: Path) -> None:
    path = _reply_file(tmp_path)
    assert not is_reply_sent(path)
    path.write_text(path.read_text().replace("status: editing", "status: sent"))
    assert is_reply_sent(path)


def test_push_send_rejects_when_already_sent(tmp_path: Path) -> None:
    path = _reply_file(tmp_path)
    path.write_text(path.read_text().replace("status: editing", "status: sent"))
    with patch("email_inbox.send._gog_send") as mock_send:
        with pytest.raises(AlreadySentError):
            push_send(path)
    mock_send.assert_not_called()


def test_push_send_force_when_already_sent(tmp_path: Path) -> None:
    path = _reply_file(tmp_path)
    path.write_text(path.read_text().replace("status: editing", "status: sent"))
    with (
        patch("email_inbox.send._gog_send"),
        patch("email_inbox.send._mark_read"),
    ):
        msg = push_send(path, force=True)
    assert "Sent" in msg


def test_push_draft_rejects_when_already_sent(tmp_path: Path) -> None:
    path = _reply_file(tmp_path)
    path.write_text(path.read_text().replace("status: editing", "status: sent"))
    with patch("email_inbox.send._gog_drafts_create") as mock_draft:
        with pytest.raises(AlreadySentError):
            push_draft(path)
    mock_draft.assert_not_called()
