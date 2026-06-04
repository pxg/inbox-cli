from unittest.mock import patch

from email_inbox.accounts import AccountsConfig, Mailbox
from email_inbox.list_inbox import fetch_combined_inbox


def _config() -> AccountsConfig:
    return AccountsConfig(
        mailboxes=[
            Mailbox("a@gmail.com", "a@gmail"),
            Mailbox("b@co.uk", "co.uk"),
        ],
        default_mailbox="a@gmail.com",
        max_unread_per_mailbox=10,
    )


@patch("email_inbox.list_inbox.gmail_search_unread")
@patch("email_inbox.list_inbox.authorized_gmail_accounts")
def test_parallel_merge_and_sort(auth_mock, search_mock) -> None:
    auth_mock.return_value = {"a@gmail.com", "b@co.uk"}

    def search_side_effect(mailbox: str, **kwargs):
        if mailbox == "a@gmail.com":
            return [
                {
                    "id": "t1",
                    "from": "Alice <a@x.com>",
                    "subject": "Older",
                    "date": "2026-06-03 10:00",
                    "messageCount": 1,
                }
            ]
        return [
            {
                "id": "t2",
                "from": "Bob <b@y.com>",
                "subject": "Newer",
                "date": "2026-06-04 09:00",
                "messageCount": 2,
            }
        ]

    search_mock.side_effect = search_side_effect
    result = fetch_combined_inbox(_config())
    assert len(result.rows) == 2
    assert result.rows[0].subject == "Newer"
    assert result.rows[0].message_count == 2
    assert result.rows[0].latest_message_id == ""
    assert result.rows[1].subject == "Older"
    assert result.rows[1].latest_message_id == "t1"


@patch("email_inbox.list_inbox.authorized_gmail_accounts")
def test_skip_unauthorized(auth_mock) -> None:
    auth_mock.return_value = {"a@gmail.com"}
    with patch("email_inbox.list_inbox.gmail_search_unread", return_value=[]):
        result = fetch_combined_inbox(_config())
    assert len(result.auth_warnings) == 1
    assert "b@co.uk" in result.auth_warnings[0]
