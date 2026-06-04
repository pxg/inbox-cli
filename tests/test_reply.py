from pathlib import Path

from email_inbox.gog import ThreadMessage
from email_inbox.reply import choose_reply_path, find_existing_reply, reply_subject


def test_reply_subject_adds_re() -> None:
    assert reply_subject("Hello") == "Re: Hello"
    assert reply_subject("Re: Hello") == "Re: Hello"


def test_reply_note_basename_unique_by_thread() -> None:
    from email_inbox.reply import reply_note_basename

    a = reply_note_basename(
        from_header="Bob Client <bob@client.example.com>",
        subject="Re: acme docs",
        thread_id="abc1111111111",
    )
    b = reply_note_basename(
        from_header="Bob Client <bob@client.example.com>",
        subject="Re: acme docs",
        thread_id="fff2222222222",
    )
    assert a != b
    assert "Bob Client" in a
    assert "acme docs" in a.lower()
    assert a.endswith("(11111111).md")


def test_choose_reply_path_increment(tmp_path: Path) -> None:
    from email_inbox.reply import reply_note_basename

    emails = tmp_path / "Projects" / "Acme" / "emails"
    emails.mkdir(parents=True)
    basename = reply_note_basename(
        from_header="Bob Client <bob@client.example.com>",
        subject="Hello",
        thread_id="tid1111111111",
    )
    (emails / basename).write_text("x")
    second = choose_reply_path(
        tmp_path,
        project="Acme",
        from_header="Bob Client <bob@client.example.com>",
        subject="Hello",
        thread_id="tid1111111111",
    )
    assert second.name == basename.replace(".md", " (2).md")


def test_find_existing_across_projects(tmp_path: Path) -> None:
    acme = tmp_path / "Projects" / "Acme" / "emails"
    acme.mkdir(parents=True)
    note = acme / "reply-note-04-06-2026.md"
    note.write_text(
        "---\n"
        "type: email-reply\n"
        "mailbox: alice@example.com\n"
        'thread_id: "tid1"\n'
        "---\n"
    )
    found = find_existing_reply(
        tmp_path,
        mailbox="alice@example.com",
        thread_id="tid1",
        project="OtherProject",
    )
    assert found == note


def test_find_existing_reply_by_thread(tmp_path: Path) -> None:
    emails = tmp_path / "Projects" / "Acme" / "emails"
    emails.mkdir(parents=True)
    (emails / "reply-note-04-06-2026.md").write_text(
        "---\n"
        "type: email-reply\n"
        "mailbox: alice@example.com\n"
        'thread_id: "tid1"\n'
        "---\n"
    )
    found = find_existing_reply(
        tmp_path,
        mailbox="alice@example.com",
        thread_id="tid1",
    )
    assert found == emails / "reply-note-04-06-2026.md"
    assert (
        find_existing_reply(
            tmp_path,
            mailbox="alice@example.com",
            thread_id="other",
        )
        is None
    )


def test_build_reply_has_frontmatter() -> None:
    from email_inbox.reply import build_reply_document

    msg = ThreadMessage(
        message_id="abc",
        from_header="Bob Client <bob@client.example.com>",
        to_header="Alice User <alice@example.com>",
        subject="acme notes",
        snippet="Hello there",
        date_header="Wed, 03 Jun 2026 10:12:24 +0100",
    )
    doc = build_reply_document(
        mailbox="alice@example.com",
        project="Acme",
        thread_id="thread1",
        message=msg,
    )
    assert "type: email-reply" in doc
    assert "project: Acme" in doc
    assert "to: \"bob@client.example.com\"" in doc


def test_build_reply_quotes_full_body_not_snippet() -> None:
    from email_inbox.reply import build_reply_document

    msg = ThreadMessage(
        message_id="abc",
        from_header="Survey Team <surveys@vendor.example.com>",
        to_header="alice@example.com",
        subject="Product feedback survey",
        snippet="Tell us about your experience with iPadOS. Take the survey Your",
        body=(
            "We love feedback. Tell us about your experience with iPadOS. "
            "Take the survey. Your responses will remain completely confidential."
        ),
        date_header="Wed, 3 Jun 2026 17:05:20 +0000 (GMT)",
    )
    doc = build_reply_document(
        mailbox="alice@example.com",
        project=None,
        thread_id="thread1",
        message=msg,
    )
    assert "> We love feedback." in doc
    assert "completely confidential." in doc
    assert "> Tell us about your experience with iPadOS. Take the survey Your" not in doc


def test_prepare_quoted_body_preserves_line_breaks() -> None:
    from email_inbox.reply import _prepare_quoted_body

    body = "Hi Alice,\n\nPlease find comments below.\n\nBest,\nCarol"
    assert _prepare_quoted_body(body) == body


def test_prepare_quoted_body_strips_outlook_quoted_thread() -> None:
    from email_inbox.reply import _prepare_quoted_body

    body = (
        "Hi Alice and team,\n\n"
        "Please find some minor comments below.\n\n"
        "Best,\n\n"
        "Carol Contact\n\n"
        "________________________________\n"
        "From: Alice User <alice@example.com>\n"
        "Sent: Monday, June 1, 2026 3:35 PM\n"
        "Subject: Re: Quarterly Report\n"
        "Hello,\n"
    )
    cleaned = _prepare_quoted_body(body)
    assert "minor comments" in cleaned
    assert "Carol Contact" in cleaned
    assert "From: Alice User" not in cleaned
    assert "\n\n" in cleaned


def test_prepare_quoted_body_strips_gmail_on_wrote() -> None:
    from email_inbox.reply import _prepare_quoted_body

    body = (
        "Thanks for the update.\n\n"
        "Best,\nAlice\n\n"
        "On Fri, 29 May 2026 at 11:10, Carol Contact <carol@example.com> wrote:\n"
        "> earlier message\n"
    )
    cleaned = _prepare_quoted_body(body)
    assert cleaned == "Thanks for the update.\n\nBest,\nAlice"


def test_build_reply_quotes_multiline_body() -> None:
    from email_inbox.reply import build_reply_document

    msg = ThreadMessage(
        message_id="abc",
        from_header="Carol Contact <carol@client.example.com>",
        to_header="alice@example.com",
        subject="Re: Report",
        snippet="Hi Alice",
        body="Hi Alice,\n\nComments below.\n\nBest,\nCarol",
        date_header="Wed, 4 Jun 2026 10:00:00 +0000",
    )
    doc = build_reply_document(
        mailbox="alice@example.com",
        project=None,
        thread_id="thread1",
        message=msg,
    )
    assert "> Hi Alice,\n> \n> Comments below." in doc


def test_build_reply_uses_hr_before_original() -> None:
    from email_inbox.reply import build_reply_document

    msg = ThreadMessage(
        message_id="abc",
        from_header="Bob Client <bob@client.example.com>",
        to_header="Alice User <alice@example.com>",
        subject="acme notes",
        snippet="Hello there",
        date_header="Wed, 03 Jun 2026 10:12:24 +0100",
    )
    doc = build_reply_document(
        mailbox="alice@example.com",
        project=None,
        thread_id="thread1",
        message=msg,
    )
    assert "## Original" not in doc
    assert "\n---\n\nFrom Bob Client (bob@client.example.com)," in doc
