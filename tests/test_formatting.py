from email_inbox.formatting import (
    display_name,
    gmail_thread_url,
    render_markdown_table,
    sanitize_table_cell,
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
