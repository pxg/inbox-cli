from pathlib import Path

import pytest

from email_inbox.accounts import AccountsConfig, Mailbox, load_accounts, parse_accounts_md


FIXTURE = Path(__file__).parent / "fixtures" / "accounts.md"


def test_parse_accounts_fixture() -> None:
    config = load_accounts(FIXTURE)
    assert config == AccountsConfig(
        mailboxes=[
            Mailbox("alice@gmail.com", "alice@gmail"),
            Mailbox("alice@example.com", "example.com"),
        ],
        default_mailbox="alice@gmail.com",
        max_unread_per_mailbox=50,
    )


def test_parse_string_mailbox() -> None:
    text = """```yaml
mailboxes:
  - one@example.com
default_mailbox: one@example.com
```"""
    config = parse_accounts_md(text)
    assert config.mailboxes[0].address == "one@example.com"
    assert config.mailboxes[0].label == "example.com"


def test_default_max_unread_when_omitted() -> None:
    text = """```yaml
mailboxes:
  - one@example.com
default_mailbox: one@example.com
```"""
    config = parse_accounts_md(text)
    assert config.max_unread_per_mailbox == 50


def test_missing_yaml_fence() -> None:
    with pytest.raises(ValueError, match="no ```yaml"):
        parse_accounts_md("# no yaml here")
