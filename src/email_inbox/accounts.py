"""Parse mailbox config from the vault accounts.md YAML block."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_YAML_FENCE = re.compile(r"```yaml\s*\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class Mailbox:
    address: str
    label: str


@dataclass(frozen=True)
class AccountsConfig:
    mailboxes: list[Mailbox]
    default_mailbox: str
    max_unread_per_mailbox: int


def parse_accounts_md(text: str) -> AccountsConfig:
    match = _YAML_FENCE.search(text)
    if not match:
        raise ValueError("accounts.md: no ```yaml fenced block found")

    raw = yaml.safe_load(match.group(1))
    if not isinstance(raw, dict):
        raise ValueError("accounts.md: YAML root must be a mapping")

    mailboxes_raw = raw.get("mailboxes") or []
    mailboxes: list[Mailbox] = []
    for item in mailboxes_raw:
        if isinstance(item, str):
            mailboxes.append(Mailbox(address=item, label=_default_label(item)))
        elif isinstance(item, dict):
            address = item.get("address")
            if not address:
                raise ValueError("mailbox entry missing address")
            label = item.get("label") or _default_label(address)
            mailboxes.append(Mailbox(address=str(address), label=str(label)))
        else:
            raise ValueError(f"invalid mailbox entry: {item!r}")

    if not mailboxes:
        raise ValueError("accounts.md: mailboxes list is empty")

    return AccountsConfig(
        mailboxes=mailboxes,
        default_mailbox=str(raw.get("default_mailbox") or mailboxes[0].address),
        max_unread_per_mailbox=int(raw.get("max_unread_per_mailbox") or 10),
    )


def load_accounts(path: Path) -> AccountsConfig:
    return parse_accounts_md(path.read_text(encoding="utf-8"))


def _default_label(address: str) -> str:
    if "@" not in address:
        return address
    local, domain = address.rsplit("@", 1)
    if domain == "gmail.com":
        return f"{local}@gmail"
    return domain
