"""Vault path resolution."""

from __future__ import annotations

import os
from pathlib import Path

from email_inbox.config import load_config_vault_root

ENV_VAULT_ROOT = "INBOX_VAULT_ROOT"
ENV_VAULT_ROOT_LEGACY = "EMAIL_INBOX_VAULT_ROOT"
DEFAULT_VAULT_ROOT = Path.home() / "Documents" / "Obsidian Vault"
CURSOR_GMAIL_DIR = Path("Projects") / "Cursor Gmail"
ACCOUNTS_FILE = CURSOR_GMAIL_DIR / "accounts.md"
SESSION_FILE = CURSOR_GMAIL_DIR / ".inbox-session.json"


def resolve_vault_root(explicit: str | None = None) -> Path:
    """CLI flag > env > ~/.config/inbox-cli/config.toml > default."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get(ENV_VAULT_ROOT) or os.environ.get(ENV_VAULT_ROOT_LEGACY)
    if env:
        return Path(env).expanduser().resolve()
    from_config = load_config_vault_root()
    if from_config:
        return from_config
    return DEFAULT_VAULT_ROOT.resolve()


def accounts_path(vault_root: Path) -> Path:
    return vault_root / ACCOUNTS_FILE


def session_path(vault_root: Path) -> Path:
    return vault_root / SESSION_FILE
