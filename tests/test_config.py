from pathlib import Path

from email_inbox.config import (
    CONFIG_FILE,
    DEFAULT_AUTO_REFRESH_SECONDS,
    ENV_AUTO_REFRESH,
    load_config,
    load_config_vault_root,
    resolve_auto_refresh_seconds,
)


def test_load_config_vault_root(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "email-inbox"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    vault = tmp_path / "My Vault"
    config_file.write_text(f'vault_root = "{vault}"\n')
    monkeypatch.setattr("email_inbox.config.CONFIG_FILE", config_file)
    assert load_config_vault_root() == vault.resolve()


def test_load_config_open_obsidian_legacy(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "email-inbox"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    config_file.write_text("open_obsidian = false\n")
    monkeypatch.setattr("email_inbox.config.CONFIG_FILE", config_file)
    assert load_config().editor.kind == "none"
    assert load_config().open_obsidian is False


def test_resolve_auto_refresh_default() -> None:
    assert resolve_auto_refresh_seconds() == DEFAULT_AUTO_REFRESH_SECONDS


def test_resolve_auto_refresh_env(monkeypatch) -> None:
    monkeypatch.setenv(ENV_AUTO_REFRESH, "0")
    assert resolve_auto_refresh_seconds() == 0


def test_load_config_auto_refresh(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "inbox-cli"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    config_file.write_text("auto_refresh_seconds = 0\n")
    monkeypatch.setattr("email_inbox.config.CONFIG_FILE", config_file)
    assert load_config().auto_refresh_seconds == 0


def test_load_config_editor_cursor(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "inbox-cli"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    config_file.write_text('editor = "cursor"\n')
    monkeypatch.setattr("email_inbox.config.CONFIG_FILE", config_file)
    assert load_config().editor.command == ("cursor", "{path}")
