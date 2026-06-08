from pathlib import Path

import pytest

from email_inbox.paths import accounts_path, resolve_vault_root, session_path


def test_resolve_explicit(tmp_path: Path) -> None:
    assert resolve_vault_root(str(tmp_path)) == tmp_path.resolve()


def test_resolve_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("INBOX_VAULT_ROOT", str(tmp_path))
    assert resolve_vault_root(None) == tmp_path.resolve()


def test_resolve_cli_over_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setenv("INBOX_VAULT_ROOT", str(tmp_path))
    assert resolve_vault_root(str(other)) == other.resolve()


def test_accounts_and_session_paths(tmp_path: Path) -> None:
    root = tmp_path
    assert accounts_path(root).name == "accounts.md"
    assert "Inbox-CLI" in str(accounts_path(root))
    assert session_path(root).name == ".inbox-session.json"
