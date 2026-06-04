from email_inbox.theme import hint_commands_text, title_bar


def test_title_bar() -> None:
    assert title_bar(3) == "INBOX // 3 UNREAD"
    assert title_bar(0) == "INBOX // ZERO"


def test_hint_text_keys() -> None:
    text = hint_commands_text(("enter", "reply"), ("q", "quit"))
    assert "[enter]" in text.plain
    assert "reply" in text.plain
